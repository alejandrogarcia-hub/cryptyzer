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
from typing import List, Dict
import asyncio

from github.RateLimit import RateLimit
import pandas as pd

from config import logger
from miners.github_miner import RepositoryData
from analyzers.models import (
    PullRequestType,
    RepositoryMetrics,
    PRMetrics,
)
from analyzers.plugins.category_analyzer import CategoryAnalyzerPlugin


class GitHubAnalyzer:
    """
    GitHub repository analyzer with rate limiting and error handling.

    This class provides methods for analyzing GitHub repositories,
    including PR analysis, branch activity tracking, and issue metrics.
    It handles GitHub API rate limiting and provides detailed logging.

    """

    def __init__(self, intervals: List[int], category_analyzer: CategoryAnalyzerPlugin):
        _now = datetime.now(timezone.utc)
        self.timeframes = {
            str(interval): _now - timedelta(days=interval) for interval in intervals
        }
        self.category_analyzer = category_analyzer
        self.semaphore = asyncio.Semaphore(10)

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

    async def _classify_batch_prs(
        self, prs_df: pd.DataFrame, feature_labels: List[str]
    ) -> Dict[str, str]:
        """
        Classify all PRs asynchronously using batch processing.

        Args:
            prs_df (pd.DataFrame): DataFrame containing PR data
            feature_labels (List[str]): Available PR type labels

        Returns:
            Dict[str, str]: Dictionary mapping PR numbers to their types
        """

        # Prepare PR data for batch processing
        prs_data = []
        for i, row in prs_df.iterrows():
            prs_data.append(
                {
                    "row": i,
                    "pr_number": row["pr_number"],
                    "title": row["title"],
                    "body": row["body"] or "",
                    "labels": [label for label in row["labels"]],
                }
            )

        # Use batch processing for classification
        results = await self.category_analyzer.categorize_batch(
            prs_data, feature_labels
        )

        return results

    async def _classify_all_prs(
        self, prs_df: pd.DataFrame, feature_labels: List[str]
    ) -> Dict[str, str]:
        """
        Classify all PRs asynchronously using batch processing.

        Args:
            prs_df (pd.DataFrame): DataFrame containing PR data

        Returns:
            Dict[str, str]: Dictionary mapping PR numbers to their types
        """

        tasks = [
            {
                "pr_number": row["pr_number"],
                "title": row["title"],
                "body": row["body"] or "",
                "labels": [label for label in row["labels"]],
            }
            for _, row in prs_df.iterrows()
        ]

        pr_types = await self.category_analyzer.categorize_all(tasks, feature_labels)
        return pr_types

    async def _classify_prs(
        self, prs_df: pd.DataFrame, feature_labels: List[str]
    ) -> Dict[str, str]:
        """
        Classify all PRs asynchronously using batch processing.

        Args:
            prs_df (pd.DataFrame): DataFrame containing PR data

        Returns:
            Dict[str, str]: Dictionary mapping PR numbers to their types
        """

        async def limited_categorize(pr_info, feature_labels):
            async with self.semaphore:
                # This ensures no more than 10 categorize calls run concurrently
                return await self.category_analyzer.categorize(pr_info, feature_labels)

        tasks = []
        for _, row in prs_df.iterrows():
            tasks.append(
                limited_categorize(
                    {
                        "pr_number": row["pr_number"],
                        "title": row["title"],
                        "body": row["body"] or "",
                        "labels": [label for label in row["labels"]],
                    },
                    feature_labels,
                )
            )

        pr_types = await asyncio.gather(*tasks)
        return pr_types

    async def analyze_repository(self, repo_data: RepositoryData) -> RepositoryMetrics:
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
            total_issues = issues_df.shape[0]
            open_issues = len([i for i in repo_data.issues if i.state == "open"])

            if total_prs_count == 0:
                logger.warning(
                    {
                        "message": "No PRs found for repository",
                        "repository": repo_data.repository_name,
                    }
                )
                return RepositoryMetrics(
                    repository_name=repo_data.repository_name,
                    total_prs_count=0,
                    open_prs_count=0,
                    closed_prs_count=0,
                    total_issues_count=total_issues,
                    open_issues_count=len(
                        [i for i in repo_data.issues if i.state == "open"]
                    ),
                    pr_interval_metrics={},
                    top_contributors=[],
                    contributors_count=0,
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

                # Classify all PRs asynchronously
                feature_labels = [pr_type.value for pr_type in PullRequestType]
                pr_types = await self._classify_all_prs(prs_df, feature_labels)
                df = pd.DataFrame(pr_types, columns=["pr_number", "pr_type"])
                df["pr_number"] = df["pr_number"].astype(int)
                prs_df = prs_df.merge(df, on="pr_number")
                del df

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
