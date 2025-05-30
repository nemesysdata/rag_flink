FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Configure Poetry
RUN poetry config virtualenvs.create false

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --without dev --no-interaction --no-ansi --no-root

# Copy application code
COPY src/ ./src/

# Expose port for health check
EXPOSE 5000

# Run the application
CMD ["python", "src/main.py"] 