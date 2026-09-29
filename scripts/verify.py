#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "README.zh-CN.md",
    "AGENTS.md",
    "hooks.json",
    "hooks/git-guard.js",
    "hooks/README.md",
    "knowledge/README.md",
    "config/config.example.json",
    "config/mcp_config.example.json",
    "config/cli-settings.example.json",
    "docs/public-private-boundary.md",
    "docs/private-repo-setup.md",
    "docs/relationship-map.md",
    "scripts/install.py",
    "scripts/verify.py",
    ".github/workflows/validate.yml",
    ".gitignore",
    ".gitattributes",
    "LICENSE",
    "NOTICE",
    "CONTRIBUTING.md",
    "SECURITY.md",
]

JSON_FILES = [
    "hooks.json",
    "config/config.example.json",
    "config/mcp_config.example.json",
    "config/cli-settings.example.json",
]

FORBIDDEN_PATH_PARTS = {
    "projects",
    "conversations",
    "brain",
    "crashes",
    "cache",
    "backups",
}

FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".pem", ".key", ".p12", ".pfx", ".log", ".pb", ".pbtxt"}

SECRET_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "Google API key"),
    (re.compile(r"ya29\.[0-9A-Za-z\-_]+"), "Google OAuth access token"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"), "Anthropic key"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI-style key"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "GitHub PAT"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained PAT"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
    (
        re.compile(r'"(?:password|secret|token|api[_-]?key)"\s*:\s*"(?!<SET_LOCALLY>|__|\$\{|<)[^"]{6,}"', re.I),
        "credential-looking JSON value",
    ),
]


def fail(message: str) -> None:
    raise SystemExit(f"verify failed: {message}")


def main() -> None:
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            fail(f"missing required file: {rel}")

    for jrel in JSON_FILES:
        try:
            json.loads((ROOT / jrel).read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"invalid JSON in {jrel}: {exc}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    zh = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    for phrase in [
        "Public-safe template",
        "private antigravity-user-config",
        "python -B scripts/verify.py",
        "Independent Template Context",
    ]:
        if phrase not in readme:
            fail(f"README.md missing phrase: {phrase}")
    for phrase in [
        "公开安全模板",
        "private antigravity-user-config",
        "python -B scripts/verify.py",
        "独立模板定位",
    ]:
        if phrase not in zh:
            fail(f"README.zh-CN.md missing phrase: {phrase}")

    for path in ROOT.rglob("*"):
        if ".git" in path.parts or "__pycache__" in path.parts or path.is_dir():
            continue
        rel = path.relative_to(ROOT)
        rel_posix = rel.as_posix()
        if any(part in FORBIDDEN_PATH_PARTS for part in rel.parts):
            fail(f"private runtime path is not allowed in template: {rel_posix}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            fail(f"private/runtime-like file type is not allowed: {rel_posix}")
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                fail(f"possible secret [{label}] in {rel_posix}")

    print("antigravity-user-config-template verification passed")


if __name__ == "__main__":
    main()
