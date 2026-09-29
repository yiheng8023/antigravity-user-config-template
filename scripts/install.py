#!/usr/bin/env python3
"""Restore Antigravity user configuration from this repository into ~/.gemini/.
Cross-platform (Windows / macOS / Linux).

Usage:
  python -B scripts/install.py               # restore into ~/.gemini/config & ~/.gemini/antigravity-cli
  python -B scripts/install.py --skip-rules  # restore settings/hooks/MCP without touching AGENTS.md / GEMINI.md
  python -B scripts/install.py --dry-run     # preview changes without writing
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOME = Path.home()
GEMINI_DIR = HOME / ".gemini"
CONFIG_DIR = GEMINI_DIR / "config"
CLI_DIR = GEMINI_DIR / "antigravity-cli"
TS = datetime.now().strftime("%Y%m%d-%H%M%S")
DRY = "--dry-run" in sys.argv[1:]
SKIP_RULES = "--skip-rules" in sys.argv[1:]


def default_projects_dir() -> str:
    if platform.system() == "Windows":
        drive = Path("C:/Projects")
        if drive.exists():
            return str(drive)
    return str(HOME / "Projects")


def backup(target: Path) -> None:
    if not target.exists():
        return
    bak = target.with_name(target.name + f".bak-{TS}")
    if DRY:
        print(f"  [dry-run] would back up {target.name} -> {bak.name}")
        return
    if target.is_dir():
        shutil.copytree(target, bak)
    else:
        shutil.copy2(target, bak)
    print(f"  backed up existing -> {bak.name}")


def copy_file(src: Path, dst: Path) -> None:
    if not DRY:
        dst.parent.mkdir(parents=True, exist_ok=True)
    backup(dst)
    if DRY:
        print(f"  [dry-run] {src.relative_to(REPO)} -> {dst}")
        return
    shutil.copy2(src, dst)
    print(f"  {src.relative_to(REPO)} -> {dst}")


def copy_dir(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    count = 0
    for item in sorted(src.rglob("*")):
        if not item.is_file():
            continue
        target = dst / item.relative_to(src)
        if not DRY:
            target.parent.mkdir(parents=True, exist_ok=True)
        backup(target)
        if not DRY:
            shutil.copy2(item, target)
        count += 1
    prefix = "[dry-run] " if DRY else ""
    print(f"  {prefix}{src.relative_to(REPO)}/ -> {dst}/  ({count} files)")


def _strip_meta(d: dict) -> dict:
    return {k: v for k, v in d.items() if not str(k).startswith("_")}


def _collect_env_refs(obj, found: set) -> None:
    if isinstance(obj, str):
        found.update(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", obj))
    elif isinstance(obj, list):
        for x in obj:
            _collect_env_refs(x, found)
    elif isinstance(obj, dict):
        for x in obj.values():
            _collect_env_refs(x, found)


def merge_mcp_servers(manifest_path: Path, target_path: Path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    servers = manifest.get("mcpServers", {})
    data = {}
    if target_path.exists():
        try:
            raw = target_path.read_text(encoding="utf-8").strip()
            if raw:
                data = json.loads(raw)
        except Exception:
            data = {}
    existing = data.get("mcpServers")
    if not isinstance(existing, dict):
        existing = {}
    added, kept, env_needed = [], [], set()
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        if name in existing:
            kept.append(name)
            continue
        clean = _strip_meta(cfg)
        existing[name] = clean
        added.append(name)
        _collect_env_refs(clean, env_needed)
    data["mcpServers"] = existing
    return data, sorted(added), sorted(kept), sorted(env_needed)


def main() -> None:
    hostname = os.environ.get("ANTIGRAVITY_HOSTNAME") or socket.gethostname() or "local-host"
    user_home = str(HOME)
    projects_dir = default_projects_dir()

    print(f"Installing Antigravity user config into: {GEMINI_DIR}" + ("   [DRY RUN — no writes]" if DRY else ""))
    if not DRY:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CLI_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Global rules (AGENTS.md) and lifecycle hooks (hooks.json + hooks/)
    if SKIP_RULES:
        print("  [skip-rules] leaving existing AGENTS.md / GEMINI.md untouched")
    else:
        copy_file(REPO / "AGENTS.md", CONFIG_DIR / "AGENTS.md")
    copy_file(REPO / "hooks.json", CONFIG_DIR / "hooks.json")
    copy_dir(REPO / "hooks", CONFIG_DIR / "hooks")

    # 2. Render config/config.example.json -> ~/.gemini/config/config.json
    cfg_template = json.loads((REPO / "config" / "config.example.json").read_text(encoding="utf-8"))
    if "userSettings" in cfg_template and isinstance(cfg_template["userSettings"], dict):
        if cfg_template["userSettings"].get("remoteControlHostname") == "__HOSTNAME__":
            cfg_template["userSettings"]["remoteControlHostname"] = hostname
    cfg_target = CONFIG_DIR / "config.json"
    backup(cfg_target)
    if DRY:
        print(f"  [dry-run] config/config.example.json -> {cfg_target}  (rendered hostname={hostname})")
    else:
        cfg_target.write_text(json.dumps(cfg_template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  config/config.example.json -> {cfg_target}  (rendered hostname={hostname})")

    # 3. Additive merge of MCP servers -> ~/.gemini/config/mcp_config.json
    mcp_manifest = REPO / "config" / "mcp_config.example.json"
    mcp_target = CONFIG_DIR / "mcp_config.json"
    merged_mcp, added, kept, env_needed = merge_mcp_servers(mcp_manifest, mcp_target)
    backup(mcp_target)
    if DRY:
        print(f"  [dry-run] would merge MCP servers into {mcp_target}")
    else:
        mcp_target.write_text(json.dumps(merged_mcp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  MCP servers merged into {mcp_target}")
    print(f"    added:  {', '.join(added) if added else '(none — all already present)'}")
    print(f"    kept:   {', '.join(kept) if kept else '(none)'}")
    if env_needed:
        print(f"    set these env vars locally for added servers: {', '.join(env_needed)}")

    # 4. Render config/cli-settings.example.json -> ~/.gemini/antigravity-cli/settings.json
    cli_template = json.loads((REPO / "config" / "cli-settings.example.json").read_text(encoding="utf-8"))
    workspaces = cli_template.get("trustedWorkspaces", [])
    rendered_ws = []
    for w in workspaces:
        val = str(w).replace("__PROJECTS_DIR__", projects_dir).replace("__USER_HOME__", user_home)
        if val not in rendered_ws:
            rendered_ws.append(val)
    cli_template["trustedWorkspaces"] = rendered_ws
    cli_target = CLI_DIR / "settings.json"
    backup(cli_target)
    if DRY:
        print(f"  [dry-run] config/cli-settings.example.json -> {cli_target}  (rendered)")
    else:
        cli_target.write_text(json.dumps(cli_template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  config/cli-settings.example.json -> {cli_target}  (rendered)")

    print("\nDone." + (" (dry run — nothing was written)" if DRY else ""))
    print("Restart Antigravity / agy CLI to ensure all settings and hooks take effect.")


if __name__ == "__main__":
    main()
