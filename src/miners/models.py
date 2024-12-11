"""
Repository Mining Data Models.

Defines the common data models used across different repository mining implementations.
Uses Pydantic for validation and serialization.
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class RepositoryPRData(BaseModel):
    """Raw Pull Request data from repository."""

    pr_number: int
    title: str
    body: Optional[str]
    state: str
    created_at: datetime
    updated_at: datetime
    merged_at: Optional[datetime]
    closed_at: Optional[datetime]
    head_ref: str  # Branch name
    author: str
    assignees: List[str]
    reviewers: List[str]
    labels: List[str]
    issue_url: Optional[str]


class RepositoryIssueData(BaseModel):
    """Raw Issue data from repository."""

    issue_number: int
    title: str
    state: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    author: str
    assignees: List[str]
    url: Optional[str]
    labels: List[str]


class RepositoryData(BaseModel):
    """Container for all mined repository data."""

    repository_name: str
    collection_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    pull_requests: List[RepositoryPRData]
    issues: List[RepositoryIssueData]
