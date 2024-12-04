import pytest
from unittest.mock import Mock, patch, MagicMock, ANY
from datetime import datetime, timezone
from report.pdf_generator import PDFReportGenerator
from analyzers.repository import (
    RepositoryMetrics,
    PRTypeMetrics,
    BranchActivityMetrics,
    TimeframeMetrics,
    PullRequestType,
    BranchType,
)
from storage.repository_store import StoredAnalysis


@pytest.fixture
def mock_store():
    """Mock repository store."""
    with patch("report.pdf_generator.RepositoryStore") as mock_class:
        # Create a mock instance
        mock_instance = Mock()
        mock_instance.get_repository_history = Mock(
            return_value=[
                StoredAnalysis(
                    repository_name="test/repo",
                    analysis_date=datetime.now(timezone.utc),
                    metrics={
                        "repository_name": "test/repo",
                        "analysis_date": datetime.now(timezone.utc).isoformat(),
                        "total_prs": 10,
                        "open_prs": 5,
                        "merged_prs": 5,
                        "active_branches": 3,
                        "total_issues": 8,
                        "open_issues": 4,
                        "pr_types": [],
                        "branch_activity": [],
                    },
                )
            ]
        )
        mock_instance.store_analysis = Mock()

        # Make the mock class return our mock instance
        mock_class.return_value = mock_instance

        yield mock_instance


@pytest.fixture
def mock_plotter():
    """Mock repository plotter."""
    with patch("report.pdf_generator.RepositoryPlotter") as mock_class:
        mock_instance = Mock()
        mock_instance.save_plots = Mock(return_value=[])
        mock_instance.create_comparison_plots = Mock(return_value=[])
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_doc_template():
    """Mock SimpleDocTemplate."""
    with patch("report.pdf_generator.SimpleDocTemplate") as mock_class:
        mock_instance = Mock()
        mock_instance.build = Mock()
        mock_class.return_value = mock_instance
        yield mock_class


@pytest.fixture
def sample_metrics():
    """Create sample metrics for testing."""
    return RepositoryMetrics(
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
                type=PullRequestType.FEATURE,
                open_count=2,
                merged_count=2,
                total_count=4,
            ),
            PRTypeMetrics(
                type=PullRequestType.BUGFIX, open_count=3, merged_count=3, total_count=6
            ),
        ],
        branch_activity=[
            BranchActivityMetrics(
                type=BranchType.FEATURE,
                opened=TimeframeMetrics(last_7_days=1, last_30_days=2, last_60_days=3),
                closed=TimeframeMetrics(last_7_days=1, last_30_days=2, last_60_days=3),
            )
        ],
    )


def test_generate_report(
    mock_store, mock_plotter, mock_doc_template, sample_metrics, tmp_path
):
    """Test PDF report generation."""
    output_path = tmp_path / "test_report.pdf"
    generator = PDFReportGenerator()

    # Generate report
    generator.generate_report(sample_metrics, str(output_path))

    # Verify interactions
    mock_store.store_analysis.assert_called_once_with(sample_metrics.to_dict())
    mock_store.get_repository_history.assert_called_once_with(
        sample_metrics.repository_name
    )
    mock_plotter.save_plots.assert_called_once()
    mock_doc_template.assert_called_once_with(str(output_path), pagesize=ANY)
    mock_doc_template.return_value.build.assert_called_once()


def test_generate_report_error(mock_store, mock_plotter, sample_metrics):
    """Test PDF generation error handling."""
    generator = PDFReportGenerator()

    # Mock error in plot generation
    mock_plotter.return_value.save_plots.side_effect = Exception("Plot error")

    # Verify error handling
    with pytest.raises(Exception):
        generator.generate_report(sample_metrics, "invalid/path/report.pdf")


def test_generate_summary_report(
    mock_store, mock_plotter, mock_doc_template, sample_metrics, tmp_path
):
    """Test summary report generation."""
    output_path = tmp_path / "test_summary.pdf"
    generator = PDFReportGenerator()

    # Create sample results
    results = {"test/repo1": sample_metrics, "test/repo2": sample_metrics}

    # Generate summary report
    generator.generate_summary_report(results, str(output_path))

    # Verify interactions
    mock_plotter.create_comparison_plots.assert_called_once_with(results)
    mock_doc_template.assert_called_once_with(str(output_path), pagesize=ANY)
    mock_doc_template.return_value.build.assert_called_once()


def test_generate_summary_report_error(mock_store, mock_plotter, sample_metrics):
    """Test summary report error handling."""
    generator = PDFReportGenerator()

    # Mock error in plot generation
    mock_plotter.create_comparison_plots.side_effect = Exception("Plot error")

    # Verify error handling
    with pytest.raises(Exception):
        generator.generate_summary_report(
            {"test/repo": sample_metrics}, "invalid/path/summary.pdf"
        )
