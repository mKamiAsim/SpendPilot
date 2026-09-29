from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from the environment, never from request headers."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url_migrator: str = Field(alias="DATABASE_URL_MIGRATOR")
    database_url_app: str = Field(alias="DATABASE_URL_APP")
    public_app_url: str = Field(default="http://localhost:8080", alias="PUBLIC_APP_URL")
    allowed_origins: str = Field(default="", alias="ALLOWED_ORIGINS")
    cookie_secure: bool | None = Field(default=None, alias="COOKIE_SECURE")
    idle_lock_minutes: int = Field(default=15, alias="IDLE_LOCK_MINUTES")
    email_delivery: str = Field(default="smtp", alias="EMAIL_DELIVERY")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", alias="SMTP_FROM")
    smtp_tls: bool = Field(default=True, alias="SMTP_TLS")
    encryption_keys: str = Field(default="", alias="APP_ENCRYPTION_KEYS")
    encryption_key_id: str = Field(default="", alias="APP_ENCRYPTION_KEY_ID")
    model_allowed_private_hosts: str = Field(default="", alias="MODEL_ALLOWED_PRIVATE_HOSTS")
    trust_proxy: bool = Field(default=False, alias="TRUST_PROXY")
    bootstrap_admin_username: str = Field(default="", alias="BOOTSTRAP_ADMIN_USERNAME")
    bootstrap_admin_email: str = Field(default="", alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str = Field(default="", alias="BOOTSTRAP_ADMIN_PASSWORD")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    file_storage_dir: str = Field(default="/var/lib/spendpilot/files", alias="FILE_STORAGE_DIR")

    @field_validator("idle_lock_minutes")
    @classmethod
    def idle_bounds(cls, value: int) -> int:
        if not 5 <= value <= 60:
            raise ValueError("IDLE_LOCK_MINUTES must be between 5 and 60.")
        return value

    @field_validator("email_delivery")
    @classmethod
    def delivery_mode(cls, value: str) -> str:
        if value not in {"smtp", "capture"}:
            raise ValueError("EMAIL_DELIVERY must be smtp or capture.")
        return value

    @field_validator("public_app_url")
    @classmethod
    def absolute_public_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("PUBLIC_APP_URL must be an absolute http or https URL.")
        return value.rstrip("/")

    @property
    def use_secure_cookies(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.public_app_url.startswith("https://")

    @property
    def allowed_origin_list(self) -> list[str]:
        origins = [item.strip() for item in self.allowed_origins.split(",") if item.strip()]
        parts = urlsplit(self.public_app_url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in origins:
            origins.append(origin)
        return origins

    @property
    def email_mode(self) -> str:
        if self.email_delivery == "capture":
            return "capture"
        if self.smtp_host:
            return "smtp"
        return "unconfigured"

    @property
    def password_reset_available(self) -> bool:
        return self.email_mode in {"smtp", "capture"}

    @property
    def private_model_hosts(self) -> frozenset[str]:
        return frozenset(
            item.strip().lower().rstrip(".")
            for item in self.model_allowed_private_hosts.split(",")
            if item.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
