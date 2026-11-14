# antigravity-user-config-template

English | [简体中文](README.zh-CN.md)

Public-safe template for creating a private Google Antigravity (`Antigravity 2.0` + `Antigravity IDE` + `agy` CLI) user-configuration repository without publishing personal memories, private prompts, credentials, account state, or machine-local runtime details.

This is a template, not a live user configuration. Use it as a safe starting point, then keep your real Antigravity configuration in your own private repository (`private antigravity-user-config`).

## Start here

| If you want to... | Go here |
| --- | --- |
| Apply portable defaults & hooks without touching your `AGENTS.md` | `python -B scripts/install.py --skip-rules` |
| Preview setup without changing your machine | `python -B scripts/install.py --dry-run` |
| Verify the template | `python -B scripts/verify.py` |
| Understand this template's boundary | [Repository Role](#repository-role) |

## Independent Template Context

This repository is an independently usable public Google Antigravity-specific configuration template. It demonstrates the broader agent-environment portability pattern through repository-owned structure, validation, and setup guidance; the pattern itself is not limited to Antigravity.

```text
antigravity-user-config-template
  -> provides public-safe structure, placeholders, dry-run setup, and validation

private antigravity-user-config
  -> owns real Antigravity rules, hooks, progressive memory, knowledge items, and backups

claude-user-config-template / codex-user-config-template
  -> are the sibling public templates for Claude Code and Codex configurations
```

## Repository Role

The template may be public. Your real configuration repository should remain private unless every file has been deliberately declassified.

## What This Repository Provides

- `AGENTS.md`: portable global rules (`~/.gemini/AGENTS.md`)
- `hooks.json` & `hooks/git-guard.js`: `PreToolUse` safety guardrail for terminal git commands
- `memory/README.md` & `knowledge/README.md`: placeholders for progressive-disclosure global memory (`~/.gemini/config/memory/`) and UI knowledge items (`~/.gemini/antigravity/knowledge/`)
- `config/config.example.json`: portable display preferences; permissions remain host-controlled
- `config/mcp_config.example.json`: sanitized `~/.gemini/config/mcp_config.json` template
- `config/cli-settings.example.json`: portable CLI preferences with no pre-trusted directories
- `scripts/install.py`, `scripts/verify.py`, `scripts/clean.py`, `scripts/memory.py`, `scripts/knowledge.py`: cross-platform installer (`--dry-run`, `--skip-rules`, `--skip-memory`), zero-leftover artifact & secret-scanning verifier, stale crash-log cleaner (`--runtime`), and memory/knowledge sync tools

## Installation behavior and verification

Existing permissions, disabled plugins, custom hooks, MCP entries, CLI preferences,
and workspace trust take precedence over template defaults. Fresh installs leave
permissions to the host, enable no plugins, trust no directories in advance, and
do not seed Remote Control or migration state. Choose `--profile turbo` explicitly
for broad permission defaults; existing settings still win. See
[configuration choices](config/README.md).
Existing rules and memory are kept; `--replace-rules` deliberately replaces rules.
`--skip-rules` skips rules, memory, and knowledge entirely. Invalid target JSON or
section types or invalid documented CLI values stop the installer before any write. Changed JSON is backed up and
replaced atomically.

Memory/knowledge sync preserve extra target files unless `--prune` is explicitly
selected. Preview a full mirror with `--restore --prune --dry-run` before applying
`--restore --prune`. Empty knowledge sources preserve all target items. Backups
scan for likely credentials and report file names/categories without token excerpts.
Public-template backups refuse private memory and knowledge; follow
[private setup](docs/private-repo-setup.md) to create your own private backup repo.

`clean.py --runtime` preserves backups, scratch, sessions and media; only runtime
crash logs older than seven days are eligible for removal.

```bash
python -B -m unittest discover -s tests -v
python -B scripts/verify.py --live
```

Python 3.10+ and Node.js are required. GitHub CI runs on Windows, macOS, and Linux.
`--live` checks local JSON, directly tests the installed Git guard, and detects an
older `agy` selected by PATH. Configuration notes describe broad permission and
trust choices without changing them. Update the selected installation through its
official updater rather than adding a duplicate PATH entry. Restart existing clients to reload hooks;
these direct checks do not establish that a running session has reloaded.
See [hook scope](hooks/README.md) and [version changes](CHANGELOG.md).

The meta-guidance block uses the AI prompt edition from YIYUAN-CALIBRATION. See
[configuration choices](config/README.md#meta-guidance-source--元指导来源) for provenance and source checks.
