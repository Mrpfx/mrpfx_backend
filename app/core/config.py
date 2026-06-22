from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "MRPFX Backend"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_URL: str = "http://localhost:8000"

    # Database - set USE_SQLITE=false to use PostgreSQL
    USE_SQLITE: bool = True  # Set to False for PostgreSQL
    SQLITE_PATH: str = "mrpfx.db"

    # PostgreSQL settings (used when USE_SQLITE=False)
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_NAME: str = "mrpfx"

    # WordPress MySQL settings
    WP_DB_HOST: str = "localhost"
    WP_DB_PORT: int = 3306
    WP_DB_USER: str = "root"
    WP_DB_PASSWORD: str = ""
    WP_DB_NAME: str = "wordpress"

    @property
    def DATABASE_URL(self) -> str:
        if self.USE_SQLITE:
            return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    @property
    def WP_DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.WP_DB_USER}:{self.WP_DB_PASSWORD}@{self.WP_DB_HOST}:{self.WP_DB_PORT}/{self.WP_DB_NAME}?charset=utf8mb4"

    # JWT Settings
    JWT_SECRET_KEY: str = "mrpfx_secret_key_change_me_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 525600
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Encryption Key
    ENCRYPTION_KEY: str = "tn4DES6YEUKFxpctSkJyWlcvssyMj9ypiRTGw7a8Etw="

    # Email Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "MRPFX"
    SMTP_TLS: bool = True
    ADMIN_EMAIL: str = ""  # Email to receive admin notifications

    # NOWPayments Settings
    NOWPAYMENTS_API_KEY: str = ""
    NOWPAYMENTS_API_URL: str = "https://api.nowpayments.io/v1"
    NOWPAYMENTS_IPN_SECRET: str = ""

    # Frontend URL (for email links)
    FRONTEND_URL: str = "http://localhost:3000"

    # Password hashing
    BCRYPT_ROUNDS: int = 12

    # Security API Key
    API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
