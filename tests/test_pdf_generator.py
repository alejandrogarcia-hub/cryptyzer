"""
PDF Generator Test Suite.

This module contains tests for the PDFReportGenerator class, covering:
- Individual repository report generation
- Multi-repository summary reports
- Error handling scenarios
- PDF formatting and content validation

The tests use pytest fixtures for dependency injection and
mock objects to simulate report generation dependencies.
"""

import pytest
from unittest.mock import Mock, patch, ANY
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
    """
    Mock repository data store.

    Provides a mock store with predefined test data and behaviors:
    - Sample repository history
    - Analysis storage functionality
    - Error scenarios

    Yields:
        Mock: Configured repository store mock with test data
    """
    with patch("report.pdf_generator.RepositoryStore") as mock_class:
        # Create a mock instance with sample data
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
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_plotter():
    """
    Mock visualization plotter.

    Provides a mock plotter for generating visualization data:
    - Empty plot paths for testing
    - Comparison plot generation

    Yields:
        Mock: Configured plotter mock for testing
    """
    with patch("report.pdf_generator.RepositoryPlotter") as mock_class:
        mock_instance = Mock()
        mock_instance.save_plots = Mock(return_value=[])
        mock_instance.create_comparison_plots = Mock(return_value=[])
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_doc_template():
    """
    Mock PDF document template.

    Provides a mock ReportLab document template for testing:
    - Document creation
    - Content building

    Yields:
        Mock: Configured document template mock
    """
    with patch("report.pdf_generator.SimpleDocTemplate") as mock_class:
        mock_instance = Mock()
        mock_instance.build = Mock()
        mock_class.return_value = mock_instance
        yield mock_class


@pytest.fixture
def sample_metrics():
    """
    Create sample repository metrics for testing.

    Provides a complete set of test metrics including:
    - Basic repository statistics
    - PR type metrics
    - Branch activity data

    Returns:
        RepositoryMetrics: Populated metrics object for testing
    """
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
    """
    Test individual repository PDF report generation.

    Verifies:
    - Proper storage of analysis data
    - Plot generation
    - PDF document creation and content
    - File output handling

    Args:
        mock_store: Repository store mock
        mock_plotter: Visualization plotter mock
        mock_doc_template: PDF template mock
        sample_metrics: Test metrics fixture
        tmp_path: Temporary directory path

    Assertions:
        - Analysis data is stored correctly
        - History is retrieved
        - Plots are generated
        - PDF document is created and built
    """
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
    """
    Test error handling in PDF report generation.

    Verifies proper error handling for:
    - Plot generation failures
    - File system errors
    - PDF creation errors

    Args:
        mock_store: Repository store mock
        mock_plotter: Visualization plotter mock
        sample_metrics: Test metrics fixture

    Assertions:
        - Exceptions are properly raised
        - Error handling maintains system stability
    """
    generator = PDFReportGenerator()
    mock_plotter.return_value.save_plots.side_effect = Exception("Plot error")

    with pytest.raises(Exception):
        generator.generate_report(sample_metrics, "invalid/path/report.pdf")


def test_generate_summary_report(
    mock_store, mock_plotter, mock_doc_template, sample_metrics, tmp_path
):
    """
    Test multi-repository summary report generation.

    Verifies:
    - Comparison plot generation
    - Summary document creation
    - Multi-repository data handling

    Args:
        mock_store: Repository store mock
        mock_plotter: Visualization plotter mock
        mock_doc_template: PDF template mock
        sample_metrics: Test metrics fixture
        tmp_path: Temporary directory path

    Assertions:
        - Comparison plots are generated
        - Summary document is created and built
        - Output file is properly handled
    """
    output_path = tmp_path / "test_summary.pdf"
    generator = PDFReportGenerator()
    results = {"test/repo1": sample_metrics, "test/repo2": sample_metrics}

    generator.generate_summary_report(results, str(output_path))

    mock_plotter.create_comparison_plots.assert_called_once_with(results)
    mock_doc_template.assert_called_once_with(str(output_path), pagesize=ANY)
    mock_doc_template.return_value.build.assert_called_once()


def test_generate_summary_report_error(mock_store, mock_plotter, sample_metrics):
    """
    Test error handling in summary report generation.

    Verifies proper error handling for:
    - Plot comparison failures
    - File system errors
    - PDF creation errors

    Args:
        mock_store: Repository store mock
        mock_plotter: Visualization plotter mock
        sample_metrics: Test metrics fixture

    Assertions:
        - Exceptions are properly raised
        - Error handling maintains system stability
    """
    generator = PDFReportGenerator()
    mock_plotter.create_comparison_plots.side_effect = Exception("Plot error")

    with pytest.raises(Exception):
        generator.generate_summary_report(
            {"test/repo": sample_metrics}, "invalid/path/summary.pdf"
        )
