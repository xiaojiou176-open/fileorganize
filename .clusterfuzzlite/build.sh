#!/bin/bash
set -euo pipefail

python3 -m pip install --disable-pip-version-check atheris
python3 -m pip install --disable-pip-version-check .

compile_python_fuzzer tests/fuzz/fuzz_safe_join.py
