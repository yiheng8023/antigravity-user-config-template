# Progressive-Disclosure Global Memory (`~/.gemini/config/memory/`)

This directory holds your curated cross-session memory files (`MEMORY.md` and `<topic>.md`) in your private `antigravity-user-config` repository.

## How it works in Antigravity 2.0
1. Place topic-specific markdown files (`<topic>.md`) in `~/.gemini/config/memory/`.
2. Reference their 1-line summaries in `~/.gemini/config/AGENTS.md` (which is injected into `<user_rules>` at the start of every Desktop and CLI session).
3. Use `python -B scripts/memory.py --backup` and `python -B scripts/memory.py --restore` to synchronize `~/.gemini/config/memory/` with your private repository.

> **Security Note**: Never commit personal memories or project history to a public template repository. Keep real memory files in your private `antigravity-user-config` repository only.
