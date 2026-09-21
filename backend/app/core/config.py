from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_NAME: str = "CrossCheckPro API"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str | None = None
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT Authentication
    JWT_SECRET: str = "crosscheckpro-custom-secret-key-change-in-prod-xyz-987"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    FRONTEND_URL: str = "http://localhost:3000"

    # SMTP Configuration (Google App Password / SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@crosscheckpro.com"

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    
    # Supabase (Storage & Postgres Database Only)
    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_SERVICE_ROLE_KEY: str = "placeholder_key"
    SUPABASE_JWT_SECRET: str = "placeholder_secret"
    
    # Storage
    SUPABASE_STORAGE_BUCKET: str = "documents"
    MAX_UPLOAD_SIZE_MB: int = 10
    
    # AI Provider
    AI_PROVIDER: str = "openai" # "openai" or "gemini"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # Security & Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    AUTH_RATE_LIMIT: int = 10
    AUTH_RATE_WINDOW_SECONDS: int = 60
    PASSWORD_RESET_RATE_LIMIT: int = 5
    PASSWORD_RESET_RATE_WINDOW_SECONDS: int = 300
    MAX_PDF_PAGES: int = 100

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
