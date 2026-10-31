#!/usr/bin/env node
/** Antigravity PreToolUse：已知破坏性 Git 操作要求确认；不输出命令或凭证。 */
'use strict';

const fs = require('fs');

function respond(decision, reason) {
  process.stdout.write(JSON.stringify(reason ? { decision, reason } : { decision }) + '\n');
}

function tokenize(command) {
  // 保留参数大小写，识别引号内的可执行文件路径及命令分隔符。
  const parts = command.match(/"(?:[^"\\]|\\.)*"|'[^']*'|\d*(?:>>?|<<?)(?:&(?:\d+|-))?|[;&|\n()]|[^\s;&|\n()<>]+/g) || [];
  return parts.map((part) => {
    if ((part.startsWith('"') && part.endsWith('"')) || (part.startsWith("'") && part.endsWith("'"))) {
      return { value: part.slice(1, -1), operator: false };
    }
    return { value: part, operator: /^[;&|\n()]$|^\d*[<>]/.test(part) };
  });
}

function shortFlag(args, flag) {
  return args.some((arg) => /^-[^-]/.test(arg) && arg.slice(1).includes(flag));
}

function cleanFlags(args) {
  // 排除模式可能以 -n 开头；只有实际开关才构成 dry run。
  const flags = new Set();
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === '--exclude') { i += 1; continue; }
    if (arg.startsWith('--exclude=')) continue;
    if (arg === '--dry-run') flags.add('n');
    if (arg === '--force') flags.add('f');
    if (!/^-[^-]/.test(arg)) continue;
    for (let j = 1; j < arg.length; j += 1) {
      if (arg[j] === 'e') {
        if (j === arg.length - 1) i += 1;
        break;
      }
      flags.add(arg[j]);
    }
  }
  return flags;
}

function commandArgs(tokens, start) {
  const args = [];
  for (let i = start; i < tokens.length; i += 1) {
    const token = tokens[i];
    if (token.operator && /^[;&|\n()]$/.test(token.value)) break;
    if (token.operator && /^\d*[<>]/.test(token.value)) {
      // 重定向可出现在任意参数之间；跳过目标后仍须继续检查后续开关。
      if (!/&(?:\d+|-)$/.test(token.value)) {
        if (!tokens[i + 1] || tokens[i + 1].operator) return null;
        i += 1;
      }
      continue;
    }
    args.push(token.value);
  }
  return args;
}

function inspectGit(command, depth = 0) {
  if (depth > 4) return '嵌套命令超过检查范围';
  const tokens = tokenize(command);
  for (let i = 0; i < tokens.length; i += 1) {
    const token = tokens[i].value;
    // 检查 shell -c / PowerShell -Command 这类带引号的内层命令。
    if (/\s/.test(token) && /\bgit(?:\.exe)?\b/i.test(token)) {
      const nested = inspectGit(token, depth + 1);
      if (nested) return nested;
    }
    if (!/(?:^|[\\/])git(?:\.exe)?$/i.test(token)) continue;
    const argv = commandArgs(tokens, i + 1);
    if (argv === null) return 'Git 命令重定向无法可靠解析';
    let j = 0;
    while (j < argv.length && argv[j].startsWith('-')) {
      if (['-C', '-c', '--git-dir', '--work-tree', '--namespace', '--config-env'].includes(argv[j])) j += 2;
      else j += 1;
    }
    const subcommand = argv[j];
    const tail = argv.slice(j + 1);
    const separator = tail.indexOf('--');
    const options = separator < 0 ? tail : tail.slice(0, separator);
    const has = (flag) => options.includes(flag);
    if (subcommand === 'push') {
      if (has('--force') || shortFlag(options, 'f') || has('--mirror')) return 'git push 强制覆盖远端历史';
      if (has('--delete') || shortFlag(options, 'd') || tail.some((arg) => arg.startsWith(':'))) return 'git push 删除远端引用';
      if (tail.some((arg) => arg.startsWith('+'))) return 'git push 强制 refspec';
    }
    if (subcommand === 'reset' && has('--hard')) return 'git reset --hard 丢弃工作区改动';
    if (subcommand === 'clean') {
      const flags = cleanFlags(options);
      if (flags.has('f') && !flags.has('n')) return 'git clean 删除未跟踪文件';
    }
    if (subcommand === 'branch' && (shortFlag(options, 'D') || ((has('--delete') || shortFlag(options, 'd')) && (has('--force') || shortFlag(options, 'f'))))) return 'git branch 强制删除分支';
    if (subcommand === 'restore') {
      const stagedOnly = (has('--staged') || shortFlag(options, 'S')) && !(has('--worktree') || shortFlag(options, 'W'));
      if (!stagedOnly) return 'git restore 丢弃工作区改动';
    }
    if (subcommand === 'checkout' && (separator >= 0 || tail.includes('.') || has('--force') || has('--ours') || has('--theirs') || shortFlag(options, 'f'))) return 'git checkout 丢弃工作区改动';
    if (subcommand === 'switch' && (has('--force') || has('--discard-changes') || shortFlag(options, 'f'))) return 'git switch 丢弃工作区改动';
    if (subcommand === 'stash' && (has('drop') || has('clear'))) return 'git stash 删除恢复记录';
    if (subcommand === 'reflog' && (has('delete') || (has('expire') && options.some((arg) => arg === '--expire=now' || arg === '--expire-unreachable=now')))) return 'git reflog 删除恢复记录';
    if (subcommand === 'update-ref' && shortFlag(options, 'd')) return 'git update-ref 删除引用';
    if (subcommand === 'filter-branch') return 'git filter-branch 重写历史';
    if (subcommand === 'gc' && has('--prune=now')) return 'git gc 立即清除恢复对象';
  }
  return null;
}

function main() {
  let raw;
  try {
    raw = fs.readFileSync(0, 'utf8').trim();
  } catch (_) {
    respond('force_ask', 'Git 护栏无法读取工具参数');
    return;
  }
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (_) {
    if (raw && !/^[{\[]/.test(raw)) payload = { CommandLine: raw };
    else {
      respond('force_ask', 'Git 护栏收到损坏或缺失的工具参数');
      return;
    }
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    respond('force_ask', 'Git 护栏无法识别工具参数');
    return;
  }
  let args = payload.toolCall?.args ?? payload.tool_call?.args ?? payload.toolUse?.args ?? payload.args ?? payload;
  if (typeof args === 'string') {
    try { args = JSON.parse(args); } catch (_) { args = null; }
  }
  const command = args && (args.CommandLine ?? args.commandLine ?? args.command ?? args.cmd);
  if (typeof command !== 'string' || !command.trim()) {
    respond('force_ask', 'Git 护栏缺少有效的 CommandLine');
    return;
  }
  const reason = inspectGit(command);
  respond(reason ? 'force_ask' : 'allow', reason ? `Git 高危操作需要确认：${reason}` : undefined);
}

main();
