"""
Repository Analysis Visualization Module.

Provides functionality for creating and managing data visualizations of repository
analysis results, including:
- Time series analysis
- Metric distributions
- Comparative analysis
- Historical trends
- Activity patterns

The module uses matplotlib and seaborn for creating publication-quality visualizations
and handles proper file management for generated plots.
"""

from typing import Dict, List
import matplotlib.pyplot as plt
import os

from analyzers.repository import RepositoryMetrics


class RepositoryPlotter:
    """
    Specialized plotter for repository-specific visualizations.

    Handles creation and management of repository analysis visualizations,
    including file management and multi-repository comparisons.

    Attributes:
        output_dir (str): Directory for saving generated plots
    """

    def __init__(self, output_dir: str = "plots"):
        """
        Initialize repository plotter with output configuration.

        Args:
            output_dir (str): Directory path for saving generated plots.
                Defaults to "plots"
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def create_pr_type_trends_plot(
        self, history: List[RepositoryMetrics], interval: str, pr_types: List[str]
    ) -> plt.Figure:
        """Create historical trend plot for PR types.

        Args:
            history (List[RepositoryMetrics]): Historical repository metrics
            interval (str): The interval to plot (e.g., "7", "30", "60")
            pr_types (List[str]): List of PR types to plot
        Returns:
            plt.Figure: Generated trend plot figure
        """
        # Extract dates and PR type data
        dates = [h.analysis_date for h in history]
        # Create figure with two subplots (Open and Closed)
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12))

        # Plot open PRs
        for pr_type in pr_types:
            values = [
                h.pr_interval_metrics[interval].open.get(pr_type, 0) for h in history
            ]
            ax1.plot(dates, values, marker="o", label=pr_type.capitalize())

        ax1.set_title(f"Open PRs by Type (Last {interval} days)")
        ax1.set_xlabel("Date")
        ax1.set_ylabel("Count")
        ax1.legend(title="PR Types")
        ax1.grid(True)
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Plot closed PRs
        for pr_type in pr_types:
            values = [
                h.pr_interval_metrics[interval].closed.get(pr_type, 0) for h in history
            ]
            ax2.plot(dates, values, marker="o", label=pr_type.capitalize())

        ax2.set_title(f"Closed PRs by Type (Last {interval} days)")
        ax2.set_xlabel("Date")
        ax2.set_ylabel("Count")
        ax2.legend(title="PR Types")
        ax2.grid(True)
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        plt.tight_layout()
        return fig

    def create_pr_type_trends_plots(
        self,
        history: List[RepositoryMetrics],
        intervals: List[str],
        pr_types: List[str],
    ) -> Dict[str, plt.Figure]:
        """Create historical trend plots for all intervals.

        Args:
            history (List[RepositoryMetrics]): Historical repository metrics
            intervals (List[str]): List of intervals to plot
            pr_types (List[str]): List of PR types to plot

        Returns:
            Dict[str, plt.Figure]: Dictionary of interval to plot figure
        """
        if not history:
            return {}

        # Create plots for each interval
        plots = {}
        for interval in intervals:
            plots[interval] = self.create_pr_type_trends_plot(
                history, interval, pr_types
            )

        return plots

    def delete_old_plots(self, interval: int):
        """Delete plots older than the given interval.

        Args:
            interval (int): The interval to delete plots older than
        """
        for file in os.listdir(self.output_dir):
            if file.endswith(".png") and int(file.split("_")[-2]) < interval:
                os.remove(os.path.join(self.output_dir, file))
