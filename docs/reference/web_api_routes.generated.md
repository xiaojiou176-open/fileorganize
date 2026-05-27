# Web API Routes Reference

> AUTO-GENERATED from `contracts/api/web_api.openapi.yaml`. Do not edit manually.

## Route Family Summary

- **Health**: `/healthz`
- **Jobs / history**: `/api/jobs`, `/api/jobs/history`, `/api/jobs/stream`, `/api/jobs/{job_id}`, `/api/jobs/{job_id}/review-queue`, `/api/jobs/{job_id}/review-queue/batch-triage`, `/api/jobs/{job_id}/review-rules/apply`, `/api/jobs/{job_id}/review-rules/from-examples`, `/api/jobs/{job_id}/review-rules/preview`
- **Job events**: `/api/jobs/{job_id}/events`, `/api/jobs/{job_id}/events/stream`, `/api/jobs/{job_id}/stream`
- **Manifest operations**: `/api/jobs/{job_id}/manifest`, `/api/jobs/{job_id}/manifest/batch`, `/api/jobs/{job_id}/manifest/conflicts`, `/api/jobs/{job_id}/manifest/conflicts/resolve`, `/api/jobs/{job_id}/manifest/rows/{row_id}`, `/api/jobs/{job_id}/manifest/view`, `/api/jobs/{job_id}/manifest/{row_id}/preview`
- **Job actions**: `/api/jobs/analyze`, `/api/jobs/apply`, `/api/jobs/rollback`, `/api/jobs/{job_id}/cancel`, `/api/jobs/{job_id}/retry`
- **Report / audit**: `/api/jobs/{job_id}/audit`, `/api/jobs/{job_id}/report`
- **Preferences**: `/api/preferences/learned-rules`, `/api/preferences/naming-templates`, `/api/preferences/review-rules`, `/api/preferences/runtime`, `/api/preferences/runtime/validate`, `/api/preferences/strategy-packs`, `/api/preferences/views`, `/api/preferences/watch-sources`
- **Other**: `/api/inbox/analyze`, `/api/inbox/scan`

## Endpoint Table

| Method | Path | Family | Operation ID | Source |
| --- | --- | --- | --- | --- |
| `GET` | `/healthz` | Health | `get_healthz` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs` | Jobs / history | `get_api_jobs` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/history` | Jobs / history | `get_api_jobs_history` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/stream` | Jobs / history | `get_api_jobs_stream` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}` | Jobs / history | `get_api_jobs_job_id` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}/review-queue` | Jobs / history | `get_review_queue` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/{job_id}/review-queue/batch-triage` | Jobs / history | `batch_triage_review_queue` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/{job_id}/review-rules/apply` | Jobs / history | `apply_review_rule` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/{job_id}/review-rules/from-examples` | Jobs / history | `draft_review_rule_from_examples` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/{job_id}/review-rules/preview` | Jobs / history | `post_api_jobs_job_id_review-rules_preview` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}/events` | Job events | `get_api_jobs_job_id_events` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}/events/stream` | Job events | `get_api_jobs_job_id_events_stream` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}/stream` | Job events | `get_api_jobs_job_id_stream` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}/manifest` | Manifest operations | `get_api_jobs_job_id_manifest` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/{job_id}/manifest/batch` | Manifest operations | `post_api_jobs_job_id_manifest_batch` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}/manifest/conflicts` | Manifest operations | `get_api_jobs_job_id_manifest_conflicts` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/{job_id}/manifest/conflicts/resolve` | Manifest operations | `post_api_jobs_job_id_manifest_conflicts_resolve` | `contracts/api/web_api.openapi.yaml` |
| `PATCH` | `/api/jobs/{job_id}/manifest/rows/{row_id}` | Manifest operations | `patch_api_jobs_job_id_manifest_rows_row_id` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}/manifest/view` | Manifest operations | `get_api_jobs_job_id_manifest_view` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}/manifest/{row_id}/preview` | Manifest operations | `get_api_jobs_job_id_manifest_row_id_preview` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/analyze` | Job actions | `post_api_jobs_analyze` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/apply` | Job actions | `post_api_jobs_apply` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/rollback` | Job actions | `post_api_jobs_rollback` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/{job_id}/cancel` | Job actions | `post_api_jobs_job_id_cancel` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/jobs/{job_id}/retry` | Job actions | `post_api_jobs_job_id_retry` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}/audit` | Report / audit | `get_api_jobs_job_id_audit` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/jobs/{job_id}/report` | Report / audit | `get_job_report` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/preferences/learned-rules` | Preferences | `list_learned_rules` | `contracts/api/web_api.openapi.yaml` |
| `DELETE` | `/api/preferences/learned-rules` | Preferences | `delete_api_preferences_learned-rules` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/preferences/naming-templates` | Preferences | `get_api_preferences_naming-templates` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/preferences/naming-templates` | Preferences | `post_api_preferences_naming-templates` | `contracts/api/web_api.openapi.yaml` |
| `DELETE` | `/api/preferences/naming-templates` | Preferences | `delete_api_preferences_naming-templates` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/preferences/review-rules` | Preferences | `get_api_preferences_review-rules` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/preferences/review-rules` | Preferences | `post_api_preferences_review-rules` | `contracts/api/web_api.openapi.yaml` |
| `DELETE` | `/api/preferences/review-rules` | Preferences | `delete_api_preferences_review-rules` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/preferences/runtime` | Preferences | `get_api_preferences_runtime` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/preferences/runtime` | Preferences | `post_api_preferences_runtime` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/preferences/runtime/validate` | Preferences | `post_api_preferences_runtime_validate` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/preferences/strategy-packs` | Preferences | `list_strategy_packs` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/preferences/views` | Preferences | `get_api_preferences_views` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/preferences/views` | Preferences | `post_api_preferences_views` | `contracts/api/web_api.openapi.yaml` |
| `DELETE` | `/api/preferences/views` | Preferences | `delete_api_preferences_views` | `contracts/api/web_api.openapi.yaml` |
| `GET` | `/api/preferences/watch-sources` | Preferences | `list_watch_sources` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/preferences/watch-sources` | Preferences | `post_api_preferences_watch-sources` | `contracts/api/web_api.openapi.yaml` |
| `DELETE` | `/api/preferences/watch-sources` | Preferences | `delete_api_preferences_watch-sources` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/inbox/analyze` | Other | `start_inbox_analyze` | `contracts/api/web_api.openapi.yaml` |
| `POST` | `/api/inbox/scan` | Other | `scan_inbox_sources` | `contracts/api/web_api.openapi.yaml` |

## API Naming Guardrails

- `overlay` / `resolved snapshot` are internal model and file-output concepts, not stable public HTTP route names.
- Do not introduce alias routes such as `/api/jobs/{id}/manifest/overlay`, `/api/jobs/{id}/manifest/resolved`, `/api/views`, `/api/naming-templates`, or `/api/jobs/{id}/rollback-audit`.
