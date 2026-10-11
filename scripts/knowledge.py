#!/usr/bin/env python3
"""Back up, restore, or check Antigravity knowledge items (~/.gemini/antigravity/knowledge/ & ~/.gemini/antigravity-cli/knowledge/).

Usage:
  python -B scripts/knowledge.py --status
  python -B scripts/knowledge.py --backup
  python -B scripts/knowledge.py --restore
  python -B scripts/knowledge.py --backup --dry-run
"""
from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPO_KNOWLEDGE = REPO / "knowledge"
LIVE_DESKTOP_KNOWLEDGE = Path.home() / ".gemini" / "antigravity" / "knowledge"
LIVE_CLI_KNOWLEDGE = Path.home() / ".gemini" / "antigravity-cli" / "knowledge"
DRY = "--dry-run" in sys.argv[1:]

SKIP_FILENAMES = {"README.md", "knowledge.lock"}
SKIP_SUFFIXES = {".lock", ".tmp"}


def _is_template_repo() -> bool:
    return REPO.name.endswith("-template") or (REPO / "docs" / "public-private-boundary.md").exists()


def _tree_files(src: Path) -> dict[str, Path]:
    res: dict[str, Path] = {}
    if not src.exists():
        return res
    for item in sorted(src.rglob("*")):
        if not item.is_file():
            continue
        if item.name in SKIP_FILENAMES or item.suffix in SKIP_SUFFIXES or item.name in (".DS_Store", "Thumbs.db"):
            continue
        rel = item.relative_to(src).as_posix()
        res[rel] = item
    return res


def status() -> None:
    print(f"Live desktop knowledge dir: {LIVE_DESKTOP_KNOWLEDGE}")
    print(f"Live CLI knowledge dir:     {LIVE_CLI_KNOWLEDGE}")
    print(f"Repo knowledge dir:         {REPO_KNOWLEDGE}")

    repo_files = _tree_files(REPO_KNOWLEDGE)
    desk_files = _tree_files(LIVE_DESKTOP_KNOWLEDGE)
    cli_files = _tree_files(LIVE_CLI_KNOWLEDGE)

    all_keys = sorted(set(repo_files) | set(desk_files) | set(cli_files))
    if not all_keys:
        print("  (no knowledge item files found)")
        return

    same = diff = missing = 0
    for k in all_keys:
        in_repo = k in repo_files
        in_desk = k in desk_files
        in_cli = k in cli_files
        if in_repo and in_desk and in_cli:
            cmp_desk = filecmp.cmp(repo_files[k], desk_files[k], shallow=False)
            cmp_cli = filecmp.cmp(repo_files[k], cli_files[k], shallow=False)
            if cmp_desk and cmp_cli:
                same += 1
            else:
                print(f"  ~ modified across tiers: {k}")
                diff += 1
        else:
            missing_tiers = []
            if not in_repo:
                missing_tiers.append("repo")
            if not in_desk:
                missing_tiers.append("desktop")
            if not in_cli:
                missing_tiers.append("cli")
            print(f"  ! missing in {','.join(missing_tiers)}: {k}")
            missing += 1

    print(f"Summary: {same} fully synchronized, {diff} modified, {missing} missing in some tiers.")


def copy_tree_contents(src: Path, dst: Path, ignore_readme: bool = False) -> int:
    if not src.exists():
        return 0
    count = 0
    for item in sorted(src.rglob("*")):
        if not item.is_file():
            continue
        if item.name in (".DS_Store", "Thumbs.db") or item.suffix in SKIP_SUFFIXES or item.name.endswith(".lock"):
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
    if len(args) != 1 or args[0] not in ("--backup", "--restore", "--status"):
        print(__doc__.strip())
        sys.exit(1)

    mode = args[0]
    tag = "[dry-run] " if DRY else ""
    if mode == "--status":
        status()
    elif mode == "--backup":
        if _is_template_repo():
            print("ABORT: Cannot run --backup in a template repository (public-safe boundary).")
            print("Real knowledge items must be backed up to your private repository only.")
            sys.exit(1)
        n = copy_tree_contents(LIVE_DESKTOP_KNOWLEDGE, REPO_KNOWLEDGE, ignore_readme=False)
        print(f"{tag}Backed up {n} file(s) from {LIVE_DESKTOP_KNOWLEDGE} -> {REPO_KNOWLEDGE}")
    else:
        n_desk = copy_tree_contents(REPO_KNOWLEDGE, LIVE_DESKTOP_KNOWLEDGE, ignore_readme=True)
        n_cli = copy_tree_contents(REPO_KNOWLEDGE, LIVE_CLI_KNOWLEDGE, ignore_readme=True)
        print(f"{tag}Restored {n_desk} file(s) -> {LIVE_DESKTOP_KNOWLEDGE} and {n_cli} file(s) -> {LIVE_CLI_KNOWLEDGE}")


if __name__ == "__main__":
    main()
