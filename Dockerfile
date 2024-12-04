FROM python:3.11-slim

WORKDIR /app

# set pythonpath to include src directory
ENV PYTHONPATH=/app/src

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements*.txt ./

# Install Python dependencies based on environment
ARG ENVIRONMENT
RUN if [ "${ENVIRONMENT}" = "development" ]; then \
    pip install -r requirements_dev.txt; \
    else \
    pip install -r requirements.txt; \
    fi

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/reports /app/plots

# Copy application code
COPY . .

# Set default command
CMD ["python", "-m", "src.app"] 