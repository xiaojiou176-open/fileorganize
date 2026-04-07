# AGENTS.md (docs)

Local policy for `docs/`.

## Goal

Keep repository documentation executable, minimal, and aligned with current behavior.

## Rules

- Documentation must stay in sync with code and gates.
- Prefer updating existing sections over adding parallel narratives.
- Keep the public docs surface thin.
- Do not reintroduce heavy internal-only documentation into the public route.

## Navigation

- Architecture: `architecture.md`
- Usage: `usage.md`
- Open-source boundary: `open_source_runbook.md`
- Logging policy: `logging_observability.md`
- Generated references: `reference/*.generated.md`

## Verification

```bash
python3 tooling/docs/render_docs.py --check
bash tooling/docs/docs_smoke.sh --install-smoke
```
