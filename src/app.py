"""
Main Application Entry Point.

This module serves as the primary entry point for the repository analysis system.
It orchestrates the analysis workflow, including:
- Repository analysis initialization
- Report directory management
- Analysis execution
- Report generation
- Error handling and logging

The application can be run directly to analyze configured repositories
and generate comprehensive reports.
"""

import asyncio
import os

from config import settings, logger
from analyzers.multi_repository import MultiRepositoryAnalyzer


async def main() -> None:
    """
    Execute the main application workflow.

    Performs the following steps:
    1. Creates output directory for reports if it doesn't exist
    2. Initializes the multi-repository analyzer
    3. Executes analysis on all configured repositories
    4. Generates summary report if analysis is successful

    Raises:
        OSError: If unable to create output directory
        Exception: If repository analysis or report generation fails

    Note:
        - Configured repositories are read from settings
        - Reports are saved to the configured output directory
        - Failed repository analyses are logged but don't stop execution
    """
    logger.info("Starting multi-repository analysis...")

    # Create output directory for reports
    os.makedirs(settings.report_output_dir, exist_ok=True)

    # Initialize repository analyzer
    analyzer = MultiRepositoryAnalyzer()

    # Execute analysis on all repositories
    results = await analyzer.analyze_repositories()

    # Generate summary report if results are available
    if results:
        analyzer.generate_summary_report(results)
        logger.info("Analysis completed successfully!")
    else:
        logger.warning("No repository analysis results available")


if __name__ == "__main__":
    logger.info("Starting application ...")
    asyncio.run(main())
