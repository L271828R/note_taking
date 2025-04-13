#!/usr/bin/env bash
#
# nnote_plugins/journal.sh
# If the current-folder (as stored in $NOTES_CURRENT_FILE) contains "journal",
# and the requested filename isn't already a date, re-run nnote with today's date.

# 1) Read the "current" folder name
if [[ -f "$NOTES_CURRENT_FILE" ]]; then
  current=$(awk 'NF{print; exit}' "$NOTES_CURRENT_FILE")
else
  exit 0
fi

# 2) Only trigger when "journal" is in that name
if [[ "$current" == *journal* ]]; then
  # 3) If the user didn't already pass a YYYY‑MM‑DD.md filename...
  if [[ ! "$1" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$ ]]; then
    # Locate the directory of your nnote script:
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    # 4) Re‑exec nnote with today's date
    exec "$script_dir/nnote" "$(date +%F).md"
  fi
fi

# Otherwise, do nothing—let nnote proceed as normal
exit 0

