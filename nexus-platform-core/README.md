# Nexus Cloud

Cloud-native genomic processing for Nexus-G: **BLAST**, **Kraken2**, **Minimap2**, and **Bowtie2** with AWS, GCP, and Azure storage.

Full documentation: [`docs-and-blueprints/nexus-cloud-genomics-tools.md`](../docs-and-blueprints/nexus-cloud-genomics-tools.md)

```bash
pip install -e ".[all]"

# BLAST
python -m nexus_cloud.blast --config nexus_cloud/config.example.json

# Kraken2
python -m nexus_cloud.kraken2 --config nexus_cloud/config.kraken2.example.json

# Minimap2
python -m nexus_cloud.minimap2 --config nexus_cloud/config.minimap2.example.json

# Bowtie2
python -m nexus_cloud.bowtie2 --config nexus_cloud/config.bowtie2.example.json
```

Each tool uses the same `cloud` + `run` config structure. Tool-specific parameters live under `blast`, `kraken2`, `minimap2`, or `bowtie2`.

## Docker

Deploy all tools in one image:

```bash
make -f docker/Makefile build
make -f docker/Makefile init-config
make -f docker/Makefile blast
```

See [`docker/README.md`](docker/README.md) and [`docs-and-blueprints/nexus-cloud-docker.md`](../docs-and-blueprints/nexus-cloud-docker.md).
