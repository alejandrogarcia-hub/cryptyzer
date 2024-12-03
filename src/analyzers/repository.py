from dataclasses import dataclass, asdict
from datetime import datetime
import json
from typing import Dict, Any

from github import Github

from config import settings, logger


@dataclass
class RepositoryMetrics:
    """Data class to store repository metrics."""

    total_prs: int
    open_prs: int
    merged_prs: int
    active_branches: int
    total_issues: int
    open_issues: int
    repository_name: str
    analysis_date: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary with serializable values."""
        data = asdict(self)
        data["analysis_date"] = self.analysis_date.isoformat()
        return data


class GitHubAnalyzer:
    """Main analyzer class for GitHub repositories."""

    def __init__(self, github_token: str = None):
        """
        Initialize GitHub analyzer.

        Args:
            github_token (str, optional): GitHub API token. If not provided,
                                        will use token from environment variables.
        """
        self.github = Github(github_token or settings.github_token)

    async def analyze_repository(self, repo_name: str) -> RepositoryMetrics:
        """Analyze a GitHub repository and collect metrics."""
        try:
            logger.info(
                json.dumps(
                    {"message": "Starting repository analysis", "repository": repo_name}
                )
            )

            repo = self.github.get_repo(repo_name)

            # Collect metrics
            total_prs = repo.get_pulls(state="all").totalCount
            open_prs = repo.get_pulls(state="open").totalCount
            merged_prs = repo.get_pulls(state="closed", sort="updated").totalCount

            branches = list(repo.get_branches())
            active_branches = len(branches)

            total_issues = repo.get_issues(state="all").totalCount
            open_issues = repo.get_issues(state="open").totalCount

            metrics = RepositoryMetrics(
                total_prs=total_prs,
                open_prs=open_prs,
                merged_prs=merged_prs,
                active_branches=active_branches,
                total_issues=total_issues,
                open_issues=open_issues,
                repository_name=repo_name,
                analysis_date=datetime.now(),
            )

            logger.info(
                json.dumps(
                    {
                        "message": "Repository analysis completed",
                        "repository": repo_name,
                        "metrics": metrics.to_dict(),
                    }
                )
            )

            return metrics

        except Exception as e:
            logger.error(
                json.dumps(
                    {
                        "message": "Repository analysis failed",
                        "repository": repo_name,
                        "error": str(e),
                    }
                )
            )
            raise
