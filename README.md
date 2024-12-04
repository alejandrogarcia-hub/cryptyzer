# Cryptyzer

A Python-based tool for analyzing GitHub repositories, gathering metrics, and generating comprehensive reports.

## Features

- GitHub repository analysis and metrics collection
- Pattern recognition in code repositories
- PDF report generation using ReportLab
- Configurable logging system
- Environment-based configuration
- Docker support for development and production

## Requirements

- Python 3.11 or higher
- GitHub Personal Access Token
- Docker and Docker Compose (for containerized deployment)

## Installation

### Local Installation

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

### Docker Installation

The application can be run in a Docker container in either development or production mode.

#### Managing Dependencies

The project uses `uv` for dependency management. Dependencies are automatically compiled during container build, but you can also manage them manually:

```bash
# Update dependencies and rebuild containers
./scripts/update_deps.sh --rebuild

# Update dependencies in running containers without rebuild
./scripts/update_deps.sh --update-running

# Only update requirements.txt (no container changes)
./scripts/update_deps.sh
```

#### Development Mode

```bash
# Build and start the development container
docker compose --profile dev up --build

# Stop the containers
docker compose --profile dev down
```

#### Production Mode

```bash
# Build and start the production container
docker compose --profile prod up --build -d

# Stop the containers
docker compose --profile prod down
```

#### Accessing Generated Reports

The following directories are mounted as volumes and will persist data between container runs:

- `./data`: Raw data files
- `./reports`: Generated PDF reports
- `./plots`: Generated plots and visualizations
- `./logs`: Application logs

All files generated inside these directories will be automatically available on your host machine in the respective folders.

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
