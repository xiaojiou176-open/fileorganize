# AGENTS.md (tooling)

Local policy for `tooling/`.

## Goal

Keep public command surfaces stable and keep internal implementation behind the public entry roots.

## Public entry roots

- `tooling/runtime/`
- `tooling/gates/`
- `tooling/docs/`
- `tooling/cleanup/`
- `tooling/ci/`
- `tooling/upstreams/`

`tooling/scripts/` is internal implementation, not the default public interface.

## Rules

- Add public commands to the correct public entry root first.
- Keep README, docs, package scripts, and workflows pointing to public entrypoints.
- Do not promote `tooling/scripts/` back into the public route unless absolutely necessary.
