# Nexus Cloud Docker Deployment

**Author:** Amina Jackson, Intechgambit  
**License:** GPL-3.0  
**Location:** `nexus-platform-core/docker`

Deploy a single container with BLAST+, Kraken2, Minimap2, Bowtie2, and the Nexus Cloud config-driven CLI — ready for AWS, GCP, or Azure object storage.

---

## What's in the image

| Component | Source |
|-----------|--------|
| BLAST+ | bioconda |
| Kraken2 | bioconda |
| Minimap2 | bioconda |
| Bowtie2 | bioconda |
| nexus-cloud | pip install from `nexus-platform-core` |
| Cloud SDKs | boto3, google-cloud-storage, azure-storage-blob |

---

## Build

From `nexus-platform-core`:

```bash
docker build -t nexus-cloud-genomics:latest -f docker/Dockerfile .
```

Or with Make:

```bash
make -f docker/Makefile build
```

Or Docker Compose:

```bash
docker compose -f docker/docker-compose.yml build
```

---

## Configure

### 1. Initialize example configs

```bash
make -f docker/Makefile init-config
```

This creates:

```
docker/
  config/
    blast.json
    kraken2.json
    minimap2.json
    bowtie2.json
  data/
  references/
  .env
```

### 2. Edit configs

Update `cloud.provider`, `cloud.bucket_path`, and `cloud.credentials` in each JSON file. Tool sections (`blast`, `kraken2`, etc.) and `run.jobs` follow the same schema as the Python package.

See [nexus-cloud-genomics-tools.md](nexus-cloud-genomics-tools.md) for parameter reference.

### 3. Set cloud credentials

**Option A — environment file (`docker/.env`):**

```bash
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
```

**Option B — IAM role** on ECS, EKS, EC2, or Batch (no keys in `.env`).

**Option C — mount GCP key** in `docker-compose.yml`:

```yaml
volumes:
  - /path/to/service-account.json:/secrets/gcp.json:ro
environment:
  GOOGLE_APPLICATION_CREDENTIALS: /secrets/gcp.json
```

---

## Run

### Make targets

```bash
make -f docker/Makefile blast
make -f docker/Makefile kraken2
make -f docker/Makefile minimap2
make -f docker/Makefile bowtie2
make -f docker/Makefile versions
```

### Docker run

```bash
docker run --rm \
  -v "$(pwd)/docker/config:/config:ro" \
  -v "$(pwd)/docker/data:/data" \
  -v "/data/local-indexes:/references:ro" \
  --env-file docker/.env \
  nexus-cloud-genomics:latest \
  blast --config /config/blast.json
```

### Docker Compose

```bash
docker compose -f docker/docker-compose.yml run --rm nexus-cloud \
  minimap2 --config /config/minimap2.json --pool-workers 4
```

### Entrypoint commands

| Command | Description |
|---------|-------------|
| `blast` | Run `python -m nexus_cloud.blast` |
| `kraken2` | Run `python -m nexus_cloud.kraken2` |
| `minimap2` | Run `python -m nexus_cloud.minimap2` |
| `bowtie2` | Run `python -m nexus_cloud.bowtie2` |
| `versions` | Print tool and package versions |
| `shell` | Interactive bash session |
| `help` | Usage summary |

---

## Local indexes and references

Mount host paths into `/references` and reference them in config:

```json
{
  "blast": { "db_path": "/references/blastdb/nt" },
  "kraken2": { "db_path": "/references/kraken2/pluspf" },
  "minimap2": { "reference_path": "/references/genome.fa" },
  "bowtie2": { "index_path": "/references/bowtie2/genome" }
}
```

```bash
-v /mnt/genomics-indexes:/references:ro
```

Large databases (NCBI `nt`, Kraken2 PlusPF) should be pre-staged on the host or a shared volume — not downloaded into the container on every run.

---

## Cloud deployment patterns

### AWS Batch / ECS

1. Push image to ECR.
2. Mount FSx or EFS for `/references` if indexes are shared.
3. Use task IAM role for S3 access (omit keys from config).
4. Pass config via S3 download in entrypoint wrapper, or mount from Secrets Manager.

Example task command:

```json
["blast", "--config", "/config/blast.json"]
```

### GCP Cloud Run / Batch

1. Push to Artifact Registry.
2. Mount Cloud Storage FUSE for indexes at `/references`.
3. Use workload identity; set `credentials_path` only if using a service account key file.

### Azure Container Instances

1. Push to ACR.
2. Set `AZURE_STORAGE_CONNECTION_STRING` in container env.
3. Mount Azure Files for shared indexes.

---

## Volumes

| Mount | Purpose |
|-------|---------|
| `/config` | Run JSON/YAML configs (read-only recommended) |
| `/data` | Scratch / local staging |
| `/references` | BLAST DBs, Kraken2 DBs, Bowtie2 indexes, reference FASTAs |

---

## Verify installation

```bash
docker run --rm nexus-cloud-genomics:latest versions
```

Expected output includes `nexus-cloud 0.3.0` and version lines for `blastn`, `kraken2`, `minimap2`, `bowtie2`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `boto3 is required` | Rebuild image; ensure `pip install ".[all]"` step succeeded |
| Config not found | Mount `docker/config` to `/config`; use `/config/blast.json` path |
| Database not found | Mount indexes at `/references` or use cloud `db_path` prefix |
| Permission denied on cloud | Check `.env`, IAM role, or bucket policy |
| Slow first build | bioconda solve can take several minutes — normal |

---

## Related docs

- [Nexus Cloud Genomics Tools](nexus-cloud-genomics-tools.md)
- [Nexus Cloud BLAST](nexus-cloud-blast.md)

---

## Contact

**Intechgambit LLC** — developers@intechgambit.com
