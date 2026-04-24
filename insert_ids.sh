#!/usr/bin/env bash
set -euo pipefail

# === Adjust if needed ===
VAULT_ROOT="${NOTES_PATH:-$HOME/projects/notes}"
PLUGIN_DIR="$VAULT_ROOT/nvim-lua"
PLUGIN_FILE="$PLUGIN_DIR/nvim-notes-macros.lua"
# ========================

if [[ ! -f "$PLUGIN_FILE" ]]; then
  echo "Error: plugin file not found: $PLUGIN_FILE" >&2
  exit 1
fi

nvim --headless -u NONE \
  -c "lua local M = dofile('$PLUGIN_FILE') M.insert_ids()" \
  -c "qa!" \
  || { echo "❌ headless Neovim call failed" >&2; exit 1; }

echo "✅ insert_ids() completed."
echo "  • Log: $VAULT_ROOT/.note_map.log"
echo "  • Map: $VAULT_ROOT/.note_map.json"

