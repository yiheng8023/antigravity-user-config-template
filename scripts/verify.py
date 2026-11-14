#!/usr/bin/env python3
"""Verify repo structure, JSON validity, memory completeness, and scan committed text for accidental secrets."""
from __future__ import annotations

import json
import os
import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

from safety import SECRET_PATTERNS, is_template_repo as template_repository

from install import read_object, validate_sections, validate_hooks, validate_cli_settings

REPO = Path(__file__).resolve().parent.parent


def is_template_repo() -> bool:
    return template_repository(REPO)


EXPECTED_BASE = [
    "AGENTS.md",
    "hooks.json",
    "hooks/git-guard.js",
    "hooks/README.md",
    "knowledge/README.md",
    "config/config.example.json",
    "config/mcp_config.example.json",
    "config/cli-settings.example.json",
    "config/config.turbo.example.json",
    "config/cli-settings.turbo.example.json",
    "config/README.md",
    "config/meta-guidance.json",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".github/workflows/validate.yml",
    "README.md",
    "README.zh-CN.md",
    "scripts/install.py",
    "scripts/safety.py",
    "tests/test_regressions.py",
    "scripts/verify.py",
    "scripts/memory.py",
    "scripts/knowledge.py",
    "scripts/clean.py",
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

FORBIDDEN_TEMPLATE_PARTS = {
    "projects",
    "conversations",
    "brain",
    "crashes",
    "cache",
    "backups",
}

FORBIDDEN_TEMPLATE_SUFFIXES = {
    ".db",
    ".sqlite",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".log",
    ".pb",
    ".pbtxt",
}

JSON_FILES = [
    "hooks.json",
    "config/config.example.json",
    "config/mcp_config.example.json",
    "config/cli-settings.example.json",
    "config/config.turbo.example.json",
    "config/cli-settings.turbo.example.json",
]

JSON_SECTIONS = {
    "config/config.example.json": {"plugins": dict, "userSettings": dict},
    "config/mcp_config.example.json": {"mcpServers": dict},
    "config/cli-settings.example.json": {"trustedWorkspaces": list},
    "config/config.turbo.example.json": {"plugins": dict, "userSettings": dict},
    "config/cli-settings.turbo.example.json": {"trustedWorkspaces": list},
}


SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".ico", ".pdf", ".db", ".sqlite", ".pb"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--guidance-source", type=Path, help="只读核验 YIYUAN-CALIBRATION 中的 AI 中文原文")
    args = parser.parse_args()
    errs: list[str] = []
    template_mode = is_template_repo()
    errs.extend(verify_guidance(REPO, args.guidance_source))

    for rel in EXPECTED_BASE:
        if not (REPO / rel).exists():
            errs.append(f"missing: {rel}")

    if template_mode:
        for rel in EXPECTED_TEMPLATE:
            if not (REPO / rel).exists():
                errs.append(f"missing template file: {rel}")

        # Required README phrasing checks
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        zh = (REPO / "README.zh-CN.md").read_text(encoding="utf-8")
        for phrase in [
            "Public-safe template",
            "private antigravity-user-config",
            "python -B scripts/verify.py",
            "Independent Template Context",
        ]:
            if phrase not in readme:
                errs.append(f"Template README.md missing phrase: {phrase}")
        for phrase in [
            "公开安全模板",
            "private antigravity-user-config",
            "python -B scripts/verify.py",
            "独立模板定位",
        ]:
            if phrase not in zh:
                errs.append(f"Template README.zh-CN.md missing phrase: {phrase}")

        # Ensure no personal memory files leaked into template
        mem_dir = REPO / "memory"
        if mem_dir.exists():
            for f in mem_dir.rglob("*"):
                if f.is_file() and f != mem_dir / "README.md":
                    errs.append(f"Template repository must NOT contain personal memory file: {f.name}")

        # Ensure no personal knowledge items leaked into template
        k_dir = REPO / "knowledge"
        if k_dir.exists():
            for p in k_dir.iterdir():
                if p.is_dir() or (p.is_file() and p.name != "README.md"):
                    errs.append(f"Template repository must NOT contain personal knowledge item: {p.name}")

        # Ensure no forbidden runtime paths or sensitive file types exist in template
        for path in REPO.rglob("*"):
            if ".git" in path.parts or "__pycache__" in path.parts or path.is_dir():
                continue
            rel = path.relative_to(REPO)
            if any(part in FORBIDDEN_TEMPLATE_PARTS for part in rel.parts):
                errs.append(f"Template contains forbidden runtime path: {rel.as_posix()}")
            if path.suffix.lower() in FORBIDDEN_TEMPLATE_SUFFIXES:
                errs.append(f"Template contains forbidden file type: {rel.as_posix()}")

        # Ensure no personal identity or paths in ANY file in template (excluding verify.py where checked)
        for path in REPO.rglob("*"):
            if ".git" in path.parts or "__pycache__" in path.parts or path.is_dir():
                continue
            rel = path.relative_to(REPO)
            if rel.as_posix() == "scripts/verify.py":
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if "宋华" in content:
                    errs.append(f"Template file {rel.as_posix()} contains personal identity [宋华]")
                if "15521" in content:
                    errs.append(f"Template file {rel.as_posix()} contains private user path [15521]")
                if rel.as_posix() == "AGENTS.md" and "yiheng8023" in content:
                    errs.append(f"Template AGENTS.md contains personal handle [yiheng8023]")
            except Exception:
                pass
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
            # Cross-check that every link in MEMORY.md resolves to an existing file (robust against anchors & path prefixes)
            for linked in re.findall(r"\]\((?:[^)\s#]*/)?([A-Za-z0-9._\-]+\.md)(?:#[^)\s]*)?\)", memory_md_text):
                if not (REPO / "memory" / linked).exists():
                    errs.append(f"memory/MEMORY.md references non-existent stale file: {linked}")
            # Cross-check that every memory link in AGENTS.md resolves to an existing file
            agents_text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
            mem_index_match = re.search(r"<!-- GLOBAL_MEMORY_START -->(.*?)<!-- GLOBAL_MEMORY_END -->", agents_text, re.DOTALL)
            if mem_index_match:
                mem_index_text = mem_index_match.group(1)
                for linked in re.findall(r"\]\((?:[^)\s#]*/)?([A-Za-z0-9._\-]+\.md)(?:#[^)\s]*)?\)", mem_index_text):
                    if not (REPO / "memory" / linked).exists():
                        errs.append(f"AGENTS.md Global Memory Index references non-existent stale file: {linked}")
            for linked in re.findall(r"\.gemini/config/memory/([A-Za-z0-9._\-]+\.md)", agents_text):
                if not (REPO / "memory" / linked).exists():
                    errs.append(f"AGENTS.md references non-existent stale memory file: {linked}")

    # Zero-leftover temporary artifact check across the repository
    temp_suffixes = {".tmp", ".temp", ".bak", ".swp", ".swo", ".pyc", ".pyo", ".orig", ".rej"}
    for path in REPO.rglob("*"):
        if ".git" in path.parts or "__pycache__" in path.parts or path.is_dir():
            continue
        if (
            path.name in (".DS_Store", "Thumbs.db")
            or path.suffix.lower() in temp_suffixes
            or ".bak-" in path.name
            or path.name.endswith("~")
            or (path.name.startswith("#") and path.name.endswith("#"))
        ):
            errs.append(f"leftover temporary artifact found: {path.relative_to(REPO).as_posix()} (run scripts/clean.py)")

    # JSON syntax validation
    for jrel in JSON_FILES:
        jpath = REPO / jrel
        if jpath.exists():
            try:
                data, _ = read_object(jpath)
                if jrel == "hooks.json":
                    validate_hooks(data)
                else:
                    validate_sections(data, jrel, JSON_SECTIONS[jrel])
                    if jrel.startswith("config/cli-settings."):
                        validate_cli_settings(data, jrel)
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
            errs.append("Node.js is required to validate hooks/git-guard.js")

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
                errs.append(f"possible secret [{label}] in {f.relative_to(REPO)}")

    if args.live:
        errs.extend(verify_live())

    if errs:
        print("Validation FAILED:")
        for e in errs:
            print("  - " + e)
        sys.exit(1)
    print(f"Validation passed ({'template' if template_mode else 'private'} mode).")


def verify_guidance(repo: Path, source_root: Path | None = None, rules_path: Path | None = None) -> list[str]:
    """核验固定来源与嵌入原文；只有显式提供源目录时才检查上游是否漂移。"""
    try:
        manifest, _ = read_object(repo / "config/meta-guidance.json")
        expected = {"sourceRepository": "YIYUAN-CALIBRATION", "sourcePath": "common/meta-guidance/ai-prompt.zh-CN.md", "edition": "ai-prompt", "language": "zh-CN"}
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError("expected the AI prompt edition and its canonical Chinese source")
        if not isinstance(manifest.get("sourceRevision"), str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", manifest["sourceRevision"]):
            raise ValueError("invalid source revision")
        digest = manifest.get("sha256Lf")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid source digest")
        rules = (rules_path if rules_path is not None else repo / "AGENTS.md").read_text(encoding="utf-8-sig")
        blocks = re.findall(r"<!-- META_GUIDANCE_START -->(.*?)<!-- META_GUIDANCE_END -->", rules, re.DOTALL)
        if len(blocks) != 1 or rules.count("<!-- META_GUIDANCE_START -->") != 1 or rules.count("<!-- META_GUIDANCE_END -->") != 1:
            raise ValueError("expected exactly one bounded meta-guidance block")
        def text_digest(text: str) -> str:
            normalized = text.replace("\r\n", "\n").strip() + "\n"
            return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if text_digest(blocks[0]) != digest:
            raise ValueError("embedded AI guidance differs from the pinned source")
        if source_root is not None:
            source = source_root / expected["sourcePath"]
            if text_digest(source.read_text(encoding="utf-8-sig")) != digest:
                raise ValueError("upstream AI guidance changed; review and update the pinned text and provenance together")
    except (ValueError, OSError, UnicodeError) as exc:
        return [f"Meta-guidance: {exc}"]
    return []


def configuration_notes(config: dict, cli: dict, home: Path) -> list[str]:
    """仅提示配置取舍，不修改用户选择，也不输出本机路径或权限规则内容。"""
    notes = []
    settings = config.get("userSettings", {})
    if settings.get("permissionPreset") == "AGENT_PERMISSION_PRESET_TURBO" or cli.get("toolPermission") == "always-proceed":
        notes.append("Turbo / always-proceed is configured; the Git guard does not isolate other commands.")
    if settings.get("allowAgentAccessNonWorkspaceFiles") is True or cli.get("allowNonWorkspaceAccess") is True:
        notes.append("Non-workspace file access is enabled.")
    # 仅做词法归一化，避免审计信任目录时访问不可用的网络盘或联接。
    def trust_key(path: str | Path) -> str:
        return os.path.normcase(os.path.abspath(os.path.expanduser(str(path))))
    broad_roots = {trust_key(home), trust_key(home.anchor)}
    if any(trust_key(w) in broad_roots for w in cli.get("trustedWorkspaces", [])):
        notes.append("The user home or filesystem root is trusted; narrower project trust is available.")
    if settings.get("remoteControlEnabled") is True:
        notes.append("Remote Control is enabled in settings; connection / daemon state was not checked.")
    if any(k in settings for k in ("permissionGrantsV2Migrated", "sandboxEnabledAtV2Migration")):
        notes.append("Host migration state exists locally; keep it out of portable templates.")
    return notes


def verify_live() -> list[str]:
    """仅读取必要状态；MCP 内容、会话与认证信息不会进入输出。"""
    errs = []
    live = {}
    root = Path.home() / ".gemini"
    guidance_errors = verify_guidance(REPO, rules_path=root / "AGENTS.md")
    errs.extend(guidance_errors)
    if not guidance_errors:
        print("Live meta-guidance matches the pinned AI source.")
    for rel, sections in [
        ("config/config.json", {"plugins": dict, "userSettings": dict}),
        ("config/mcp_config.json", {"mcpServers": dict}),
        ("antigravity-cli/settings.json", {"trustedWorkspaces": list}),
    ]:
        target = root / rel
        try:
            if not target.exists():
                raise ValueError(f"Missing live file: {rel}")
            data, _ = read_object(target)
            validate_sections(data, rel, sections)
            if rel == "antigravity-cli/settings.json":
                validate_cli_settings(data, "CLI settings.json")
            live[rel] = data
            print(f"Live JSON valid: {rel}")
        except (ValueError, OSError) as exc:
            errs.append(str(exc))
    if "config/config.json" in live and "antigravity-cli/settings.json" in live:
        for note in configuration_notes(live["config/config.json"], live["antigravity-cli/settings.json"], Path.home()):
            print("Configuration note: " + note)
    try:
        hooks, _ = read_object(root / "config/hooks.json")
        validate_hooks(hooks)
        guard = hooks.get("git-guard", {})
        if not guard:
            raise ValueError("Live git-guard is missing")
        if guard.get("enabled") is False:
            print("Live git-guard: disabled by user; preserved")
        else:
            expected = f'node "{(root / "config/hooks/git-guard.js").as_posix()}"'
            handlers = [h for group in guard.get("PreToolUse", []) for h in group.get("hooks", []) if group.get("matcher") == "run_command"]
            if not any(h.get("command") == expected for h in handlers):
                raise ValueError("Live git-guard does not use the installed absolute path")
            for command, decision in [("git status --short", "allow"), ("git -C repo reset --hard", "force_ask")]:
                result = subprocess.run(["node", str(root / "config/hooks/git-guard.js")], input=json.dumps({"toolCall": {"args": {"CommandLine": command}}}), capture_output=True, text=True, encoding="utf-8", timeout=10, cwd=Path.home())
                if result.returncode or json.loads(result.stdout).get("decision") != decision:
                    raise ValueError("Installed git-guard behavior check failed")
            print("Live git-guard: ordinary command allowed; destructive command requires review")
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        errs.append(str(exc))
    selected = shutil.which("agy")
    preferred = root / "bin" / ("agy.exe" if sys.platform == "win32" else "agy")
    try:
        if selected is None:
            raise ValueError("agy is not on PATH")
        def version(path):
            result = subprocess.run([str(path), "--version"], capture_output=True, text=True, timeout=10)
            match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)\s*", result.stdout.strip())
            if result.returncode or not match:
                raise ValueError("Cannot determine agy version")
            return tuple(map(int, match.groups()))
        current = version(selected)
        print("Live agy: " + ".".join(map(str, current)))
        if preferred.exists() and version(preferred) > current:
            errs.append("PATH selects an older agy than ~/.gemini/bin; update the selected installation without adding another PATH entry")
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        errs.append(str(exc))
    return errs


if __name__ == "__main__":
    main()
