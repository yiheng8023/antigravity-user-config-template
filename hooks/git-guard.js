#!/usr/bin/env node
/**
 * Antigravity PreToolUse Hook: Git 高危命令安全护栏 (git-guard.js)
 *
 * 在极速模式 (TURBO) 下，常规终端命令直接零阻力放行 ("decision": "allow")；
 * 一旦检测到可能丢弃未提交工作或重写远端历史的破坏性 Git 命令，
 * 立即触发强制人工确认 ("decision": "force_ask")，守住代码库安全底线。
 */

const fs = require('fs');

let raw = '';
try {
  raw = fs.readFileSync(0, 'utf8');
} catch (_) {}

let payload = {};
try {
  payload = JSON.parse(raw || '{}');
} catch (_) {}

const args = (payload.toolCall && payload.toolCall.args) || {};
const cmd = String(args.CommandLine || args.commandLine || args.command || '');

const dangerPatterns = [
  { re: /git\s+push\b[^\n]*--force(?!-with-lease)/i, msg: 'git push --force (会覆盖远端历史，建议改用 --force-with-lease)' },
  { re: /git\s+push\b[^\n]*(?:\s-f\b|\s-[a-zA-Z]*f[a-zA-Z]*\b)/i, msg: 'git push -f (强制推送)' },
  { re: /git\s+push\b[^\n]*--delete/i, msg: 'git push --delete (删除远端分支/标签)' },
  { re: /git\s+push\b\s+\S+\s+:[^\s]+/i, msg: 'git push origin :branch (删除远端分支)' },
  { re: /git\s+reset\b[^\n]*--hard/i, msg: 'git reset --hard (丢弃工作区与暂存区改动)' },
  { re: /git\s+clean\b[^\n]*-[a-zA-Z]*f/i, msg: 'git clean -f (永久删除未跟踪文件)' },
  { re: /git\s+branch\b[^\n]*\s-D\b/, msg: 'git branch -D (强制删除未合并分支)' },
  { re: /git\s+checkout\b[^\n]*\s--\s+\S/i, msg: 'git checkout -- <file> (丢弃工作区文件改动)' },
  { re: /git\s+restore\b[^\n]*--worktree/i, msg: 'git restore --worktree (丢弃工作区改动)' },
  { re: /git\s+reflog\b[^\n]*delete/i, msg: 'git reflog delete (抹除 reflog 恢复记录)' },
  { re: /git\s+update-ref\b[^\n]*\s-d\b/i, msg: 'git update-ref -d (直接删除 Git 引用)' },
  { re: /git\s+filter-branch\b/i, msg: 'git filter-branch (大规模重写历史)' },
  { re: /git\s+gc\b[^\n]*--prune=now/i, msg: 'git gc --prune=now (立即彻底清除悬空对象，无法恢复)' },
];

for (const item of dangerPatterns) {
  if (item.re.test(cmd)) {
    const response = {
      decision: 'force_ask',
      reason: `⚠️ Git 高危操作护栏拦截: ${item.msg}\n拟执行命令: ${cmd}`,
    };
    process.stdout.write(JSON.stringify(response) + '\n');
    process.exit(0);
  }
}

process.stdout.write(JSON.stringify({ decision: 'allow' }) + '\n');
process.exit(0);
