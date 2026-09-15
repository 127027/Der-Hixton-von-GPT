#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AGENT_DIR="${HIXTON_AGENT_DIR:-.agent}"
LOG_DIR="$AGENT_DIR/qa-logs"
SUMMARY_FILE="$AGENT_DIR/qa-summary.txt"
mkdir -p "$LOG_DIR"
: > "$SUMMARY_FILE"

failures=0

run_gate() {
  local name="$1"
  shift
  local log_file="$LOG_DIR/${name}.log"

  echo "==> $name" | tee -a "$SUMMARY_FILE"
  if "$@" >"$log_file" 2>&1; then
    echo "PASS $name" | tee -a "$SUMMARY_FILE"
  else
    local rc=$?
    echo "FAIL $name rc=$rc log=$log_file" | tee -a "$SUMMARY_FILE"
    failures=$((failures + 1))
  fi
}

run_gate python_compile python -m compileall -q src
run_gate ruff python -m ruff check src tests
run_gate mypy python -m mypy src
run_gate pytest timeout 20m python -m pytest -q

if [[ -d ui ]]; then
  run_gate ui_test npm --prefix ui test
  run_gate ui_typecheck npm --prefix ui run check
  run_gate ui_build npm --prefix ui run build
fi

printf '\nTOTAL_FAILURES=%d\n' "$failures" | tee -a "$SUMMARY_FILE"

if (( failures > 0 )); then
  echo "QUALITY_GATE=FAIL" | tee -a "$SUMMARY_FILE"
  exit 1
fi

echo "QUALITY_GATE=PASS" | tee -a "$SUMMARY_FILE"
