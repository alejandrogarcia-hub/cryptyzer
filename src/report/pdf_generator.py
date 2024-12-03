from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from analyzers.repository import RepositoryMetrics
from config import logger


class PDFReportGenerator:
    """Generate PDF reports from repository metrics."""

    def __init__(self):
        """Initialize PDF report generator."""
        self.styles = getSampleStyleSheet()

    def generate_report(self, metrics: RepositoryMetrics, output_path: str) -> None:
        """
        Generate a PDF report from repository metrics.

        Args:
            metrics (RepositoryMetrics): Repository metrics to include in report
            output_path (str): Path where PDF should be saved

        Raises:
            IOError: If PDF creation fails
        """
        try:
            logger.info(
                {
                    "message": "Starting PDF report generation",
                    "repository": metrics.repository_name,
                    "output_path": output_path,
                }
            )

            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []

            # Add title
            title = Paragraph(
                f"GitHub Repository Analysis: {metrics.repository_name}",
                self.styles["Heading1"],
            )
            elements.append(title)

            # Create metrics table
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
                        ("FONTSIZE", (0, 0), (-1, 0), 14),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                        ("FONTSIZE", (0, 1), (-1, -1), 12),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )

            elements.append(table)
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
