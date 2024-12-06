"""
GitHub Analyzer Test Suite.

This module contains tests for the GitHubAnalyzer class, covering:
- Repository analysis functionality
- Rate limit handling
- Error scenarios
- Mock GitHub API interactions

The tests use pytest fixtures for dependency injection and
mock objects to simulate GitHub API responses.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from analyzers.repository import GitHubAnalyzer, RepositoryMetrics


@pytest.fixture(autouse=True)
def mock_settings():
    """
    Mock application settings for testing.

    Provides a mock settings object with predefined values for:
    - GitHub token
    - Log level

    Yields:
        MagicMock: Mocked settings object with test configuration
    """
    with patch("analyzers.repository.settings") as mock_settings:
        mock_settings.github_token = "dummy_token"
        mock_settings.log_level = "INFO"
        yield mock_settings


@pytest.fixture
def mock_github():
    """
    Mock GitHub API client.

    Provides a mock GitHub client with preconfigured rate limits and
    simulated API responses.

    Yields:
        MagicMock: Mocked GitHub client with test configuration

    Note:
        Includes mock rate limit configuration with:
        - 1000 remaining calls
        - 5000 total limit
        - Current time as reset time
    """
    with patch("analyzers.repository.Github") as mock:
        # Mock rate limit configuration
        rate_limit = MagicMock()
        rate_limit.core.remaining = 1000
        rate_limit.core.limit = 5000
        rate_limit.core.reset.replace.return_value = datetime.now(timezone.utc)
        mock.return_value.get_rate_limit.return_value = rate_limit
        yield mock


@pytest.fixture
def analyzer(mock_github):
    """
    Create GitHubAnalyzer instance for testing.

    Args:
        mock_github: Mocked GitHub client fixture

    Returns:
        GitHubAnalyzer: Analyzer instance with mocked dependencies
    """
    return GitHubAnalyzer()


@pytest.mark.asyncio
async def test_analyze_repository_success(analyzer, mock_github):
    """
    Test successful repository analysis scenario.

    Verifies that the analyzer correctly:
    - Processes repository data
    - Handles pull requests
    - Analyzes branches
    - Tracks issues
    - Generates metrics

    Args:
        analyzer: GitHubAnalyzer instance
        mock_github: Mocked GitHub client

    Assertions:
        - Returns valid RepositoryMetrics instance
        - Contains expected repository name
        - Has valid counts for PRs, branches, and issues
        - Includes PR type analysis
        - Includes branch activity metrics
    """
    # Mock repository data
    mock_repo = Mock()

    # Mock pull request data
    mock_pr = Mock()
    mock_pr.title = "feat: new feature"
    mock_pr.body = "Feature description"
    mock_pr.labels = []
    mock_pr.updated_at = datetime.now(timezone.utc)
    mock_pr.created_at = datetime.now(timezone.utc)
    mock_pr.merged_at = None
    mock_pr.head.ref = "feature/new-feature"

    mock_repo.get_pulls.return_value = [mock_pr]

    # Mock branch data
    mock_branch = Mock()
    mock_branch.name = "feature/test"
    mock_branch.commit.commit.author.date = datetime.now(timezone.utc)
    mock_repo.get_branches.return_value = [mock_branch]

    # Mock issue data
    mock_issue = Mock()
    mock_issue.updated_at = datetime.now(timezone.utc)
    mock_issue.state = "open"
    mock_repo.get_issues.return_value = [mock_issue]

    mock_github.return_value.get_repo.return_value = mock_repo

    # Execute analysis
    metrics = await analyzer.analyze_repository("test/repo")

    # Verify results
    assert isinstance(metrics, RepositoryMetrics)
    assert metrics.repository_name == "test/repo"
    assert metrics.total_prs >= 0
    assert metrics.open_prs >= 0
    assert metrics.merged_prs >= 0
    assert metrics.active_branches >= 0
    assert metrics.total_issues >= 0
    assert metrics.open_issues >= 0
    assert len(metrics.pr_types) > 0
    assert len(metrics.branch_activity) > 0


@pytest.mark.asyncio
async def test_analyze_repository_rate_limit(analyzer, mock_github):
    """
    Test GitHub API rate limit handling.

    Verifies that the analyzer properly:
    - Detects rate limit exhaustion
    - Raises appropriate exception
    - Includes reset time information

    Args:
        analyzer: GitHubAnalyzer instance
        mock_github: Mocked GitHub client

    Assertions:
        - Raises exception with rate limit message
        - Exception includes reset time information
    """
    # Configure rate limit exhaustion
    rate_limit = MagicMock()
    rate_limit.core.remaining = 0
    rate_limit.core.limit = 5000
    rate_limit.core.reset.replace.return_value = datetime.now(timezone.utc)
    mock_github.return_value.get_rate_limit.return_value = rate_limit

    # Verify rate limit exception
    with pytest.raises(Exception) as exc_info:
        await analyzer.analyze_repository("test/repo")
    assert "rate limit exhausted" in str(exc_info.value)


@pytest.mark.asyncio
async def test_analyze_repository_error(analyzer, mock_github):
    """
    Test error handling during repository analysis.

    Verifies that the analyzer properly:
    - Handles GitHub API errors
    - Propagates exceptions with context
    - Maintains error information

    Args:
        analyzer: GitHubAnalyzer instance
        mock_github: Mocked GitHub client

    Assertions:
        - Raises exception with API error message
        - Preserves original error information
    """
    # Simulate GitHub API error
    mock_github.return_value.get_repo.side_effect = Exception("API Error")

    # Verify error handling
    with pytest.raises(Exception) as exc_info:
        await analyzer.analyze_repository("test/repo")
    assert "API Error" in str(exc_info.value)
