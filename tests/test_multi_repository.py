import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone
from analyzers.multi_repository import MultiRepositoryAnalyzer
from analyzers.repository import (
    RepositoryMetrics,
    PRTypeMetrics,
    BranchActivityMetrics,
    TimeframeMetrics,
)


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("analyzers.multi_repository.settings") as mock_settings:
        mock_settings.github_token.get_secret_value.return_value = "dummy_token"
        mock_settings.repository_urls = [
            "https://github.com/test/repo1",
            "https://github.com/test/repo2",
        ]
        mock_settings.report_output_dir = "test_reports"
        yield mock_settings


@pytest.fixture
def mock_analyzer():
    """Mock GitHub analyzer."""
    with patch("analyzers.multi_repository.GitHubAnalyzer") as mock:
        analyzer_instance = mock.return_value
        analyzer_instance.analyze_repository = AsyncMock()
        analyzer_instance.analyze_repository.return_value = RepositoryMetrics(
            repository_name="test/repo",
            analysis_date=datetime.now(timezone.utc),
            total_prs=10,
            open_prs=5,
            merged_prs=5,
            active_branches=3,
            total_issues=8,
            open_issues=4,
            pr_types=[
                PRTypeMetrics(
                    type="feature", open_count=2, merged_count=2, total_count=4
                ),
                PRTypeMetrics(
                    type="bugfix", open_count=3, merged_count=3, total_count=6
                ),
            ],
            branch_activity=[
                BranchActivityMetrics(
                    type="feature",
                    opened=TimeframeMetrics(
                        last_7_days=1, last_30_days=2, last_60_days=3
                    ),
                    closed=TimeframeMetrics(
                        last_7_days=1, last_30_days=2, last_60_days=3
                    ),
                )
            ],
        )
        yield analyzer_instance


@pytest.fixture
def mock_pdf_generator():
    """Mock PDF generator."""
    with patch("analyzers.multi_repository.PDFReportGenerator") as mock_class:
        # Create a mock instance
        mock_instance = Mock()
        mock_instance.generate_report = Mock()
        mock_instance.generate_summary_report = Mock()

        # Make the mock class return our mock instance
        mock_class.return_value = mock_instance

        yield mock_instance


@pytest.mark.asyncio
async def test_analyze_repositories_success(
    mock_settings, mock_analyzer, mock_pdf_generator
):
    """Test successful analysis of multiple repositories."""
    analyzer = MultiRepositoryAnalyzer()

    # Set up mock repository names
    repo_names = ["test/repo1", "test/repo2"]
    mock_metrics = [
        RepositoryMetrics(
            repository_name=repo_name,
            analysis_date=datetime.now(timezone.utc),
            total_prs=10,
            open_prs=5,
            merged_prs=5,
            active_branches=3,
            total_issues=8,
            open_issues=4,
            pr_types=[
                PRTypeMetrics(
                    type="feature", open_count=2, merged_count=2, total_count=4
                ),
                PRTypeMetrics(
                    type="bugfix", open_count=3, merged_count=3, total_count=6
                ),
            ],
            branch_activity=[
                BranchActivityMetrics(
                    type="feature",
                    opened=TimeframeMetrics(
                        last_7_days=1, last_30_days=2, last_60_days=3
                    ),
                    closed=TimeframeMetrics(
                        last_7_days=1, last_30_days=2, last_60_days=3
                    ),
                )
            ],
        )
        for repo_name in repo_names
    ]

    # Set up mock analyzer to return different metrics for each repo
    mock_analyzer.analyze_repository.side_effect = mock_metrics

    # Run analysis
    results = await analyzer.analyze_repositories()

    # Verify results
    assert len(results) == 2
    assert all(isinstance(metrics, RepositoryMetrics) for metrics in results.values())

    # Verify individual reports were generated
    assert mock_pdf_generator.generate_report.call_count == 2

    # Verify the correct metrics were passed to generate_report
    calls = mock_pdf_generator.generate_report.call_args_list
    assert len(calls) == 2
    for i, call in enumerate(calls):
        args, _ = call
        assert args[0] == mock_metrics[i]  # First argument should be metrics


@pytest.mark.asyncio
async def test_analyze_repositories_partial_failure(
    mock_settings, mock_analyzer, mock_pdf_generator
):
    """Test analysis with some repositories failing."""
    analyzer = MultiRepositoryAnalyzer()

    # Create a successful metrics result
    success_metrics = RepositoryMetrics(
        repository_name="test/repo2",
        analysis_date=datetime.now(timezone.utc),
        total_prs=10,
        open_prs=5,
        merged_prs=5,
        active_branches=3,
        total_issues=8,
        open_issues=4,
        pr_types=[
            PRTypeMetrics(type="feature", open_count=2, merged_count=2, total_count=4),
            PRTypeMetrics(type="bugfix", open_count=3, merged_count=3, total_count=6),
        ],
        branch_activity=[
            BranchActivityMetrics(
                type="feature",
                opened=TimeframeMetrics(last_7_days=1, last_30_days=2, last_60_days=3),
                closed=TimeframeMetrics(last_7_days=1, last_30_days=2, last_60_days=3),
            )
        ],
    )

    # Make first repository analysis fail
    mock_analyzer.analyze_repository.side_effect = [
        Exception("Test error"),
        success_metrics,
    ]

    # Run analysis
    results = await analyzer.analyze_repositories()

    # Verify results
    assert len(results) == 1  # Only one successful analysis
    assert mock_pdf_generator.generate_report.call_count == 1

    # Verify the correct metrics were passed to generate_report
    mock_pdf_generator.generate_report.assert_called_once()
    args, _ = mock_pdf_generator.generate_report.call_args
    assert args[0] == success_metrics


def test_generate_summary_report_success(
    mock_settings, mock_analyzer, mock_pdf_generator
):
    """Test successful generation of summary report."""
    analyzer = MultiRepositoryAnalyzer()

    # Create sample metrics
    sample_metrics = RepositoryMetrics(
        repository_name="test/repo",
        analysis_date=datetime.now(timezone.utc),
        total_prs=10,
        open_prs=5,
        merged_prs=5,
        active_branches=3,
        total_issues=8,
        open_issues=4,
        pr_types=[
            PRTypeMetrics(type="feature", open_count=2, merged_count=2, total_count=4),
            PRTypeMetrics(type="bugfix", open_count=3, merged_count=3, total_count=6),
        ],
        branch_activity=[
            BranchActivityMetrics(
                type="feature",
                opened=TimeframeMetrics(last_7_days=1, last_30_days=2, last_60_days=3),
                closed=TimeframeMetrics(last_7_days=1, last_30_days=2, last_60_days=3),
            )
        ],
    )

    # Create sample results
    results = {"test/repo1": sample_metrics, "test/repo2": sample_metrics}

    # Generate summary report
    report_path = analyzer.generate_summary_report(results)

    # Verify summary report was generated
    mock_pdf_generator.generate_summary_report.assert_called_once_with(
        results, report_path
    )


def test_generate_summary_report_error(
    mock_settings, mock_analyzer, mock_pdf_generator
):
    """Test error handling in summary report generation."""
    analyzer = MultiRepositoryAnalyzer()

    # Mock error in report generation
    mock_pdf_generator.generate_summary_report.side_effect = Exception("Test error")

    # Verify error handling
    with pytest.raises(Exception):
        analyzer.generate_summary_report({})
