# antigravity-user-config-template

[English](README.md) | 简体中文

用于创建私有 Google Antigravity（涵盖 `Antigravity 2.0`、`Antigravity IDE` 与 `agy` CLI）用户配置仓库的公开安全模板，避免公开个人全局记忆、知识库、私有提示词、凭据、账号状态或本机运行细节。

本仓是模板，不是正在运行的真实用户配置。请将其作为安全起点，将真实配置保存在你自己的私有仓库（`private antigravity-user-config`）中；同事或外部用户也可直接使用本仓一键应用满血设置与安全护栏。

## 快速开始

| 如果你想…… | 请看这里 |
| --- | --- |
| 仅应用满血设置、MCP 与安全护栏（不覆盖自己的 `AGENTS.md`） | `python -B scripts/install.py --skip-rules` |
| 在不改动本机的情况下预览安装 | `python -B scripts/install.py --dry-run` |
| 校验模板完整性与安全边界 | `python -B scripts/verify.py` |
| 清理临时过程产物与运行时缓存 | `python -B scripts/clean.py --runtime` |
| 了解模板与私有仓库边界 | [仓库定位](#仓库定位) |

## 独立模板定位

本仓是可以独立使用的公开 Google Antigravity 专用配置模板，通过本仓自有结构、校验脚本与搭建说明展示更通用的 agent 环境可移植模式。

```text
antigravity-user-config-template
  -> 提供公开安全结构、占位符、dry-run 安装预览与自动化校验

private antigravity-user-config
  -> 承载真实 Antigravity 全局规则、钩子、渐进式全局记忆、知识库与备份

claude-user-config-template / codex-user-config-template
  -> 同系列的 Claude Code 与 Codex 公开安全配置模板
```

## 仓库定位

公开模板只保留可复用结构、脱敏占位配置与校验脚本；个人真实配置、全局记忆（`memory/`）、知识库快照（`knowledge/`）与本机路径映射应保存在私有仓库中。

## 安装边界与验证

已有权限、插件禁用状态、自定义 hooks、MCP、CLI 偏好和信任目录优先于模板。
首次安装仍使用 Turbo 权限及较宽的目录信任范围，请先查看 JSON 模板。
已有规则和记忆默认保留；显式替换规则使用 `--replace-rules`。
`--skip-rules` 完整跳过规则、记忆和知识库。目标 JSON 或字段类型无效时，安装器
在写入前停止；变更 JSON 先备份，再原子替换。

记忆和知识库同步默认保留目标额外文件。只有显式 `--prune` 才删除过期项，先用
`--restore --prune --dry-run` 预览；空知识源始终保留目标。备份扫描疑似凭证，
诊断只返回文件名和类别。公开模板拒绝备份私人记忆及知识，建立私有备份仓请看
[私仓搭建说明](docs/private-repo-setup.md)。

`clean.py --runtime` 保留备份、scratch、会话和媒体，只清理七天前的崩溃日志。

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/verify.py --live
```

依赖 Python 3.10+、Node.js。GitHub CI 覆盖 Windows、macOS、Linux。
`--live` 检查本地 JSON、安装后的 Git 护栏，并检测旧版 `agy` 对 `~/.gemini/bin`
的 PATH 遮蔽。运行中的客户端需重开以加载 hooks；直接协议测试不证明现有会话已重载。
护栏适用范围见 [hooks 说明](hooks/README.md)，版本变更见 [CHANGELOG](CHANGELOG.md)。
