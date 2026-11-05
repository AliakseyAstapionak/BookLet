import pytest
from services.users import UserService
from utils import hash_password
from utils.auth import MAX_FAILS
from sqlalchemy import delete
from models import UserModel, UserSettingsModel
import asyncio

LOGIN_URL = "/BookLet/login"
TFA_URL = "/BookLet/login/2fa"
RESEND_2FA_URL = "/BookLet/login/2fa/resend"
LOGOUT_URL = "/BookLet/logout"

USERNAME = "alice"
EMAIL = "alice@example.com"
PASSWORD = "Str0ngPass!"
CREDS = {"username": USERNAME, "password": PASSWORD}


async def make_user(db, *, two_factor=False, active=True):
    hashed = await hash_password(PASSWORD)
    await UserService.create_user(username=USERNAME, email=EMAIL, hashed_pwd=hashed, db=db)
    user = await UserService.get_user_by_username(username=USERNAME, db=db, with_settings=True)
    user.settings.two_factor_enabled = two_factor
    user.is_active = active
    await db.commit()
    return user

async def login_2fa(ac, db, sent_emails):
    """Логин с включённой 2FA. Возвращает uid и код из письма."""
    user = await make_user(db, two_factor=True)
    response = await ac.post(LOGIN_URL, json=CREDS)
    assert response.status_code == 200
    return user.id, sent_emails[-1]["code"]


