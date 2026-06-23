from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.mongo_db_name]


async def close_mongo_connection():
    global client
    if client:
        client.close()


async def check_mongo_connection() -> bool:
    try:
        await client.admin.command("ping")
        return True
    except Exception:
        return False


def get_mongo_db() -> AsyncIOMotorDatabase:
    return db