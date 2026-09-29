# Private Repository Setup

1. Create a private repository from this template.
2. Clone it locally.
3. Replace placeholder `AGENTS.md` content with your real private rules.
4. Add slash commands and hooks only after reviewing their side effects.
5. Keep credentials in local environment variables or local-only files.
6. Run `python -B scripts/verify.py` before every commit.

Recommended flow:

```bash
python -B scripts/verify.py
python -B scripts/install.py --dry-run
python -B scripts/install.py
```

Do not publish the private repository unless it has been separately
declassified.
