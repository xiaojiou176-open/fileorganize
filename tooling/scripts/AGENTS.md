# AGENTS.md (tooling/scripts)

Local policy for the internal `tooling/scripts/` layer.

## Boundary

This directory is internal implementation only.

Public entrypoints live under:

- `tooling/runtime/`
- `tooling/gates/`
- `tooling/docs/`
- `tooling/cleanup/`
- `tooling/ci/`
- `tooling/upstreams/`

## Rules

- Do not advertise these paths as default user-facing commands.
- Add new files here only when they are truly internal helpers.
- Validate the corresponding public wrapper after changing internal scripts.
- Keep internal checks aligned with `quality_gate`, `doc_drift`, `write_before_search`, `no_logs_no_merge`, and pre-push / pre-commit behavior.
