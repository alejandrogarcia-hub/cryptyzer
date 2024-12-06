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

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, List

from github import Github
from github.PaginatedList import PaginatedList
from github.RateLimit import RateLimit

from config import settings, logger


class BranchType(Enum):
    """
    Classification of repository branch types.

    Attributes:
        FEATURE: Feature development branches
        BUGFIX: Bug fix branches
        HOTFIX: Critical/urgent fix branches
        REFACTOR: Code refactoring branches
        TEST: Testing branches
        OTHER: Uncategorized branches
    """

    FEATURE = "feature"
    BUGFIX = "bugfix"
    HOTFIX = "hotfix"
    REFACTOR = "refactor"
    TEST = "test"
    OTHER = "other"


class PullRequestType(Enum):
    """
    Classification of pull request types.

    Attributes:
        FEATURE: New feature implementations
        BUGFIX: Bug fixes
        HOTFIX: Critical/urgent fixes
        REFACTOR: Code refactoring
        TEST: Testing changes
        ISSUE: Issue-related changes
        OTHER: Uncategorized changes
    """

    FEATURE = "feature"
    BUGFIX = "bugfix"
    HOTFIX = "hotfix"
    REFACTOR = "refactor"
    TEST = "test"
    ISSUE = "issue"
    OTHER = "other"


@dataclass
class TimeframeMetrics:
    """
    Metrics collected over different time periods.

    Attributes:
        last_7_days (int): Activity count in the last 7 days
        last_30_days (int): Activity count in the last 30 days
        last_60_days (int): Activity count in the last 60 days
    """

    last_7_days: int
    last_30_days: int
    last_60_days: int


@dataclass
class BranchActivityMetrics:
    """
    Branch activity metrics for a specific branch type.

    Attributes:
        type (BranchType): Branch classification type
        opened (TimeframeMetrics): Metrics for newly opened branches
        closed (TimeframeMetrics): Metrics for closed/merged branches
    """

    type: BranchType
    opened: TimeframeMetrics
    closed: TimeframeMetrics


@dataclass
class PRTypeMetrics:
    """
    Pull request metrics for a specific PR type.

    Attributes:
        type (PullRequestType): Pull request classification type
        open_count (int): Number of open PRs
        merged_count (int): Number of merged PRs
        total_count (int): Total number of PRs
    """

    type: PullRequestType
    open_count: int
    merged_count: int
    total_count: int


