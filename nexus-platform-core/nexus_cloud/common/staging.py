"""Cloud index and reference staging helpers."""

from __future__ import annotations

import tempfile
from pathlib import Path

from nexus_cloud.storage.base import CloudStorage


def stage_index_files(
    storage: CloudStorage,
    index_path: str,
    work_dir: Path,
    suffixes: list[str],
    subdir: str = "index",
) -> str:
    """
    Resolve a local index prefix or download index files from cloud storage.

    Returns the local path prefix usable by the aligner/classifier.
    """
    local_candidate = Path(index_path)
    if local_candidate.exists():
        return str(local_candidate)

    stage_dir = work_dir / subdir
    stage_dir.mkdir(parents=True, exist_ok=True)
    prefix = index_path.rstrip("/")
    base_name = Path(prefix).name or "index"

    downloaded = 0
    for suffix in suffixes:
        key = f"{prefix}{suffix}"
        try:
            storage.read(key, stage_dir / f"{base_name}{suffix}")
            downloaded += 1
        except Exception:
            continue

    staged = stage_dir / base_name
    if downloaded == 0:
        raise FileNotFoundError(
            f"Index not found locally or in cloud at prefix: {prefix}"
        )
    return str(staged)


def stage_directory(
    storage: CloudStorage,
    cloud_prefix: str,
    work_dir: Path,
    required_files: list[str],
    subdir: str = "staged",
) -> Path:
    """Download a set of required files under a cloud prefix into a local directory."""
    stage_dir = work_dir / subdir
    stage_dir.mkdir(parents=True, exist_ok=True)
    prefix = cloud_prefix.rstrip("/")

    found = 0
    for filename in required_files:
        key = f"{prefix}/{filename}".replace("//", "/")
        try:
            storage.read(key, stage_dir / filename)
            found += 1
        except Exception:
            continue

    if found == 0:
        raise FileNotFoundError(
            f"No required files found in cloud at prefix: {prefix}"
        )
    return stage_dir


def stage_reference(
    storage: CloudStorage,
    reference_path: str,
    work_dir: Path,
) -> str:
    """Stage a single reference FASTA from local disk or cloud object key."""
    local_candidate = Path(reference_path)
    if local_candidate.is_file():
        return str(local_candidate)

    dest = work_dir / "reference.fa"
    storage.read(reference_path, dest)
    return str(dest)


def stage_db_temp(
    storage: CloudStorage,
    db_path: str,
    suffixes: list[str],
    temp_prefix: str,
) -> tuple[str, tempfile.TemporaryDirectory | None]:
    """Stage an index once for shared use across batch workers."""
    if Path(db_path).exists():
        return db_path, None

    temp = tempfile.TemporaryDirectory(prefix=temp_prefix)
    local_prefix = stage_index_files(
        storage, db_path, Path(temp.name), suffixes
    )
    return local_prefix, temp
