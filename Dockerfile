# Use Python 3.9 with build tools - not slim
FROM python:3.9

# Set working directory
WORKDIR /app

# Install system dependencies including build essentials for compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    git \
    openbabel \
    libopenbabel-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Download and setup AutoDock Vina (from official source)
# Vina binaries: https://github.com/ccsb-scripps/AutoDock-Vina/releases
RUN mkdir -p /opt/vina && \
    cd /opt/vina && \
    wget -q https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64 && \
    chmod +x vina_1.2.5_linux_x86_64 && \
    mv vina_1.2.5_linux_x86_64 /usr/local/bin/vina && \
    rm -rf /opt/vina

# Verify Vina installation
RUN which vina && vina --version

# Copy project files AFTER system tools are ready
COPY . /app/

# Install Python dependencies in optimal order
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    openbabel-wheel \
    "numpy>=1.21.0" \
    "scipy>=1.7.0" \
    "biopython>=1.81" \
    "openmm>=7.7" \
    "pandas>=1.3.0" \
    "rdkit>=2023.09.1" \
    "meeko>=0.5.0" \
    "gemmi>=0.5.0" \
    "mdtraj>=1.9.0" \
    "typer[all]>=0.9.0" \
    "pyyaml>=6.0"

# Install AutoScan package (without dependencies, already installed above)
RUN pip install --no-cache-dir --no-deps -e .

# Create data directories
RUN mkdir -p /app/data/receptors /app/data/ligands /app/tools

# AutoScan runtime configuration
ENV AUTOSCAN_DATA_DIR=/app/data \
    AUTOSCAN_CONFIG_DIR=/app/config \
    PATH="/usr/local/bin:$PATH"

# Verify all tools are available
RUN which vina && which obabel && python -c "import meeko; import rdkit; print('All imports OK')"

# Set flexible entrypoint
ENTRYPOINT ["python"]
CMD ["-c", "print('AutoScan validation environment ready')"]


