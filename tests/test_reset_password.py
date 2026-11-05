import pytest
from urllib.parse import urlparse, parse_qs

from services.email import EmailService
from services.users import UserService
from utils import hash_password

FORGOT_URL = "/BookLet/forgot_password"
RESET_URL = "/BookLet/reset_password"
LOGIN_URL = "/BookLet/login"

USERNAME = "alice"
EMAIL = "alice@example.com"
PASSWORD = "Str0ngPass!"
NEW_PASSWORD = "NewStr0ngPass!"

FORGOT = {"username": USERNAME, "email": EMAIL}
GENERIC_ERROR = "Произошла ошибка, проверьте данные."


@pytest.fixture
def reset_emails(monkeypatch):
    emails = []

    async def fake_send(email_to, reset_link, *args, **kwargs):
        emails.append({"email_to": email_to, "reset_link": reset_link})

    monkeypatch.setattr(EmailService, "send_reset_password_email", fake_send)
    return emails


async def make_user(db, *, active=True):
    hashed = await hash_password(PASSWORD)
    await UserService.create_user(username=USERNAME, email=EMAIL, hashed_pwd=hashed, db=db)
    user = await UserService.get_user_by_username(username=USERNAME, db=db, with_settings=True)
    user.settings.two_factor_enabled = False
    user.is_active = active
    await db.commit()
    return user


def token_from(link: str) -> str:
    return parse_qs(urlparse(link).query)["reset_token"][0]


async def request_token(ac, db, reset_emails) -> str:
    """Создаёт пользователя, запрашивает сброс и возвращает токен из письма."""
    await make_user(db)
    response = await ac.post(FORGOT_URL, json=FORGOT)
    assert response.status_code == 200
    return token_from(reset_emails[-1]["reset_link"])



@pytest.mark.asyncio
async def test_forgot_password_success(ac, db_session, fake_redis, reset_emails):
    await make_user(db_session)

    response = await ac.post(FORGOT_URL, json=FORGOT)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(reset_emails) == 1
    assert reset_emails[0]["email_to"] == EMAIL
    assert token_from(reset_emails[0]["reset_link"])


@pytest.mark.asyncio
async def test_forgot_password_email_case_insensitive(ac, db_session, fake_redis, reset_emails):
    await make_user(db_session)

    response = await ac.post(FORGOT_URL, json={"username": USERNAME, "email": EMAIL.upper()})

    assert response.status_code == 200
    assert len(reset_emails) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "nobody", "email": EMAIL},                 # нет такого пользователя
        {"username": USERNAME, "email": "other@example.com"},   # почта не совпала
        {"username": USERNAME, "email": "not-an-email"},        # схема формат не проверяет
    ],
)
@pytest.mark.asyncio
async def test_forgot_password_wrong_data(ac, db_session, fake_redis, reset_emails, payload):
    await make_user(db_session)

    response = await ac.post(FORGOT_URL, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_ERROR
    assert len(reset_emails) == 0


@pytest.mark.asyncio
async def test_forgot_password_inactive_account(ac, db_session, fake_redis, reset_emails):
    await make_user(db_session, active=False)

    response = await ac.post(FORGOT_URL, json=FORGOT)

    assert response.status_code == 400
    assert response.json()["detail"] == "Аккаунт неактивен."
    assert len(reset_emails) == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"username": USERNAME},
        {"email": EMAIL},
    ],
)
@pytest.mark.asyncio
async def test_forgot_password_invalid_payload(ac, db_session, fake_redis, reset_emails, payload):
    response = await ac.post(FORGOT_URL, json=payload)

    assert response.status_code == 422
    assert len(reset_emails) == 0



@pytest.mark.asyncio
async def test_reset_password_success(ac, db_session, fake_redis, reset_emails):
    token = await request_token(ac, db_session, reset_emails)

    response = await ac.post(RESET_URL, json={"token": token, "new_password": NEW_PASSWORD})

    assert response.status_code == 200
    assert response.json() == {"success": True, "msg": "Пароль успешно изменен"}


@pytest.mark.asyncio
async def test_reset_password_new_password_works_old_does_not(ac, db_session, fake_redis, reset_emails):
    token = await request_token(ac, db_session, reset_emails)
    await ac.post(RESET_URL, json={"token": token, "new_password": NEW_PASSWORD})

    old = await ac.post(LOGIN_URL, json={"username": USERNAME, "password": PASSWORD})
    assert old.status_code == 400
    assert "access_token" not in ac.cookies

    new = await ac.post(LOGIN_URL, json={"username": USERNAME, "password": NEW_PASSWORD})
    assert new.status_code == 200
    assert "access_token" in ac.cookies


