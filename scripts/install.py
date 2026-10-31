#!/usr/bin/env python3
"""安装或恢复 Antigravity 配置；默认保留已有设置、插件选择和信任范围。"""
from __future__ import annotations

import argparse
import copy
import filecmp
import json
import os
import platform
import re
import shutil
import socket
import tempfile
from datetime import datetime
from pathlib import Path

from safety import require_contained

REPO = Path(__file__).resolve().parent.parent


def read_object(path: Path) -> tuple[dict, bytes | None]:
    if not path.exists():
        return {}, None
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        raise ValueError(f"Invalid JSON: {path.name}; original file preserved") from None
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path.name}; original file preserved")
    return data, raw


def validate_sections(data: dict, name: str, sections: dict[str, type]) -> None:
    for key, kind in sections.items():
        if key in data and not isinstance(data[key], kind):
            raise ValueError(f"Invalid {name}.{key}: expected {kind.__name__}")
    if "trustedWorkspaces" in data and any(not isinstance(w, str) for w in data["trustedWorkspaces"]):
        raise ValueError(f"Invalid {name}.trustedWorkspaces: expected strings")
    for key in ("plugins", "mcpServers"):
        if key in data and any(not isinstance(v, dict) for v in data[key].values()):
            raise ValueError(f"Invalid {name}.{key}: expected object entries")


def validate_hooks(data: dict) -> None:
    for name, config in data.items():
        if not isinstance(config, dict):
            raise ValueError(f"Invalid hook definition: {name}")
        if "enabled" in config and not isinstance(config["enabled"], bool):
            raise ValueError(f"Invalid hook enabled flag: {name}")
        for event in ("PreToolUse", "PostToolUse", "PreInvocation", "PostInvocation", "Stop", "SessionStart"):
            if event not in config:
                continue
            groups = config[event]
            if not isinstance(groups, list) or any(not isinstance(group, dict) for group in groups):
                raise ValueError(f"Invalid hook event: {name}.{event}")
            for group in groups:
                if "hooks" in group and (not isinstance(group["hooks"], list) or any(not isinstance(handler, dict) for handler in group["hooks"])):
                    raise ValueError(f"Invalid hook handlers: {name}.{event}")


def backup(target: Path) -> None:
    if target.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(target, target.with_name(f"{target.name}.bak-{stamp}"))
        print(f"  backed up: {target.name}")


def check_unchanged(target: Path, original: bytes | None) -> None:
    current = target.read_bytes() if target.exists() else None
    if current != original:
        raise ValueError(f"Concurrent change: {target.name}; rerun after the other writer finishes")


