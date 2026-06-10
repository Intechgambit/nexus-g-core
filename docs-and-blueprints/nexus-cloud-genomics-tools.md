# Nexus Cloud Genomics Tools

**Author:** Amina Jackson, Intechgambit  
**License:** GPL-3.0  
**Location:** `nexus-platform-core/nexus_cloud`

Nexus Cloud provides config-driven, cloud-native wrappers for four core genomic tools used in Nexus-G pipelines. Each tool reads inputs from cloud storage, runs locally, and uploads results back — with **batch parallelism** via process pools.

| Tool | Module | Config section | Example config |
|------|--------|----------------|----------------|
| NCBI BLAST+ | `nexus_cloud.blast` | `blast` | `config.example.json` |
| Kraken2 | `nexus_cloud.kraken2` | `kraken2` | `config.kraken2.example.json` |
| Minimap2 | `nexus_cloud.minimap2` | `minimap2` | `config.minimap2.example.json` |
| Bowtie2 | `nexus_cloud.bowtie2` | `bowtie2` | `config.bowtie2.example.json` |

Detailed BLAST documentation: [nexus-cloud-blast.md](nexus-cloud-blast.md)

---

## Shared Config Structure

Every tool config file has three sections:

```json
{
  "cloud": { "provider": "aws", "bucket_path": "...", "credentials": {} },
  "<tool>": { "... tool parameters ..." },
  "run": { "pool_workers": 4, "jobs": [ { "input": "...", "output": "..." } ] }
}
```

### `cloud` (all tools)

