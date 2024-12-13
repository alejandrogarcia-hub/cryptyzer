"""
GitHub Analyzer Test Suite.

This module contains tests for the GitHubAnalyzer class, covering:
- Repository analysis functionality
- PR type classification
- Interval-based metrics
- Error scenarios
"""

import pytest
from datetime import datetime, timezone

import pandas as pd

from miners.models import RepositoryPRData, RepositoryIssueData, RepositoryData
from analyzers.repository import GitHubAnalyzer
from analyzers.plugins.category_analyzer import PRTypeCategoryAnalyzerPlugin
from analyzers.models import RepositoryMetrics, PullRequestType


@pytest.fixture
def feature_labels():
    """Create sample feature labels for testing."""
    return [pr_type.value for pr_type in PullRequestType]


@pytest.fixture
def sample_pull_requests():
    """Create sample pull requests for testing."""
    now = datetime.now(timezone.utc)
    return [
        RepositoryPRData(
            pr_number=1,
            title="feat: new feature",
            body="Feature description",
            state="open",
            labels=["feature"],
            assignees=["user1"],
            reviewers=["user2"],
            created_at=now,
            updated_at=now,
            closed_at=None,
            merged_at=None,
            head_ref="feature/new-feature",
            author="user1",
            issue_url=None,
        ),
        RepositoryPRData(
            pr_number=2,
            title="fix: bug fix",
            body="Bug fix description",
            state="closed",
            labels=["bugfix"],
            assignees=["user2"],
            reviewers=["user1"],
            created_at=now,
            updated_at=now,
            closed_at=now,
            merged_at=now,
            head_ref="fix/bug-fix",
            author="user2",
            issue_url=None,
        ),
        RepositoryPRData(
            pr_number=3,
            title="test: new tests",
            body="Test description",
            state="open",
            labels=["test"],
            assignees=["user3"],
            reviewers=["user1"],
            created_at=now,
            updated_at=now,
            closed_at=None,
            merged_at=None,
            head_ref="test/new-tests",
            author="user3",
            issue_url=None,
        ),
    ]


@pytest.fixture
def sample_issues():
    """Create sample issues for testing."""
    now = datetime.now(timezone.utc)
    return [
        RepositoryIssueData(
            issue_number=1,
            title="Issue 1",
            body="Issue description",
            state="open",
            labels=["bug"],
            assignees=["user1"],
            created_at=now,
            updated_at=now,
            closed_at=None,
            author="user1",
            url=None,
        ),
        RepositoryIssueData(
            issue_number=2,
            title="Issue 2",
            body="Issue description",
            state="closed",
            labels=["enhancement"],
            assignees=["user2"],
            created_at=now,
            updated_at=now,
            closed_at=now,
            author="user2",
            url=None,
        ),
    ]


@pytest.fixture
def sample_repo_data(sample_pull_requests, sample_issues):
    """Create sample repository data for testing."""
    return RepositoryData(
        repository_name="test/repo",
        collection_date=datetime.now(timezone.utc),
        pull_requests=sample_pull_requests,
        issues=sample_issues,
    )


@pytest.fixture
def category_analyzer():
    """Create PRTypeCategoryAnalyzerPlugin instance for testing."""
    return PRTypeCategoryAnalyzerPlugin()


@pytest.fixture
def analyzer(category_analyzer):
    """Create GitHubAnalyzer instance for testing."""
    return GitHubAnalyzer(intervals=[7, 30, 60], category_analyzer=category_analyzer)


@pytest.mark.asyncio
async def test_analyze_repository_success(analyzer, sample_repo_data):
    """Test successful repository analysis scenario."""
    # Execute analysis
    metrics = await analyzer.analyze_repository(sample_repo_data)

    # Verify basic metrics
    assert isinstance(metrics, RepositoryMetrics)
    assert metrics.repository_name == "test/repo"
    assert metrics.total_prs_count == 3
    assert metrics.open_prs_count == 2
    assert metrics.closed_prs_count == 1
    assert metrics.total_issues_count == 2
    assert metrics.open_issues_count == 1

    # Verify PR interval metrics
    assert "7" in metrics.pr_interval_metrics
    assert "30" in metrics.pr_interval_metrics
    assert "60" in metrics.pr_interval_metrics

    # Verify PR types in interval metrics
    seven_day_metrics = metrics.pr_interval_metrics["7"]
    assert "feature" in seven_day_metrics.open
    assert "bugfix" in seven_day_metrics.closed
    assert "test" in seven_day_metrics.open

    # Verify contributors
    assert metrics.contributors_count == 3
    assert "user1" in metrics.top_contributors
    assert len(metrics.top_contributors) == 1


@pytest.mark.asyncio
async def test_analyze_repository_empty_data(analyzer):
    """Test analysis with empty repository data."""
    empty_data = RepositoryData(
        repository_name="test/repo",
        collection_date=datetime.now(timezone.utc),
        pull_requests=[],
        issues=[],
    )

    metrics = await analyzer.analyze_repository(empty_data)

    assert metrics.total_prs_count == 0
    assert metrics.open_prs_count == 0
    assert metrics.closed_prs_count == 0
    assert metrics.total_issues_count == 0
    assert metrics.open_issues_count == 0
    assert metrics.contributors_count == 0
    assert len(metrics.top_contributors) == 0


@pytest.mark.asyncio
async def test_classify_all_prs(analyzer, sample_pull_requests, feature_labels):
    """Test PR type classification logic."""
    # Test with labels

    prs_df = pd.DataFrame([sample.model_dump() for sample in sample_pull_requests])
    pr_types = await analyzer._classify_all_prs(prs_df, feature_labels)
    for resp, feature_label in zip(pr_types, ["feature", "bugfix", "test"]):
        assert resp["pr_type"] == feature_label
