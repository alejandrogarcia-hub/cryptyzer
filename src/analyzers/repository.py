"""
GitHub Repository Analysis Module.

Provides comprehensive analysis of GitHub repositories including metrics for:
- Pull request activity and categorization
- Branch activity patterns
- Issue tracking and management
- Repository health indicators

The module handles GitHub API rate limiting and provides detailed logging
of all analysis operations.
"""

from datetime import datetime, timedelta, timezone
from typing import List

from github.RateLimit import RateLimit
import pandas as pd

from config import logger
from miners.github_miner import RepositoryData
from analyzers.models import (
    PullRequestType,
    RepositoryMetrics,
    PRMetrics,
)


class GitHubAnalyzer:
    """
    GitHub repository analyzer with rate limiting and error handling.

    This class provides methods for analyzing GitHub repositories,
    including PR analysis, branch activity tracking, and issue metrics.
    It handles GitHub API rate limiting and provides detailed logging.

    """

    def __init__(self, intervals: List[int]):
        _now = datetime.now(timezone.utc)
        self.timeframes = {
            str(interval): _now - timedelta(days=interval) for interval in intervals
        }

    def _check_rate_limit(self, check_name: str = None) -> None:
        """
        Check GitHub API rate limit status and handle limits.

        Args:
            check_name (str, optional): Name of the check point for logging.

        Raises:
            Exception: When rate limit is exhausted, with time until reset.
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

    def _work_activity_type(
        self, title: str, body: str, labels: List[str]
    ) -> PullRequestType:
        """
        Categorize pull request type based on metadata.

        Args:
            title (str): PR title
            body (str): PR description
            labels (List[str]): PR labels

        Returns:
            PullRequestType: Classified pull request type based on content and labels.
        """
        title_lower = title.lower()
        combined_text = f"{title_lower} {body.lower() if body else ''}"
        labels_lower = [label.lower() for label in labels]

        result = None
        # Check labels first
        for label in labels_lower:
            if "feature" in label or "enhancement" in label:
                result = PullRequestType.FEATURE
            elif "bug" in label or "bugfix" in label:
                result = PullRequestType.BUGFIX
            elif "hotfix" in label or "critical" in label or "urgent" in label:
                result = PullRequestType.HOTFIX
            elif "test" in label or "testing" in label:
                result = PullRequestType.TEST
            elif "issue" in label:
                result = PullRequestType.ISSUE

        # Check title and body
        if any(
            keyword in combined_text for keyword in ["feature", "feat", "enhancement"]
        ):
            result = PullRequestType.FEATURE
        elif any(keyword in combined_text for keyword in ["fix", "bug", "issue #"]):
            result = PullRequestType.BUGFIX
        elif any(
            keyword in combined_text for keyword in ["hotfix", "critical", "urgent"]
        ):
            result = PullRequestType.HOTFIX
        elif any(keyword in combined_text for keyword in ["test", "testing"]):
            result = PullRequestType.TEST
        elif any(
            keyword in combined_text
            for keyword in ["refactor", "refactoring", "refact"]
        ):
            result = PullRequestType.REFACTOR
        elif "issue" in combined_text or "#" in title_lower:
            result = PullRequestType.ISSUE

        return result.value if result else PullRequestType.OTHER.value

    async def analyze_repository(self, repo_data: RepositoryData) -> None:
        """
        Perform comprehensive analysis of a GitHub repository.

        Analyzes repository metrics including:
        - Pull request statistics and categorization
        - Branch activity patterns
        - Issue tracking metrics
        - Overall repository health indicators

        Args:
            repo_data (RepositoryData): Repository data

        Returns:
            RepositoryMetrics: Comprehensive analysis results

        Raises:
            Exception: If analysis fails or rate limit is exceeded
        """
        logger.info(
            {
                "message": "Starting repository analysis",
                "repository": repo_data.repository_name,
            }
        )
        try:
            prs_df = pd.DataFrame([pr.model_dump() for pr in repo_data.pull_requests])
            issues_df = pd.DataFrame([issue.model_dump() for issue in repo_data.issues])

            total_prs_count = prs_df.shape[0]
            if total_prs_count == 0:
                logger.warning(
                    {
                        "message": "No PRs found for repository",
                        "repository": repo_data.repository_name,
                    }
                )
                total_prs_count = 0
                open_prs_count = 0
                pr_interval_metrics = {}
                top_contributors = []
                all_contributors = set()

            total_issues = issues_df.shape[0]
            open_issues = (
                issues_df[issues_df["state"] == "open"].shape[0]
                if total_issues > 0
                else 0
            )

            if total_prs_count > 0:
                open_prs_count = prs_df[prs_df["state"] == "open"].shape[0]

                # Calculate contributor activity
                all_contributors = set()
                contributor_activity = {}

                # Count activity for each contributor (both as reviewer and assignee)
                for _, pr in prs_df.iterrows():
                    # Add assignees
                    for assignee in pr["assignees"]:
                        all_contributors.add(assignee)
                        contributor_activity[assignee] = (
                            contributor_activity.get(assignee, 0) + 1
                        )
                    # Add reviewers
                    for reviewer in pr["reviewers"]:
                        all_contributors.add(reviewer)
                        contributor_activity[reviewer] = (
                            contributor_activity.get(reviewer, 0) + 1
                        )

                # Convert to pandas Series for easy top percentage calculation
                activity_series = pd.Series(contributor_activity)
                # Get top 20% of contributors, minimum 1
                top_n = max(1, int(len(activity_series) * 0.2))
                top_contributors = activity_series.nlargest(top_n).index.tolist()

                # add a column to the prs with the pr category type
                prs_df["pr_type"] = prs_df.apply(
                    lambda row: self._work_activity_type(
                        row["title"],
                        row["body"] or "",
                        [label for label in row["labels"]],
                    ),
                    axis=1,
                )

                # get the number for each self.timeframes
                for interval, interval_date in self.timeframes.items():
                    prs_df[interval] = prs_df["updated_at"] >= interval_date

                # get counts for each pr_type, state, and interval
                pr_interval_metrics = {}
                for interval, _ in self.timeframes.items():
                    d = (
                        prs_df[prs_df[interval]]
                        .groupby(["pr_type", "state", interval])
                        .size()
                        .unstack(fill_value=0)
                        .to_dict()
                    )

                    if len(d) == 0:
                        logger.warning(
                            {
                                "message": "No PRs found for interval",
                                "interval": interval,
                            }
                        )
                        pr_interval_metrics[interval] = PRMetrics(
                            open={}, closed={}, contributors_count=0
                        )
                        continue

                    d = d[True]

                    # d has a key Tuple[str, str] and value int, we need to convert it to a dict with str keys and int values.
                    # however, one key is of type (bugfix, open) and might be another key of type (bugfix, closed)
                    # the result shall be {"bugfix": {"open": 1, "closed": 1}}
                    counts = {}
                    for key, value in d.items():
                        if key[1] not in counts:
                            counts[key[1]] = {}

                        counts[key[1]][key[0]] = value

                    # contributors_count is the number of unique assignees and reviewers
                    counts["contributors_count"] = len(
                        set(prs_df[prs_df[interval]]["assignees"].explode().unique())
                        | set(prs_df[prs_df[interval]]["reviewers"].explode().unique())
                    )

                    pr_interval_metrics[interval] = PRMetrics(
                        open=counts["open"] if "open" in counts else {},
                        closed=counts["closed"] if "closed" in counts else {},
                        contributors_count=counts["contributors_count"],
                    )

            logger.info({"message": "creating metrics object"})
            metrics = RepositoryMetrics(
                repository_name=repo_data.repository_name,
                total_prs_count=total_prs_count,
                open_prs_count=open_prs_count,
                closed_prs_count=total_prs_count - open_prs_count,
                total_issues_count=total_issues,
                open_issues_count=open_issues,
                pr_interval_metrics=pr_interval_metrics,
                top_contributors=top_contributors,
                contributors_count=len(all_contributors),
            )

            logger.info(
                {
                    "message": "Repository analysis completed",
                    "repository": repo_data.repository_name,
                }
            )

            return metrics

        except Exception as e:
            logger.error(
                {
                    "message": "Repository analysis failed",
                    "repository": repo_data.repository_name,
                    "error": str(e),
                }
            )
            raise e