@dataclass
class RepositoryMetrics:
    """
    Comprehensive repository metrics and analysis results.

    Attributes:
        total_prs (int): Total number of pull requests
        open_prs (int): Number of open pull requests
        merged_prs (int): Number of merged pull requests
        active_branches (int): Number of active branches
        total_issues (int): Total number of issues
        open_issues (int): Number of open issues
        repository_name (str): Name of the analyzed repository
        analysis_date (datetime): Timestamp of the analysis
        pr_types (List[PRTypeMetrics]): Breakdown of PR types and their metrics
        branch_activity (List[BranchActivityMetrics]): Branch activity metrics by type
    """

    total_prs: int
    open_prs: int
    merged_prs: int
    active_branches: int
    total_issues: int
    open_issues: int
    repository_name: str
    analysis_date: datetime
    pr_types: List[PRTypeMetrics]
    branch_activity: List[BranchActivityMetrics]

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert metrics to a dictionary with serializable values.

        Returns:
            Dict[str, Any]: Dictionary containing serialized metrics data
                with ISO-formatted dates and enum values converted to strings.
        """
        data = asdict(self)
        data["analysis_date"] = self.analysis_date.isoformat()

        # Convert PR types to serializable format
        data["pr_types"] = [
            {
                "type": pr.type.value,
                "open_count": pr.open_count,
                "merged_count": pr.merged_count,
                "total_count": pr.total_count,
            }
            for pr in self.pr_types
        ]

        # Convert branch activity to serializable format
        data["branch_activity"] = [
            {
                "type": ba.type.value,
                "opened": asdict(ba.opened),
                "closed": asdict(ba.closed),
            }
            for ba in self.branch_activity
        ]

        return data


class GitHubAnalyzer:
    """
    GitHub repository analyzer with rate limiting and error handling.

    This class provides methods for analyzing GitHub repositories,
    including PR analysis, branch activity tracking, and issue metrics.
    It handles GitHub API rate limiting and provides detailed logging.

    Attributes:
        github (Github): Authenticated GitHub API client instance
    """

    def __init__(self, github_token: str = None):
        """
        Initialize the GitHub analyzer.

        Args:
            github_token (str, optional): GitHub API token. If not provided,
                uses token from settings.
        """
        self.github = Github(github_token or settings.github_token)

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

    def _categorize_branch_type(self, branch_name: str) -> BranchType:
        """
        Determine branch type based on its name.

        Args:
            branch_name (str): Name of the branch to categorize.

        Returns:
            BranchType: Classified branch type based on naming patterns.
        """
        name_lower = branch_name.lower()
        if any(keyword in name_lower for keyword in ["feature", "feat"]):
            return BranchType.FEATURE
        if any(keyword in name_lower for keyword in ["bug", "fix"]):
            return BranchType.BUGFIX
        if any(keyword in name_lower for keyword in ["hotfix", "critical"]):
            return BranchType.HOTFIX
        if any(
            keyword in name_lower for keyword in ["refactor", "refactoring", "refact"]
        ):
            return BranchType.REFACTOR
        if "test" in name_lower:
            return BranchType.TEST
        return BranchType.OTHER

    def _analyze_branch_activity(self, repo) -> List[BranchActivityMetrics]:
        """
        Analyze branch activity for the last 60 days.

        Args:
            repo (github.Repository.Repository): GitHub repository object.

        Returns:
            List[BranchActivityMetrics]: Branch activity metrics by branch type.
        """
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=60)

        timeframes = {
            7: now - timedelta(days=7),
            30: now - timedelta(days=30),
            60: cutoff_date,
        }

        activity_metrics = {
            branch_type: {
                "opened": {days: 0 for days in timeframes.keys()},
                "closed": {days: 0 for days in timeframes.keys()},
            }
            for branch_type in BranchType
        }

        # Analyze only recent branches
        for branch in repo.get_branches():
            commit = branch.commit.commit
            if commit.author.date < cutoff_date:
                continue

            branch_type = self._categorize_branch_type(branch.name)
            commit_date = commit.author.date

            for days, frame_cutoff in timeframes.items():
                if commit_date > frame_cutoff:
                    activity_metrics[branch_type]["opened"][days] += 1

        # Analyze recent merged PRs only
        merged_prs: PaginatedList = repo.get_pulls(
            state="closed",
            sort="updated",
            direction="desc",  # Get most recent first
        )

        # Process PRs until we hit the cutoff date
        for pr in merged_prs:
            if not pr.merged_at or pr.merged_at < cutoff_date:
                break  # Stop processing older PRs

            branch_type = self._categorize_branch_type(pr.head.ref)
            for days, frame_cutoff in timeframes.items():
                if pr.merged_at > frame_cutoff:
                    activity_metrics[branch_type]["closed"][days] += 1

        return [
            BranchActivityMetrics(
                type=branch_type,
                opened=TimeframeMetrics(
                    last_7_days=metrics["opened"][7],
                    last_30_days=metrics["opened"][30],
                    last_60_days=metrics["opened"][60],
                ),
                closed=TimeframeMetrics(
                    last_7_days=metrics["closed"][7],
                    last_30_days=metrics["closed"][30],
                    last_60_days=metrics["closed"][60],
                ),
            )
            for branch_type, metrics in activity_metrics.items()
        ]

    def _categorize_pr_type(
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

        # Check labels first
        for label in labels_lower:
            if "feature" in label or "enhancement" in label:
                return PullRequestType.FEATURE
            if "bug" in label or "bugfix" in label:
                return PullRequestType.BUGFIX
            if "hotfix" in label or "critical" in label or "urgent" in label:
                return PullRequestType.HOTFIX
            if "test" in label or "testing" in label:
                return PullRequestType.TEST
            if "issue" in label:
                return PullRequestType.ISSUE

        # Check title and body
        if any(
            keyword in combined_text for keyword in ["feature", "feat", "enhancement"]
        ):
            return PullRequestType.FEATURE
        if any(keyword in combined_text for keyword in ["fix", "bug", "issue #"]):
            return PullRequestType.BUGFIX
        if any(
            keyword in combined_text for keyword in ["hotfix", "critical", "urgent"]
        ):
            return PullRequestType.HOTFIX
        if any(keyword in combined_text for keyword in ["test", "testing"]):
            return PullRequestType.TEST
        if any(
            keyword in combined_text
            for keyword in ["refactor", "refactoring", "refact"]
        ):
            return PullRequestType.REFACTOR
        if "issue" in combined_text or "#" in title_lower:
            return PullRequestType.ISSUE

        return PullRequestType.OTHER

    def _analyze_pr_types(self, repo) -> List[PRTypeMetrics]:
        """
        Analyze types of pull requests from the last 60 days.

        Args:
            repo (github.Repository.Repository): GitHub repository object.

        Returns:
            List[PRTypeMetrics]: PR metrics categorized by type.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=60)

        # Get only recent PRs
        recent_prs = repo.get_pulls(
            state="all",
            sort="updated",
            direction="desc",  # Get most recent first
        )

        type_counts = {pr_type: 0 for pr_type in PullRequestType}

        for pr in recent_prs:
            # Stop if we hit PRs older than 60 days
            if pr.updated_at < cutoff_date:
                break

            pr_type = self._categorize_pr_type(
                pr.title, pr.body or "", [label.name for label in pr.labels]
            )
            type_counts[pr_type] += 1

        return [
            PRTypeMetrics(type=pr_type, count=count)
            for pr_type, count in type_counts.items()
        ]

    async def analyze_repository(self, repo_name: str) -> RepositoryMetrics:
        """
        Perform comprehensive analysis of a GitHub repository.

        Analyzes repository metrics including:
        - Pull request statistics and categorization
        - Branch activity patterns
        - Issue tracking metrics
        - Overall repository health indicators

        Args:
            repo_name (str): Full name of the repository (owner/repo)

        Returns:
            RepositoryMetrics: Comprehensive analysis results

        Raises:
            Exception: If analysis fails or rate limit is exceeded
        """
        try:
            self._check_rate_limit(check_name="current value")
            logger.info(
                {"message": "Starting repository analysis", "repository": repo_name}
            )

            repo = self.github.get_repo(repo_name)
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=60)

            self._check_rate_limit(check_name="get_repository")

            # Get open PRs first (including drafts)
            open_prs = repo.get_pulls(state="open", sort="updated", direction="desc")
            self._check_rate_limit(check_name="get_open_prs")

            # Track active branches through PRs
            active_branch_names = set()
            recent_open_prs = []

            for pr in open_prs:
                if pr.updated_at < cutoff_date:
                    break
                active_branch_names.add(pr.head.ref)
                recent_open_prs.append(pr)

            self._check_rate_limit(check_name="get_merged_prs")

            # Get merged PRs within cutoff
            merged_prs = [
                pr
                for pr in repo.get_pulls(
                    state="closed", sort="updated", direction="desc"
                )
                if pr.merged_at and pr.merged_at >= cutoff_date
            ]

            # Calculate metrics
            total_prs = len(recent_open_prs) + len(merged_prs)
            open_prs_count = len(recent_open_prs)
            merged_prs_count = len(merged_prs)
            active_branches_count = len(active_branch_names)

            self._check_rate_limit(check_name="get_recent_issues")

            # Get recent issues
            recent_issues = repo.get_issues(
                state="all", sort="updated", direction="desc"
            )

            self._check_rate_limit(check_name="get_recent_issues")

            total_issues = 0
            open_issues = 0

            for issue in recent_issues:
                if issue.updated_at < cutoff_date:
                    break
                total_issues += 1
                if issue.state == "open":
                    open_issues += 1

            # Analyze PR types separately for open and merged PRs
            logger.info({"message": "Analyzing PR types"})

            # Initialize counters for each PR type
            type_counts = {
                pr_type: {"open": 0, "merged": 0} for pr_type in PullRequestType
            }

            # Analyze open PRs
            for pr in recent_open_prs:
                pr_type = self._categorize_pr_type(
                    pr.title, pr.body or "", [label.name for label in pr.labels]
                )
                type_counts[pr_type]["open"] += 1

            # Analyze merged PRs
            for pr in merged_prs:
                pr_type = self._categorize_pr_type(
                    pr.title, pr.body or "", [label.name for label in pr.labels]
                )
                type_counts[pr_type]["merged"] += 1

            pr_types = [
                PRTypeMetrics(
                    type=pr_type,
                    open_count=counts["open"],
                    merged_count=counts["merged"],
                    total_count=counts["open"] + counts["merged"],
                )
                for pr_type, counts in type_counts.items()
            ]

            # Analyze branch activity only for active branches
            activity_metrics = {
                branch_type: {
                    "opened": {days: 0 for days in [7, 30, 60]},
                    "closed": {days: 0 for days in [7, 30, 60]},
                }
                for branch_type in BranchType
            }

            timeframes = {
                7: datetime.now(timezone.utc) - timedelta(days=7),
                30: datetime.now(timezone.utc) - timedelta(days=30),
                60: cutoff_date,
            }

            # Track branch activity through PRs
            for pr in recent_open_prs:
                branch_type = self._categorize_branch_type(pr.head.ref)
                for days, frame_cutoff in timeframes.items():
                    if pr.created_at > frame_cutoff:
                        activity_metrics[branch_type]["opened"][days] += 1

            for pr in merged_prs:
                branch_type = self._categorize_branch_type(pr.head.ref)
                for days, frame_cutoff in timeframes.items():
                    if pr.merged_at > frame_cutoff:
                        activity_metrics[branch_type]["closed"][days] += 1

            branch_activity = [
                BranchActivityMetrics(
                    type=branch_type,
                    opened=TimeframeMetrics(
                        last_7_days=metrics["opened"][7],
                        last_30_days=metrics["opened"][30],
                        last_60_days=metrics["opened"][60],
                    ),
                    closed=TimeframeMetrics(
                        last_7_days=metrics["closed"][7],
                        last_30_days=metrics["closed"][30],
                        last_60_days=metrics["closed"][60],
                    ),
                )
                for branch_type, metrics in activity_metrics.items()
            ]

            logger.info({"message": "Creating metrics object"})
            metrics = RepositoryMetrics(
                total_prs=total_prs,
                open_prs=open_prs_count,
                merged_prs=merged_prs_count,
                active_branches=active_branches_count,
                total_issues=total_issues,
                open_issues=open_issues,
                repository_name=repo_name,
                analysis_date=datetime.now(timezone.utc),
                pr_types=pr_types,
                branch_activity=branch_activity,
            )

            logger.info(
                {"message": "Repository analysis completed", "repository": repo_name}
            )

            return metrics

        except Exception as e:
            logger.error(
                {
                    "message": "Repository analysis failed",
                    "repository": repo_name,
                    "error": str(e),
                }
            )
            raise
