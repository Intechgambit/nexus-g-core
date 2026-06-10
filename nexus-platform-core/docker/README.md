# Nexus Cloud Docker

Deployable image with **BLAST+**, **Kraken2**, **Minimap2**, **Bowtie2**, and the `nexus-cloud` Python package.

Full guide: [`docs-and-blueprints/nexus-cloud-docker.md`](../../docs-and-blueprints/nexus-cloud-docker.md)

## Quick start

```bash
cd nexus-platform-core

# 1. Build image
make -f docker/Makefile build

# 2. Copy example configs
make -f docker/Makefile init-config

# 3. Edit docker/config/*.json and docker/.env

# 4. Run a tool
make -f docker/Makefile blast
make -f docker/Makefile kraken2
```

## Direct docker commands

```bash
docker build -t nexus-cloud-genomics:latest -f docker/Dockerfile .

docker run --rm \
  -v "$(pwd)/docker/config:/config:ro" \
  -v "$(pwd)/docker/data:/data" \
  --env-file docker/.env \
  nexus-cloud-genomics:latest blast --config /config/blast.json
```

## Docker Compose

```bash
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml run --rm nexus-cloud kraken2 --config /config/kraken2.json
```

## Mount local indexes

Point `db_path`, `index_path`, or `reference_path` in your config to `/references/...` and mount host data:

```bash
-v /data/blastdb:/references/blastdb:ro
```

```json
"blast": { "db_path": "/references/blastdb/nt" }
```
