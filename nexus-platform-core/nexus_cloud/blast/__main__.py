"""Allow `python -m nexus_cloud.blast` invocation."""

from nexus_cloud.blast.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