| Field | Required | Description |
|-------|----------|-------------|
| `provider` | yes | `aws`, `gcp`, or `azure` |
| `bucket_path` | yes | Bucket/container URI with optional prefix |
| `credentials` | no | Provider-specific keys (see [BLAST doc](nexus-cloud-blast.md#cloud-credentials-by-provider)) |

### `run` (all tools)

| Field | Default | Description |
|-------|---------|-------------|
| `pool_workers` | `1` | Parallel jobs (process pool) |
| `jobs` | — | Array of input/output pairs |
| `input` / `output` | — | Single-job shorthand |

Jobs support optional fields:

| Field | Used by | Description |
|-------|---------|-------------|
| `input2` | Bowtie2 | R2 reads for paired-end mode |
| `report` | Kraken2 | Taxonomic report output key |

---

## Quick Start

**`--config` is required for every tool.** All parameters (`cloud`, tool section, `run`) are read from the config file. CLI flags only override config values.

```bash
cd nexus-platform-core
pip install -e ".[all]"

cp nexus_cloud/config.kraken2.example.json my-run.json
# edit cloud credentials, db_path, jobs

python -m nexus_cloud.kraken2 --config my-run.json
python -m nexus_cloud.kraken2 --config my-run.json --pool-workers 8
```

Local (non-cloud) BLAST: [giat-local-blast.md](giat-local-blast.md)

---

## Kraken2

Taxonomic classification against a Kraken2 database.

### Config (`kraken2` section)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `db_path` | yes | — | Local directory or cloud prefix with `hash.k2d`, `opts.k2d`, `taxo.k2d` |
| `confidence` | no | `0.0` | Confidence scoring threshold |
| `minimum_base_quality` | no | `0` | Minimum Phred quality for classification |
| `num_threads` | no | `4` | Threads per Kraken2 process |
| `extra_args` | no | `[]` | Additional CLI flags |

### Example

```json
{
  "cloud": {
    "provider": "aws",
    "bucket_path": "s3://my-bucket/genomics",
    "credentials": { "region_name": "us-east-1" }
  },
  "kraken2": {
    "db_path": "/data/kraken2/pluspf",
    "confidence": 0.0,
    "minimum_base_quality": 0,
    "num_threads": 4
  },
  "run": {
    "pool_workers": 4,
    "jobs": [
      {
        "input": "reads/sample1.fastq",
        "output": "results/sample1.kraken",
        "report": "results/sample1.report"
      }
    ]
  }
}
```

```bash
python -m nexus_cloud.kraken2 --config my-run.json
```

### Python API

```python
from nexus_cloud import Kraken2CloudConfig, Kraken2Runner

config = Kraken2CloudConfig.from_file("my-run.json")
runner = Kraken2Runner(config.to_storage(), config.kraken2)
results = runner.run_batch(config.run.jobs, pool_workers=config.run.pool_workers)
```

---

## Minimap2

Long-read and assembly alignment to a reference genome.

### Config (`minimap2` section)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `reference_path` | yes | — | Local or cloud reference FASTA |
| `preset` | no | `map-ont` | Minimap2 preset (`map-ont`, `map-hifi`, `map-pb`, `asm20`, etc.) |
| `num_threads` | no | `4` | Threads per alignment |
| `output_format` | no | `sam` | `sam` or `paf` |
| `extra_args` | no | `[]` | Additional CLI flags |

### Example

```json
{
  "minimap2": {
    "reference_path": "references/genome.fa",
    "preset": "map-ont",
    "num_threads": 4,
    "output_format": "sam"
  },
  "run": {
    "pool_workers": 4,
    "jobs": [
      { "input": "reads/sample1.fastq", "output": "alignments/sample1.sam" }
    ]
  }
}
```

```bash
python -m nexus_cloud.minimap2 --config my-run.json
```

### Python API

```python
from nexus_cloud import Minimap2CloudConfig, Minimap2Runner

config = Minimap2CloudConfig.from_file("my-run.json")
runner = Minimap2Runner(config.to_storage(), config.minimap2)
uri = runner.run("reads/sample.fastq", "alignments/sample.sam")
```

---

## Bowtie2

Short-read alignment to an indexed reference.

### Config (`bowtie2` section)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `index_path` | yes | — | Local or cloud Bowtie2 index prefix |
| `mode` | no | `single` | `single` (`-U`) or `paired` (`-1`/`-2`) |
| `num_threads` | no | `4` | Threads per alignment |
| `extra_args` | no | `[]` | Additional CLI flags |

### Example (paired-end)

```json
{
  "bowtie2": {
    "index_path": "/data/indexes/genome",
    "mode": "paired",
    "num_threads": 4
  },
  "run": {
    "pool_workers": 4,
    "jobs": [
      {
        "input": "reads/sample_R1.fastq",
        "input2": "reads/sample_R2.fastq",
        "output": "alignments/sample.sam"
      }
    ]
  }
}
```

```bash
python -m nexus_cloud.bowtie2 --config my-run.json
```

### Python API

```python
from nexus_cloud import Bowtie2CloudConfig, Bowtie2Runner

config = Bowtie2CloudConfig.from_file("my-run.json")
runner = Bowtie2Runner(config.to_storage(), config.bowtie2)
runner.run("reads/R1.fastq", "alignments/out.sam", input2_key="reads/R2.fastq")
```

---

## Parallel Execution

All four tools share the same parallelism model:

- **`run.pool_workers`** — number of concurrent jobs (process pool)
- **`<tool>.num_threads`** — threads inside each tool process
- **Indexes/references staged once** per batch run and shared across workers

On a 16-core node:

```json
"<tool>": { "num_threads": 4 },
"run":    { "pool_workers": 4 }
```

---

## CLI Entry Points

| Command | Installed script |
|---------|------------------|
| `python -m nexus_cloud.blast` | `nexus-cloud-blast` |
| `python -m nexus_cloud.kraken2` | `nexus-cloud-kraken2` |
| `python -m nexus_cloud.minimap2` | `nexus-cloud-minimap2` |
| `python -m nexus_cloud.bowtie2` | `nexus-cloud-bowtie2` |

All CLIs accept `--config` plus optional overrides for cloud, tool, and run parameters.

---

## Docker deployment

Run all tools from a single container:

```bash
cd nexus-platform-core
make -f docker/Makefile build
make -f docker/Makefile init-config
make -f docker/Makefile kraken2
```

Full guide: [nexus-cloud-docker.md](nexus-cloud-docker.md)

---

## Prerequisites

| Tool | Binary required in PATH |
|------|---------------------------|
| BLAST | `blastn`, `blastp`, etc. (BLAST+) |
| Kraken2 | `kraken2` |
| Minimap2 | `minimap2` |
| Bowtie2 | `bowtie2` |

Cloud SDKs: `pip install -e ".[all]"`

---

## Contact

**Intechgambit LLC** — developers@intechgambit.com
