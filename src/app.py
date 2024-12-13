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

from openai import AsyncOpenAI
import tiktoken

from config import settings, logger
from analyzers.multi_repository import MultiRepositoryAnalyzer
from analyzers.repository import GitHubAnalyzer
from miners.github_miner import GitHubMiner, RepositoryMiner
from storage.repository_store import RepositoryStore
from report.pdf_generator import PDFReportGenerator
from visualization.plotter import RepositoryPlotter
from analyzers.plugins.category_analyzer import (
    CategoryAnalyzerPlugin,
    PRTypeCategoryAnalyzerPlugin,
    LLMPRTypeCategoryAnalyzerPlugin,
)


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
    logger.info(f"AI_BASED: {settings.ai_based}")

    # Create output directory for reports
    os.makedirs(settings.report_output_dir, exist_ok=True)

    # Initialize GitHub miner
    logger.debug("initializing github miner...")
    github_miner: RepositoryMiner = GitHubMiner(
        settings.github_token.get_secret_value(),
        max(settings.intervals),
    )

    # Initialize OpenAI client
    logger.debug("initializing category analyzer...")
    category_analyzer: CategoryAnalyzerPlugin = PRTypeCategoryAnalyzerPlugin()
    if settings.ai_based:
        logger.debug("initializing openai client...")
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
        encoding = tiktoken.encoding_for_model(settings.openai_encoding_name)
        category_analyzer = LLMPRTypeCategoryAnalyzerPlugin(
            openai_client,
            encoding,
            settings.openai_max_requests_per_minute,
            settings.openai_max_tokens_per_minute,
            settings.data_dir,
            settings.openai_period,
        )

    # Initialize repository analyzer
    logger.debug("initializing repository analyzer...")

    store = RepositoryStore(settings.data_dir)
    analyzer = GitHubAnalyzer(settings.intervals, category_analyzer)
    multi_analyzer = MultiRepositoryAnalyzer(
        store, analyzer, github_miner, settings.repository_urls
    )

    # Execute analysis on all repositories
    logger.info("analyzing repositories...")
    repo_metrics = await multi_analyzer.analyze_repositories()

    # Get all analysis from data store per repo
    # store the data in a dict with repo_name as key and analysis as value
    logger.info("loading historical data from data store...")
    historical_data = {}
    for repo_name, _ in repo_metrics.items():
        historical_data[repo_name] = store.load_analysis(repo_name)

    logger.info("generating reports...")

    # Create temporary directory for plots
    temp_plot_dir = os.path.join(settings.report_output_dir, "temp_plots")
    os.makedirs(temp_plot_dir, exist_ok=True)

    plotter = RepositoryPlotter(temp_plot_dir)
    pdf_generator = PDFReportGenerator(plotter)
    pdf_generator.generate_report(
        repo_metrics, historical_data, settings.report_output_dir, temp_plot_dir
    )

    # delete plots older than max(settings.intervals),
    plotter.delete_old_plots(max(settings.intervals))

    logger.info("application finished")


if __name__ == "__main__":
    logger.info("Starting application ...")
    asyncio.run(main())
