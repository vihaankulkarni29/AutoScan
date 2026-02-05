# Use Python 3.9 slim image as base
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# CRITICAL: openbabel and autodock-vina are essential for the docking engine
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    openbabel \
    autodock-vina \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create data directories
RUN mkdir -p /app/data/receptors /app/data/ligands

# Set the entrypoint to the CLI
ENTRYPOINT ["autodock"]
CMD ["--help"]
