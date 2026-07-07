from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo():
    global client, db
    if client is not None:
        client.close()
    client = AsyncIOMotorClient(
        settings.mongo_url,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=5000,
    )
    db = client[settings.mongo_db_name]


async def close_mongo_connection():
    global client, db
    if client:
        client.close()
        client = None
        db = None


async def check_mongo_connection() -> bool:
    try:
        await client.admin.command("ping")
        return True
    except Exception:
        return False


def get_mongo_db() -> AsyncIOMotorDatabase:
    return db