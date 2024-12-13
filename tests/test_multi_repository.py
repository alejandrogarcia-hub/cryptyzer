import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone
from analyzers.multi_repository import MultiRepositoryAnalyzer
from miners.models import RepositoryData
from analyzers.models import RepositoryMetrics, PRMetrics


@pytest.fixture
def mock_store():
    """Mock repository store."""
    store = Mock()
    store.load_repository_data.return_value = None
    store.load_analysis.return_value = None
    store.load_repository_data.return_value = None
    store.store_analysis.return_value = None
    return store


@pytest.fixture
def mock_miner():
    """Mock repository miner."""
    miner = Mock()
    miner.mine_repository = AsyncMock()
    miner.mine_repository.return_value = RepositoryData(
        repository_name="test/repo",
        collection_date=datetime.now(timezone.utc),
        pull_requests=[],
        issues=[],
    )
    return miner


@pytest.fixture
def mock_analyzer():
    """Mock GitHub analyzer."""
    analyzer = Mock()
    analyzer.analyze_repository = AsyncMock()

    # Create sample metrics with PR interval metrics
    pr_metrics = {
        "7": PRMetrics(
            open={"feature": 2, "bugfix": 3},
            closed={"feature": 2, "bugfix": 3},
            contributors_count=5,
        ),
        "30": PRMetrics(
            open={"feature": 4, "bugfix": 6},
            closed={"feature": 4, "bugfix": 6},
            contributors_count=8,
        ),
    }

    analyzer.analyze_repository.return_value = RepositoryMetrics(
        repository_name="test/repo",
        analysis_date=datetime.now(timezone.utc),
        total_prs_count=10,
        open_prs_count=5,
        closed_prs_count=5,
        total_issues_count=8,
        open_issues_count=4,
        pr_interval_metrics=pr_metrics,
        top_contributors=["user1", "user2"],
        contributors_count=5,
    )
    return analyzer


@pytest.mark.asyncio
async def test_analyze_repositories_success(mock_store, mock_miner, mock_analyzer):
    """Test successful analysis of multiple repositories."""
    # Setup mock store to return repository data
    mock_store.load_repository_data.return_value = [
        RepositoryData(
            repository_name="test/repo1",
            collection_date=datetime.now(timezone.utc),
            pull_requests=[],
            issues=[],
        )
    ]

    # Initialize analyzer with mocks
    analyzer = MultiRepositoryAnalyzer(
        repository_store=mock_store,
        analyzer=mock_analyzer,
        miner=mock_miner,
        repository_urls=[
            "https://github.com/test/repo1",
            "https://github.com/test/repo2",
        ],
    )

    # Run analysis
    results = await analyzer.analyze_repositories()

    # Verify results
    assert len(results) == 2
    assert all(isinstance(metrics, RepositoryMetrics) for metrics in results.values())

    # Verify store interactions
    assert (
        mock_store.load_repository_data.call_count >= 2
    )  # Called for initial check and analysis

    mock_store.save_repository_data.assert_not_called()

    assert (
        mock_store.store_analysis.call_count >= 1
    )  # Called for storing analysis results

    # Verify miner interactions
    mock_miner.mine_repository.assert_not_called()

    # Verify analyzer interactions
    assert (
        mock_analyzer.analyze_repository.call_count >= 1
    )  # Called for repositories needing analysis


@pytest.mark.asyncio
async def test_analyze_repositories_with_existing_data(
    mock_store, mock_miner, mock_analyzer
):
    """Test analysis when repository data already exists for today."""
    # Setup mock store to return existing data
    today_data = RepositoryData(
        repository_name="test/repo1",
        collection_date=datetime.now(timezone.utc),
        pull_requests=[],
        issues=[],
    )
    mock_store.load_repository_data.return_value = [today_data]

    # Initialize analyzer
    analyzer = MultiRepositoryAnalyzer(
        repository_store=mock_store,
        analyzer=mock_analyzer,
        miner=mock_miner,
        repository_urls=["https://github.com/test/repo1"],
    )

    # Run analysis
    results = await analyzer.analyze_repositories()

    # Verify results
    assert len(results) == 1

    # Verify store was checked but no new data was saved
    # assert called twice
    assert mock_store.load_repository_data.call_count == 2
    mock_store.save_repository_data.assert_not_called()

    # Verify miner was not called
    mock_miner.mine_repository.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_repositories_with_existing_analysis(
    mock_store, mock_miner, mock_analyzer
):
    """Test when analysis already exists for today."""
    # Setup mock store to return existing analysis
    today_analysis = RepositoryMetrics(
        repository_name="test/repo1",
        analysis_date=datetime.now(timezone.utc),
        total_prs_count=10,
        open_prs_count=5,
        closed_prs_count=5,
        total_issues_count=8,
        open_issues_count=4,
        pr_interval_metrics={},
        top_contributors=[],
        contributors_count=5,
    )
    mock_store.load_analysis.return_value = [today_analysis]

    # Initialize analyzer
    analyzer = MultiRepositoryAnalyzer(
        repository_store=mock_store,
        analyzer=mock_analyzer,
        miner=mock_miner,
        repository_urls=["https://github.com/test/repo1"],
    )

    # Run analysis
    results = await analyzer.analyze_repositories()

    # Verify results
    assert len(results) == 1
    assert results["test/repo1"] == today_analysis

    # Verify no new analysis was performed
    mock_analyzer.analyze_repository.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_repositories_error_handling(
    mock_store, mock_miner, mock_analyzer
):
    """Test error handling during repository analysis."""
    # Setup mock store to return data for the second repository
    mock_store.load_repository_data.side_effect = [
        None,  # First call for repo1 (initial check)
        None,  # First call for repo2 (initial check)
        [  # Second call for repo2 (pipeline load)
            RepositoryData(
                repository_name="test/repo2",
                collection_date=datetime.now(timezone.utc),
                pull_requests=[],
                issues=[],
            )
        ],
    ]
    mock_store.load_analysis.return_value = None

    # Make miner raise an exception for the first repository
    mock_miner.mine_repository.side_effect = [
        Exception("Mining failed"),  # First repo fails
        RepositoryData(  # Second repo succeeds
            repository_name="test/repo2",
            collection_date=datetime.now(timezone.utc),
            pull_requests=[],
            issues=[],
        ),
    ]

    # Setup analyzer to return metrics for the second repository
    mock_analyzer.analyze_repository.return_value = RepositoryMetrics(
        repository_name="test/repo2",
        analysis_date=datetime.now(timezone.utc),
        total_prs_count=10,
        open_prs_count=5,
        closed_prs_count=5,
        total_issues_count=8,
        open_issues_count=4,
        pr_interval_metrics={},
        top_contributors=[],
        contributors_count=5,
    )

    # Initialize analyzer
    analyzer = MultiRepositoryAnalyzer(
        repository_store=mock_store,
        analyzer=mock_analyzer,
        miner=mock_miner,
        repository_urls=[
            "https://github.com/test/repo1",
            "https://github.com/test/repo2",
        ],
    )

    # Run analysis
    results = await analyzer.analyze_repositories()

    # Verify only one repository was successfully analyzed
    assert len(results) == 1
    assert "test/repo2" in results

    # Verify interactions
    assert (
        mock_store.load_repository_data.call_count == 3
    )  # Two calls per repo (initial + pipeline)
    assert mock_miner.mine_repository.call_count == 2  # Called for both repos
    assert (
        mock_analyzer.analyze_repository.call_count == 1
    )  # Only successful for second repo
    assert mock_store.store_analysis.call_count == 1  # Only stored for successful repo
