# GIAT Local BLAST Run

**Author:** Amina Jackson, Intechgambit  
**License:** GPL-3.0  
**Location:** `giat-analytics-engine`

Config-driven local NCBI BLAST+ runs — same parameter model as Nexus Cloud BLAST, without cloud storage.

---

## Quick start

```bash
cd giat-analytics-engine
cp configs/blast.example.json my-blast.json
# edit db_path, jobs, blast parameters

python ncbi_blast_run.py --config my-blast.json
```

Optional overrides (all primary values still come from config):

```bash
python ncbi_blast_run.py --config my-blast.json --pool-workers 8 --evalue 1e-10
```

---

## Config reference

### `blast`

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `db_path` | yes | — | Local BLAST database prefix |
| `program` | no | `blastn` | BLAST program |
| `evalue` | no | `1e-5` | E-value threshold |
| `word_size` | no | `16` | Word size |
| `num_threads` | no | `4` | Threads per BLAST process |
| `outfmt` | no | tabular fmt 6 | Output format |
| `extra_args` | no | `[]` | Extra BLAST flags |

### `run`

| Field | Default | Description |
|-------|---------|-------------|
| `pool_workers` | `1` | Parallel BLAST jobs |
| `jobs` | — | `{input, output}` local file paths |

Example: `giat-analytics-engine/configs/blast.example.json`

---

## Related

- [Nexus Cloud BLAST](nexus-cloud-blast.md) — cloud I/O variant
- `ncbi_blast_db_setup.py` — build or download BLAST databases
