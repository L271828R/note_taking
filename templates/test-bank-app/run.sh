#!/usr/bin/env bash
# test-bank — launch the spaced-repetition quiz engine

ROOT="$(cd "$(dirname "$0")" && pwd)"
NOTES_FOLDERS_PATH="${NOTES_FOLDERS_PATH:-}"
NOTES_CURRENT_FILE="${NOTES_CURRENT_FILE:-}"

# Resolve the current notes folder (where testbank.md files live)
if [ -n "$NOTES_CURRENT_FILE" ] && [ -f "$NOTES_CURRENT_FILE" ]; then
    CURRENT="$(cat "$NOTES_CURRENT_FILE" | tr -d '[:space:]')"
    if [ -n "$NOTES_FOLDERS_PATH" ] && [ -n "$CURRENT" ]; then
        NOTES_DIR="$NOTES_FOLDERS_PATH/$CURRENT"
    fi
fi

# Fallback: two levels up from apps/test-bank/
NOTES_DIR="${NOTES_DIR:-$(dirname "$(dirname "$ROOT")")}"

VENV_PYTHON="$NOTES_FOLDERS_PATH/../../../projects/notes/python_scripts/venv/bin/python3"

# Try the notes venv first, then system python3
if [ -f "$VENV_PYTHON" ]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="$(command -v python3)"
fi

if [ -z "$PYTHON" ]; then
    echo "Error: python3 not found." >&2
    exit 1
fi

exec "$PYTHON" "$ROOT/quiz.py" --notes-dir "$NOTES_DIR" --db "$ROOT/progress.db"
