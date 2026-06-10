#!/usr/bin/env bash
set -euo pipefail

print_help() {
  cat <<'EOF'
Nexus Cloud Genomics Container
BLAST | Kraken2 | Minimap2 | Bowtie2 with AWS, GCP, and Azure I/O

Usage:
  docker run --rm -v $(pwd)/config:/config nexus-cloud-genomics blast --config /config/blast.json
  docker run --rm -v $(pwd)/config:/config nexus-cloud-genomics kraken2 --config /config/kraken2.json
  docker run --rm -v $(pwd)/config:/config nexus-cloud-genomics minimap2 --config /config/minimap2.json
  docker run --rm -v $(pwd)/config:/config nexus-cloud-genomics bowtie2 --config /config/bowtie2.json

Commands:
  blast       Run NCBI BLAST+ via nexus_cloud.blast
  kraken2     Run Kraken2 via nexus_cloud.kraken2
  minimap2    Run Minimap2 via nexus_cloud.minimap2
  bowtie2     Run Bowtie2 via nexus_cloud.bowtie2
  versions    Print installed tool versions
  shell       Open an interactive shell
  help        Show this message

Environment:
  NEXUS_CONFIG_DIR  Default config mount path (default: /config)
  NEXUS_DATA_DIR    Default data mount path (default: /data)

Installed CLIs:
  nexus-cloud-blast, nexus-cloud-kraken2, nexus-cloud-minimap2, nexus-cloud-bowtie2
EOF
}

print_versions() {
  echo "=== Nexus Cloud tool versions ==="
  python -c "import nexus_cloud; print(f'nexus-cloud {nexus_cloud.__version__}')"
  for tool in blastn kraken2 minimap2 bowtie2; do
    if command -v "$tool" >/dev/null 2>&1; then
      "$tool" --version 2>&1 | head -1 || true
    else
      echo "$tool: not found"
    fi
  done
}

if [[ $# -eq 0 ]]; then
  print_help
  exit 0
fi

cmd="$1"
shift

case "$cmd" in
  blast)
    exec python -m nexus_cloud.blast "$@"
    ;;
  kraken2)
    exec python -m nexus_cloud.kraken2 "$@"
    ;;
  minimap2)
    exec python -m nexus_cloud.minimap2 "$@"
    ;;
  bowtie2)
    exec python -m nexus_cloud.bowtie2 "$@"
    ;;
  versions)
    print_versions
    ;;
  shell|bash)
    exec /bin/bash "$@"
    ;;
  help|--help|-h)
    print_help
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    echo "Run 'help' for usage." >&2
    exit 1
    ;;
esac
