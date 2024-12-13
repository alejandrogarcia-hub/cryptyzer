"""
Application Configuration Module.

Manages application settings and environment variables using Pydantic for validation.
Provides centralized configuration management with type safety and validation.

Features:
- Environment variable loading and validation
- Secure credential management
- Configuration validation and type checking
- Path normalization for output directories
"""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os
from logger import LogManager


class Settings(BaseSettings):
    """
    Application configuration settings with validation.

    Manages and validates all application settings including:
    - Application identification
    - GitHub authentication
    - Repository configurations
    - Logging settings
    - Output directory configurations
    - OpenAI configuration
    - AI analysis settings

    Attributes:
        app_name (str): Name of the application
        dev (bool): Debug mode flag
        log_dir (str): Directory for log files
        github_token (SecretStr): GitHub API authentication token
        github_repo_urls (str): Comma-separated repository URLs
        log_level (int): Logging level (default: debug)
        report_output_dir (str): Directory for generated reports
        openai_api_key (SecretStr): OpenAI API key
        openai_llm_model (str): OpenAI LLM model to use
        ai_based (bool): Whether to use AI-based analysis
    """

    # Application settings
    app_name: str = Field(default="Cryptyzer", description="Application name")
    dev: bool = Field(default=False, description="Debug mode")
    log_dir: str = Field(default="logs", description="Logging directory")

    # GitHub configuration
    github_token: SecretStr = Field(..., description="GitHub token")
    github_repo_urls: str = Field(
        ..., description="Comma-separated GitHub repository URLs to analyze"
    )

    # OpenAI configuration
    openai_api_key: SecretStr = Field(..., description="OpenAI API key")
    openai_llm_model: str = Field(default="gpt-4-mini", description="OpenAI LLM model")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", description="OpenAI embedding model"
    )
    openai_encoding_name: str = Field(default="o200k_base", description="Encoding name")
    openai_max_requests_per_minute: int = Field(
        default=500, description="OpenAI max requests per minute"
    )
    openai_max_tokens_per_minute: int = Field(
        default=200000, description="OpenAI max tokens per minute"
    )
    openai_period: int = Field(default=60, description="OpenAI period in seconds")

    # AI Analysis configuration
    ai_based: bool = Field(default=False, description="Use AI-based analysis")

    # Optional configuration with defaults
    log_level: int = Field(default=10, description="Logging level, default debug")

    data_dir: str = Field(default="data", description="Data output directory")

    report_output_dir: str = Field(
        default="reports", description="Report output directory"
    )

    interval_days: str = Field(
        default="7,30,60", description="Comma-separated interval days to analyze"
    )

    @property
    def intervals(self) -> List[int]:
        """
        Get interval days from configuration.

        Splits and cleans the comma-separated interval days string.

        Returns:
            List[int]: List of interval days
        """
        return [int(day) for day in self.interval_days.split(",")]

    @property
    def repository_urls(self) -> List[str]:
        """
        Get list of repository URLs from configuration.

        Splits and cleans the comma-separated repository URLs string.

        Returns:
            List[str]: List of cleaned repository URLs
        """
        return [url.strip() for url in self.github_repo_urls.split(",")]

    @field_validator("report_output_dir")
    def ensure_absolute_path(cls, v: str) -> str:
        """
        Ensure report directory path is absolute.

        Converts relative paths to absolute paths based on current working directory.

        Args:
            v (str): Directory path to validate

        Returns:
            str: Absolute path to report directory
        """
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

# Initialize logging configuration
logger = LogManager(
    app_name=settings.app_name.lower(),
    log_dir=settings.log_dir,
    development=settings.dev,
    level=settings.log_level,
).logger
