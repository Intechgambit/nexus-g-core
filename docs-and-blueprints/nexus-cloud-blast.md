# Nexus Cloud BLAST Package

**Author:** Amina Jackson, Intechgambit  
**License:** GPL-3.0  
**Location:** `nexus-platform-core/nexus_cloud`

Nexus Cloud runs NCBI BLAST+ against query sequences in cloud object storage and writes results back. All cloud credentials, BLAST parameters, and batch jobs are configured through a single **config file** — no long CLI flag lists required.

> See also: [Nexus Cloud Genomics Tools](nexus-cloud-genomics-tools.md) for Kraken2, Minimap2, and Bowtie2 modules sharing the same config pattern.

---

## Quick Start (Config File)

1. Copy the example config:

```bash
cp nexus-platform-core/nexus_cloud/config.example.json my-blast-run.json
```

2. Edit `cloud`, `blast`, and `run` sections (see [Config Reference](#config-reference)).

3. Run:

```bash
cd nexus-platform-core
pip install -e ".[all]"

python -m nexus_cloud.blast --config my-blast-run.json
```

**`--config` is required.** All parameters are read from the config file. CLI flags only override config values:


```bash
python -m nexus_cloud.blast --config my-blast-run.json --pool-workers 8 --evalue 1e-10
```

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         NexusCloudConfig            │
                    │  (config.json / config.yaml)        │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
       ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
       │   Cloud     │     │    BLAST    │     │    Run      │
       │  provider   │     │  parameters │     │ pool_workers│
       │ + creds     │     │ + db_path   │     │ + jobs[]    │
       └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
              │                   │                   │
              └───────────────────┼───────────────────┘
                                  ▼
                         ┌─────────────────┐
                         │   BlastRunner   │
                         │  Process Pool   │
                         └────────┬────────┘
                                  │
                    read ◄────────┼────────► upload
                                  ▼
                         ┌─────────────────┐
                         │  Cloud Storage  │
                         └─────────────────┘
```

| Module | Path | Purpose |
|--------|------|---------|
| `NexusCloudConfig` | `nexus_cloud/config.py` | Load and validate config files |
| `BlastRunner` | `nexus_cloud/blast/runner.py` | BLAST execution + parallel batch runs |
| `AwsBucketStorage` | `nexus_cloud/storage/aws_bucket.py` | S3 read/upload |
| `GcpBucketStorage` | `nexus_cloud/storage/gcp_bucket.py` | GCS read/upload |
| `AzureBlobStorage` | `nexus_cloud/storage/azure_blob.py` | Azure Blob read/upload |

---

## Prerequisites

1. **NCBI BLAST+** in `PATH` (`blastn`, `blastp`, etc.)
2. **Python 3.10+**
3. **Provider SDK** (install as extras):

```bash
pip install -e ".[all]"    # aws + gcp + azure
pip install -e ".[aws]"
pip install pyyaml         # optional, for .yaml configs
```

---

## Config Reference

Config files use JSON (`.json`) or YAML (`.yaml`, `.yml`). Three top-level sections are required:

### `cloud` — storage provider

| Field | Required | Description |
|-------|----------|-------------|
| `provider` | yes | `aws`, `gcp`, or `azure` |
| `bucket_path` | yes | Bucket/container URI with optional prefix |
| `credentials` | no | Provider-specific credentials (see below) |

### `blast` — BLAST parameters

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `db_path` | yes | — | Local path or cloud key prefix to BLAST database |
| `program` | no | `blastn` | `blastn`, `blastp`, `blastx`, `tblastn`, `tblastx` |
| `evalue` | no | `1e-5` | E-value threshold |
| `word_size` | no | `16` | Word size for seeding |
| `num_threads` | no | `4` | Threads **per BLAST process** |
| `outfmt` | no | tabular fmt 6 | BLAST output format string |
| `extra_args` | no | `[]` | Extra BLAST flags, e.g. `["-max_target_seqs","10"]` |

### `run` — jobs and parallelism

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `pool_workers` | no | `1` | Number of **parallel BLAST jobs** (process pool) |
| `jobs` | yes* | — | List of `{input, output}` pairs |
| `input` / `output` | yes* | — | Single-job shorthand (alternative to `jobs`) |

\* Provide either `jobs` array or single `input` + `output`.

### Example config (batch run)

```json
{
  "cloud": {
    "provider": "aws",
    "bucket_path": "s3://my-bucket/genomics",
    "credentials": {
      "aws_access_key_id": "YOUR_ACCESS_KEY",
      "aws_secret_access_key": "YOUR_SECRET_KEY",
      "region_name": "us-east-1"
    }
  },
  "blast": {
    "db_path": "/data/blastdb/nt",
    "program": "blastn",
    "evalue": 1e-5,
    "word_size": 16,
    "num_threads": 4,
    "extra_args": ["-max_target_seqs", "10"]
  },
  "run": {
    "pool_workers": 4,
    "jobs": [
      {"input": "queries/sample1.fasta", "output": "results/sample1_blast.tsv"},
      {"input": "queries/sample2.fasta", "output": "results/sample2_blast.tsv"},
      {"input": "queries/sample3.fasta", "output": "results/sample3_blast.tsv"}
    ]
  }
}
```

A full copyable template lives at `nexus-platform-core/nexus_cloud/config.example.json`.

### Single-job config

```json
{
  "cloud": {
    "provider": "gcp",
    "bucket_path": "gs://my-bucket/genomics",
    "credentials": {
      "credentials_path": "/path/to/service-account.json"
    }
  },
  "blast": {
    "db_path": "/data/blastdb/nt"
  },
  "run": {
    "input": "queries/sample.fasta",
    "output": "results/sample_blast.tsv"
  }
}
```

---

## Parallel BLAST (Pool Workers)

High-volume runs process multiple queries concurrently via a **process pool**:

- `run.pool_workers` controls how many BLAST jobs run in parallel.
- `blast.num_threads` controls threads **inside each** BLAST process.
- The BLAST database is staged **once** and shared across all workers.

**Sizing guidance:** On a machine with 16 cores, a common pattern is:

```json
"blast": { "num_threads": 4 },
"run":   { "pool_workers": 4 }
```

This runs 4 BLAST processes × 4 threads = 16 cores utilized.

```bash
# 8 parallel jobs, override config at runtime
python -m nexus_cloud.blast --config my-blast-run.json --pool-workers 8
```

Batch output:

```
OK  queries/sample1.fasta -> s3://my-bucket/genomics/results/sample1_blast.tsv
OK  queries/sample2.fasta -> s3://my-bucket/genomics/results/sample2_blast.tsv
Batch complete: 2 succeeded, 0 failed
```

---

## Cloud Credentials by Provider

### AWS S3

```json
"cloud": {
  "provider": "aws",
  "bucket_path": "s3://my-bucket/genomics",
  "credentials": {
    "aws_access_key_id": "...",
    "aws_secret_access_key": "...",
    "aws_session_token": "...",
    "region_name": "us-east-1",
    "profile_name": "my-profile"
  }
}
```

Credentials are optional when using IAM roles or AWS profiles.

### Google Cloud Storage

```json
"cloud": {
  "provider": "gcp",
  "bucket_path": "gs://my-bucket/genomics",
  "credentials": {
    "credentials_path": "/path/to/service-account.json",
    "project_id": "my-project"
  }
}
```

Omit `credentials_path` to use Application Default Credentials.

### Azure Blob Storage

```json
"cloud": {
  "provider": "azure",
  "bucket_path": "my-container/genomics",
  "credentials": {
    "connection_string": "DefaultEndpointsProtocol=https;..."
  }
}
```

Or use `account_name` + `account_key` + optional `account_url`.

---

## Python API

### Config-driven

```python
from nexus_cloud import BlastRunner, NexusCloudConfig

config = NexusCloudConfig.from_file("my-blast-run.json")
runner = BlastRunner(config.to_storage(), config.blast)

jobs = [(j.input_key, j.output_key) for j in config.run.jobs]
results = runner.run_batch(jobs, pool_workers=config.run.pool_workers)

for r in results:
    print(r.input_key, r.remote_uri if r.success else r.error)
```

### Programmatic (no config file)

```python
from nexus_cloud import AwsBucketStorage, BlastConfig, BlastRunner

storage = AwsBucketStorage("s3://my-bucket/genomics", credentials={...})
config = BlastConfig(db_path="/data/blastdb/nt", num_threads=4)

runner = BlastRunner(storage, config)
runner.run("queries/sample.fasta", "results/sample_blast.tsv")

# Or batch
jobs = [
    ("queries/a.fasta", "results/a.tsv"),
    ("queries/b.fasta", "results/b.tsv"),
]
runner.run_batch(jobs, pool_workers=4)
```

### Storage modules independently

```python
from nexus_cloud import GcpBucketStorage

storage = GcpBucketStorage(
    bucket_path="gs://my-bucket/data",
    credentials={"credentials_path": "/path/to/key.json"},
)
storage.read("input/reads.fasta", "/tmp/reads.fasta")
storage.upload("/tmp/report.tsv", "output/report.tsv")
```

---

## Database Handling

`blast.db_path` accepts:

1. **Local path** — BLAST database prefix on the compute node (recommended for large DBs like `nt`)
2. **Cloud key prefix** — index files (`.nhr/.nin/.nsq` etc.) are downloaded once before the batch run

---

## CLI Reference (flags override config)

| Flag | Config path | Description |
|------|-------------|-------------|
| `--config`, `-c` | — | Path to JSON/YAML config file |
| `--provider` | `cloud.provider` | Cloud provider |
| `--bucket-path` | `cloud.bucket_path` | Bucket/container path |
| `--input` | `run.input` | Single job input key |
| `--output` | `run.output` | Single job output key |
| `--db-path` | `blast.db_path` | BLAST database prefix |
| `--evalue` | `blast.evalue` | E-value threshold |
| `--word-size` | `blast.word_size` | Word size |
| `--num-threads` | `blast.num_threads` | Threads per BLAST job |
| `--pool-workers` | `run.pool_workers` | Parallel job count |
| `--program` | `blast.program` | BLAST program |
| `--outfmt` | `blast.outfmt` | Output format |
| `--extra-args` | `blast.extra_args` | JSON array of extra flags |

Provider credential flags (`--aws-access-key-id`, `--credentials-path`, `--connection-string`, etc.) map into `cloud.credentials` when used with `--config`.

---

## Integration with Nexus-G Pipelines

Workflow manifests can reference a config file path. Secrets (cloud credentials) should be injected at runtime via environment-specific config overlays or a secrets manager, keeping credential values out of version control.

Typical pipeline step:

1. Stage queries to cloud storage
2. Run `python -m nexus_cloud.blast --config pipeline/blast-config.json`
3. Consume uploaded TSV results in downstream reporting

---

## Troubleshooting

| Issue | Resolution |
|-------|------------|
| `blastn not found in PATH` | Install NCBI BLAST+ |
| `cloud.provider is required` | Add `cloud` section to config |
| `blast.db_path is required` | Add `blast.db_path` to config |
| `run.jobs or run.input/run.output is required` | Define jobs in `run` section |
| Provider SDK import error | `pip install -e ".[aws]"` (or gcp/azure) |
| YAML config fails | `pip install pyyaml` |
| Slow batch runs | Increase `pool_workers`; balance with `num_threads` |
| Database not found | Verify local path or cloud index files at prefix |

---

## Contact

**Intechgambit LLC** — developers@intechgambit.com
