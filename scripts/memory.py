#!/usr/bin/env python3
"""Sync Antigravity progressive-disclosure global memory (~/.gemini/config/memory/ <-> repo/memory/).

Usage:
  python -B scripts/memory.py --backup            # copy live ~/.gemini/config/memory/*.md -> repo/memory/
  python -B scripts/memory.py --restore           # copy repo/memory/*.md -> live ~/.gemini/config/memory/
  python -B scripts/memory.py --status            # compare live vs repo memory files
  python -B scripts/memory.py --backup --dry-run  # preview without writing
  python -B scripts/memory.py --restore --prune   # 显式删除目标中源快照未包含的记忆
"""
from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

from safety import is_template_repo, require_contained, scan_files

REPO = Path(__file__).resolve().parent.parent
REPO_MEM = REPO / "memory"
LIVE_MEM = Path.home() / ".gemini" / "config" / "memory"
DRY = "--dry-run" in sys.argv[1:]
PRUNE = "--prune" in sys.argv[1:]

def _scan_secrets(folder: Path) -> list[str]:
    return scan_files(_md_files(folder, ignore_readme=True))


def _md_files(folder: Path, ignore_readme: bool = False) -> dict[str, Path]:
    if not folder.exists():
        return {}
    files = {
        f.name: f
        for f in sorted(folder.glob("*.md"))
        if f.is_file() and not (ignore_readme and f.name == "README.md")
    }
    for path in files.values():
        require_contained(path, folder)
    return files


def status() -> None:
    print(f"Live memory dir: {LIVE_MEM}")
    print(f"Repo memory dir: {REPO_MEM}")
    live = _md_files(LIVE_MEM, ignore_readme=True)
    repo = _md_files(REPO_MEM, ignore_readme=True)
    all_names = sorted(set(live) | set(repo))
    if not all_names:
        print("  (no memory .md files in either location)")
        return
    same = only_live = only_repo = diff = 0
    for name in all_names:
        if name in live and name not in repo:
            print(f"  + only in live: {name}")
            only_live += 1
        elif name in repo and name not in live:
            print(f"  - only in repo: {name}")
            only_repo += 1
        elif filecmp.cmp(live[name], repo[name], shallow=False):
            same += 1
        else:
            print(f"  ~ differs:      {name}")
            diff += 1
    print(f"Summary: {same} identical, {diff} modified, {only_live} only-live, {only_repo} only-repo.")


def sync(src: Path, dst: Path, direction: str, ignore_readme: bool = False) -> None:
    tag = "[dry-run] " if DRY else ""
    if not src.exists():
        print(f"  ({src} does not exist — nothing to {direction})")
        return
    if direction == "backup":
        hits = _scan_secrets(src)
        if hits:
            print("ABORT — potential secrets detected in live memory files:")
            for h in hits:
                print(f"  ! {h}")
            sys.exit(1)

    src_files = _md_files(src, ignore_readme=ignore_readme)
    dst_files = _md_files(dst, ignore_readme=True)
    if not src_files:
        print(f"  (no memory files in {src} — nothing to {direction})")
        return

    for name in src_files:
        require_contained(dst / name, dst)

    if not DRY:
        dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name, f in src_files.items():
        target = dst / name
        if target.exists() and filecmp.cmp(f, target, shallow=False):
            continue
        if not DRY:
            shutil.copy2(f, target)
        print(f"  {tag}{direction}: {name}")
        copied += 1

    removed = 0
    for name, target in (dst_files.items() if PRUNE else []):
        if name not in src_files:
            if not DRY:
                target.unlink()
            print(f"  {tag}pruned stale in {direction} target: {name}")
            removed += 1

    print(
        f"{tag}{direction.capitalize()} complete: {copied} updated, "
        f"{len(src_files) - copied} unchanged"
        + (f", {removed} pruned" if removed else "")
        + f" ({dst})"
    )


def _is_template_repo() -> bool:
    return is_template_repo(REPO)


def main() -> None:
    args = [a for a in sys.argv[1:] if a not in ("--dry-run", "--prune")]
    if len(args) != 1 or args[0] not in ("--backup", "--restore", "--status"):
        print(__doc__.strip())
        sys.exit(1)
    cmd = args[0]
    if cmd == "--status":
        status()
    elif cmd == "--backup":
        if _is_template_repo():
            print("ABORT: Cannot run --backup in a template repository (public-safe boundary).")
            print("Real memory files must be backed up to your private repository only.")
            sys.exit(1)
        sync(LIVE_MEM, REPO_MEM, "backup", ignore_readme=True)
    elif cmd == "--restore":
        sync(REPO_MEM, LIVE_MEM, "restore", ignore_readme=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        sys.exit(f"Sync stopped: {exc}")
