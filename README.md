# Cryptyzer

A Python-based tool for analyzing GitHub repositories, gathering metrics, and generating comprehensive reports.

## Features
- GitHub repository analysis and metrics collection
- Pattern recognition in code repositories
- PDF report generation using ReportLab
- Configurable logging system
- Environment-based configuration

## Requirements
- Python 3.11 or higher
- GitHub Personal Access Token

## Installation

```bash
# Clone the repository
git clone https://github.com/alejandrogarcia-hub/cryptyzer.git
cd cryptyzer

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

1. Copy the example environment file:
```bash
cp .env_example .env
```

2. Configure your environment variables in `.env`:
```env
APP_NAME=Cryptyzer
GITHUB_TOKEN=your_github_token_here
GITHUB_REPO_URL=https://github.com/your/repo.git
```

## Development Setup

Install development dependencies:
```bash
pip install -e ".[dev]"
```

## Testing

Run tests with pytest:
```bash
pytest
```

## Project Structure
```
cryptyzer/
├── src/           # Source code
├── tests/         # Test files
├── logs/          # Application logs
├── reports/       # Generated reports
└── requirements.txt
```

## Dependencies
- pydantic: Data validation
- PyGithub: GitHub API integration
- ReportLab: PDF report generation
- pytest: Testing framework

## License
[Add your license here]