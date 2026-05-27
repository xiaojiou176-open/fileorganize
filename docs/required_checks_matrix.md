# Required Checks Matrix

> AUTO-GENERATED from `contracts/governance/required_checks_policy.yaml` + GitHub workflow topology. Do not edit manually.

## Workflow Snapshot

- Workflow files: `.github/workflows/ci.yml`, `.github/workflows/trivy-fs.yml`, `.github/workflows/trufflehog.yml`, `.github/workflows/zizmor.yml`
- Branch protection target: `main`
- Declared required checks: `16`
- Workflow job entries discovered: `50`
- `merge_group` trigger coverage: all required-check workflows enabled

## Required Checks Alignment Matrix

| workflow_file | job_id | purpose | blocking level | Failure-domain policy | Branch protection guidance | workflow status |
| --- | --- | --- | --- | --- | --- | --- |
| `.github/workflows/ci.yml` | `fork-pr-safety-gate` | Fork PR safety gate that asserts untrusted PRs stay on hosted-only public checks | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `commit-message-lint` | Conventional Commits message gate | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `atomic-commit-gate` | Atomic commit gate for file-count and line-count thresholds | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `secrets-supply-chain-gate` | Secrets and supply-chain blocking scan | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `lint-backend` | Backend lint plus docs/logging/contract gates | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `lint-frontend` | Frontend/style/UI audit gate | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `webui-build-test` | WebUI correctness gate (`npm ci` + `vitest` + `vite build`) | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `ci-hardening-gate` | CI hardening gate for workflow structure and dependency anti-regression | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `quality-gate-full` | Remote canonical full-verification gate (coverage/static/security/full pytest plus canonical short checks) | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `packaging-gate` | Packaging/installability gate (`docs_smoke --install-smoke`) | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `mutation-canary-gate` | Dedicated mutation canary gate split from the test job to block false greens | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `functional-gate` | Supplemental critical-functional smoke gate | `required` | `hosted-primary-plus-hosted-retry` | Mark as a required status check | `present` |
| `.github/workflows/ci.yml` | `test` | Python version parity and supplemental regression verification (without duplicating short-check terminal truth) | `required` | `hosted-primary-plus-hosted-retry` | Mark the aggregated `test` resolver as required; matrix lanes remain diagnostic detail | `present` |
| `.github/workflows/zizmor.yml` | `zizmor` | GitHub Actions security lint for closeout-owned workflow surfaces | `required` | `hosted-single-lane` | Mark as a required status check | `present` |
| `.github/workflows/trivy-fs.yml` | `trivy-fs` | Filesystem vulnerability scan for tracked repository content | `required` | `hosted-single-lane` | Mark as a required status check | `present` |
| `.github/workflows/trufflehog.yml` | `trufflehog` | Git history secret scan with a second engine in addition to gitleaks | `required` | `hosted-single-lane` | Mark as a required status check | `present` |

## Failure-Domain Summary

