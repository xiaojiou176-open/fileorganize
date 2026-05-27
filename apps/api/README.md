# apps/api

This directory holds the Web API entry layer.

## Responsibilities

- expose the job API
- adapt HTTP and SSE surfaces
- keep the API aligned with the same core `analyze`, `apply`, `rollback`, `report`, and manifest workflow used by the CLI

## Non-goals

- do not redefine core business rules here
- do not bypass manifest, rollback, or logging contracts
