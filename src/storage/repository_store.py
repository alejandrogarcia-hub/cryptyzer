"""
Repository Storage Module.

This module handles the persistent storage and retrieval of repository analysis results
and raw data. It provides functionality to store and load both analysis metrics and
repository data while maintaining historical records.
"""

import json
from datetime import datetime
import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass


from config import logger
from miners.models import RepositoryData
from analyzers.models import RepositoryMetrics


@dataclass
class StoredAnalysis:
    """
    Data class representing a stored repository analysis snapshot.

    Attributes:
        repository_name (str): Name of the analyzed repository.
        analysis_date (datetime): When the analysis was performed.
        metrics (dict): Analysis metrics and results.
    """

    repository_name: str
    analysis_date: datetime
    metrics: dict


class RepositoryStore:
    """
    Manages persistent storage of repository data and analysis results.
    Handles both saving and loading of historical repository information.
    """

    def __init__(self, data_dir: str):
        """Initialize the repository storage system.

        Args:
            data_dir (str): Base directory path for storing repository data.
        """

        self.storage_dir = Path(data_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_repo_data_file_path(self, repo_name: str, file_type: str = "json") -> str:
        """Generate the file path for raw repository data.

        Args:
            repo_name (str): Name of the repository.
            file_type (str): File extension for the storage format. Defaults to "json".

        Returns:
            str: Complete file path for storing repository data.
        """
        # Convert repo name to safe filename
        safe_name = repo_name.replace("/", "_").replace("\\", "_")
        return os.path.join(self.storage_dir, f"{safe_name}.{file_type}")

    def _get_repo_analysis_file_path(
        self, repo_name: str, file_type: str = "json"
    ) -> str:
        """Generate the file path for repository analysis results.

        Args:
            repo_name (str): Name of the repository.
            file_type (str): File extension for the storage format. Defaults to "json".

        Returns:
            str: Complete file path for storing analysis results.
        """
        # Convert repo name to safe filename
        safe_name = repo_name.replace("/", "_").replace("\\", "_")
        return os.path.join(self.storage_dir, f"{safe_name}_analysis.{file_type}")

    def store_analysis(self, metrics: dict) -> None:
        """Store repository analysis results while maintaining history.

        Args:
            metrics (dict): Analysis metrics to store, including repository name.

        Raises:
            Exception: If storage operation fails.
        """
        try:
            file_path = self._get_repo_analysis_file_path(metrics["repository_name"])

            # Load existing data if any
            existing_data = []
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    existing_data = json.load(f)

            # Add new analysis
            existing_data.append(metrics)

            # Store updated data
            with open(file_path, "w") as f:
                json.dump(
                    existing_data, f, indent=2, default=str
                )  # Added default=str for datetime handling

            logger.info(
                {
                    "message": "Stored repository analysis",
                    "repository": metrics["repository_name"],
                    "file_path": file_path,
                    "contributors_tracked": metrics.get("contributors_count", 0) > 0,
                }
            )

        except Exception as e:
            logger.error(
                {
                    "message": "Failed to store repository analysis",
                    "repository": metrics["repository_name"],
                    "error": str(e),
                }
            )
            raise

    def load_analysis(
        self, repo_name: str, limit: Optional[int] = None
    ) -> Optional[List[RepositoryMetrics]]:
        """Retrieve historical analysis data for a repository.

        Args:
            repo_name (str): Name of the repository.
            limit (Optional[int]): Maximum number of historical records to return.

        Returns:
            Optional[List[RepositoryMetrics]]: List of analysis records, sorted by date descending.

        Raises:
            Exception: If retrieval operation fails.
        """
        try:
            file_path = self._get_repo_analysis_file_path(repo_name)
            if not os.path.exists(file_path):
                return None

            with open(file_path, "r") as f:
                data = json.load(f)

            # Convert to StoredAnalysis objects
            analyses = [
                RepositoryMetrics(
                    repository_name=item["repository_name"],
                    analysis_date=item["analysis_date"],
                    total_prs_count=item["total_prs_count"],
                    open_prs_count=item["open_prs_count"],
                    closed_prs_count=item["closed_prs_count"],
                    total_issues_count=item["total_issues_count"],
                    open_issues_count=item["open_issues_count"],
                    pr_interval_metrics=item["pr_interval_metrics"],
                    top_contributors=item["top_contributors"],
                    contributors_count=item["contributors_count"],
                )
                for item in data
            ]

            # Sort by date descending and apply limit if specified
            analyses.sort(key=lambda x: x.analysis_date, reverse=True)
            if limit:
                analyses = analyses[:limit]

            return analyses

        except Exception as e:
            logger.error(
                {
                    "message": "Failed to retrieve repository history",
                    "repository": repo_name,
                    "error": str(e),
                }
            )
            raise

    def save_repository_data(self, data: RepositoryData) -> None:
        """Save raw repository data while maintaining history.

        Args:
            data (RepositoryData): Repository data to save.

        Raises:
            Exception: If save operation fails.
        """
        repo_file = self._get_repo_data_file_path(data.repository_name, "json")
        data_dict = data.model_dump()

        try:
            existing_data = []
            if os.path.exists(repo_file):
                with open(repo_file, "r") as f:
                    try:
                        existing_data = json.load(f)
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
                    except json.JSONDecodeError:
                        # Handle corrupted file by starting fresh
                        logger.error(
                            {
                                "message": "Corrupted repository data file",
                                "repository": data.repository_name,
                                "file": str(repo_file),
                            }
                        )
                        existing_data = []

            # Add new data to the list
            existing_data.append(data_dict)

            # Write all data back to file
            with open(repo_file, "w") as f:
                json.dump(existing_data, f, indent=2, default=str)

            logger.info(
                {
                    "message": "Repository data saved successfully",
                    "repository": data.repository_name,
                    "file": str(repo_file),
                }
            )

        except Exception as e:
            logger.error(
                {
                    "message": "Failed to save repository data",
                    "repository": data.repository_name,
                    "error": str(e),
                }
            )
            raise

    def load_repository_data(self, repo_name: str) -> Optional[List[RepositoryData]]:
        """Load all repository data snapshots.

        Args:
            repo_name (str): Name of the repository.

        Returns:
            Optional[List[RepositoryData]]: List of all repository data snapshots, empty list if none found.

        Raises:
            Exception: If load operation fails.
        """
        repo_file = self._get_repo_data_file_path(repo_name, "json")
        if not os.path.exists(repo_file):
            return None

        try:
            # load data from json file
            with open(repo_file, "r") as f:
                data_list = json.load(f)

            # Handle both single dict and list of dicts
            if isinstance(data_list, dict):
                data_list = [data_list]

            # Sort by date descending and apply limit if specified
            data_list.sort(key=lambda x: x["collection_date"], reverse=True)
            # Convert all items to RepositoryData objects
            return [RepositoryData(**data) for data in data_list]

        except Exception as e:
            logger.error(
                {
                    "message": "Failed to load repository data",
                    "repository": repo_name,
                    "error": str(e),
                }
            )
            raise
