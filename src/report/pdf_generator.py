"""
PDF Report Generation Module.

This module handles the generation of detailed PDF reports from repository analysis data.
Features include:
- Individual repository reports with metrics and visualizations
- Summary reports comparing multiple repositories
- Historical trend analysis and visualization
- Customized tables and charts for different metrics

Uses ReportLab for PDF generation and handles both tabular data and graphical elements.
"""

from typing import Dict, List
import os
import matplotlib.pyplot as plt

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)

from config import logger
from analyzers.models import RepositoryMetrics, PullRequestType
from visualization.plotter import RepositoryPlotter


class PDFReportGenerator:
    """
    Generates formatted PDF reports from repository analysis results.

    This class handles the creation of both individual repository reports
    and comparative summary reports, including metrics tables and visualizations.

    Attributes:
        styles (getSampleStyleSheet): ReportLab styles for document formatting.
        plotter (RepositoryPlotter): Instance for creating data visualizations.
    """

    def __init__(self, plotter: RepositoryPlotter):
        """Initialize the PDF generator with visualization capabilities.

        Args:
            plotter (RepositoryPlotter): Instance for creating data visualizations.
        """
        self.styles = getSampleStyleSheet()
        self.plotter = plotter

    def _create_metrics_table(self, metrics: RepositoryMetrics) -> Table:
        """Create a formatted table showing basic repository metrics.

        Args:
            metrics (RepositoryMetrics): Repository metrics to display.

        Returns:
            Table: Formatted ReportLab table with basic metrics.
        """
        data = [
            ["Metric", "Value"],
            ["Total Pull Requests", metrics.total_prs_count],
            ["Open Pull Requests", metrics.open_prs_count],
            ["Closed Pull Requests", metrics.closed_prs_count],
            ["Total Issues", metrics.total_issues_count],
            ["Open Issues", metrics.open_issues_count],
            ["Contributors", metrics.contributors_count],
            ["Analysis Date", metrics.analysis_date.strftime("%Y-%m-%d %H:%M:%S")],
        ]

        table = Table(data, colWidths=[3 * inch, 2 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        return table

    def _create_interval_metrics_table(
        self, metrics: RepositoryMetrics, intervals: List[str], pr_types: List[str]
    ) -> Table:
        """Create a formatted table showing interval-based PR metrics by type.

        Args:
            metrics (RepositoryMetrics): Repository metrics containing interval data.

        Returns:
            Table: Formatted ReportLab table with interval and PR type metrics.
        """
        # Create headers with intervals
        headers = ["PR Type"] + [f"Last {interval} days" for interval in intervals]
        subheaders = ["..."] + ["Open | Closed"] * len(intervals)

        data = [headers, subheaders]

        # Add data for each PR type
        for pr_type in pr_types:
            row = [pr_type.capitalize()]
            for interval in intervals:
                pr_metrics = metrics.pr_interval_metrics[interval]
                open_count = pr_metrics.open.get(pr_type, 0)
                closed_count = pr_metrics.closed.get(pr_type, 0)
                row.append(f"{open_count} | {closed_count}")
            data.append(row)

        # Add contributors row
        contributors_row = ["Contributors"]
        for interval in intervals:
            contributors_row.append(
                str(metrics.pr_interval_metrics[interval].contributors_count)
            )
        data.append(contributors_row)

        # Calculate column widths: 2 inch for PR type, 1.5 inch for each interval
        col_widths = [2 * inch] + [1.5 * inch] * len(intervals)

        table = Table(data, colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    # Header styling
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, -1),
                        8,
                    ),  # Smaller font to fit all columns
                    # Subheader styling
                    ("BACKGROUND", (1, 1), (-1, 1), colors.lightgrey),
                    ("TEXTCOLOR", (1, 1), (-1, 1), colors.black),
                    ("FONTSIZE", (0, 1), (-1, 1), 7),  # Even smaller font for subheader
                    # Data rows styling
                    ("BACKGROUND", (0, 2), (-1, -2), colors.lightblue),  # PR type rows
                    ("BACKGROUND", (0, -1), (-1, -1), colors.beige),  # Contributors row
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    # Alternating colors for PR type rows
                    *[
                        ("BACKGROUND", (0, i), (-1, i), colors.paleturquoise)
                        for i in range(3, len(pr_types) + 2, 2)
                    ],
                    # Span first row headers
                    ("SPAN", (0, 0), (0, 1)),  # Span PR Type column
                ]
            )
        )
        return table

    def safe_repo_name(self, repo_name: str) -> str:
        """Convert a repository name to a safe filename.

        Args:
            repo_name (str): Original repository name.

        Returns:
            str: Safe filename for the repository.
        """
        return repo_name.replace("/", "_").replace("\\", "_")

    def generate_report(
        self,
        metrics: List[Dict[str, RepositoryMetrics]],
        historical_data: Dict[str, List[RepositoryMetrics]],
        output_path: str,
        plots_dir: str,
    ) -> None:
        """Generate a comprehensive PDF report for a single repository.

        Args:
            metrics (List[Dict[str, RepositoryMetrics]]): Analysis results for the repository.
            historical_data (Dict[str, List[RepositoryMetrics]]): Historical analysis data for the repository.
            output_path (str): Path where the PDF report should be saved.
            plots_dir (str): Path where the plots should be saved.

        Raises:
            Exception: If report generation fails.
        """
        try:
            for repo_name, repo_metrics in metrics.items():
                logger.info(
                    {
                        "message": "Starting PDF report generation",
                        "repository": repo_name,
                        "output_path": output_path,
                    }
                )
                safe_repo_name = self.safe_repo_name(repo_name)
                doc = SimpleDocTemplate(
                    f"{output_path}/{safe_repo_name}_{repo_metrics.analysis_date.strftime('%Y-%m-%d')}.pdf",
                    pagesize=letter,
                )
                elements = []

                # Title
                elements.extend(
                    [
                        Paragraph(
                            f"GitHub Repository Analysis: {repo_name}",
                            self.styles["Heading1"],
                        ),
                        Spacer(1, 20),
                    ]
                )

                # Basic Metrics
                elements.extend(
                    [
                        Paragraph("Repository Metrics", self.styles["Heading2"]),
                        Spacer(1, 10),
                        self._create_metrics_table(repo_metrics),
                        Spacer(1, 30),
                    ]
                )

                # Interval Metrics
                pr_types = [pr_type.value for pr_type in PullRequestType]
                intervals = list(repo_metrics.pr_interval_metrics.keys())
                elements.extend(
                    [
                        Paragraph("Interval Analysis", self.styles["Heading2"]),
                        Spacer(1, 10),
                        self._create_interval_metrics_table(
                            repo_metrics, intervals, pr_types
                        ),
                        Spacer(1, 30),
                    ]
                )

                # Top Contributors
                elements.extend(
                    [
                        Paragraph("Top Contributors", self.styles["Heading2"]),
                        Spacer(1, 10),
                        Paragraph(
                            ", ".join(repo_metrics.top_contributors[:5]),
                            self.styles["Normal"],
                        ),
                        Spacer(1, 30),
                    ]
                )

                # Historical PR Type Trends
                elements.extend(
                    [
                        Paragraph("Historical PR Type Trends", self.styles["Heading2"]),
                        Spacer(1, 10),
                    ]
                )

                trend_plots = self.plotter.create_pr_type_trends_plots(
                    historical_data[repo_name],
                    intervals,
                    pr_types,
                )

                for interval, fig in trend_plots.items():
                    img_filename = f"{safe_repo_name}_pr_trends_{interval}_{repo_metrics.analysis_date.strftime('%Y-%m-%d')}.png"
                    plot_path = os.path.join(plots_dir, img_filename)
                    fig.savefig(plot_path, format="png", dpi=300, bbox_inches="tight")
                    plt.close(fig)

                    # Add plot to PDF
                    elements.extend(
                        [
                            Paragraph(
                                f"PR Type Trends - Last {interval} Days",
                                self.styles["Heading3"],
                            ),
                            Spacer(1, 10),
                            Image(plot_path, width=7 * inch, height=7 * inch),
                            Spacer(1, 20),
                        ]
                    )

                doc.build(elements)
                logger.info(
                    {
                        "message": "PDF report generated successfully",
                        "output_path": output_path,
                    }
                )

        except Exception as e:
            logger.error(
                {
                    "message": "PDF report generation failed",
                    "error": str(e),
                    "output_path": output_path,
                }
            )
            raise

    def generate_summary_report(
        self, results: Dict[str, RepositoryMetrics], output_path: str
    ) -> None:
        """Generate a summary report comparing multiple repositories.

        Args:
            results (Dict[str, RepositoryMetrics]): Collection of repository metrics.
            output_path (str): Path where the PDF report should be saved.

        Raises:
            Exception: If report generation fails.
        """
        try:
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []

            # Title
            elements.extend(
                [
                    Paragraph(
                        "GitHub Repositories Analysis Summary", self.styles["Heading1"]
                    ),
                    Spacer(1, 20),
                ]
            )

            # Comparison table
            data = [["Metric"] + list(results.keys())]
            metrics_to_compare = [
                ("Total PRs", "total_prs_count"),
                ("Open PRs", "open_prs_count"),
                ("Closed PRs", "closed_prs_count"),
                ("Total Issues", "total_issues_count"),
                ("Open Issues", "open_issues_count"),
                ("Contributors", "contributors_count"),
            ]

            for metric_name, metric_attr in metrics_to_compare:
                row = [metric_name]
                for metrics in results.values():
                    row.append(getattr(metrics, metric_attr))
                data.append(row)

            table = Table(data)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            elements.append(table)

            doc.build(elements)
            logger.info(
                {
                    "message": "Summary report generated successfully",
                    "output_path": output_path,
                }
            )

        except Exception as e:
            logger.error(
                {
                    "message": "Summary report generation failed",
                    "error": str(e),
                    "output_path": output_path,
                }
            )
            raise
