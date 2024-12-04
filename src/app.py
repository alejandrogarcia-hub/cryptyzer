import asyncio
import os

from config import settings, logger
from analyzers.multi_repository import MultiRepositoryAnalyzer


async def main():
    """Main function to run the application."""
    logger.info("Starting multi-repository analysis...")

    # Create output directory
    os.makedirs(settings.report_output_dir, exist_ok=True)

    # Initialize analyzer
    analyzer = MultiRepositoryAnalyzer()

    # Analyze all repositories
    results = await analyzer.analyze_repositories()

    # Generate summary report
    if results:
        analyzer.generate_summary_report(results)
        logger.info("Analysis completed successfully!")
    else:
        logger.warning("No repository analysis results available")


if __name__ == "__main__":
    logger.info("Starting application ...")
    asyncio.run(main())
