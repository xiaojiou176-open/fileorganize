#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$DIR")"
REPO_ROOT="$(dirname "$ROOT")"
CONFIG_LIB="$ROOT/scripts/lib_config.sh"
VENV=""
PYPROJECT="$REPO_ROOT/pyproject.toml"
RUNTIME_LOCK="$REPO_ROOT/tooling/requirements.lock.txt"
DEV_LOCK="$REPO_ROOT/tooling/requirements-dev.lock.txt"
RUNTIME_SHELL="$REPO_ROOT/tooling/requirements.txt"
DEV_SHELL="$REPO_ROOT/tooling/requirements-dev.txt"
LOCK_PYTHON_BIN="${LOCK_PYTHON_BIN:-}"
LOCK_VENV_DIR="$REPO_ROOT/.runtime-cache/tmp/upgrade-deps-lock-venv"

if [ ! -f "$CONFIG_LIB" ]; then
  echo "missing config helper: $CONFIG_LIB" >&2
  exit 1
fi
source "$CONFIG_LIB"
load_governance_defaults "$REPO_ROOT"
apply_runtime_env_defaults "$REPO_ROOT"
VENV="$(governance_runtime_venv_path "$REPO_ROOT")"
IFS='|' read -r ALLOW_EXTERNAL ALLOW_EXTERNAL_SOURCE \
  <<< "$(resolve_allow_external_with_source "0")"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --venv)
      VENV="$2"
      shift 2
      ;;
    --pyproject)
      PYPROJECT="$2"
      shift 2
      ;;
    --runtime-lock)
      RUNTIME_LOCK="$2"
      shift 2
      ;;
    --dev-lock)
      DEV_LOCK="$2"
      shift 2
      ;;
    --runtime-shell)
      RUNTIME_SHELL="$2"
      shift 2
      ;;
    --dev-shell)
      DEV_SHELL="$2"
      shift 2
      ;;
    --lock-python)
      LOCK_PYTHON_BIN="$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--venv PATH] [--pyproject PATH] [--runtime-lock PATH] [--dev-lock PATH] [--runtime-shell PATH] [--dev-shell PATH] [--lock-python PATH]" >&2
      exit 2
      ;;
  esac
done

to_abs_path() {
  local target="$1"
  if [ -d "$target" ]; then
    (cd "$target" && pwd -P)
  else
    local parent
    parent="$(cd "$(dirname "$target")" && pwd -P)"
    printf '%s/%s\n' "$parent" "$(basename "$target")"
  fi
}

