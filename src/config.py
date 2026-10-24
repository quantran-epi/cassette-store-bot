import json
from typing import Any

from pydantic import SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class CommaOrJsonEnvSettingsSource(EnvSettingsSource):
    """Env source that avoids JSON-decoding comma-separated strings for complex fields."""

    def decode_complex_value(self, field_name: str, field_info: Any, value: Any) -> Any:
        try:
            return super().decode_complex_value(field_name, field_info, value)
        except (ValueError, TypeError):
            # Fallback for comma-separated or non-JSON string values
            return value


class CommaOrJsonDotEnvSettingsSource(DotEnvSettingsSource):
    """Dotenv source that avoids JSON-decoding comma-separated strings for complex fields."""

    def decode_complex_value(self, field_name: str, field_info: Any, value: Any) -> Any:
        try:
            return super().decode_complex_value(field_name, field_info, value)
        except (ValueError, TypeError):
            return value


class Settings(BaseSettings):
    """Application settings with fail-fast validation and masked secrets."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram bot configuration
    telegram_bot_token: SecretStr
    telegram_whitelist_user_ids: list[int] = []

    # LLM Gateway configuration (9router / OpenAI-compatible)
    nine_router_api_key: SecretStr = SecretStr("")
    nine_router_base_url: str = "https://api.9router.com/v1"
    nine_router_model_id: str = "gpt-4o-mini"

    # SQLite Database configuration
    sqlite_db_path: str = "cassette_store.db"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        custom_dotenv = (
            CommaOrJsonDotEnvSettingsSource(
                settings_cls,
                env_file=dotenv_settings.env_file,
                env_file_encoding=dotenv_settings.env_file_encoding,
            )
            if isinstance(dotenv_settings, DotEnvSettingsSource)
            else dotenv_settings
        )
        return (
            init_settings,
            CommaOrJsonEnvSettingsSource(settings_cls),
            custom_dotenv,
            file_secret_settings,
        )

    @field_validator("telegram_whitelist_user_ids", mode="before")
    @classmethod
    def parse_whitelist(cls, v: Any) -> list[int]:
        """Parse comma-separated string, JSON array, or list of user IDs."""
        if isinstance(v, (list, set, tuple)):
            return [int(x) for x in v]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                parsed = json.loads(v)
                return [int(x) for x in parsed]
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, (int, float)):
            return [int(v)]
        raise ValueError(f"Invalid format for whitelist IDs: {v}")
