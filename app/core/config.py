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

    # Email
    email_host: str = "smtp.gmail.com"
    email_port: int = 587
    email_host_user: str = ""
    email_host_password: str = ""
    email_use_tls: bool = True
    default_from_email: str = "AI Knowledge Base <noreply@example.com>"
    frontend_url: str = "http://localhost:3000"

    # S3 / Object Storage
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "ai-knowledgebase-docs"
    s3_region: str = "us-east-1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()