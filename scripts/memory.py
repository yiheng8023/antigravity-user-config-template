#!/usr/bin/env python3
"""Sync Antigravity progressive-disclosure global memory (~/.gemini/config/memory/ <-> repo/memory/).

Usage:
  python -B scripts/memory.py --backup            # copy live ~/.gemini/config/memory/*.md -> repo/memory/
  python -B scripts/memory.py --restore           # copy repo/memory/*.md -> live ~/.gemini/config/memory/
  python -B scripts/memory.py --status            # compare live vs repo memory files
  python -B scripts/memory.py --backup --dry-run  # preview without writing
"""
from __future__ import annotations

import filecmp
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REPO_MEM = REPO / "memory"
LIVE_MEM = Path.home() / ".gemini" / "config" / "memory"
DRY = "--dry-run" in sys.argv[1:]

SECRET_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "Google API key"),
    (re.compile(r"ya29\.[0-9A-Za-z\-_]+"), "Google OAuth access token"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"), "Anthropic key"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI-style key"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "GitHub PAT"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained PAT"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), "JWT"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
]


def _scan_secrets(folder: Path) -> list[str]:
    hits: list[str] = []
    if not folder.exists():
        return hits
    for f in sorted(folder.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        for pat, label in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                hits.append(f"{f.name}: [{label}] {m.group(0)[:14]}...")
    return hits


def _md_files(folder: Path, ignore_readme: bool = False) -> dict[str, Path]:
    if not folder.exists():
        return {}
    return {
        f.name: f
        for f in sorted(folder.glob("*.md"))
        if f.is_file() and not (ignore_readme and f.name == "README.md")
    }


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
    if direction == "backup":
        for name, target in dst_files.items():
            if name not in src_files:
                if not DRY:
                    target.unlink()
                print(f"  {tag}pruned stale in repo: {name}")
                removed += 1

    print(
        f"{tag}{direction.capitalize()} complete: {copied} updated, "
        f"{len(src_files) - copied} unchanged"
        + (f", {removed} pruned" if removed else "")
        + f" ({dst})"
    )


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    if len(args) != 1 or args[0] not in ("--backup", "--restore", "--status"):
        print(__doc__.strip())
        sys.exit(1)
    cmd = args[0]
    if cmd == "--status":
        status()
    elif cmd == "--backup":
        sync(LIVE_MEM, REPO_MEM, "backup", ignore_readme=True)
    elif cmd == "--restore":
        sync(REPO_MEM, LIVE_MEM, "restore", ignore_readme=True)


if __name__ == "__main__":
    main()
