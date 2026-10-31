"""供校验和备份复用的本地数据边界检查。"""
from __future__ import annotations

import re
from pathlib import Path


SECRET_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"), "Google API key"),
    (re.compile(r"ya29\.[0-9A-Za-z\-_]+"), "Google OAuth access token"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"), "Anthropic key"),
    (re.compile(r"sk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{20,}"), "OpenAI-style key"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "GitHub PAT"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "GitHub fine-grained PAT"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), "JWT"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
    (re.compile(r'"(?:password|secret|token|api[_-]?key)"\s*:\s*"(?!<|__|\$\{)[^"]{6,}"', re.I), "credential-looking JSON value"),
    (re.compile(r"Bearer\s+(?!<|__|\$\{)[A-Za-z0-9_.\-]{20,}", re.I), "Bearer credential"),
]


def secret_labels(text: str) -> list[str]:
    return [label for pattern, label in SECRET_PATTERNS if pattern.search(text)]


def scan_files(files: dict[str, Path]) -> list[str]:
    """仅返回文件名和类别，凭证片段始终留在本机文件内。"""
    hits = []
    for name, path in sorted(files.items()):
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits.extend(f"{name}: [{label}]" for label in secret_labels(text))
    return hits


def is_template_repo(repo: Path) -> bool:
    return repo.name.endswith("-template") or (repo / "docs/public-private-boundary.md").exists()


def require_contained(path: Path, root: Path) -> None:
    """拒绝通过符号链接或目录联接访问同步边界之外的文件。"""
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes sync root: {path.name}")
