from typing import List, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from analyzers.repository import RepositoryMetrics
from config import logger
from visualization.plotter import RepositoryPlotter
from storage.repository_store import RepositoryStore


class PDFReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.plotter = RepositoryPlotter()
        self.store = RepositoryStore()

    def _create_pr_types_table(self, metrics: RepositoryMetrics):
        data = [["PR Type", "Open", "Merged", "Total"]]
        for pr_type in metrics.pr_types:
            data.append(
                [
                    pr_type.type.value.title(),
                    pr_type.open_count,
                    pr_type.merged_count,
                    pr_type.total_count,
                ]
            )

        table = Table(data, colWidths=[2 * inch, inch, inch, inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.lightblue),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        return table

    def _create_branch_activity_table(self, metrics: RepositoryMetrics):
        # Create header row
        data = [["Branch Type", "Timeframe", "Opened", "Closed"]]

        # Add data rows for each branch type
        for activity in metrics.branch_activity:
            # Add rows for each timeframe
            data.extend(
                [
                    [
                        activity.type.value.title(),
                        "Last 7 Days",
                        activity.opened.last_7_days,
                        activity.closed.last_7_days,
                    ],
                    [
                        "",
                        "Last 30 Days",
                        activity.opened.last_30_days,
                        activity.closed.last_30_days,
                    ],
                    [
                        "",
                        "Last 60 Days",
                        activity.opened.last_60_days,
                        activity.closed.last_60_days,
                    ],
                ]
            )

        table = Table(data, colWidths=[1.5 * inch, 1.5 * inch, inch, inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    # Merge cells for branch types
                    *[
                        ("SPAN", (0, i * 3 + 1), (0, i * 3 + 3))
                        for i in range(len(metrics.branch_activity))
                    ],
                    ("BACKGROUND", (0, 1), (-1, -1), colors.lightgreen),
                ]
            )
        )
        return table

    def _add_plots(self, elements: List, plots: List[str]) -> None:
        """Add plots to the PDF document."""
        for plot_path in plots:
            elements.extend(
                [Spacer(1, 30), Image(plot_path, width=7 * inch, height=4 * inch)]
            )

    def generate_report(self, metrics: RepositoryMetrics, output_path: str) -> None:
        try:
            # Store the analysis results
            self.store.store_analysis(metrics.to_dict())

            # Get historical data
            history = self.store.get_repository_history(metrics.repository_name)

            # Generate plots
            plot_paths = self.plotter.save_plots(history)

            # Generate PDF with plots
            logger.info(
                {
                    "message": "Starting PDF report generation",
                    "repository": metrics.repository_name,
                    "output_path": output_path,
                }
            )

            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []

            # Title
            elements.extend(
                [
                    Paragraph(
                        f"GitHub Repository Analysis: {metrics.repository_name}",
                        self.styles["Heading1"],
                    ),
                    Spacer(1, 20),
                ]
            )

            # Basic metrics
            data = [
                ["Metric", "Value"],
                ["Total Pull Requests", metrics.total_prs],
                ["Open Pull Requests", metrics.open_prs],
                ["Merged Pull Requests", metrics.merged_prs],
                ["Active Branches", metrics.active_branches],
                ["Total Issues", metrics.total_issues],
                ["Open Issues", metrics.open_issues],
                ["Analysis Date", metrics.analysis_date.strftime("%Y-%m-%d %H:%M:%S")],
            ]

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

            # PR Types section
            elements.extend(
                [
                    Spacer(1, 30),
                    Paragraph("Pull Request Types", self.styles["Heading2"]),
                    Spacer(1, 10),
                    self._create_pr_types_table(metrics),
                ]
            )

            # Branch Activity section
            elements.extend(
                [
                    Spacer(1, 30),
                    Paragraph("Branch Activity Analysis", self.styles["Heading2"]),
                    Spacer(1, 10),
                    self._create_branch_activity_table(metrics),
                ]
            )

            # Add plots
            elements.extend(
                [
                    Spacer(1, 30),
                    Paragraph("Historical Analysis", self.styles["Heading1"]),
                    Spacer(1, 20),
                ]
            )
            self._add_plots(elements, plot_paths)

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
        """Generate a summary report comparing all repositories."""
        try:
            logger.info(
                {
                    "message": "Starting summary report generation",
                    "repositories": list(results.keys()),
                    "output_path": output_path,
                }
            )

            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []

            # Add title
            elements.extend(
                [
                    Paragraph(
                        "GitHub Repositories Analysis Summary", self.styles["Heading1"]
                    ),
                    Spacer(1, 20),
                ]
            )

            # Create comparison table
            data = [["Metric"] + list(results.keys())]
            metrics_to_compare = [
                ("Total PRs", "total_prs"),
                ("Open PRs", "open_prs"),
                ("Merged PRs", "merged_prs"),
                ("Active Branches", "active_branches"),
                ("Total Issues", "total_issues"),
                ("Open Issues", "open_issues"),
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

            # Add comparison plots
            elements.extend(
                [
                    Spacer(1, 30),
                    Paragraph("Repository Comparisons", self.styles["Heading1"]),
                    Spacer(1, 20),
                ]
            )

            # Generate and add comparison plots
            plot_paths = self.plotter.create_comparison_plots(results)
            self._add_plots(elements, plot_paths)

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
