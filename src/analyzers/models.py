"""
Repository Mining Data Models.

Defines the common data models used across different repository mining implementations.
Uses Pydantic for validation and serialization.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict

from pydantic import BaseModel, Field


class PullRequestType(Enum):
    """
    Classification of pull request types.

    Attributes:
        FEATURE: New feature implementations
        BUGFIX: Bug fixes
        HOTFIX: Critical/urgent fixes
        REFACTOR: Code refactoring
        TEST: Testing changes
        ISSUE: Issue-related changes
        OTHER: Uncategorized changes
    """

    FEATURE = "feature"
    BUGFIX = "bugfix"
    HOTFIX = "hotfix"
    REFACTOR = "refactor"
    TEST = "test"
    ISSUE = "issue"
    OTHER = "other"


class PRMetrics(BaseModel):
    """Metrics for a PR type."""

    open: Dict[str, int]
    closed: Dict[str, int]
    contributors_count: int


class RepositoryMetrics(BaseModel):
    """Metrics for a repository."""

    repository_name: str
    analysis_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_prs_count: int
    open_prs_count: int
    closed_prs_count: int
    total_issues_count: int
    open_issues_count: int
    pr_interval_metrics: Dict[str, PRMetrics]
    top_contributors: List[str]
    contributors_count: int
