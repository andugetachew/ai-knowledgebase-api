import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.postgres import Base, get_db
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.db.redis import connect_to_redis, close_redis_connection
from app.main import app

TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/ai_knowledgebase_test_db"


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def setup_test_db():
    # Own short-lived engine, fully created/disposed within this fixture's
    # session-scoped loop. Per-test fixtures (db_session) create their own
    # engines instead of reusing this one, since asyncpg connections are
    # bound to the loop that created them and can't be reused across the
    # function-scoped loops that each test gets.
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    yield

    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def setup_mongo():
    # Motor's AsyncIOMotorClient binds its internal executor to the event
    # loop active when it's constructed (same loop-affinity issue as
    # asyncpg). Since every test now runs on its own function-scoped loop,
    # the Mongo client must be reconnected fresh per test rather than once
    # per session, or later tests reuse a client whose loop has closed.
    await connect_to_mongo()
    yield
    await close_mongo_connection()


@pytest_asyncio.fixture(autouse=True)
async def setup_redis():
    # Same loop-affinity reasoning as setup_mongo above: redis.asyncio's
    # connection pool is bound to the event loop active when it's created.
    # Without this fixture, redis_client in app/db/redis.py stays None for
    # the whole test session because lifespan() never runs under
    # ASGITransport, so any endpoint calling get_redis() would get None.
    await connect_to_redis()
    yield
    await close_redis_connection()
@pytest_asyncio.fixture(autouse=True)
async def cleanup_mongo():
    from app.db.mongodb import get_mongo_db
    yield
    try:
        mongo_db = get_mongo_db()
        if mongo_db is not None:
            await mongo_db["chat_messages"].delete_many({})
            await mongo_db["chunks"].delete_many({})
    except Exception:
        pass


@pytest_asyncio.fixture
async def db_session():
    # Fresh engine per test, created on whichever function-scoped loop this
    # test is running on, disposed before that loop closes.
    engine = create_async_engine(TEST_DATABASE_URL)
    session_local = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_local() as session:
        yield session
        try:
            await session.rollback()
            await session.execute(text("TRUNCATE TABLE documents, workspaces, users CASCADE"))
            await session.commit()
        except Exception:
            await session.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_user(client) -> dict:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "docuser@test.com",
            "password": "testpassword123",
            "full_name": "Doc User",
            "workspace_name": "Doc Workspace",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "docuser@test.com", "password": "testpassword123"},
    )
    return {
        "token": login.json()["access_token"],
        "workspace_id": reg.json()["workspace_id"],
    }


@pytest_asyncio.fixture
async def auth_headers(registered_user) -> dict:
    return {"Authorization": f"Bearer {registered_user['token']}"}


@pytest_asyncio.fixture
async def workspace_id(registered_user) -> str:
    return registered_user["workspace_id"]