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

CLI_ENUMS = {
    "agentMode": ("", "accept-edits", "auto", "plan"),
    "toolPermission": ("request-review", "proceed-in-sandbox", "always-proceed", "strict"),
    "artifactReviewPolicy": ("asks-for-review", "agent-decides", "always-proceed"),
    "verbosity": ("high", "medium", "low"),
}
CLI_BOOLEANS = (
    "allowNonWorkspaceAccess", "enableTerminalSandbox", "notifications",
    "showFeedbackSurvey", "showTips", "useG1Credits",
)
TURBO_TEMPLATES = {
    "config/config.example.json": "config/config.turbo.example.json",
    "config/cli-settings.example.json": "config/cli-settings.turbo.example.json",
}
LEGACY_RULES_STUB = "<!-- Antigravity 全局规则已迁至 ~/.gemini/AGENTS.md；此兼容文件不再携带规则正文。 -->\n"


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


def validate_cli_settings(data: dict, name: str) -> None:
    """校验模板使用的公开 CLI 字段；保留未知字段以兼容后续版本。"""
    validate_sections(data, name, {"trustedWorkspaces": list})
    for key, choices in CLI_ENUMS.items():
        if key in data and (not isinstance(data[key], str) or data[key] not in choices):
            raise ValueError(f"Invalid {name}.{key}: expected a documented option")
    for key in CLI_BOOLEANS:
        if key in data and not isinstance(data[key], bool):
            raise ValueError(f"Invalid {name}.{key}: expected boolean")
    if "$schema" in data and not isinstance(data["$schema"], str):
        raise ValueError(f"Invalid {name}.$schema: expected string")


def read_template(source: str, profile: str) -> dict:
    path = REPO / source
    if not path.is_file():
        raise ValueError(f"Missing template: {source}")
    template, _ = read_object(path)
    if profile == "turbo" and source in TURBO_TEMPLATES:
        overlay_source = TURBO_TEMPLATES[source]
        overlay_path = REPO / overlay_source
        if not overlay_path.is_file():
            raise ValueError(f"Missing template: {overlay_source}")
        overlay, _ = read_object(overlay_path)
        if source == "config/config.example.json":
            for data in (template, overlay):
                validate_sections(data, source, {"plugins": dict, "userSettings": dict})
            for section in ("plugins", "userSettings"):
                template.setdefault(section, {}).update(overlay.get(section, {}))
        else:
            validate_cli_settings(template, source)
            validate_cli_settings(overlay, overlay_source)
            template.update(overlay)
    return template


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


def install_rules(home: Path, dry: bool, replace: bool) -> None:
    """使用 App、CLI 和 IDE 扩展共有的入口；默认保留已有任一入口的规则。"""
    target = home / ".gemini/AGENTS.md"
    legacy = home / ".gemini/config/AGENTS.md"
    if not replace and (target.exists() or legacy.exists()):
        print("  kept existing global rules; --replace-rules explicitly migrates the legacy config/AGENTS.md")
        return
    for path in (target, legacy):
        require_contained(path, home / ".gemini")
        if path.exists() and not path.is_file():
            raise ValueError(f"Expected rules file: {path}")
    if target.exists() and legacy.exists() and target.samefile(legacy):
        raise ValueError("Global rules entries refer to the same file; separate the links before migration. No rules were changed")
    legacy_original = legacy.read_bytes() if legacy.exists() else None
    copy_file(REPO / "AGENTS.md", target, dry)
    if legacy_original is not None and legacy_original.decode("utf-8-sig", errors="replace").replace("\r\n", "\n") != LEGACY_RULES_STUB:
        check_unchanged(legacy, legacy_original)
        if dry:
            print("  [dry-run] would replace legacy config/AGENTS.md with a body-free migration notice")
        else:
            backup(legacy)
            legacy.write_text(LEGACY_RULES_STUB, encoding="utf-8")
            print("  migrated legacy rules; canonical body exists only at ~/.gemini/AGENTS.md")


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
    parser.add_argument("--replace-rules", action="store_true", help="备份后替换 ~/.gemini/AGENTS.md，并迁移旧 config/AGENTS.md")
    parser.add_argument("--profile", choices=("default", "turbo"), default="default", help="首次安装的默认值；turbo 显式启用宽权限，已有值仍优先")
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
            template = read_template(source, args.profile)
            existing, original = read_object(target)
            validate_sections(template, source, sections)
            validate_sections(existing, target.name, sections)
            if source == "config/cli-settings.example.json":
                validate_cli_settings(template, source)
                validate_cli_settings(existing, "CLI settings.json")
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
        print(f"Profile: {args.profile}; existing values take precedence.")
        # 所有 JSON 预检通过后才复制或写入，避免损坏配置引发半途覆盖。
        if not args.skip_rules:
            install_rules(home, args.dry_run, args.replace_rules)
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
