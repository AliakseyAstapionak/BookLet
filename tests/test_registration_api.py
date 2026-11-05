from services.users import UserService
import pytest
import pytest_asyncio
from utils.auth import MAX_FAILS

URL = "/BookLet/registration"
VERIFY_URL = "/BookLet/registration/verify_email"
RESEND_URL = "/BookLet/registration/verify_email/resend_code"

VALID = {
    "username": "alice",
    "email": "alice@example.com",
    "password": "Str0ngPass!",   
}

@pytest.mark.asyncio
async def test_registration_success(ac, fake_redis, sent_emails):
    response = await ac.post(URL, json=VALID)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert "reg_token" in ac.cookies  
    assert len(sent_emails) == 1

@pytest.mark.parametrize(
    "payload, bad_field",
    [
        ({}, "username"),                                          # пустое тело
        ({"email": VALID["email"], "password": VALID["password"]}, "username"),
        ({"username": VALID["username"], "password": VALID["password"]}, "email"),
        ({"username": VALID["username"], "email": VALID["email"]}, "password"),
        ({**VALID, "email": "not-an-email"}, "email"),             # неверный формат почты
        ({**VALID, "email": ""}, "email"),
        ({**VALID, "username": ""}, "username"),                   # пустое имя
        ({**VALID, "username": "a"}, "username"),                  # слишком короткое (если есть min_length)
        ({**VALID, "password": ""}, "password"),
        ({**VALID, "password": "123"}, "password"),                # слишком простой (если есть правила)
        ({**VALID, "username": 12345}, "username"),                # неверный тип
    ],
)
@pytest.mark.asyncio
async def test_registration_invalid_data(ac, db_session,fake_redis, sent_emails, payload, bad_field):
    response = await ac.post(URL, json=payload)

    assert response.status_code == 422
    error_fields = [err["loc"][-1] for err in response.json()["detail"]]
    assert bad_field in error_fields

    assert await UserService.existing_username(username="alice", db=db_session) is False
    assert await UserService.existing_email(email="alice@example.com", db=db_session) is False

    assert len(sent_emails) == 0
    assert "reg_token" not in response.cookies

@pytest.mark.parametrize(
    "payload, detail",
    [
        ({**VALID, "email": "other@example.com"}, "Данное имя уже занято"),
        ({**VALID, "username": "alice123"}, "Данная почта уже занята"),
    ],
)
@pytest.mark.asyncio
async def test_busy_username_or_email(ac, db_session, fake_redis, sent_emails, payload, detail):
    await UserService.create_user(
        username=VALID["username"],
        email=VALID["email"],
        hashed_pwd="x",
        db=db_session,
    )

    response = await ac.post(URL, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == detail
    assert len(sent_emails) == 0
    assert "reg_token" not in response.cookies

@pytest.mark.asyncio
async def test_registration_fail_limit(ac, db_session, fake_redis, sent_emails):
    await UserService.create_user(
        username="alice", email="alice@example.com", hashed_pwd="x", db=db_session
    )
    key = "registration_fail:127.0.0.1"
    payload = {"username": "bob", "email": "alice@example.com", "password": "Str0ngPass!"}

    for attempt in range(1, MAX_FAILS + 1):
        response = await ac.post(URL, json=payload)
        assert response.status_code == 400
        assert int(await fake_redis.get(key)) == attempt

    assert await fake_redis.ttl(key) > 0

    response = await ac.post(URL, json=payload)
    assert response.status_code == 429
    assert "Слишком много попыток" in response.json()["detail"]
    assert int(await fake_redis.get(key)) == MAX_FAILS

async def register(ac, sent_emails):
    response = await ac.post(URL, json=VALID)
    assert response.status_code == 200
    code = sent_emails[-1]["code"]
    assert len(code) == 6 and code.isdigit()
    return code

@pytest.mark.asyncio
async def test_verify_success(ac, db_session, fake_redis, sent_emails):
    code = await register(ac, sent_emails)
    assert "reg_token" in ac.cookies
    response = await ac.post(VERIFY_URL, json={"usercode": code})

    assert response.status_code == 201
    assert response.json()["success"] is True

    assert await UserService.existing_username(username="alice", db=db_session) is True
    assert await UserService.existing_email(email="alice@example.com", db=db_session) is True
  
    assert "reg_token" not in ac.cookies
    assert await fake_redis.exists("reg_code:alice@example.com") == 0

@pytest.mark.asyncio
async def test_verify_invalid_code(ac, db_session, fake_redis, sent_emails):
    code = await register(ac, sent_emails)
    assert "reg_token" in ac.cookies
    key = "reg_code:alice@example.com"
    attempts_before = int(await fake_redis.hget(key, "attempts"))

    wrong_code = "000000"
    response = await ac.post(VERIFY_URL, json={"usercode": wrong_code})

    assert response.status_code == 401
    assert "Неверный код" in response.json()["detail"]

    assert await UserService.existing_username(username="alice", db=db_session) is False
    assert await UserService.existing_email(email="alice@example.com", db=db_session) is False

    assert "reg_token" in ac.cookies
    assert await fake_redis.exists(key) == 1
    assert int(await fake_redis.hget(key, "attempts")) == attempts_before - 1

    ok = await ac.post(VERIFY_URL, json={"usercode": code})
    assert ok.status_code == 201

@pytest.mark.asyncio
async def test_resend_registration_code(ac, db_session, fake_redis, sent_emails):
    await register(ac, sent_emails)
    assert "reg_token" in ac.cookies

    # имитируем, что пауза прошла
    await fake_redis.delete("reg_cd:alice@example.com")

    response = await ac.post(RESEND_URL)

    assert response.status_code == 200
    assert len(sent_emails) == 2


@pytest.mark.asyncio
async def test_resend_registration_code_cooldown(ac, db_session, fake_redis, sent_emails):
    await register(ac, sent_emails)
    assert "reg_token" in ac.cookies

    assert await fake_redis.ttl("reg_cd:alice@example.com") > 0

    response = await ac.post(RESEND_URL)

    assert response.status_code == 429
    assert len(sent_emails) == 1


@pytest.mark.asyncio
async def test_resend_registration_code_cooldown_restarts(ac, db_session, fake_redis, sent_emails):
    await register(ac, sent_emails)
    await fake_redis.delete("reg_cd:alice@example.com")

    first = await ac.post(RESEND_URL)
    assert first.status_code == 200
    assert len(sent_emails) == 2

    # после успешной повторной отправки пауза включается снова
    second = await ac.post(RESEND_URL)
    assert second.status_code == 429
    assert len(sent_emails) == 2