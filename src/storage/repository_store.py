"""Module for storing repository analysis results."""

import json
from datetime import datetime
import os
from typing import List, Optional
from dataclasses import dataclass

from config import logger


@dataclass
class StoredAnalysis:
    repository_name: str
    analysis_date: datetime
    metrics: dict


class RepositoryStore:
    def __init__(self, storage_dir: str = "data"):
        """Initialize repository storage."""
        self.storage_dir = storage_dir
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        """Ensure storage directory exists."""
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_repo_file_path(self, repo_name: str) -> str:
        """Get the file path for a repository's data."""
        # Convert repo name to safe filename
        safe_name = repo_name.replace("/", "_").replace("\\", "_")
        return os.path.join(self.storage_dir, f"{safe_name}.json")

    def store_analysis(self, metrics: dict) -> None:
        """Store repository analysis results."""
        try:
            file_path = self._get_repo_file_path(metrics["repository_name"])

            # Load existing data if any
            existing_data = []
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    existing_data = json.load(f)

            # Add new analysis
            existing_data.append(
                {"analysis_date": metrics["analysis_date"], "metrics": metrics}
            )

            # Store updated data
            with open(file_path, "w") as f:
                json.dump(existing_data, f, indent=2)

            logger.info(
                {
                    "message": "Stored repository analysis",
                    "repository": metrics["repository_name"],
                    "file_path": file_path,
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

    def get_repository_history(
        self, repo_name: str, limit: Optional[int] = None
    ) -> List[StoredAnalysis]:
        """Get historical analysis data for a repository."""
        try:
            file_path = self._get_repo_file_path(repo_name)
            if not os.path.exists(file_path):
                return []

            with open(file_path, "r") as f:
                data = json.load(f)

            # Convert to StoredAnalysis objects
            analyses = [
                StoredAnalysis(
                    repository_name=repo_name,
                    analysis_date=datetime.fromisoformat(item["analysis_date"]),
                    metrics=item["metrics"],
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
