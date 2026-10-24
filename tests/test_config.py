import pytest
from pydantic import ValidationError

from src.config import Settings


def test_settings_loads_comma_separated_whitelist(monkeypatch):
    """Test parsing comma-separated string into list[int]."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot_token_123")
    monkeypatch.setenv("TELEGRAM_WHITELIST_USER_IDS", "123, 456, 789")

    settings = Settings()

    assert settings.telegram_whitelist_user_ids == [123, 456, 789]
    assert settings.telegram_bot_token.get_secret_value() == "fake_bot_token_123"


def test_settings_loads_json_array_whitelist(monkeypatch):
    """Test parsing JSON array string into list[int]."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_bot_token_123")
    monkeypatch.setenv("TELEGRAM_WHITELIST_USER_IDS", "[123, 456]")

    settings = Settings()

    assert settings.telegram_whitelist_user_ids == [123, 456]


def test_settings_requires_telegram_bot_token(monkeypatch):
    """Test ValidationError is raised when telegram_bot_token is missing."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_WHITELIST_USER_IDS", "123")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_secrets_masked_in_str_and_repr(monkeypatch):
    """Test SecretStr masks sensitive tokens from plain text inspection."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "super_secret_telegram_token")
    monkeypatch.setenv("NINE_ROUTER_API_KEY", "super_secret_9router_key")
    monkeypatch.setenv("TELEGRAM_WHITELIST_USER_IDS", "123")

    settings = Settings()

    # Secret values must not be visible in str() or repr()
    assert "super_secret_telegram_token" not in str(settings)
    assert "super_secret_telegram_token" not in repr(settings)
    assert "super_secret_9router_key" not in str(settings)
    assert "super_secret_9router_key" not in repr(settings)

    # But secret value can be accessed explicitly
    assert settings.telegram_bot_token.get_secret_value() == "super_secret_telegram_token"
    assert settings.nine_router_api_key.get_secret_value() == "super_secret_9router_key"


def test_settings_defaults(monkeypatch):
    """Test default values for sqlite path and 9router gateway."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token_123")
    monkeypatch.delenv("SQLITE_DB_PATH", raising=False)
    monkeypatch.delenv("NINE_ROUTER_BASE_URL", raising=False)
    monkeypatch.delenv("NINE_ROUTER_MODEL_ID", raising=False)

    settings = Settings()

    assert settings.sqlite_db_path == "cassette_store.db"
    assert settings.nine_router_base_url == "https://api.9router.com/v1"
    assert settings.nine_router_model_id == "gpt-4o-mini"