assert_in_repo() {
  local path="$1"
  case "$path" in
    "$REPO_ROOT"/*) ;;
    *)
      if [ "$ALLOW_EXTERNAL" != "1" ]; then
        echo "Path must be inside repository: $path" >&2
        exit 1
      fi
      ;;
  esac
}

to_repo_relative_path() {
  local path="$1"
  case "$path" in
    "$REPO_ROOT")
      printf '.\n'
      ;;
    "$REPO_ROOT"/*)
      printf '%s\n' "${path#"$REPO_ROOT"/}"
      ;;
    *)
      printf '%s\n' "$path"
      ;;
  esac
}

VENV="$(to_abs_path "$VENV")"
PYPROJECT="$(to_abs_path "$PYPROJECT")"
RUNTIME_LOCK="$(to_abs_path "$RUNTIME_LOCK")"
DEV_LOCK="$(to_abs_path "$DEV_LOCK")"
RUNTIME_SHELL="$(to_abs_path "$RUNTIME_SHELL")"
DEV_SHELL="$(to_abs_path "$DEV_SHELL")"
assert_in_repo "$VENV"
assert_in_repo "$PYPROJECT"
assert_in_repo "$RUNTIME_LOCK"
assert_in_repo "$DEV_LOCK"
assert_in_repo "$RUNTIME_SHELL"
assert_in_repo "$DEV_SHELL"

PIPTOOLS_PYPROJECT="$(to_repo_relative_path "$PYPROJECT")"
PIPTOOLS_RUNTIME_LOCK="$(to_repo_relative_path "$RUNTIME_LOCK")"
PIPTOOLS_DEV_LOCK="$(to_repo_relative_path "$DEV_LOCK")"

echo "==> upgrade_deps allow-external=${ALLOW_EXTERNAL} source=${ALLOW_EXTERNAL_SOURCE}"

if [ ! -x "$VENV/bin/python" ]; then
  echo "venv not found: $VENV" >&2
  exit 1
fi

if [ ! -f "$PYPROJECT" ]; then
  echo "pyproject.toml not found: $PYPROJECT" >&2
  exit 1
fi

if [ -z "$LOCK_PYTHON_BIN" ]; then
  if command -v python3.10 >/dev/null 2>&1; then
    LOCK_PYTHON_BIN="$(command -v python3.10)"
  else
    LOCK_PYTHON_BIN="$VENV/bin/python"
  fi
fi

echo "==> upgrade_deps lock-python=$LOCK_PYTHON_BIN"
"$LOCK_PYTHON_BIN" -m venv "$LOCK_VENV_DIR" --clear
"$LOCK_VENV_DIR/bin/python" -m pip install --disable-pip-version-check "pip==25.0.1"
"$LOCK_VENV_DIR/bin/python" -m pip install --upgrade "pip-tools==7.5.3"

(
  cd "$REPO_ROOT"
  "$LOCK_VENV_DIR/bin/python" -m piptools compile \
    --upgrade \
    --allow-unsafe \
    --generate-hashes \
    --resolver=backtracking \
    --output-file "$PIPTOOLS_RUNTIME_LOCK" \
    "$PIPTOOLS_PYPROJECT"

  "$LOCK_VENV_DIR/bin/python" -m piptools compile \
    --upgrade \
    --allow-unsafe \
    --generate-hashes \
    --resolver=backtracking \
    --extra dev \
    --output-file "$PIPTOOLS_DEV_LOCK" \
    "$PIPTOOLS_PYPROJECT"
)

SOURCE_HASH="$("$VENV/bin/python" - "$PYPROJECT" <<'PY'
import hashlib
import sys
from pathlib import Path

content = Path(sys.argv[1]).read_bytes()
print(hashlib.sha256(content).hexdigest())
PY
)"

stamp_marker() {
  local file_path="$1"
  "$VENV/bin/python" - "$file_path" "$SOURCE_HASH" <<'PY'
import sys
from pathlib import Path

target = Path(sys.argv[1])
marker = sys.argv[2]
lines = target.read_text(encoding="utf-8").splitlines()
filtered = [line for line in lines if not line.startswith("# source-pyproject-sha256:")]
target.write_text("# source-pyproject-sha256: " + marker + "\n" + "\n".join(filtered) + "\n", encoding="utf-8")
PY
}

strip_unsafe_bootstrap_packages() {
  local file_path="$1"
  "$VENV/bin/python" - "$file_path" <<'PY'
import sys
from pathlib import Path

target = Path(sys.argv[1])
lines = target.read_text(encoding="utf-8").splitlines()
blocked = ("pip==",)
filtered: list[str] = []
skip = False

for line in lines:
    stripped = line.strip()
    if skip and stripped and not line.startswith(" "):
        skip = False
    if any(stripped.startswith(prefix) for prefix in blocked):
        skip = True
        continue
    if skip:
        continue
    filtered.append(line)

while filtered and not filtered[-1].strip():
    filtered.pop()

target.write_text("\n".join(filtered) + "\n", encoding="utf-8")
PY
}

strip_unsafe_bootstrap_packages "$RUNTIME_LOCK"
strip_unsafe_bootstrap_packages "$DEV_LOCK"
stamp_marker "$RUNTIME_LOCK"
stamp_marker "$DEV_LOCK"

cat > "$RUNTIME_SHELL" <<EOF
# AUTOGENERATED compatibility shell. Do not edit by hand.
# Single source of truth: pyproject.toml
# source-pyproject-sha256: ${SOURCE_HASH}
-r requirements.lock.txt
EOF

cat > "$DEV_SHELL" <<EOF
# AUTOGENERATED compatibility shell. Do not edit by hand.
# Single source of truth: pyproject.toml
# source-pyproject-sha256: ${SOURCE_HASH}
-r requirements-dev.lock.txt
EOF

echo "Dependencies resolved from pyproject.toml:"
echo "  runtime lock: $RUNTIME_LOCK"
echo "  dev lock:     $DEV_LOCK"
echo "  shell files:  $RUNTIME_SHELL, $DEV_SHELL"
