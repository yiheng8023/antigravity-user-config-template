# Configuration choices / 配置取舍

Checked against the official documentation on 2026-11-14. Local validation used
Antigravity Desktop 2.32.1 and CLI 1.5.9; this is an observed baseline, not a minimum
version requirement or proof of every client feature.

于 2026-11-14 核对官方文档；本机检查基线为 Antigravity Desktop 2.32.1、CLI 1.5.9。
该基线不是最低版本要求，也不代表全部客户端功能已验收。

| Choice / 选项 | Default install / 默认安装 | `--profile turbo` |
| --- | --- | --- |
| Permissions / 权限 | Leave unset; use host defaults / 不写入，沿用宿主默认值 | Fill missing unrestricted settings / 为缺失设置补充宽权限 |
| CLI edits / CLI 文件编辑 | Host default / 宿主默认 | `accept-edits` |
| Workspace trust / 目录信任 | Empty on a fresh install / 首装为空 | Empty on a fresh install / 首装为空 |
| Plugins / 插件 | No bundled enablement / 不批量启用 | No bundled enablement / 不批量启用 |
| Remote Control / 远程控制 | Leave to host and user / 由宿主和用户管理 | Leave to host and user / 由宿主和用户管理 |
| Existing values / 已有设置 | Preserve / 保留 | Preserve / 保留 |

```sh
python -B scripts/install.py --dry-run
python -B scripts/install.py --skip-rules
python -B scripts/install.py --profile turbo --dry-run
```

Profiles supply **missing defaults**, not a forced mode switch. Reinstalling with
the default profile does not revoke an existing Turbo choice, and selecting Turbo
does not override an existing restrictive choice. Change active permissions with
the client's permission controls. Turbo removes normal isolation; the Git guard
only reviews recognized Git commands and cannot replace that isolation.

配置档只补缺失默认值，不强制切换模式。用默认档重装不会撤销已有 Turbo，
选择 Turbo 也不会覆盖已有的限制设置。调整生效权限应使用客户端权限界面。
Turbo 不提供普通模式的隔离；Git 护栏只检查已识别的 Git 命令，无法替代隔离。

Install plugins through the official Marketplace or `agy plugin` as needed.
An `enabled` flag does not install a plugin, satisfy its variables, or authorize
its services. Keep account configuration and MCP credentials local.

插件通过官方 Marketplace 或 `agy plugin` 按需安装。`enabled` 标记不等于已安装、
已配置变量或已获得服务授权。账号配置与 MCP 凭证保留在本机。

Host migration flags, empty permission-grant snapshots and machine hostnames are
not portable preferences. Bundled templates omit them; the installer preserves
existing host-owned state. CLI `verbosity` controls display detail, not reasoning
effort; the default is `medium`, and an existing `high` remains unchanged.

宿主迁移标记、空权限授权快照和机器主机名不是可移植偏好，模板不再携带；
安装器保留本机已有状态。CLI `verbosity` 控制显示细节，不是推理强度；默认
使用 `medium`，已有的 `high` 保留。

`verify.py --live` reports configuration tradeoffs without changing them. Its
checks validate files and exercise the installed hook directly; they do not prove
that a running client has reloaded, that a sandbox is available, or that MCP and
Remote Control services work. Choose trust per project instead of pre-trusting a
whole home directory. Keep private rules and historical memory out of the public
template, and recheck version claims against the actual installed host.

`verify.py --live` 只提示配置取舍，不自动改动。它校验文件并直接测试已安装护栏，
不证明运行中的客户端已重载、沙箱可用，或 MCP、Remote Control 服务正常。
目录信任按具体项目选择，避免预先信任整个用户目录。私人规则、历史记忆不进入
公开模板；历史版本记录应以实际安装状态重新核对。

Sources / 依据：

- [Agent settings](https://antigravity.google/docs/agent-settings)
- [CLI configuration reference](https://antigravity.google/docs/cli/reference#configuration-keys-settingsjson)
- [CLI JSON schema](https://antigravity.google/schemas/v1/settings.json)
- [Plugins](https://antigravity.google/docs/plugins)
- [Hooks](https://antigravity.google/docs/hooks)

## Meta-guidance source / 元指导来源

The bounded block in `AGENTS.md` uses the **AI prompt edition** from
`YIYUAN-CALIBRATION/common/meta-guidance/ai-prompt.zh-CN.md`.
`config/meta-guidance.json` pins the source revision and the SHA-256 of the text
normalized to LF, with outer whitespace removed and one final newline.
The regular verifier checks the embedded block against that digest; to check the
current local source as well, run:

```sh
python -B scripts/verify.py --guidance-source ../YIYUAN-CALIBRATION
```

`AGENTS.md` 的标记块使用 **AI 提示词版**中文原文。来源提交和规范化文本摘要记录
在 `config/meta-guidance.json`。普通校验只证明嵌入文本与固定来源一致；显式提供
原文仓目录才会检查当前上游是否变化。更新时一起审查原文、标记块和来源记录，
个人规则放在标记块之外。通用版不用于这个标记块。

## Shared rules entry / 多端共享规则入口

The App, CLI, standalone IDE and IDE extensions support `~/.gemini/AGENTS.md`.
The installer uses that common entry. If either it or the old
`~/.gemini/config/AGENTS.md` already exists, a normal install keeps the rules.
`--replace-rules` backs up and replaces the common file, then replaces any old
config-level body with a migration notice. This avoids cumulatively loading two
full copies. Other `GEMINI.md` files and modular rules remain user-owned.

App、CLI、独立 IDE 与 IDE 扩展共同使用 `~/.gemini/AGENTS.md`。首次安装写入该入口；
任一新旧入口已有规则时，默认保留。明确使用 `--replace-rules` 后，安装器备份并
更新共有入口，将旧 `~/.gemini/config/AGENTS.md` 正文迁为兼容提示，避免重复注入。
其他 `GEMINI.md` 和模块规则仍由用户管理。规则共用入口不代表权限、服务核心、
账号状态或运行会话完全共享；扩展应在本机原生宿主中新会话验收。

[Official rules locations / 官方规则路径](https://antigravity.google/docs/rules)
