#!/usr/bin/env bash
# testbank.sh  <RESULTS_FILE>  <TARGET_DIR>
# Appends " [N questions]" to the testbank.md line in results.

RESULTS_FILE="$1"
TARGET="$2"

[[ -f "$RESULTS_FILE" ]] || exit 1

filepath="$TARGET/testbank.md"
[[ -f "$filepath" ]] || exit 0

total=$(grep -c '^# Question' "$filepath" 2>/dev/null || echo 0)

sed -i '' "s|\(.*testbank\.md.*\)|\1 [${total} questions]|" "$RESULTS_FILE"
