# Environment Contract Reference

> AUTO-GENERATED from `contracts/runtime/env_contract_registry.yaml`. Do not edit manually.

## Contract Snapshot

- Contract vars: `59`
- Business env prefixes: `MOVI_`, `GEMINI_`, `LIVE_`, `CLEAN_CACHE_`, `PRE_COMMIT_`, `PYTEST_`, `HEARTBEAT_`, `QUALITY_GATE_`
- Category budgets: `MOVI_42`, `GEMINI_5`, `LIVE_5`, `CLEAN_CACHE_3`, `PRE_COMMIT_3`, `PYTEST_3`, `HEARTBEAT_2`, `QUALITY_GATE_3`

## required

| Variable | Prefix |
| --- | --- |
| `GEMINI_API_KEY` | `GEMINI_` |
| `GEMINI_MODEL` | `GEMINI_` |

## runtime-optional

| Variable | Prefix |
| --- | --- |
| `MOVI_WORKSPACE_ROOT` | `MOVI_` |
| `MOVI_INPUT_ROOT` | `MOVI_` |
| `MOVI_OUTPUT_ROOT` | `MOVI_` |
| `MOVI_MANIFEST_ROOT` | `MOVI_` |
| `MOVI_ARTIFACT_ROOT` | `MOVI_` |
| `MOVI_EVIDENCE_BUNDLE_PATH` | `MOVI_` |
| `MOVI_RUN_LIVE_TESTS` | `MOVI_` |
| `MOVI_LIVE_TEST_URL` | `MOVI_` |
| `MOVI_LIVE_COVERAGE_FILE` | `MOVI_` |
| `LIVE_COVERAGE_FILE` | `LIVE_` |
| `LIVE_HEARTBEAT_INTERVAL_SECONDS` | `LIVE_` |
| `LIVE_MAX_DURATION_SECONDS` | `LIVE_` |
| `LIVE_MAX_RETRIES` | `LIVE_` |
| `MOVI_ROLLBACK_HMAC_KEY` | `MOVI_` |
| `MOVI_ALLOW_HOST_EXECUTION` | `MOVI_` |
| `MOVI_ALLOW_EXTERNAL` | `MOVI_` |
| `MOVI_COMPOSE_FILE` | `MOVI_` |
| `MOVI_COMPOSE_SERVICE` | `MOVI_` |
| `MOVI_CI_IMAGE` | `MOVI_` |
| `MOVI_PREBUILT_VENV_DIR` | `MOVI_` |
| `MOVI_WEB_API_HOST` | `MOVI_` |
| `MOVI_WEB_API_PORT` | `MOVI_` |
| `MOVI_WEBUI_HOST` | `MOVI_` |
| `MOVI_WEBUI_PORT` | `MOVI_` |
| `MOVI_VENV_DIR` | `MOVI_` |
| `MOVI_ATOMIC_ALLOWLIST` | `MOVI_` |
| `MOVI_ATOMIC_MAX_FILES` | `MOVI_` |
| `MOVI_ATOMIC_MAX_LINES` | `MOVI_` |
| `MOVI_CLI_REPORT_BUDGET_MS` | `MOVI_` |
| `MOVI_PRE_PUSH_MODE` | `MOVI_` |
| `MOVI_REQUIRE_NON_EMPTY_RANGE` | `MOVI_` |
| `MOVI_ROLLBACK_RTO_BUDGET_MS` | `MOVI_` |
| `CLEAN_CACHE_ROOT` | `CLEAN_CACHE_` |
| `HEARTBEAT_INTERVAL_SECONDS` | `HEARTBEAT_` |
| `GEMINI_UI_AUDIT_MODEL` | `GEMINI_` |
| `GEMINI_UI_AUDIT_TIMEOUT_MS` | `GEMINI_` |
| `QUALITY_GATE_MAX_STEP_SECONDS` | `QUALITY_GATE_` |
| `QUALITY_GATE_ALLOW_LIVE_NETWORK_TIMEOUT` | `QUALITY_GATE_` |
| `PYTEST_HEARTBEAT_NAME` | `PYTEST_` |
| `PYTEST_MAX_DURATION_SECONDS` | `PYTEST_` |

## runtime-optional (observability context)

| Variable | Prefix |
| --- | --- |
| `MOVI_TRACE_ID` | `MOVI_` |
| `MOVI_SESSION_ID` | `MOVI_` |
| `MOVI_REQUEST_ID` | `MOVI_` |
| `MOVI_USER_ID` | `MOVI_` |
| `MOVI_RUN_BUNDLE_ROOT` | `MOVI_` |
| `MOVI_RUN_DIR` | `MOVI_` |
| `MOVI_RUN_EVENTS_PATH` | `MOVI_` |
| `MOVI_RUN_STDERR_PATH` | `MOVI_` |
| `MOVI_RUN_SUMMARY_PATH` | `MOVI_` |
| `MOVI_RUN_EVIDENCE_INDEX_PATH` | `MOVI_` |

## ci-only

| Variable | Prefix |
| --- | --- |
| `MOVI_IN_CONTAINER` | `MOVI_` |
| `PRE_COMMIT_FROM_REF` | `PRE_COMMIT_` |
| `PRE_COMMIT_TO_REF` | `PRE_COMMIT_` |

## test-only

| Variable | Prefix |
| --- | --- |
| `MOVI_ENABLE_TEST_HOOKS` | `MOVI_` |
| `MOVI_APPLY_CRASH_AT` | `MOVI_` |
| `PYTEST_CURRENT_TEST` | `PYTEST_` |
| `LIVE_TEST_PID` | `LIVE_` |
