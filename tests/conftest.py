import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import fakeredis.aioredis
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from fastapi.testclient import TestClient
from main import app
from core import Base, get_db
import os
from utils import create_jwt
from booking_helpers import Actor, create_user


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5436/test_db",
)

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest_asyncio.fixture
async def engine():
    assert 'test' in TEST_DATABASE_URL.split('/')[-1]
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    async with engine.begin() as conn:
       # await conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(engine):
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

@pytest_asyncio.fixture
async def ac(db_session):
    async def override_get_db():
        yield db_session   

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear() 

@pytest_asyncio.fixture
async def fake_redis(monkeypatch):
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    for path in [
            "core.redis.redis_client",
            "core.redis_client",
            "api.auth.registration.redis_client",
            "api.auth.login.redis_client",
            "api.health.redis_client",
            "utils.auth.redis_client",
    ]:
        monkeypatch.setattr(path, redis)
    yield redis
    await redis.flushall()
    await redis.aclose()




@pytest.fixture
def sent_emails(monkeypatch):
    calls = []

    async def fake_send(email_to, code, expire_minutes=10):
        calls.append({"email_to": email_to, "code": code})
   
    monkeypatch.setattr("services.email.EmailService.send_registration_code", fake_send)
    monkeypatch.setattr("services.email.EmailService.send_mail_code", fake_send)

   
    return calls

from httpx import AsyncClient as _AsyncClient

@pytest_asyncio.fixture
async def make_actor(ac, db_session):
    """Фабрика: создаёт пользователя и отдельный HTTP-клиент с его access_token.
    Зависит от `ac`, чтобы get_db был подменён на тестовую сессию."""
    clients = []

    async def _make(username: str, *, active: bool = True) -> Actor:
        user = await create_user(db_session, username, active=active)
        http = _AsyncClient(transport=ASGITransport(app=app), base_url="http://test",
                            cookies={"access_token": create_jwt(user.id, user.username)})
        clients.append(http)
        return Actor(id=user.id, username=user.username, http=http)

    yield _make
    for c in clients:
        await c.aclose()


@pytest_asyncio.fixture
async def provider(make_actor):
    return await make_actor("master")


@pytest_asyncio.fixture
async def customer(make_actor):
    return await make_actor("client")


@pytest_asyncio.fixture
async def other_customer(make_actor):
    return await make_actor("client2")