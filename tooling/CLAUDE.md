# CLAUDE.md (tooling)

Quick execution memory for `tooling/`.

## Mental model

Treat `tooling/` like the repository control panel:

- `runtime` runs things
- `gates` blocks or allows things
- `docs` renders and validates docs
- `cleanup` clears residue
- `ci` supports remote execution
- `upstreams` tracks dependency and upstream governance
- `scripts` is internal wiring

## Rule of thumb

Prefer editing the public entry surface first, then the internal implementation behind it.
