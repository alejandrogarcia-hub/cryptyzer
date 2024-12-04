#!/bin/bash

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Update dependencies using uv
echo "Updating dependencies..."
uv pip compile pyproject.toml -o requirements.txt
uv pip compile --all-extras pyproject.toml -o requirements_dev.txt

# Check if we need to rebuild containers
if [ "$1" == "--rebuild" ]; then
    echo "Rebuilding containers..."
    docker compose --profile dev down
    docker compose --profile prod down
    docker compose build --no-cache
    echo "Containers rebuilt successfully!"
fi

# Check if we need to update running containers
if [ "$1" == "--update-running" ]; then
    echo "Updating dependencies in running containers..."
    # Update dev container if running
    if docker compose ps | grep -q "dev"; then
        docker compose exec dev pip install -r requirements.txt
    fi
    # Update prod container if running
    if docker compose ps | grep -q "prod"; then
        docker compose exec prod pip install -r requirements.txt
    fi
    echo "Running containers updated successfully!"
fi

echo "Dependencies update completed!" 