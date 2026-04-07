# CLAUDE.md (tooling/scripts)

Quick execution memory for the internal scripts layer.

## Mental model

This directory is the wiring behind the control panel.

- maintainable
- reusable
- not the default public button surface

## Reminder

If a `tooling/scripts/*` path shows up in public-facing docs, that is usually a governance regression.
Typical internal keywords to preserve are `quality_gate`, `doc_drift`, `write_before_search`, `no_logs_no_merge`, and pre-push gate behavior.
