"""
Application configuration loaded from environment variables.

All Lambda environment variables are injected by the SAM template.
For local development, values are read from the .env file via
pydantic-settings.

Never import boto3 or AWS SDK clients here — this module must
be importable without AWS credentials (for unit tests).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """CloudPulse application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AWS
    aws_region: str = "ap-south-1"

    # DynamoDB Tables
    dynamodb_resources_table: str = "cloudpulse-resources"
    dynamodb_incidents_table: str = "cloudpulse-incidents"
    dynamodb_metrics_table: str = "cloudpulse-metrics"
    dynamodb_endpoint_url: str | None = None

    # CloudWatch
    cloudwatch_namespace: str = "CloudPulse"

    # EventBridge
    eventbridge_bus_name: str = "default"

    # SNS
    sns_topic_arn: str = ""

    # API
    cors_allowed_origins: str = "http://localhost:5173"

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings. Use as a FastAPI dependency."""
    return Settings()