@pytest.mark.asyncio
async def test_login_success_without_2fa(ac, db_session, fake_redis, sent_emails):
    await make_user(db_session)

    response = await ac.post(LOGIN_URL, json=CREDS)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "access_token" in ac.cookies
    assert "2fa_token" not in ac.cookies
    assert len(sent_emails) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"username": USERNAME, "password": "WrongPass1!"}, 
        {"username": "nobody", "password": PASSWORD},     
    ],
)
@pytest.mark.asyncio
async def test_login_wrong_credentials(ac, db_session, fake_redis, sent_emails, payload):
    await make_user(db_session)

    response = await ac.post(LOGIN_URL, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Неверный логин или пароль"
    assert "access_token" not in ac.cookies
    assert len(sent_emails) == 0

@pytest.mark.asyncio
async def test_login_inactive_account(ac, db_session, fake_redis, sent_emails):
    await make_user(db_session, active=False)

    response = await ac.post(LOGIN_URL, json=CREDS)

    assert response.status_code == 400
    assert response.json()["detail"] == "Аккаунт неактивен"
    assert "access_token" not in ac.cookies

@pytest.mark.asyncio
async def test_login_fail_limit(ac, db_session, fake_redis, sent_emails):
    await make_user(db_session)
    key = "login_fail:127.0.0.1"   
    bad = {"username": USERNAME, "password": "WrongPass1!"}

    for attempt in range(1, MAX_FAILS + 1):
        response = await ac.post(LOGIN_URL, json=bad)
        assert response.status_code == 400
        assert int(await fake_redis.get(key)) == attempt

    response = await ac.post(LOGIN_URL, json=CREDS)
    assert response.status_code == 429
    assert "access_token" not in ac.cookies


@pytest.mark.asyncio
async def test_login_with_2fa_sends_code(ac, db_session, fake_redis, sent_emails):
    user = await make_user(db_session, two_factor=True)

    response = await ac.post(LOGIN_URL, json=CREDS)

    assert response.status_code == 200
    assert response.json()["msg"] == "Код отправлен на почту"
    assert "2fa_token" in ac.cookies
    assert "access_token" not in ac.cookies
    assert len(sent_emails) == 1
    assert len(sent_emails[0]["code"]) == 6
    assert await fake_redis.exists(f"2fa_code:{user.id}") == 1

@pytest.mark.asyncio
async def test_login_2fa_code_already_sent(ac, db_session, fake_redis, sent_emails):
    await make_user(db_session, two_factor=True)

    await ac.post(LOGIN_URL, json=CREDS)
    response = await ac.post(LOGIN_URL, json=CREDS)

    assert response.status_code == 200
    assert response.json()["msg"] == "Код уже отправлен, проверьте почту"
    assert len(sent_emails) == 1   

@pytest.mark.asyncio
async def test_2fa_verification(ac, db_session, fake_redis, sent_emails):
    user = await make_user(db_session, two_factor=True)
    cd_key = f"2fa_cd:{user.id}"
    code_key = f"2fa_code:{user.id}"

    response = await ac.post(LOGIN_URL, json=CREDS)
    assert response.status_code == 200
    assert "2fa_token" in ac.cookies
    assert len(sent_emails) == 1
    assert await fake_redis.exists(cd_key) == 1
    assert await fake_redis.exists(code_key) == 1

    code = sent_emails[0]["code"]
    assert len(code) == 6 and code.isdigit()

    response = await ac.post(TFA_URL, json={"usercode": code})
    assert response.status_code == 200
    assert response.json()["success"] is True

    assert "access_token" in ac.cookies
    assert "2fa_token" not in ac.cookies
    assert await fake_redis.exists(code_key) == 0
    assert await fake_redis.exists(cd_key) == 0


@pytest.mark.asyncio
async def test_2fa_wrong_code(ac, db_session, fake_redis, sent_emails):
    user = await make_user(db_session, two_factor=True)
    code_key = f"2fa_code:{user.id}"

    await ac.post(LOGIN_URL, json=CREDS)
    code = sent_emails[0]["code"]
    wrong_code = "000000"

    response = await ac.post(TFA_URL, json={"usercode": wrong_code})

    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный код. Осталось попыток: 2"
    assert "access_token" not in ac.cookies
    assert "2fa_token" in ac.cookies                     
    assert await fake_redis.exists(code_key) == 1      
    assert int(await fake_redis.hget(code_key, "attempts")) == 2

    ok = await ac.post(TFA_URL, json={"usercode": code})
    assert ok.status_code == 200
    assert "access_token" in ac.cookies


@pytest.mark.asyncio
async def test_2fa_wrong_code_attempts_exhausted(ac, db_session, fake_redis, sent_emails):
    user = await make_user(db_session, two_factor=True)
    code_key = f"2fa_code:{user.id}"

    await ac.post(LOGIN_URL, json=CREDS)
    code = sent_emails[0]["code"]
    wrong_code = "000000" 

    for left in (2, 1, 0):
        response = await ac.post(TFA_URL, json={"usercode": wrong_code})
        assert response.status_code == 401
        assert response.json()["detail"] == f"Неверный код. Осталось попыток: {left}"

    response = await ac.post(TFA_URL, json={"usercode": wrong_code})
    assert response.status_code == 429
    assert await fake_redis.exists(code_key) == 0

    # верный код после этого уже не принимается
    response = await ac.post(TFA_URL, json={"usercode": code})
    assert response.status_code == 401
    assert response.json()["detail"] == "Код истёк, запросите новый"
    assert "access_token" not in ac.cookies


@pytest.mark.asyncio
async def test_2fa_expired_code(ac, db_session, fake_redis, sent_emails):
    uid, code = await login_2fa(ac, db_session, sent_emails)
    await fake_redis.delete(f"2fa_code:{uid}")

    response = await ac.post(TFA_URL, json={"usercode": code})

    assert response.status_code == 401
    assert response.json()["detail"] == "Код истёк, запросите новый"
    assert "access_token" not in ac.cookies


@pytest.mark.asyncio
async def test_2fa_without_token(ac, db_session, fake_redis, sent_emails):
    response = await ac.post(TFA_URL, json={"usercode": "123456"})

    assert response.status_code == 401  
    assert "access_token" not in ac.cookies


@pytest.mark.asyncio
async def test_2fa_resend_success(ac, db_session, fake_redis, sent_emails):
    uid, _ = await login_2fa(ac, db_session, sent_emails)
    await fake_redis.delete(f"2fa_cd:{uid}")        

    response = await ac.post(RESEND_2FA_URL)

    assert response.status_code == 200
    assert response.json()["msg"] == "Код отправлен повторно"
    assert len(sent_emails) == 2
    assert sent_emails[1]["email_to"] == EMAIL
    assert len(sent_emails[1]["code"]) == 6
    assert "2fa_token" in ac.cookies


@pytest.mark.asyncio
async def test_2fa_resend_new_code_replaces_old(ac, db_session, fake_redis, sent_emails):
    uid, old_code = await login_2fa(ac, db_session, sent_emails)
    await fake_redis.delete(f"2fa_cd:{uid}")

    await ac.post(RESEND_2FA_URL)
    new_code = sent_emails[1]["code"]
    assert new_code != old_code, "случайные коды совпали, перезапустите тест"

    response = await ac.post(TFA_URL, json={"usercode": old_code})
    assert response.status_code == 401

    response = await ac.post(TFA_URL, json={"usercode": new_code})
    assert response.status_code == 200
    assert "access_token" in ac.cookies


@pytest.mark.asyncio
async def test_2fa_resend_resets_attempts(ac, db_session, fake_redis, sent_emails):
    uid, _ = await login_2fa(ac, db_session, sent_emails)
    code_key = f"2fa_code:{uid}"

    for _ in range(2):
        await ac.post(TFA_URL, json={"usercode": "000000"})
    assert int(await fake_redis.hget(code_key, "attempts")) == 1

    await fake_redis.delete(f"2fa_cd:{uid}")
    response = await ac.post(RESEND_2FA_URL)

    assert response.status_code == 200
    assert int(await fake_redis.hget(code_key, "attempts")) == 3
    assert 0 < await fake_redis.ttl(code_key) <= 300


@pytest.mark.asyncio
async def test_2fa_resend_revives_expired_code(ac, db_session, fake_redis, sent_emails):
    uid, _ = await login_2fa(ac, db_session, sent_emails)
    code_key = f"2fa_code:{uid}"

    await fake_redis.delete(code_key)
    await fake_redis.delete(f"2fa_cd:{uid}")

    response = await ac.post(RESEND_2FA_URL)
    assert response.status_code == 200
    assert await fake_redis.exists(code_key) == 1

    ok = await ac.post(TFA_URL, json={"usercode": sent_emails[-1]["code"]})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_2fa_resend_without_token(ac, db_session, fake_redis, sent_emails):
    response = await ac.post(RESEND_2FA_URL)

    assert response.status_code == 401
    assert len(sent_emails) == 0


@pytest.mark.asyncio
async def test_2fa_resend_user_deleted(ac, db_session, fake_redis, sent_emails):
    uid, _ = await login_2fa(ac, db_session, sent_emails)
    await fake_redis.delete(f"2fa_cd:{uid}")

    await db_session.execute(delete(UserSettingsModel).where(UserSettingsModel.user_id == uid))
    await db_session.execute(delete(UserModel).where(UserModel.id == uid))
    await db_session.commit()

    response = await ac.post(RESEND_2FA_URL)

    assert response.status_code == 401
    assert response.json()["detail"] == "Сессия входа недействительна"

@pytest.mark.asyncio
async def test_2fa_resend_blocked_by_cooldown(ac, db_session, fake_redis, sent_emails):
    uid, _ = await login_2fa(ac, db_session, sent_emails)
    code_key = f"2fa_code:{uid}"
    hash_before = await fake_redis.hget(code_key, "hashed_code")

    response = await ac.post(RESEND_2FA_URL)

    assert response.status_code == 429
    assert len(sent_emails) == 1
    assert await fake_redis.hget(code_key, "hashed_code") == hash_before


@pytest.mark.asyncio
async def test_2fa_resend_cooldown_message(ac, db_session, fake_redis, sent_emails):
    await login_2fa(ac, db_session, sent_emails)

    response = await ac.post(RESEND_2FA_URL)

    detail = response.json()["detail"]
    assert detail.startswith("Повторить можно через")
    seconds = int(detail.split("через")[1].split("сек")[0])
    assert 1 <= seconds <= 60


@pytest.mark.asyncio
async def test_2fa_cooldown_is_set_on_login(ac, db_session, fake_redis, sent_emails):
    uid, _ = await login_2fa(ac, db_session, sent_emails)

    assert 0 < await fake_redis.ttl(f"2fa_cd:{uid}") <= 60


@pytest.mark.asyncio
async def test_2fa_cooldown_restarts_after_resend(ac, db_session, fake_redis, sent_emails):
    uid, _ = await login_2fa(ac, db_session, sent_emails)
    await fake_redis.delete(f"2fa_cd:{uid}")

    first = await ac.post(RESEND_2FA_URL)
    assert first.status_code == 200
    assert 0 < await fake_redis.ttl(f"2fa_cd:{uid}") <= 60

    second = await ac.post(RESEND_2FA_URL)
    assert second.status_code == 429
    assert len(sent_emails) == 2


@pytest.mark.asyncio
async def test_2fa_cooldown_expires_by_itself(ac, db_session, fake_redis, sent_emails):
    uid, _ = await login_2fa(ac, db_session, sent_emails)
    await fake_redis.expire(f"2fa_cd:{uid}", 1)
    await asyncio.sleep(1.2)          # реально ждёт, можно удалить тест ради скорости

    response = await ac.post(RESEND_2FA_URL)

    assert response.status_code == 200
    assert len(sent_emails) == 2


@pytest.mark.asyncio
async def test_login_during_cooldown_does_not_send_new_code(ac, db_session, fake_redis, sent_emails):
    uid, code = await login_2fa(ac, db_session, sent_emails)

    response = await ac.post(LOGIN_URL, json=CREDS)

    assert response.status_code == 200
    assert response.json()["msg"] == "Код уже отправлен, проверьте почту"
    assert len(sent_emails) == 1

    ok = await ac.post(TFA_URL, json={"usercode": code})
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_login_after_cooldown_sends_new_code(ac, db_session, fake_redis, sent_emails):
    uid, _ = await login_2fa(ac, db_session, sent_emails)
    await fake_redis.delete(f"2fa_cd:{uid}")

    response = await ac.post(LOGIN_URL, json=CREDS)

    assert response.status_code == 200
    assert response.json()["msg"] == "Код отправлен на почту"
    assert len(sent_emails) == 2


# ---------- logout ----------

@pytest.mark.asyncio
async def test_logout_success(ac, db_session, fake_redis, sent_emails):
    await make_user(db_session)
    await ac.post(LOGIN_URL, json=CREDS)
    assert "access_token" in ac.cookies

    response = await ac.post(LOGOUT_URL)

    assert response.status_code == 200
    assert response.json() == {"success": True, "msg": "Вы вышли из аккаунта"}
    assert "access_token" not in ac.cookies


@pytest.mark.asyncio
async def test_logout_already_logged_out(ac, db_session, fake_redis, sent_emails):
    response = await ac.post(LOGOUT_URL)

    assert response.status_code == 200
    assert response.json() == {"success": False, "msg": "Вы уже вышли"}
