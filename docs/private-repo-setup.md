# Private Repository Setup

1. Create a private repository from this template.
2. Clone it locally.
3. Rename the local checkout so its name does not end in `-template`, and rename
   `docs/public-private-boundary.md` to `docs/template-origin-boundary.md` in your
   **private copy**. The original marker intentionally blocks private backups in
   a public template checkout. Confirm the new GitHub repository is private before
   adding any personal data.
4. Replace placeholder `AGENTS.md` content with your real private rules.
5. Add slash commands and hooks only after reviewing their side effects.
6. Keep credentials in local environment variables or local-only files.
7. Run `python -B scripts/verify.py` before every commit.

Recommended flow:

```bash
python -B scripts/verify.py
python -B scripts/install.py --dry-run
python -B scripts/install.py
```

Do not publish the private repository unless it has been separately
declassified.
