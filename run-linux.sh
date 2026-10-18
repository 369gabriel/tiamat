#!/usr/bin/env bash
# Run Tiamat on Linux against the macOS League client running under Darling.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if [[ ! -x .venv/bin/python ]]; then
    python -m venv .venv
    .venv/bin/pip install -q -e .
fi

export DPREFIX="${DPREFIX:-$HOME/.darling}"
exec .venv/bin/python tiamat/main.py "$@"
