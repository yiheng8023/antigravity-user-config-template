#!/usr/bin/env python3
"""Prune temporary process artifacts, stale caches, and obsolete files.
Cross-platform (Windows / macOS / Linux). Zero third-party dependencies.

Usage:
  python -B scripts/clean.py                 # prune repo temporary artifacts
  python -B scripts/clean.py --runtime       # prune repo and crash logs older than seven days; preserve scratch, media and backups
  python -B scripts/clean.py --dry-run       # preview items to be cleaned without deleting
  python -B scripts/clean.py --verbose       # list every individual removed file
"""
from __future__ import annotations

import shutil
import time
import sys
from pathlib import Path

from safety import require_contained

REPO = Path(__file__).resolve().parent.parent
HOME = Path.home()
GEMINI_DIR = HOME / ".gemini"
DRY = "--dry-run" in sys.argv[1:]
CLEAN_RUNTIME = "--runtime" in sys.argv[1:]
VERBOSE = "--verbose" in sys.argv[1:]

TEMP_FILE_EXTENSIONS = {
    ".tmp",
    ".temp",
    ".bak",
    ".pyc",
    ".pyo",
    ".swp",
    ".swo",
    ".orig",
    ".rej",
}

TEMP_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
}

TEMP_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def _log(msg: str, count: int) -> None:
    if VERBOSE or count <= 15:
        print(msg)
    elif count == 16:
        print("  ... (additional items omitted; use --verbose to list all)")


def clean_repo(repo_dir: Path) -> tuple[int, int]:
    deleted_files = 0
    deleted_dirs = 0
    tag = "[dry-run] " if DRY else ""

    if not repo_dir.exists():
        return 0, 0

    # 1. Clean temp directories
    for p in sorted(repo_dir.rglob("*")):
        if not p.exists() or not p.is_dir() or ".git" in p.parts:
            continue
        if p.name in TEMP_DIR_NAMES:
            require_contained(p, repo_dir)
            if not DRY:
                shutil.rmtree(p, ignore_errors=True)
                if not p.exists():
                    deleted_dirs += 1
                    _log(f"  {tag}removed directory: {p.relative_to(repo_dir)}", deleted_files + deleted_dirs)
            else:
                deleted_dirs += 1
                _log(f"  {tag}removed directory: {p.relative_to(repo_dir)}", deleted_files + deleted_dirs)

    # 2. Clean temp files
    for p in sorted(repo_dir.rglob("*")):
        if not p.exists() or p.is_dir() or ".git" in p.parts:
            continue
        is_temp = (
            p.name in TEMP_FILE_NAMES
            or p.suffix.lower() in TEMP_FILE_EXTENSIONS
            or ".bak-" in p.name
            or p.name.endswith("~")
            or (p.name.startswith("#") and p.name.endswith("#"))
        )
        if is_temp:
            require_contained(p, repo_dir)
            if not DRY:
                try:
                    p.unlink()
                    deleted_files += 1
                    _log(f"  {tag}removed temp file:  {p.relative_to(repo_dir)}", deleted_files + deleted_dirs)
                except OSError:
                    pass
            else:
                deleted_files += 1
                _log(f"  {tag}removed temp file:  {p.relative_to(repo_dir)}", deleted_files + deleted_dirs)

    return deleted_files, deleted_dirs


def clean_runtime(gemini_dir: Path) -> tuple[int, int]:
    deleted_files = 0
    deleted_dirs = 0
    tag = "[dry-run] " if DRY else ""

    if not gemini_dir.exists():
        return 0, 0

    print(f"\nScanning Antigravity runtime environment ({gemini_dir})...")

    # 仅清理七天前的崩溃日志，保留备份、scratch、会话和媒体。
    crash_dirs = [
        gemini_dir / "antigravity" / "crashes",
        gemini_dir / "antigravity-cli" / "crashes",
    ]
    for c_dir in crash_dirs:
        if c_dir.exists() and c_dir.is_dir():
            for item in sorted(c_dir.iterdir()):
                if item.is_file() and not item.is_symlink() and item.stat().st_mtime < time.time() - 7 * 86400 and (item.name.startswith("crash_") or item.suffix.lower() in (".dmp", ".log", ".tmp")):
                    require_contained(item, gemini_dir)
                    if not DRY:
                        try:
                            item.unlink()
                            deleted_files += 1
                            _log(f"  {tag}pruned runtime crash log:    {item}", deleted_files + deleted_dirs)
                        except OSError:
                            pass
                    else:
                        deleted_files += 1
                        _log(f"  {tag}pruned runtime crash log:    {item}", deleted_files + deleted_dirs)
    return deleted_files, deleted_dirs


def main() -> None:
    allowed = {"--dry-run", "--runtime", "--verbose", "-h", "--help"}
    unknown = [a for a in sys.argv[1:] if a not in allowed]
    if unknown or "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print(__doc__.strip())
        sys.exit(0 if not unknown else 1)

    print(f"Cleaning repository artifacts: {REPO}" + (" [DRY RUN]" if DRY else ""))
    rf, rd = clean_repo(REPO)
    print(f"Repository clean finished: {rf} files removed, {rd} directories removed.")

    if CLEAN_RUNTIME:
        rt_f, rt_d = clean_runtime(GEMINI_DIR)
        print(f"Runtime clean finished: {rt_f} files removed, {rt_d} directories removed.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        sys.exit(f"Cleanup stopped: {exc}")
