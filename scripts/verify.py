#!/usr/bin/env python3
"""Verify repo structure, JSON validity, memory completeness, and scan committed text for accidental secrets."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def is_template_repo() -> bool:
    return REPO.name.endswith("-template") or (REPO / "docs" / "public-private-boundary.md").exists()


EXPECTED_BASE = [
    "AGENTS.md",
    "hooks.json",
    "hooks/git-guard.js",
    "knowledge/README.md",
    "config/config.example.json",
    "config/mcp_config.example.json",
    "config/cli-settings.example.json",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".github/workflows/validate.yml",
    "README.md",
    "README.zh-CN.md",
    "scripts/install.py",
    "scripts/verify.py",
    "scripts/memory.py",
    "scripts/knowledge.py",
]

EXPECTED_TEMPLATE = [
    "LICENSE",
    "NOTICE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "memory/README.md",
    "docs/public-private-boundary.md",
    "docs/private-repo-setup.md",
    "docs/relationship-map.md",
]

JSON_FILES = [
    "hooks.json",
    "config/config.example.json",
    "config/mcp_config.example.json",
    "config/cli-settings.example.json",
]

SECRET_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "Google API key"),
    (re.compile(r"ya29\.[0-9A-Za-z\-_]+"), "Google OAuth access token"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"), "Anthropic key"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI-style key"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "GitHub PAT"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained PAT"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), "JWT"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
    (
        re.compile(r'"(?:password|secret|token|api[_-]?key)"\s*:\s*"(?!<SET_LOCALLY>|__|\$\{|<)[^"]{6,}"', re.I),
        "credential-looking JSON value",
    ),
]

SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".ico", ".pdf", ".db", ".sqlite", ".pb"}


def main() -> None:
    errs: list[str] = []
    template_mode = is_template_repo()

    for rel in EXPECTED_BASE:
        if not (REPO / rel).exists():
            errs.append(f"missing: {rel}")

    if template_mode:
        for rel in EXPECTED_TEMPLATE:
            if not (REPO / rel).exists():
                errs.append(f"missing template file: {rel}")

        # Ensure no personal memory files leaked into template
        mem_dir = REPO / "memory"
        if mem_dir.exists():
            for f in mem_dir.glob("*.md"):
                if f.name != "README.md":
                    errs.append(f"Template repository must NOT contain personal memory file: {f.name}")

        # Ensure no personal knowledge items leaked into template
        k_dir = REPO / "knowledge"
        if k_dir.exists():
            for p in k_dir.iterdir():
                if p.is_dir() or (p.is_file() and p.name != "README.md"):
                    errs.append(f"Template repository must NOT contain personal knowledge item: {p.name}")

        # Ensure no personal identity or paths in AGENTS.md
        agents_path = REPO / "AGENTS.md"
        if agents_path.exists():
            agents_text = agents_path.read_text(encoding="utf-8")
            if "宋华" in agents_text or "15521" in agents_text or "yiheng8023" in agents_text:
                errs.append("Template AGENTS.md contains personal identity or private user path")
    else:
        # Private repo checks
        if not (REPO / "memory" / "MEMORY.md").exists():
            errs.append("missing: memory/MEMORY.md")
        else:
            # Cross-check that every memory/*.md is registered in MEMORY.md
            memory_md_text = (REPO / "memory" / "MEMORY.md").read_text(encoding="utf-8")
            for f in (REPO / "memory").glob("*.md"):
                if f.name in ("MEMORY.md", "README.md"):
                    continue
                if f.name not in memory_md_text:
                    errs.append(f"memory file {f.name} is not indexed in memory/MEMORY.md")

    # JSON syntax validation
    for jrel in JSON_FILES:
        jpath = REPO / jrel
        if jpath.exists():
            try:
                json.loads(jpath.read_text(encoding="utf-8"))
            except Exception as exc:
                errs.append(f"invalid JSON in {jrel}: {exc}")

    # Knowledge items metadata validation
    for meta in (REPO / "knowledge").glob("*/metadata.json"):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            if not isinstance(data.get("title"), str) or not isinstance(data.get("summary"), str):
                errs.append(f"missing title/summary in {meta.relative_to(REPO)}")
        except Exception as exc:
            errs.append(f"invalid JSON in {meta.relative_to(REPO)}: {exc}")

    # Check git-guard.js syntax via node --check
    guard_js = REPO / "hooks" / "git-guard.js"
    if guard_js.exists():
        try:
            res = subprocess.run(["node", "--check", str(guard_js)], capture_output=True, text=True)
            if res.returncode != 0:
                errs.append(f"JavaScript syntax error in hooks/git-guard.js: {res.stderr.strip()}")
        except FileNotFoundError:
            pass  # node not in PATH during CI step if node not installed; handled gracefully

    # Secret scanning
    for f in REPO.rglob("*"):
        if f.is_dir() or ".git" in f.parts or "__pycache__" in f.parts or f.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat, label in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                errs.append(f"possible secret [{label}] in {f.relative_to(REPO)}: {m.group(0)[:14]}...")

    if errs:
        print("Validation FAILED:")
        for e in errs:
            print("  - " + e)
        sys.exit(1)
    print(f"Validation passed ({'template' if template_mode else 'private'} mode).")


if __name__ == "__main__":
    main()
