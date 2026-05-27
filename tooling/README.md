# tooling

This directory is the repository control surface that turns policy into executable commands.

## Structure

- `tooling/runtime/`: runtime entrypoints
- `tooling/gates/`: quality and governance gates
- `tooling/docs/`: docs rendering and smoke checks
- `tooling/cleanup/`: cleanup paths
- `tooling/ci/`: CI and release helpers
- `tooling/upstreams/`: upstream and dependency governance
- `tooling/scripts/`: internal implementation

## Boundary

Public docs and user-facing instructions should point to the public entry roots, not to `tooling/scripts/`.
