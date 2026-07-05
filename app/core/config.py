from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Knowledge Base API"
    environment: str = "development"
    secret_key: str
    database_url: str
    mongo_url: str
    mongo_db_name: str = "ai_knowledgebase_mongo"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_free_price_id: str = ""
    stripe_pro_price_id: str = ""
    stripe_webhook_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()