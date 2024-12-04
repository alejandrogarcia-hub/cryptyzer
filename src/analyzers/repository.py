from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, Any, List

from github import Github
from github.PaginatedList import PaginatedList
from github.RateLimit import RateLimit

from config import settings, logger


class BranchType(Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    HOTFIX = "hotfix"
    REFACTOR = "refactor"
    TEST = "test"
    OTHER = "other"


class PullRequestType(Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    HOTFIX = "hotfix"
    REFACTOR = "refactor"
    TEST = "test"
    ISSUE = "issue"
    OTHER = "other"


@dataclass
class TimeframeMetrics:
    last_7_days: int
    last_30_days: int
    last_60_days: int


@dataclass
class BranchActivityMetrics:
    type: BranchType
    opened: TimeframeMetrics
    closed: TimeframeMetrics


@dataclass
class PRTypeMetrics:
    type: PullRequestType
    open_count: int
    merged_count: int
    total_count: int


@dataclass
class RepositoryMetrics:
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
        """Convert metrics to dictionary with serializable values."""
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
    def __init__(self, github_token: str = None):
        self.github = Github(github_token or settings.github_token)

    def _check_rate_limit(self, check_name: str = None) -> None:
        """
        Check GitHub API rate limit status.
        Logs warning when approaching limit and critical when limit is reached.
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
        """Analyze branch activity for the last 60 days."""
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
        """Categorize PR type based on title, body and labels."""
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
        """Analyze types of pull requests from the last 60 days."""
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