def write_json(target: Path, data: dict, original: bytes | None, dry: bool) -> None:
    if original is not None and json.loads(original.decode("utf-8-sig")) == data:
        print(f"  unchanged: {target.name}")
        return
    check_unchanged(target, original)
    if dry:
        print(f"  [dry-run] would update: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    backup(target)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False) as stream:
            temp_path = Path(stream.name)
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        check_unchanged(target, original)
        os.replace(temp_path, target)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    print(f"  updated: {target.name}")


def copy_file(src: Path, dst: Path, dry: bool, preserve: bool = False) -> None:
    if dst.exists() and filecmp.cmp(src, dst, shallow=False):
        return
    if preserve and dst.exists():
        print(f"  kept existing content: {dst}")
        return
    if dry:
        print(f"  [dry-run] would copy: {src.relative_to(REPO)} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup(dst)
    shutil.copy2(src, dst)


def copy_dir(src: Path, dst: Path, dry: bool, preserve: bool = False) -> None:
    for item in sorted(src.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(src)
        if rel.as_posix() == "README.md" or item.name.endswith(".lock") or ".bak" in item.name:
            continue
        require_contained(item, src)
        require_contained(dst / rel, dst)
        copy_file(item, dst / rel, dry, preserve=preserve)


def merge_config(template: dict, existing: dict, hostname: str) -> dict:
    result = copy.deepcopy(existing)
    for section in ("plugins", "userSettings"):
        target = result.setdefault(section, {})
        for key, value in template.get(section, {}).items():
            target.setdefault(key, copy.deepcopy(value))
    if result["userSettings"].get("remoteControlHostname") == "__HOSTNAME__":
        result["userSettings"]["remoteControlHostname"] = hostname
    return result


def merge_mcp(template: dict, existing: dict) -> dict:
    result = copy.deepcopy(existing)
    servers = result.setdefault("mcpServers", {})
    for name, config in template.get("mcpServers", {}).items():
        servers.setdefault(name, {k: v for k, v in config.items() if not k.startswith("_")})
    return result


def merge_hooks(template: dict, existing: dict, hook_path: Path) -> dict:
    result = copy.deepcopy(existing)
    for name, config in template.items():
        result.setdefault(name, copy.deepcopy(config))
    # 仅迁移本项目旧版的相对路径；其他钩子、禁用状态和自定义命令均保留。
    guard = result.get("git-guard")
    if isinstance(guard, dict):
        for group in guard.get("PreToolUse", []):
            if isinstance(group, dict):
                for handler in group.get("hooks", []):
                    if isinstance(handler, dict) and handler.get("command") == "node ./hooks/git-guard.js":
                        handler["command"] = f'node "{hook_path.as_posix()}"'
    return result


def merge_cli(template: dict, existing: dict, home: Path) -> dict:
    projects = Path("C:/Projects") if platform.system() == "Windows" and Path("C:/Projects").exists() else home / "Projects"
    result = copy.deepcopy(template)
    result["trustedWorkspaces"] = [w.replace("__PROJECTS_DIR__", str(projects)).replace("__USER_HOME__", str(home)) for w in template.get("trustedWorkspaces", [])]
    result.update(copy.deepcopy(existing))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-rules", action="store_true", help="保留规则、记忆和知识库")
    parser.add_argument("--skip-memory", action="store_true", help="保留记忆和知识库")
    parser.add_argument("--replace-rules", action="store_true", help="备份后替换已有 AGENTS.md")
    args = parser.parse_args()
    if args.skip_rules and args.replace_rules:
        parser.error("--skip-rules and --replace-rules cannot be combined")
    home = Path.home()
    config_dir = home / ".gemini/config"
    cli_dir = home / ".gemini/antigravity-cli"
    specifications = [
        ("config/config.example.json", config_dir / "config.json", {"plugins": dict, "userSettings": dict}),
        ("config/mcp_config.example.json", config_dir / "mcp_config.json", {"mcpServers": dict}),
        ("hooks.json", config_dir / "hooks.json", {}),
        ("config/cli-settings.example.json", cli_dir / "settings.json", {"trustedWorkspaces": list}),
    ]
    try:
        prepared = []
        for source, target, sections in specifications:
            template, _ = read_object(REPO / source)
            if not (REPO / source).is_file():
                raise ValueError(f"Missing template: {source}")
            existing, original = read_object(target)
            validate_sections(template, source, sections)
            validate_sections(existing, target.name, sections)
            if source == "hooks.json":
                validate_hooks(template)
                validate_hooks(existing)
            prepared.append((template, existing, target, original))
        hostname = os.environ.get("ANTIGRAVITY_HOSTNAME") or socket.gethostname()
        results = [
            merge_config(prepared[0][0], prepared[0][1], hostname),
            merge_mcp(prepared[1][0], prepared[1][1]),
            merge_hooks(prepared[2][0], prepared[2][1], config_dir / "hooks/git-guard.js"),
            merge_cli(prepared[3][0], prepared[3][1], home),
        ]
        for _, _, target, original in prepared:
            check_unchanged(target, original)
        if shutil.which("node") is None:
            raise ValueError("Node.js is required for the Git hook; no configuration was changed")
        print(f"Installing into: {home / '.gemini'}" + (" [DRY RUN]" if args.dry_run else ""))
        # 所有 JSON 预检通过后才复制或写入，避免损坏配置引发半途覆盖。
        if not args.skip_rules:
            copy_file(REPO / "AGENTS.md", config_dir / "AGENTS.md", args.dry_run, preserve=not args.replace_rules)
        copy_dir(REPO / "hooks", config_dir / "hooks", args.dry_run)
        if not (args.skip_rules or args.skip_memory):
            copy_dir(REPO / "memory", config_dir / "memory", args.dry_run, preserve=True)
            for app in ("antigravity", "antigravity-cli"):
                copy_dir(REPO / "knowledge", home / ".gemini" / app / "knowledge", args.dry_run, preserve=True)
        for result, (_, _, target, original) in zip(results, prepared):
            write_json(target, result, original, args.dry_run)
        added = set(results[1]["mcpServers"]) - set(prepared[1][1].get("mcpServers", {}))
        refs = sorted(set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", json.dumps({k: results[1]["mcpServers"][k] for k in added}))))
        if refs:
            print("Set these environment variables locally: " + ", ".join(refs))
        print("Done. Restart Antigravity / agy to load updated hooks.")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Installation stopped: {exc}\n")


if __name__ == "__main__":
    main()
