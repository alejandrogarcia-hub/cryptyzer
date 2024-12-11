"""
GitHub Repository Data Mining Module.

This module handles the extraction and storage of raw GitHub repository data.
It focuses on efficient data collection and persistence while maintaining
type safety through Pydantic models.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List

from github import Github
from github.PullRequest import PullRequest
from github.Issue import Issue
from github.RateLimit import RateLimit
from github.Repository import Repository

from config import settings, logger
from miners.base import RepositoryMiner
from miners.models import RepositoryData, RepositoryPRData, RepositoryIssueData


class GitHubMiner(RepositoryMiner):
    """
    GitHubMiner is responsible for mining data from GitHub repositories.
    It extracts pull requests and issues, transforming them into Pydantic models.
    """

    def __init__(
        self,
        github_token: Optional[str] = None,
        cutoff_days: int = 60,
    ):
        """Initialize GitHub miner with authentication and configuration.

        Args:
            github_token (Optional[str]): GitHub API token for authentication.
            cutoff_days (int): Number of days to consider for mining data.
        """
        self.github = Github(github_token or settings.github_token.get_secret_value())
        self.cutoff_days = cutoff_days

    def _check_rate_limit(self, check_name: str = None) -> None:
        """
        Check and log the GitHub API rate limit status.

        Args:
            check_name (Optional[str]): Identifier for the rate limit check point.

        Raises:
            Exception: Raised when the rate limit is exhausted, indicating time until reset.
        """
        rate_limit: RateLimit = self.github.get_rate_limit().core
        remaining = rate_limit.remaining
        reset_time = rate_limit.reset.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        # Log current rate limit status
        logger.info(
            {
                "message": f"{check_name} API rate limit status",
                "remaining_points": remaining,
                "total_points": rate_limit.limit,
                "reset_time": reset_time.isoformat(),
                "minutes_to_reset": (reset_time - now).total_seconds() / 60,
            }
        )

        # If less than 10% of rate limit remains, log a warning
        if remaining < (rate_limit.limit * 0.1) and remaining > 0:
            logger.warning(
                {
                    "message": "GitHub API rate limit running low",
                    "remaining_points": remaining,
                    "reset_time": reset_time.isoformat(),
                }
            )

        # If rate limit is exhausted, log critical and wait for reset
        if remaining == 0:
            wait_time = (reset_time - now).total_seconds()
            logger.critical(
                {
                    "message": "GitHub API rate limit exhausted",
                    "reset_time": reset_time.isoformat(),
                    "wait_time_seconds": wait_time,
                }
            )
            raise Exception(
                f"GitHub API rate limit exhausted. Resets in {wait_time/60:.1f} minutes"
            )

    def _get_pr_data(
        self, pr: PullRequest, assignees: List[str], reviewers: List[str]
    ) -> RepositoryPRData:
        """Convert a GitHub PullRequest object to a Pydantic model.

        Args:
            pr (PullRequest): The GitHub PullRequest object.
            assignees (List[str]): List of assignee usernames.
            reviewers (List[str]): List of reviewer usernames.

        Returns:
            RepositoryPRData: A Pydantic model representing the PR data.
        """
        return RepositoryPRData(
            pr_number=pr.number,
            title=pr.title,
            body=pr.body,
            state=pr.state,
            created_at=pr.created_at,
            updated_at=pr.updated_at,
            merged_at=pr.merged_at,
            closed_at=pr.closed_at,
            head_ref=pr.head.ref,
            author=pr.user.login,
            assignees=assignees,
            reviewers=reviewers,
            labels=[label.name for label in pr.labels],
            issue_url=pr.issue_url,
        )

    def _get_issue_data(
        self,
        issue: Issue,
        assignees: List[str],
    ) -> RepositoryIssueData:
        """Convert a GitHub Issue object to a Pydantic model.

        Args:
            issue (Issue): The GitHub Issue object.
            assignees (List[str]): List of assignee usernames.

        Returns:
            RepositoryIssueData: A Pydantic model representing the issue data.
        """
        return RepositoryIssueData(
            issue_number=issue.number,
            title=issue.title,
            state=issue.state,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            closed_at=issue.closed_at,
            author=issue.user.login,
            assignees=assignees,
            url=issue.pull_request.raw_data["url"] if issue.pull_request else None,
            labels=[label.name for label in issue.labels],
        )

    async def mine_repository(self, repo_name: str) -> RepositoryData:
        """
        Extract and transform data from a specified GitHub repository.

        Args:
            repo_name (str): The full name of the repository (e.g., 'owner/repo').

        Returns:
            RepositoryData: A Pydantic model containing the mined repository data.

        Raises:
            Exception: Raised if the mining process fails.
        """
        logger.info({"message": "Starting repository mining", "repository": repo_name})

        try:
            repo: Repository = self.github.get_repo(repo_name)
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.cutoff_days)

            self._check_rate_limit("Repository mining")

            # Collect PRs
            prs = repo.get_pulls(state="all", sort="updated", direction="desc")
            prs_list = []
            for pr in prs:
                if pr.updated_at < cutoff_date:
                    break
                assignees = list(set([assignee.login for assignee in pr.assignees]))
                reviewers = list(
                    set([review.user.login for review in pr.get_reviews()])
                )
                prs_list.append(self._get_pr_data(pr, assignees, reviewers))

            self._check_rate_limit("PR mining")
            # Collect Issues
            issues = repo.get_issues(state="all", sort="updated", direction="desc")
            issues_list = []
            for issue in issues:
                if issue.updated_at < cutoff_date:
                    break
                assignees = list(set([assignee.login for assignee in issue.assignees]))
                issues_list.append(self._get_issue_data(issue, assignees))

            del issues, prs
            self._check_rate_limit("Issue mining")

            return RepositoryData(
                repository_name=repo_name, pull_requests=prs_list, issues=issues_list
            )

        except Exception as e:
            logger.error(
                {
                    "message": "Repository mining failed",
                    "repository": repo_name,
                    "error": str(e),
                }
            )
            raise
