# Git command guard

`hooks.json` registers `git-guard.js` for Antigravity `PreToolUse` / `run_command`.
The installer renders the bundled handler to an absolute local path, so it works
from unrelated project directories. It preserves other hooks, custom handlers,
and the guard's existing disabled state.

The handler reads the proposed command from JSON on stdin and returns JSON on
stdout, following the [official hook contract](https://antigravity.google/docs/hooks).
`allow` delegates to the next hook/default permission policy; `force_ask` requires
review even when cached permissions or Turbo would otherwise approve it.

Known destructive operations include forced pushes/refspecs and mirror pushes,
remote deletion, hard reset, forced clean, forced branch deletion, worktree restore,
checkout/switch discard, stash deletion, reflog deletion, ref deletion, history
filtering, and immediate garbage pruning. Global Git options (`-C`, `-c`,
`--git-dir`) and `git.exe` paths are recognized. Safe `branch -d`, clean dry runs,
and `restore --staged` remain allowed. Each command in a compound restore is
checked independently. `push --force-with-lease` remains delegated to default policy.

Malformed or missing input requires review. Reasons contain an operation category,
never the full proposed command, which may contain private arguments.

This is a best-effort command guard, not a shell sandbox. Aliases, arbitrary scripts,
encoded commands, executable indirection, and every shell grammar cannot be covered.
Keep ordinary permission rules and original backups. Restart Antigravity/agy after
installation; direct protocol tests do not establish that an existing session has
reloaded hooks.
