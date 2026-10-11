# Hooks

Hooks can automate local Google Antigravity workflows, but they can also mutate files,
run commands, or push data.

Keep this public template hook-free by default. Add hook examples only when
they are safe, dry-run friendly, and clearly documented.

Do not commit hooks that silently upload memory, push repositories, install
software, or read secrets unless they are explicitly public-safe examples.

## PreToolUse Guardrail Example: `git-guard.js`

Configured in `hooks.json` under `PreToolUse` for `run_command`. In `TURBO` mode, non-destructive commands pass through automatically (`decision: allow`), while destructive Git commands trigger mandatory manual confirmation (`decision: force_ask`):

- **Remote history rewrites**: `git push --force` (excluding `--force-with-lease`), `git push -f`, and `git push +<ref>` refspec force pushes.
- **Remote deletion**: `git push --delete`, `git push origin :<branch>`.
- **Worktree discard**: `git reset --hard`, `git checkout -- <file>`, `git checkout .`, `git checkout -f`, `git switch -f/--discard-changes`, and `git restore` (when modifying worktree). Safe unstaging `git restore --staged` / `-S` is allowed.
- **Untracked deletion & force branch deletion**: `git clean -f/--force`, `git branch -D/--delete --force`.
- **Destructive stash & history manipulation**: `git stash drop`, `git stash clear`, `git reflog delete`, `git update-ref -d`, `git filter-branch`, and `git gc --prune=now`.
