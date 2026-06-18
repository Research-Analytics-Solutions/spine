<!-- Thanks for contributing to Spine! -->

## What & why

<!-- What does this change, and why? Link any issue. -->

## Checklist

- [ ] Gates pass locally: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy`
- [ ] Added/updated tests (no network — use `ScriptedProvider` / fakes)
- [ ] New feature is a **middleware / backend / adapter**, not a kernel edit
- [ ] Updated docs / package `README.md` if behavior changed
- [ ] Conventional commit message (`feat:`, `fix:`, `docs:`, …)
