from datetime import datetime
from typing import List, Dict
import asyncio

from config import settings, logger
from analyzers.repository import GitHubAnalyzer, RepositoryMetrics
from report.pdf_generator import PDFReportGenerator


class MultiRepositoryAnalyzer:
    """Analyzer for multiple GitHub repositories."""

    def __init__(self):
        self.analyzer = GitHubAnalyzer(settings.github_token.get_secret_value())
        self.pdf_generator = PDFReportGenerator()

    async def analyze_repositories(self) -> Dict[str, RepositoryMetrics]:
        """Analyze all configured repositories."""
        results = {}
        for repo_url in settings.repository_urls:
            try:
                repo_name = str(repo_url).rstrip(".git").split("/")[-2:]
                repo_name = "/".join(repo_name)

                logger.info(
                    {"message": f"Analyzing repository", "repository": repo_name}
                )

                metrics = await self.analyzer.analyze_repository(repo_name)
                results[repo_name] = metrics

                # Generate individual report
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
        """Generate report path for a repository."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"summary_{timestamp}.pdf"
            if is_summary
            else f"{repo_name.replace('/', '_')}_{timestamp}.pdf"
        )
        return f"{settings.report_output_dir}/{filename}"

    def generate_summary_report(self, results: Dict[str, RepositoryMetrics]) -> str:
        """Generate a summary report for all repositories."""
        try:
            report_path = self._get_report_path("", is_summary=True)
            self.pdf_generator.generate_summary_report(results, report_path)
            return report_path
        except Exception as e:
            logger.error(
                {"message": "Failed to generate summary report", "error": str(e)}
            )
            raise
