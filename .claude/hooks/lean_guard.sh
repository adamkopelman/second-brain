#!/usr/bin/env bash
# Runs lean_guard.py with whichever Python exists (python3 / python / py). Allows the call if none.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c "import sys" >/dev/null 2>&1; then
    exec "$py" "$HERE/lean_guard.py"
  fi
done
exit 0
