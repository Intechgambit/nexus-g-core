# syntax=docker/dockerfile:1

FROM mambaorg/micromamba:2.0.6

LABEL org.opencontainers.image.title="Nexus Cloud Genomics"
LABEL org.opencontainers.image.description="Deployable image for BLAST, Kraken2, Minimap2, and Bowtie2 with cloud storage I/O"
LABEL org.opencontainers.image.vendor="Intechgambit LLC"
LABEL org.opencontainers.image.licenses="GPL-3.0"

USER root
WORKDIR /opt/nexus-cloud

# Bioinformatics CLIs from bioconda
COPY docker/environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml \
    && micromamba clean -a --force-pkgs-dirs \
    && rm -f /tmp/environment.yml

# Nexus Cloud Python package and cloud SDKs
COPY pyproject.toml README.md requirements.txt ./
COPY nexus_cloud/ ./nexus_cloud/
RUN micromamba run -n base pip install --no-cache-dir ".[all,yaml]"

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENV NEXUS_CONFIG_DIR=/config \
    NEXUS_DATA_DIR=/data \
    PYTHONUNBUFFERED=1

# Optional local indexes / references (mount host paths here)
VOLUME ["/config", "/data", "/references"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["help"]
