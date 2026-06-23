from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Knowledge Base API"
    environment: str = "development"
    secret_key: str

    database_url: str

    mongo_url: str
    mongo_db_name: str = "ai_knowledgebase_mongo"

    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    anthropic_api_key: str = ""


settings = Settings()