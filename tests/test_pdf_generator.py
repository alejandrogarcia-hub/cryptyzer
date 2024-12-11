"""
PDF Generator Test Suite.

This module contains tests for the PDFReportGenerator class, covering:
- Individual repository report generation
- Multi-repository summary reports
- Error handling scenarios
- PDF formatting and content validation
- Historical trend visualization
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import os
from report.pdf_generator import PDFReportGenerator
from analyzers.models import RepositoryMetrics, PRMetrics


@pytest.fixture
def mock_plotter():
    """Mock visualization plotter."""
    plotter = Mock()
    plotter.create_pr_type_trends_plots = Mock(
        return_value={"7": Mock(), "30": Mock(), "60": Mock()}
    )
    return plotter


@pytest.fixture
def mock_doc_template():
    """Mock PDF document template."""
    with patch("report.pdf_generator.SimpleDocTemplate") as mock_class:
        mock_instance = Mock()
        mock_instance.build = Mock()
        mock_class.return_value = mock_instance
        yield mock_class


@pytest.fixture
def sample_metrics():
    """Create sample repository metrics for testing."""
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
        "60": PRMetrics(
            open={"feature": 6, "bugfix": 9},
            closed={"feature": 6, "bugfix": 9},
            contributors_count=10,
        ),
    }

    return RepositoryMetrics(
        repository_name="test/repo",
        analysis_date=datetime.now(timezone.utc),
        total_prs_count=10,
        open_prs_count=5,
        closed_prs_count=5,
        total_issues_count=8,
        open_issues_count=4,
        pr_interval_metrics=pr_metrics,
        top_contributors=["user1", "user2", "user3", "user4", "user5"],
        contributors_count=5,
    )


@pytest.fixture
def sample_historical_data():
    """Create sample historical data for testing."""
    pr_metrics = {
        "7": PRMetrics(
            open={"feature": 1, "bugfix": 2},
            closed={"feature": 1, "bugfix": 2},
            contributors_count=3,
        ),
        "30": PRMetrics(
            open={"feature": 2, "bugfix": 4},
            closed={"feature": 2, "bugfix": 4},
            contributors_count=5,
        ),
        "60": PRMetrics(
            open={"feature": 3, "bugfix": 6},
            closed={"feature": 3, "bugfix": 6},
            contributors_count=7,
        ),
    }

    historical_metrics = RepositoryMetrics(
        repository_name="test/repo",
        analysis_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        total_prs_count=5,
        open_prs_count=2,
        closed_prs_count=3,
        total_issues_count=4,
        open_issues_count=2,
        pr_interval_metrics=pr_metrics,
        top_contributors=["user1", "user2", "user3"],
        contributors_count=3,
    )

    return {"test/repo": [historical_metrics]}


def test_generate_report(
    mock_plotter, mock_doc_template, sample_metrics, sample_historical_data, tmp_path
):
    """Test individual repository PDF report generation."""
    # Setup
    output_path = str(tmp_path)
    temp_plot_dir = os.path.join(output_path, "temp_plots")
    generator = PDFReportGenerator(mock_plotter)
    repo_metrics = {"test/repo": sample_metrics}

    # Generate report
    generator.generate_report(
        repo_metrics, sample_historical_data, output_path, temp_plot_dir
    )

    # Verify plotter interactions
    mock_plotter.create_pr_type_trends_plots.assert_called_once()

    # Verify document creation
    mock_doc_template.assert_called_once()
    mock_doc_template.return_value.build.assert_called_once()


def test_generate_report_with_multiple_repos(
    mock_plotter, mock_doc_template, sample_metrics, sample_historical_data, tmp_path
):
    """Test PDF report generation for multiple repositories."""
    # Setup
    output_path = str(tmp_path)
    temp_plot_dir = os.path.join(output_path, "temp_plots")
    generator = PDFReportGenerator(mock_plotter)

    # Create metrics for multiple repos
    repo_metrics = {"test/repo1": sample_metrics, "test/repo2": sample_metrics}
    historical_data = {
        "test/repo1": sample_historical_data["test/repo"],
        "test/repo2": sample_historical_data["test/repo"],
    }

    # Generate report
    generator.generate_report(repo_metrics, historical_data, output_path, temp_plot_dir)

    # Verify plotter was called for each repo
    assert mock_plotter.create_pr_type_trends_plots.call_count == 2

    # Verify document creation for each repo
    assert mock_doc_template.call_count == 2
    assert mock_doc_template.return_value.build.call_count == 2


def test_generate_report_error_handling(
    mock_plotter, mock_doc_template, sample_metrics, sample_historical_data, tmp_path
):
    """Test error handling in PDF report generation."""
    output_path = str(tmp_path)
    temp_plot_dir = os.path.join(output_path, "temp_plots")
    generator = PDFReportGenerator(mock_plotter)
    repo_metrics = {"test/repo": sample_metrics}

    # Simulate plot generation error
    mock_plotter.create_pr_type_trends_plots.side_effect = Exception("Plot error")

    # Verify error handling
    with pytest.raises(Exception):
        generator.generate_report(
            repo_metrics, sample_historical_data, output_path, temp_plot_dir
        )


def test_temp_plot_directory_cleanup(
    mock_plotter, mock_doc_template, sample_metrics, sample_historical_data, tmp_path
):
    """Test temporary plot directory cleanup."""
    # Setup
    output_path = str(tmp_path)
    temp_plot_dir = os.path.join(output_path, "temp_plots")
    generator = PDFReportGenerator(mock_plotter)
    repo_metrics = {"test/repo": sample_metrics}

    # Generate report
    generator.generate_report(
        repo_metrics, sample_historical_data, output_path, temp_plot_dir
    )

    # Verify temp directory was cleaned up
    assert not os.path.exists(temp_plot_dir)
