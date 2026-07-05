from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as documents_router
from app.api.v1.search import router as search_router
from app.api.v1.usage import router as usage_router
from app.api.v1.websocket import router as ws_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.workspace import router as workspace_router
from app.api.v1.subscription import router as subscription_router
from app.api.v1.admin import router as admin_router
from app.core.config import settings
from app.db.mongodb import close_mongo_connection, connect_to_mongo, check_mongo_connection
from app.db.postgres import engine
from app.db.redis import connect_to_redis, close_redis_connection, check_redis_connection
from app.api.v1.checkout import router as checkout_router
from app.api.v1.stripe_webhook import router as webhook_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    await connect_to_redis()
    yield
    await close_mongo_connection()
    await close_redis_connection()
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(search_router)
app.include_router(usage_router)
app.include_router(ws_router)
app.include_router(analytics_router)
app.include_router(workspace_router)
app.include_router(subscription_router)
app.include_router(admin_router)
app.include_router(checkout_router)
app.include_router(webhook_router)

@app.get("/")
async def root():
    return {"message": f"{settings.app_name} is running", "environment": settings.environment}


@app.get("/health")
async def health_check():
    postgres_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        postgres_ok = False

    mongo_ok = await check_mongo_connection()
    redis_ok = await check_redis_connection()

    return {
        "postgres": "connected" if postgres_ok else "unreachable",
        "mongo": "connected" if mongo_ok else "unreachable",
        "redis": "connected" if redis_ok else "unreachable",
    }