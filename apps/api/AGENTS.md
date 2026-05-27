# AGENTS.md (apps/api)

This directory contains the Web API entry surface and HTTP adaptation layer for the core `analyze`, `apply`, `rollback`, `report`, and manifest workflow.

## Boundary

- Keep business rules out of the API layer.
- Treat `contracts/api` and generated references as the API truth sources.
- Keep HTTP adaptation aligned with manifest-driven job execution.
