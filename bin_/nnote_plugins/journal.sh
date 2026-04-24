#!/usr/bin/env bash
#
# Prevent re-entry loop by checking for a flag
if [[ -n "$NNOTE_ALREADY_JOURNALED" ]]; then
  exit 0
fi

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
    # 4) Re‑exec nnote with today's date, and mark that we did it
    exec env NNOTE_EXIT_AFTER_PLUGIN=1 NNOTE_ALREADY_JOURNALED=1 "$script_dir/nnote" "$(date +%F).md"
  fi
fi

exit 0