| job_id | failure_domain_policy | reason |
| --- | --- | --- |
| `fork-pr-safety-gate` | `hosted-primary-plus-hosted-retry` | Control-style gate with no runtime image dependency; keep the public safety check on GitHub-hosted lanes only. |
| `commit-message-lint` | `hosted-primary-plus-hosted-retry` | Depends only on git history and deterministic script logic, so hosted primary plus hosted retry is appropriate. |
| `atomic-commit-gate` | `hosted-primary-plus-hosted-retry` | Pure diff/script gate with no need for secrets or repository-owned runner inventory. |
| `secrets-supply-chain-gate` | `hosted-primary-plus-hosted-retry` | Secrets and supply-chain scanning stays on GitHub-hosted lanes so fork PRs can run it without private infrastructure. |
| `lint-backend` | `hosted-primary-plus-hosted-retry` | Backend lint and docs/policy gates are deterministic and containerized, so hosted primary with hosted retry remains appropriate. |
| `lint-frontend` | `hosted-primary-plus-hosted-retry` | Frontend lint and deterministic build/lint paths fit hosted primary, while hosted retry preserves a second GitHub-hosted lane. |
| `webui-build-test` | `hosted-primary-plus-hosted-retry` | Deterministic frontend test/build lane stays GitHub-hosted for public collaboration safety. |
| `ci-hardening-gate` | `hosted-primary-plus-hosted-retry` | Pure workflow-structure validation belongs on GitHub-hosted lanes only. |
| `quality-gate-full` | `hosted-primary-plus-hosted-retry` | The canonical full gate is fully containerized and uses hosted retry instead of repository-owned runner fallback. |
| `packaging-gate` | `hosted-primary-plus-hosted-retry` | Install smoke is deterministic packaging validation, so hosted primary plus hosted retry is appropriate. |
| `mutation-canary-gate` | `hosted-primary-plus-hosted-retry` | Mutation canary is deterministic and containerized, so hosted primary with hosted retry remains the right failure-domain split. |
| `functional-gate` | `hosted-primary-plus-hosted-retry` | Critical functional smoke is containerized and does not depend on repository-owned runner state. |
| `test` | `hosted-primary-plus-hosted-retry` | The Python version parity matrix already consumes the runtime image family, so hosted primary with hosted retry is sufficient. |
| `zizmor` | `hosted-single-lane` | Zizmor runs as a single GitHub-hosted workflow that blocks high-severity workflow-security regressions. |
| `trivy-fs` | `hosted-single-lane` | Trivy filesystem scanning runs as a single GitHub-hosted workflow and blocks high/critical findings. |
| `trufflehog` | `hosted-single-lane` | TruffleHog runs as a single GitHub-hosted workflow and blocks verified/unknown secret findings in git history. |

## Workflow Job Inventory

| workflow_file | job_id | in required_checks policy |
| --- | --- | --- |
| `.github/workflows/ci.yml` | `atomic-commit-gate` | `yes` |
| `.github/workflows/ci.yml` | `atomic-commit-gate-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `atomic-commit-gate-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `build-ci-image` | `no` |
| `.github/workflows/ci.yml` | `change-detection` | `no` |
| `.github/workflows/ci.yml` | `change-detection-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `change-detection-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `ci-bootstrap` | `no` |
| `.github/workflows/ci.yml` | `ci-hardening-gate` | `yes` |
| `.github/workflows/ci.yml` | `ci-hardening-gate-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `ci-hardening-gate-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `cleanup-resources` | `no` |
| `.github/workflows/ci.yml` | `commit-message-lint` | `yes` |
| `.github/workflows/ci.yml` | `commit-message-lint-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `commit-message-lint-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `evidence-bundle` | `no` |
| `.github/workflows/ci.yml` | `fork-pr-safety-gate` | `yes` |
| `.github/workflows/ci.yml` | `functional-gate` | `yes` |
| `.github/workflows/ci.yml` | `functional-gate-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `functional-gate-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `lint-backend` | `yes` |
| `.github/workflows/ci.yml` | `lint-backend-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `lint-backend-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `lint-frontend` | `yes` |
| `.github/workflows/ci.yml` | `lint-frontend-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `lint-frontend-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `live-smoke-preflight` | `no` |
| `.github/workflows/ci.yml` | `live-smoke-preflight-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `live-smoke-preflight-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `mutation-canary-gate` | `yes` |
| `.github/workflows/ci.yml` | `mutation-canary-gate-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `mutation-canary-gate-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `packaging-gate` | `yes` |
| `.github/workflows/ci.yml` | `packaging-gate-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `packaging-gate-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `quality-gate-full` | `yes` |
| `.github/workflows/ci.yml` | `quality-gate-full-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `quality-gate-full-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `secrets-supply-chain-gate` | `yes` |
| `.github/workflows/ci.yml` | `secrets-supply-chain-gate-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `secrets-supply-chain-gate-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `test` | `yes` |
| `.github/workflows/ci.yml` | `test-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `test-hosted-retry` | `no` |
| `.github/workflows/ci.yml` | `webui-build-test` | `yes` |
| `.github/workflows/ci.yml` | `webui-build-test-hosted-primary` | `no` |
| `.github/workflows/ci.yml` | `webui-build-test-hosted-retry` | `no` |
| `.github/workflows/trivy-fs.yml` | `trivy-fs` | `yes` |
| `.github/workflows/trufflehog.yml` | `trufflehog` | `yes` |
| `.github/workflows/zizmor.yml` | `zizmor` | `yes` |
