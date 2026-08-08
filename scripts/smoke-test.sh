#!/usr/bin/env bash
set -euo pipefail
PYTHON="${PYTHON:-python3}"
echo "== Novel Reader smoke test =="
echo "[1/5] compileall"; "$PYTHON" -m compileall -q novel_reader
echo "[2/5] pytest"; "$PYTHON" -m pytest -q
echo "[3/5] version"; "$PYTHON" cli.py --version
echo "[4/5] self-test"; "$PYTHON" cli.py --self-test
echo "[5/5] compatibility report"; "$PYTHON" cli.py --compat-report
echo "Smoke test concluído."
