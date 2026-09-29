# antigravity-user-config-template

[English](README.md) | 简体中文

用于创建私有 Google Antigravity（涵盖 `Antigravity 2.0`、`Antigravity IDE` 与 `agy` CLI）用户配置仓库的公开安全模板，避免公开个人知识库、私有提示词、凭据、账号状态或本机运行细节。

本仓是模板，不是正在运行的真实用户配置。请将其作为安全起点，将真实配置保存在你自己的私有仓库（`private antigravity-user-config`）中。

## 快速开始

| 如果你想…… | 请看这里 |
| --- | --- |
| 创建自己的私有 Antigravity 配置仓库 | 使用本模板作为公开安全起点 |
| 在不改动本机的情况下预览安装 | `python -B scripts/install.py --dry-run` |
| 校验模板完整性与安全边界 | `python -B scripts/verify.py` |
| 了解模板与私有仓库边界 | [仓库定位](#仓库定位) |

## 独立模板定位

本仓是可以独立使用的公开 Google Antigravity 专用配置模板，通过本仓自有结构、校验脚本与搭建说明展示更通用的 agent 环境可移植模式。

```text
antigravity-user-config-template
  -> 提供公开安全结构、占位符、dry-run 安装预览与自动化校验

private antigravity-user-config
  -> 承载真实 Antigravity 全局规则、钩子、知识库、本机安装策略与备份

claude-user-config-template / codex-user-config-template
  -> 同系列的 Claude Code 与 Codex 公开安全配置模板
```

## 仓库定位

公开模板只保留可复用结构、脱敏占位配置与校验脚本；个人真实配置、知识库快照与本机路径映射应保存在私有仓库中。
