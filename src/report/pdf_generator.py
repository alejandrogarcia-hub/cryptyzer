from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from analyzers.repository import RepositoryMetrics
from config import logger


class PDFReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()

    def _create_pr_types_table(self, metrics: RepositoryMetrics):
        data = [["PR Type", "Open", "Merged", "Total"]]
        for pr_type in metrics.pr_types:
            data.append([
                pr_type.type.value.title(),
                pr_type.open_count,
                pr_type.merged_count,
                pr_type.total_count
            ])

        table = Table(data, colWidths=[2*inch, inch, inch, inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 14),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.lightblue),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))
        return table

    def _create_branch_activity_table(self, metrics: RepositoryMetrics):
        # Create header row
        data = [["Branch Type", "Timeframe", "Opened", "Closed"]]
        
        # Add data rows for each branch type
        for activity in metrics.branch_activity:
            # Add rows for each timeframe
            data.extend([
                [activity.type.value.title(), "Last 7 Days", 
                 activity.opened.last_7_days, activity.closed.last_7_days],
                ["", "Last 30 Days", 
                 activity.opened.last_30_days, activity.closed.last_30_days],
                ["", "Last 60 Days", 
                 activity.opened.last_60_days, activity.closed.last_60_days]
            ])

        table = Table(data, colWidths=[1.5*inch, 1.5*inch, inch, inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            # Merge cells for branch types
            *[("SPAN", (0, i*3+1), (0, i*3+3)) 
              for i in range(len(metrics.branch_activity))],
            ("BACKGROUND", (0, 1), (-1, -1), colors.lightgreen),
        ]))
        return table

    def generate_report(self, metrics: RepositoryMetrics, output_path: str) -> None:
        try:
            logger.info({
                "message": "Starting PDF report generation",
                "repository": metrics.repository_name,
                "output_path": output_path,
            })

            doc = SimpleDocTemplate(output_path, pagesize=letter)
            elements = []

            # Title
            elements.extend([
                Paragraph(f"GitHub Repository Analysis: {metrics.repository_name}", 
                         self.styles["Heading1"]),
                Spacer(1, 20)
            ])

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
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table)

            # PR Types section
            elements.extend([
                Spacer(1, 30),
                Paragraph("Pull Request Types", self.styles["Heading2"]),
                Spacer(1, 10),
                self._create_pr_types_table(metrics)
            ])

            # Branch Activity section
            elements.extend([
                Spacer(1, 30),
                Paragraph("Branch Activity Analysis", self.styles["Heading2"]),
                Spacer(1, 10),
                self._create_branch_activity_table(metrics)
            ])

            doc.build(elements)
            logger.info({"message": "PDF report generated successfully", 
                        "output_path": output_path})

        except Exception as e:
            logger.error({
                "message": "PDF report generation failed",
                "error": str(e),
                "output_path": output_path,
            })
            raise