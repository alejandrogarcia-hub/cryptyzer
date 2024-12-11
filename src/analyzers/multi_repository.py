"""
Multi-Repository Analysis Module.

This module provides functionality for analyzing multiple GitHub repositories in parallel
and generating both individual and summary reports. It coordinates the analysis process
and report generation for configured repositories, handling:

- Parallel repository analysis
- Individual PDF report generation
- Summary report generation across all repositories
- Error handling and logging
"""

from datetime import datetime
from typing import List, Dict

from config import logger
from analyzers.repository import GitHubAnalyzer
from analyzers.models import RepositoryMetrics
from miners.base import RepositoryMiner
from storage.repository_store import RepositoryStore


class MultiRepositoryAnalyzer:
    """
    Coordinates the analysis of multiple GitHub repositories.

    This class manages the workflow for analyzing multiple repositories,
    generating reports, and storing results. It ensures efficient processing
    and error handling throughout the analysis lifecycle.

    Attributes:
        analyzer (GitHubAnalyzer): Instance for analyzing individual repositories.
        store (RepositoryStore): Instance for storing analysis results.
        miner (RepositoryMiner): Instance for mining repository data.
        repository_urls (List[str]): List of repository URLs to analyze.
    """

    def __init__(
        self,
        repository_store: RepositoryStore,
        analyzer: GitHubAnalyzer,
        miner: RepositoryMiner,
        repository_urls: List[str],
    ):
        """Initialize the multi-repository analyzer.

        Args:
            repository_store (RepositoryStore): Instance for storing analysis results.
            analyzer (GitHubAnalyzer): Instance for analyzing individual repositories.
            miner (RepositoryMiner): Instance for mining repository data.
            repository_urls (List[str]): List of repository URLs to analyze.
        """
        self.analyzer = analyzer
        self.store = repository_store
        self.miner = miner
        self.repository_urls = repository_urls

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
        for repo_url in self.repository_urls:
            try:
                # Extract repository name from URL
                repo_name = str(repo_url).rstrip(".git").split("/")[-2:]
                repo_name = "/".join(repo_name)

                logger.info(
                    {"message": "Analyzing repository", "repository": repo_name}
                )

                # Load repository data
                repo_data = self.store.load_repository_data(repo_name)

                # Skip mining if data exists and is from today
                if (
                    repo_data
                    and repo_data[-1].collection_date.date() == datetime.now().date()
                ):
                    logger.info(
                        {
                            "message": "Repository data already exists for today, skipping mining",
                            "repository": repo_name,
                        }
                    )
                else:
                    repo_data = await self.miner.mine_repository(repo_name)
                    self.store.save_repository_data(repo_data)
                    repo_data = [repo_data]

                # Check if analysis has been done today
                analysis = self.store.load_analysis(repo_name)
                if (
                    analysis
                    and analysis[0].analysis_date.date() == datetime.now().date()
                ):
                    logger.info(
                        {
                            "message": "Repository analysis already exists for today, skipping analysis",
                            "repository": repo_name,
                        }
                    )
                    results[repo_name] = analysis[0]
                    continue

                # Analyze repository and generate report
                repo_metrics = await self.analyzer.analyze_repository(repo_data[0])
                results[repo_name] = repo_metrics
                # Store analysis results for historical tracking
                self.store.store_analysis(repo_metrics.model_dump())

            except Exception as e:
                logger.error(
                    {
                        "message": "Failed to analyze repository",
                        "repository": repo_name,
                        "error": str(e),
                    }
                )

        return results
