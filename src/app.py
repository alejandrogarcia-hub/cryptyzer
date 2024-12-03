import asyncio
import os

from config import settings, logger
from analyzers.repository import GitHubAnalyzer
from report.pdf_generator import PDFReportGenerator


async def main():
    """Main function to run the application."""
    logger.info("Initializing GitHub Analyzer ...")
    analyzer = GitHubAnalyzer(settings.github_token.get_secret_value())

    # Analyze repository
    logger.info(f"Analyzing repository {settings.github_repo_url} ...")
    metrics = await analyzer.analyze_repository(settings.github_repo_url)

    # Ensure report directory exists
    os.makedirs(settings.report_output_dir, exist_ok=True)

    # Generate report filename from repository name
    repo_name = settings.github_repo_url.split("/")[-1].replace(".git", "")
    report_path = os.path.join(
        settings.report_output_dir,
        f"{repo_name}_analysis_{metrics.analysis_date.strftime('%Y%m%d_%H%M%S')}.pdf",
    )

    logger.info(f"Generating PDF report at {report_path} ...")
    # Generate PDF report
    generator = PDFReportGenerator()
    generator.generate_report(metrics, report_path)

    logger.info("Analysis completed successfully!")


if __name__ == "__main__":
    logger.info("Starting application ...")
    asyncio.run(main())