@pytest.mark.asyncio
async def test_reset_password_token_is_single_use(ac, db_session, fake_redis, reset_emails):
    token = await request_token(ac, db_session, reset_emails)

    first = await ac.post(RESET_URL, json={"token": token, "new_password": NEW_PASSWORD})
    assert first.status_code == 200

    second = await ac.post(RESET_URL, json={"token": token, "new_password": "Another1Pass!"})
    assert second.status_code == 400

    # пароль остался от первого сброса
    login = await ac.post(LOGIN_URL, json={"username": USERNAME, "password": NEW_PASSWORD})
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_old_token_dies_after_new_request(ac, db_session, fake_redis, reset_emails):
    """Два токена на один и тот же пароль: после использования одного второй тоже мёртв."""
    token1 = await request_token(ac, db_session, reset_emails)
    await ac.post(FORGOT_URL, json=FORGOT)
    token2 = token_from(reset_emails[-1]["reset_link"])

    ok = await ac.post(RESET_URL, json={"token": token1, "new_password": NEW_PASSWORD})
    assert ok.status_code == 200

    response = await ac.post(RESET_URL, json={"token": token2, "new_password": "Another1Pass!"})
    assert response.status_code == 400


@pytest.mark.parametrize("token", ["garbage", "a.b.c", ""])
@pytest.mark.asyncio
async def test_reset_password_invalid_token(ac, db_session, fake_redis, reset_emails, token):
    await make_user(db_session)

    response = await ac.post(RESET_URL, json={"token": token, "new_password": NEW_PASSWORD})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_tampered_token(ac, db_session, fake_redis, reset_emails):
    token = await request_token(ac, db_session, reset_emails)
    tampered = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")

    response = await ac.post(RESET_URL, json={"token": tampered, "new_password": NEW_PASSWORD})

    assert response.status_code == 401

    login = await ac.post(LOGIN_URL, json={"username": USERNAME, "password": PASSWORD})
    assert login.status_code == 200      # пароль не изменился


@pytest.mark.asyncio
async def test_reset_password_inactive_user(ac, db_session, fake_redis, reset_emails):
    token = await request_token(ac, db_session, reset_emails)
    user = await UserService.get_user_by_username(username=USERNAME, db=db_session)
    user.is_active = False
    await db_session.commit()

    response = await ac.post(RESET_URL, json={"token": token, "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    assert response.json()["detail"] == "Произошла ошибка. Проверьте данные"


@pytest.mark.asyncio
async def test_reset_password_user_not_found(ac, db_session, fake_redis, reset_emails, monkeypatch):
    token = await request_token(ac, db_session, reset_emails)

    async def no_user(*args, **kwargs):
        return None

    monkeypatch.setattr(UserService, "get_user_by_id", no_user)

    response = await ac.post(RESET_URL, json={"token": token, "new_password": NEW_PASSWORD})

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_update_fails_returns_404(ac, db_session, fake_redis, reset_emails, monkeypatch):
    """Ветка гонки: пользователь найден, но UserService.reset_password ничего не обновил."""
    token = await request_token(ac, db_session, reset_emails)

    async def fail(*args, **kwargs):
        return False

    monkeypatch.setattr(UserService, "reset_password", fail)

    response = await ac.post(RESET_URL, json={"token": token, "new_password": NEW_PASSWORD})

    assert response.status_code == 404
    assert "пользователь не найден" in response.json()["detail"]


@pytest.mark.parametrize("new_password", ["", "123", "short"])
@pytest.mark.asyncio
async def test_reset_password_weak_password(ac, db_session, fake_redis, reset_emails, new_password):
    token = await request_token(ac, db_session, reset_emails)

    response = await ac.post(RESET_URL, json={"token": token, "new_password": new_password})

    assert response.status_code == 422

    login = await ac.post(LOGIN_URL, json={"username": USERNAME, "password": PASSWORD})
    assert login.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"new_password": NEW_PASSWORD},
        {"token": "x"},
    ],
)
@pytest.mark.asyncio
async def test_reset_password_missing_fields(ac, db_session, fake_redis, reset_emails, payload):
    response = await ac.post(RESET_URL, json=payload)

    assert response.status_code == 422