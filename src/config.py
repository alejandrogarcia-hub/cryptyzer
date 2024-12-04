from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os
from logger import LogManager


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = Field(default="Cryptyzer", description="Application name")
    dev: bool = Field(default=False, description="Debug mode")
    log_dir: str = Field(default="logs", description="Logging directory")

    # GitHub configuration
    github_token: SecretStr = Field(..., description="GitHub token")
    github_repo_urls: str = Field(
        ..., description="Comma-separated GitHub repository URLs to analyze"
    )

    # Optional configuration with defaults
    log_level: int = Field(default=10, description="Logging level, default debug")
    report_output_dir: str = Field(
        default="reports", description="Report output directory"
    )

    @property
    def repository_urls(self) -> List[str]:
        """Get list of repository URLs."""
        return [url.strip() for url in self.github_repo_urls.split(",")]

    @field_validator("report_output_dir")
    def ensure_absolute_path(cls, v):
        """Ensure report output directory is an absolute path."""
        if not os.path.isabs(v):
            return os.path.abspath(v)
        return v

    # Configure env file loading
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields in .env file
    )


# Create global settings instance
settings = Settings()

# Initialize logging
logger = LogManager(
    app_name=settings.app_name,
    log_dir=settings.log_dir,
    development=settings.dev,
    level=settings.log_level,
).logger
