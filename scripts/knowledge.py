#!/usr/bin/env python3
"""Back up or restore Antigravity knowledge items (~/.gemini/antigravity/knowledge/ & ~/.gemini/antigravity-cli/knowledge/).

Usage:
  python -B scripts/knowledge.py --backup
  python -B scripts/knowledge.py --restore
  python -B scripts/knowledge.py --backup --dry-run
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPO_KNOWLEDGE = REPO / "knowledge"
LIVE_DESKTOP_KNOWLEDGE = Path.home() / ".gemini" / "antigravity" / "knowledge"
LIVE_CLI_KNOWLEDGE = Path.home() / ".gemini" / "antigravity-cli" / "knowledge"
DRY = "--dry-run" in sys.argv[1:]


def copy_tree_contents(src: Path, dst: Path, ignore_readme: bool = False) -> int:
    if not src.exists():
        return 0
    count = 0
    for item in sorted(src.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(src)
        if ignore_readme and rel.as_posix() == "README.md":
            continue
        target = dst / rel
        if not DRY:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
        count += 1
    return count


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    if len(args) != 1 or args[0] not in ("--backup", "--restore"):
        print(__doc__.strip())
        sys.exit(1)

    mode = args[0]
    tag = "[dry-run] " if DRY else ""
    if mode == "--backup":
        n = copy_tree_contents(LIVE_DESKTOP_KNOWLEDGE, REPO_KNOWLEDGE, ignore_readme=False)
        print(f"{tag}Backed up {n} file(s) from {LIVE_DESKTOP_KNOWLEDGE} -> {REPO_KNOWLEDGE}")
    else:
        n_desk = copy_tree_contents(REPO_KNOWLEDGE, LIVE_DESKTOP_KNOWLEDGE, ignore_readme=True)
        n_cli = copy_tree_contents(REPO_KNOWLEDGE, LIVE_CLI_KNOWLEDGE, ignore_readme=True)
        print(f"{tag}Restored {n_desk} file(s) -> {LIVE_DESKTOP_KNOWLEDGE} and {n_cli} file(s) -> {LIVE_CLI_KNOWLEDGE}")


if __name__ == "__main__":
    main()
