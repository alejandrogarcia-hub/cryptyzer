import pytest
from unittest.mock import Mock, patch
from analyzers.repository import GitHubAnalyzer, RepositoryMetrics


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for testing."""
    with patch("analyzers.repository.settings") as mock_settings:
        mock_settings.github_token = "dummy_token"
        mock_settings.log_level = "INFO"
        yield mock_settings


@pytest.fixture
def mock_github():
    with patch("analyzers.repository.Github") as mock:
        yield mock


@pytest.fixture
def analyzer(mock_github):
    return GitHubAnalyzer()  # No need to pass token, will use from settings


@pytest.mark.asyncio
async def test_analyze_repository_success(analyzer, mock_github):
    # Mock repository data
    mock_repo = Mock()
    mock_repo.get_pulls.return_value.totalCount = 10
    mock_repo.get_branches.return_value = [Mock(), Mock()]
    mock_repo.get_issues.return_value.totalCount = 5

    mock_github.return_value.get_repo.return_value = mock_repo

    # Run analysis with await
    metrics = await analyzer.analyze_repository("test/repo")

    # Verify results
    assert isinstance(metrics, RepositoryMetrics)
    assert metrics.total_prs == 10
    assert metrics.active_branches == 2
    assert metrics.total_issues == 5
