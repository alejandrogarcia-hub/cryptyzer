"""Module for creating analysis visualizations."""

from typing import Dict, List, Any, Optional
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import pandas as pd
import os
import numpy as np

from storage.repository_store import StoredAnalysis
from analyzers.repository import RepositoryMetrics
from config import logger


class AnalysisPlotter:
    """Class for creating visualizations of repository analysis results."""

    def __init__(self):
        """Initialize the plotter with default style settings."""
        sns.set_style("whitegrid")
        plt.rcParams["figure.figsize"] = (12, 6)

    def _parse_timestamp(self, timestamp: str) -> datetime:
        """Parse ISO format timestamp string.

        Args:
            timestamp: ISO format timestamp string

        Returns:
            datetime object
        """
        return datetime.fromisoformat(timestamp)

    def create_time_series_plot(
        self,
        history: List[Dict[str, Any]],
        metric_name: str,
        title: Optional[str] = None,
    ) -> plt.Figure:
        """Create a time series plot for a specific metric.

        Args:
            history: List of historical analysis results
            metric_name: Name of the metric to plot
            title: Optional plot title

        Returns:
            matplotlib Figure object
        """
        # Extract timestamps and metric values
        timestamps = [self._parse_timestamp(item["timestamp"]) for item in history]
        values = [item["data"].get(metric_name, 0) for item in history]

        # Create DataFrame for plotting
        df = pd.DataFrame({"timestamp": timestamps, "value": values})

        # Create the plot
        fig, ax = plt.subplots()
        sns.lineplot(data=df, x="timestamp", y="value", marker="o")

        # Customize the plot
        plt.xticks(rotation=45)
        plt.title(title or f"{metric_name} Over Time")
        plt.xlabel("Date")
        plt.ylabel(metric_name)

        # Adjust layout to prevent label cutoff
        plt.tight_layout()

        return fig

    def create_comparison_plot(
        self,
        history: List[Dict[str, Any]],
        metrics: List[str],
        title: Optional[str] = None,
    ) -> plt.Figure:
        """Create a plot comparing multiple metrics over time.

        Args:
            history: List of historical analysis results
            metrics: List of metric names to compare
            title: Optional plot title

        Returns:
            matplotlib Figure object
        """
        timestamps = [self._parse_timestamp(item["timestamp"]) for item in history]

        # Create DataFrame with all metrics
        data = []
        for metric in metrics:
            values = [item["data"].get(metric, 0) for item in history]
            for t, v in zip(timestamps, values):
                data.append({"timestamp": t, "value": v, "metric": metric})

        df = pd.DataFrame(data)

        # Create the plot
        fig, ax = plt.subplots()
        sns.lineplot(data=df, x="timestamp", y="value", hue="metric", marker="o")

        # Customize the plot
        plt.xticks(rotation=45)
        plt.title(title or "Metrics Comparison Over Time")
        plt.xlabel("Date")
        plt.ylabel("Value")
        plt.legend(title="Metrics")

        # Adjust layout
        plt.tight_layout()

        return fig

    def create_distribution_plot(
        self,
        history: List[Dict[str, Any]],
        metric_name: str,
        title: Optional[str] = None,
    ) -> plt.Figure:
        """Create a distribution plot for a metric's values over time.

        Args:
            history: List of historical analysis results
            metric_name: Name of the metric to analyze
            title: Optional plot title

        Returns:
            matplotlib Figure object
        """
        values = [item["data"].get(metric_name, 0) for item in history]

        # Create the plot
        fig, ax = plt.subplots()
        sns.histplot(values, kde=True)

        # Customize the plot
        plt.title(title or f"{metric_name} Distribution")
        plt.xlabel(metric_name)
        plt.ylabel("Count")

        # Adjust layout
        plt.tight_layout()

        return fig


