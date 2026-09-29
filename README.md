# antigravity-user-config-template

English | [简体中文](README.zh-CN.md)

Public-safe template for creating a private Google Antigravity (`Antigravity 2.0` + `Antigravity IDE` + `agy` CLI) user-configuration repository without publishing personal knowledge, private prompts, credentials, account state, or machine-local runtime details.

This is a template, not a live user configuration. Use it as a safe starting point, then keep your real Antigravity configuration in your own private repository (`private antigravity-user-config`).

## Start here

| If you want to... | Go here |
| --- | --- |
| Create your own private Antigravity config repo | Use this template as the public-safe starting point |
| Preview setup without changing your machine | `python -B scripts/install.py --dry-run` |
| Verify the template | `python -B scripts/verify.py` |
| Understand this template's boundary | [Repository Role](#repository-role) |

## Independent Template Context

This repository is an independently usable public Google Antigravity-specific configuration template. It demonstrates the broader agent-environment portability pattern through repository-owned structure, validation, and setup guidance; the pattern itself is not limited to Antigravity.

```text
antigravity-user-config-template
  -> provides public-safe structure, placeholders, dry-run setup, and validation

private antigravity-user-config
  -> owns real Antigravity rules, hooks, knowledge, local install policy, and backups

claude-user-config-template / codex-user-config-template
  -> are the sibling public templates for Claude Code and Codex configurations
```

## Repository Role

The template may be public. Your real configuration repository should remain private unless every file has been deliberately declassified.

## What This Repository Provides

- `AGENTS.md`: portable global rules (`~/.gemini/config/AGENTS.md`)
- `hooks.json` & `hooks/git-guard.js`: `PreToolUse` safety guardrail for terminal git commands
- `config/config.example.json`: sanitized full-power `~/.gemini/config/config.json` template (`__HOSTNAME__` placeholder)
- `config/mcp_config.example.json`: sanitized `~/.gemini/config/mcp_config.json` template
- `config/cli-settings.example.json`: sanitized `~/.gemini/antigravity-cli/settings.json` template (`__PROJECTS_DIR__`, `__USER_HOME__`)
- `scripts/install.py` & `scripts/verify.py`: cross-platform installer (`--dry-run` supported) and no-secret verifier
