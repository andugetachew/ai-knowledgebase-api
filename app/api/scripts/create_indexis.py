"""
Run once to create MongoDB indexes for chat_messages.
Usage: python -m app.scripts.create_indexes
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings


async def create_indexes():
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.mongo_db_name]

    await db["chat_messages"].create_index([("conversation_id", 1), ("created_at", 1)])
    await db["chat_messages"].create_index([("workspace_id", 1), ("created_at", -1)])
    print("Indexes created on chat_messages")

    client.close()


if __name__ == "__main__":
    asyncio.run(create_indexes())