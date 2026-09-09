"""Unit tests for configuration."""

from app.config import Settings, get_settings


def test_settings_defaults():
    settings = Settings()
    assert settings.aws_region == "us-east-1" or settings.aws_region == "ap-south-1"
    assert (
        "cloudpulse-resources" in settings.dynamodb_resources_table
        or "test-resources" in settings.dynamodb_resources_table
    )
    assert settings.cors_origins_list != []


def test_cors_origins_split():
    settings = Settings(cors_allowed_origins="http://localhost:3000, https://example.com")
    origins = settings.cors_origins_list
    assert "http://localhost:3000" in origins
    assert "https://example.com" in origins
    assert len(origins) == 2


def test_get_settings_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
