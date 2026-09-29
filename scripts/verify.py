#!/usr/bin/env python3
"""Verify repo structure, JSON validity, and scan committed text for accidental secrets."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

EXPECTED = [
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
    for rel in EXPECTED:
        if not (REPO / rel).exists():
            errs.append(f"missing: {rel}")

    if not ((REPO / "memory" / "MEMORY.md").exists() or (REPO / "memory" / "README.md").exists()):
        errs.append("missing: memory/MEMORY.md or memory/README.md")

    for jrel in JSON_FILES:
        jpath = REPO / jrel
        if jpath.exists():
            try:
                json.loads(jpath.read_text(encoding="utf-8"))
            except Exception as exc:
                errs.append(f"invalid JSON in {jrel}: {exc}")

    for meta in (REPO / "knowledge").glob("*/metadata.json"):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            if not isinstance(data.get("title"), str) or not isinstance(data.get("summary"), str):
                errs.append(f"missing title/summary in {meta.relative_to(REPO)}")
        except Exception as exc:
            errs.append(f"invalid JSON in {meta.relative_to(REPO)}: {exc}")

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
    print("Validation passed.")


if __name__ == "__main__":
    main()
