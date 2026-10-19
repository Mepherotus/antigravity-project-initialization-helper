#!/bin/sh
set -eu

# Prerequisites verification
if ! command -v git >/dev/null 2>&1; then
    echo "Error: git is required but not found in PATH." >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required but not found in PATH." >&2
    exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    echo "Error: Python 3.9 or higher is required." >&2
    exit 1
fi

# Resolve directory of init.sh
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Prepend package directory to PYTHONPATH if antigravity_init package exists locally
if [ -d "${SCRIPT_DIR}/antigravity_init" ]; then
    if [ -n "${PYTHONPATH:-}" ]; then
        export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"
    else
        export PYTHONPATH="${SCRIPT_DIR}"
    fi
fi

# Dispatch execution to antigravity_init
exec python3 -m antigravity_init "$@"
