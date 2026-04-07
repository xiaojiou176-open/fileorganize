# CLAUDE.md (docs)

Quick execution memory for `docs/`.

## Focus

- Keep docs aligned with executable truth
- Preserve a thin public route
- Regenerate render-managed surfaces after doc contract changes

## Main files

- `docs/usage.md`
- `docs/architecture.md`
- `docs/open_source_runbook.md`
- `docs/logging_observability.md`

## Main checks

```bash
python3 tooling/docs/render_docs.py --check
bash tooling/docs/docs_smoke.sh --install-smoke
```
