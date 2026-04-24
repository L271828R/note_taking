#!/usr/bin/env bash
#
# count-kanban.sh  <RESULTS_FILE>  <TARGET_DIR>
#
# ONLY appends " tickets=<n>" to lines whose filename contains "kanban".
# Leaves every other line (and its colors) exactly as-is.

RESULTS_FILE="$1"
TARGET="$2"

if [[ ! -f "$RESULTS_FILE" ]]; then
  echo "count-kanban.sh: '$RESULTS_FILE' not found!" >&2
  exit 1
fi

tmp=$(mktemp)
while IFS= read -r line; do
  # grab the filename (2nd field)
  name=$(awk '{print $2}' <<<"$line")

  if [[ "$name" == *kanban* ]]; then
    # count "Ticket" lines in the actual file (0 if none)
    cnt=$(grep -c 'Ticket' "$TARGET/$name" 2>/dev/null)
    printf "%s tickets=%s\n" "$line" "$cnt" >> "$tmp"
  else
    # non-kanban → re-print exactly (preserves any ANSI codes)
    printf "%s\n" "$line" >> "$tmp"
  fi
done < "$RESULTS_FILE"

mv "$tmp" "$RESULTS_FILE"

