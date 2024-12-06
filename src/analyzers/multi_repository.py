"""
Multi-Repository Analysis Module.

Provides functionality for analyzing multiple GitHub repositories in parallel
and generating both individual and summary reports. This module coordinates
the analysis process and report generation for configured repositories.

The module handles:
- Parallel repository analysis
- Individual PDF report generation
- Summary report generation across all repositories
- Error handling and logging
"""

from datetime import datetime
from typing import Dict

from config import settings, logger
from analyzers.repository import GitHubAnalyzer, RepositoryMetrics
from report.pdf_generator import PDFReportGenerator


class MultiRepositoryAnalyzer:
    """
    Analyzer for processing multiple GitHub repositories.

    This class coordinates the analysis of multiple repositories,
    handles report generation, and manages the overall analysis workflow.

    Attributes:
        analyzer (GitHubAnalyzer): Instance for analyzing individual repositories
        pdf_generator (PDFReportGenerator): Instance for generating PDF reports
    """

    def __init__(self):
        """
        Initialize the multi-repository analyzer.

        Sets up the GitHub analyzer with authentication and
        initializes the PDF report generator.
        """
        self.analyzer = GitHubAnalyzer(settings.github_token.get_secret_value())
        self.pdf_generator = PDFReportGenerator()

    async def analyze_repositories(self) -> Dict[str, RepositoryMetrics]:
        """
        Analyze all configured repositories and generate individual reports.

        Processes each repository configured in settings, generates individual
        PDF reports, and collects analysis results.

        Returns:
            Dict[str, RepositoryMetrics]: Mapping of repository names to their
                analysis results.

        Note:
            If analysis fails for a repository, it logs the error and continues
            with remaining repositories.
        """
        results = {}
        for repo_url in settings.repository_urls:
            try:
                # Extract repository name from URL
                repo_name = str(repo_url).rstrip(".git").split("/")[-2:]
                repo_name = "/".join(repo_name)

                logger.info(
                    {"message": "Analyzing repository", "repository": repo_name}
                )

                # Analyze repository and generate report
                metrics = await self.analyzer.analyze_repository(repo_name)
                results[repo_name] = metrics

                # Generate individual repository report
                report_path = self._get_report_path(repo_name)
                self.pdf_generator.generate_report(metrics, report_path)

            except Exception as e:
                logger.error(
                    {
                        "message": "Failed to analyze repository",
                        "repository": repo_name,
                        "error": str(e),
                    }
                )

        return results

    def _get_report_path(self, repo_name: str, is_summary: bool = False) -> str:
        """
        Generate the file path for a repository report.

        Args:
            repo_name (str): Name of the repository
            is_summary (bool, optional): Whether this is a summary report.
                Defaults to False.

        Returns:
            str: Full path for the report file

        Note:
            Report filenames include timestamps to prevent overwrites
            and maintain history.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"summary_{timestamp}.pdf"
            if is_summary
            else f"{repo_name.replace('/', '_')}_{timestamp}.pdf"
        )
        return f"{settings.report_output_dir}/{filename}"

    def generate_summary_report(self, results: Dict[str, RepositoryMetrics]) -> str:
        """
        Generate a summary report across all analyzed repositories.

        Creates a comprehensive report comparing metrics across all
        successfully analyzed repositories.

        Args:
            results (Dict[str, RepositoryMetrics]): Collection of repository
                analysis results

        Returns:
            str: Path to the generated summary report

        Raises:
            Exception: If report generation fails

        Note:
            The summary report includes comparative analytics and trends
            across all repositories.
        """
        try:
            report_path = self._get_report_path("", is_summary=True)
            self.pdf_generator.generate_summary_report(results, report_path)
            return report_path
        except Exception as e:
            logger.error(
                {"message": "Failed to generate summary report", "error": str(e)}
            )
            raise