class RepositoryPlotter:
    def __init__(self, output_dir: str = "plots"):
        """Initialize repository plotter."""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def create_pr_trend_plot(self, history: List[StoredAnalysis]) -> plt.Figure:
        """Create pull request trend plot."""
        dates = [h.analysis_date for h in history]
        open_prs = [h.metrics["open_prs"] for h in history]
        merged_prs = [h.metrics["merged_prs"] for h in history]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(dates, open_prs, marker="o", label="Open PRs")
        ax.plot(dates, merged_prs, marker="s", label="Merged PRs")

        ax.set_title("Pull Request Trends")
        ax.set_xlabel("Date")
        ax.set_ylabel("Count")
        ax.legend()
        ax.grid(True)

        # Rotate date labels for better readability
        plt.xticks(rotation=45)
        plt.tight_layout()

        return fig

    def create_pr_type_distribution_plot(
        self, history: List[StoredAnalysis]
    ) -> plt.Figure:
        """Create PR type distribution plot."""
        latest = history[0]  # Most recent analysis
        pr_types = latest.metrics["pr_types"]

        types = [pt["type"] for pt in pr_types]
        open_counts = [pt["open_count"] for pt in pr_types]
        merged_counts = [pt["merged_count"] for pt in pr_types]

        fig, ax = plt.subplots(figsize=(12, 6))
        x = range(len(types))
        width = 0.35

        ax.bar([i - width / 2 for i in x], open_counts, width, label="Open")
        ax.bar([i + width / 2 for i in x], merged_counts, width, label="Merged")

        ax.set_title("Pull Request Type Distribution")
        ax.set_xlabel("PR Type")
        ax.set_ylabel("Count")
        ax.set_xticks(x)
        ax.set_xticklabels(types, rotation=45)
        ax.legend()
        plt.tight_layout()

        return fig

    def create_branch_activity_plot(self, history: List[StoredAnalysis]) -> plt.Figure:
        """Create branch activity plot."""
        latest = history[0]  # Most recent analysis
        branch_activity = latest.metrics["branch_activity"]

        types = [ba["type"] for ba in branch_activity]
        opened_7d = [ba["opened"]["last_7_days"] for ba in branch_activity]
        closed_7d = [ba["closed"]["last_7_days"] for ba in branch_activity]
        opened_30d = [ba["opened"]["last_30_days"] for ba in branch_activity]
        closed_30d = [ba["closed"]["last_30_days"] for ba in branch_activity]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # 7 days plot
        x = range(len(types))
        width = 0.35
        ax1.bar([i - width / 2 for i in x], opened_7d, width, label="Opened")
        ax1.bar([i + width / 2 for i in x], closed_7d, width, label="Closed")
        ax1.set_title("Branch Activity (Last 7 Days)")
        ax1.set_xlabel("Branch Type")
        ax1.set_ylabel("Count")
        ax1.set_xticks(x)
        ax1.set_xticklabels(types, rotation=45)
        ax1.legend()

        # 30 days plot
        ax2.bar([i - width / 2 for i in x], opened_30d, width, label="Opened")
        ax2.bar([i + width / 2 for i in x], closed_30d, width, label="Closed")
        ax2.set_title("Branch Activity (Last 30 Days)")
        ax2.set_xlabel("Branch Type")
        ax2.set_ylabel("Count")
        ax2.set_xticks(x)
        ax2.set_xticklabels(types, rotation=45)
        ax2.legend()

        plt.tight_layout()
        return fig

    def save_plots(self, history: List[StoredAnalysis]) -> List[str]:
        """Generate and save all plots for a repository."""
        if not history:
            return []

        repo_name = history[0].repository_name.replace("/", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        plots = [
            ("pr_trend", self.create_pr_trend_plot),
            ("pr_distribution", self.create_pr_type_distribution_plot),
            ("branch_activity", self.create_branch_activity_plot),
        ]

        saved_plots = []
        for name, plot_func in plots:
            try:
                fig = plot_func(history)
                filename = f"{repo_name}_{name}_{timestamp}.png"
                filepath = os.path.join(self.output_dir, filename)
                fig.savefig(filepath)
                plt.close(fig)
                saved_plots.append(filepath)
            except Exception as e:
                logger.error(
                    {
                        "message": f"Failed to create {name} plot",
                        "repository": repo_name,
                        "error": str(e),
                    }
                )

        return saved_plots

    def create_comparison_plots(
        self, results: Dict[str, RepositoryMetrics]
    ) -> List[str]:
        """Create comparison plots for multiple repositories."""
        if not results:
            return []

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_plots = []

        try:
            # PR Status Comparison
            fig, ax = plt.subplots(figsize=(12, 6))
            repos = list(results.keys())
            x = range(len(repos))
            width = 0.35

            open_prs = [metrics.open_prs for metrics in results.values()]
            merged_prs = [metrics.merged_prs for metrics in results.values()]

            ax.bar([i - width / 2 for i in x], open_prs, width, label="Open PRs")
            ax.bar([i + width / 2 for i in x], merged_prs, width, label="Merged PRs")

            ax.set_title("Pull Request Status Comparison")
            ax.set_xlabel("Repository")
            ax.set_ylabel("Count")
            ax.set_xticks(x)
            ax.set_xticklabels(repos, rotation=45, ha="right")
            ax.legend()
            plt.tight_layout()

            # Save PR comparison plot
            pr_plot_path = os.path.join(
                self.output_dir, f"pr_comparison_{timestamp}.png"
            )
            fig.savefig(pr_plot_path)
            plt.close(fig)
            saved_plots.append(pr_plot_path)

            # Issue Status Comparison
            fig, ax = plt.subplots(figsize=(12, 6))
            open_issues = [metrics.open_issues for metrics in results.values()]
            total_issues = [metrics.total_issues for metrics in results.values()]

            ax.bar([i - width / 2 for i in x], open_issues, width, label="Open Issues")
            ax.bar(
                [i + width / 2 for i in x], total_issues, width, label="Total Issues"
            )

            ax.set_title("Issue Status Comparison")
            ax.set_xlabel("Repository")
            ax.set_ylabel("Count")
            ax.set_xticks(x)
            ax.set_xticklabels(repos, rotation=45, ha="right")
            ax.legend()
            plt.tight_layout()

            # Save issue comparison plot
            issue_plot_path = os.path.join(
                self.output_dir, f"issue_comparison_{timestamp}.png"
            )
            fig.savefig(issue_plot_path)
            plt.close(fig)
            saved_plots.append(issue_plot_path)

            # PR Types Distribution
            fig, ax = plt.subplots(figsize=(12, 6))
            pr_types = set()
            for metrics in results.values():
                pr_types.update(pt.type.value for pt in metrics.pr_types)

            pr_types = sorted(pr_types)
            bar_positions = np.arange(len(repos))
            bar_width = 0.15

            for i, pr_type in enumerate(pr_types):
                counts = []
                for metrics in results.values():
                    type_metrics = next(
                        (pt for pt in metrics.pr_types if pt.type.value == pr_type),
                        None,
                    )
                    counts.append(type_metrics.total_count if type_metrics else 0)

                ax.bar(
                    bar_positions + i * bar_width,
                    counts,
                    bar_width,
                    label=pr_type.title(),
                )

            ax.set_title("Pull Request Types Distribution")
            ax.set_xlabel("Repository")
            ax.set_ylabel("Count")
            ax.set_xticks(bar_positions + bar_width * (len(pr_types) - 1) / 2)
            ax.set_xticklabels(repos, rotation=45, ha="right")
            ax.legend()
            plt.tight_layout()

            # Save PR types plot
            pr_types_plot_path = os.path.join(
                self.output_dir, f"pr_types_comparison_{timestamp}.png"
            )
            fig.savefig(pr_types_plot_path)
            plt.close(fig)
            saved_plots.append(pr_types_plot_path)

            return saved_plots

        except Exception as e:
            logger.error(
                {"message": "Failed to create comparison plots", "error": str(e)}
            )
            # Clean up any partially created plots
            for plot_path in saved_plots:
                try:
                    if os.path.exists(plot_path):
                        os.remove(plot_path)
                except Exception:
                    pass
            raise
        finally:
            # Ensure all plots are closed
            plt.close("all")
