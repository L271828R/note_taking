#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 [options] <file.md>

Options:
  -i, --inject           Inject an ID if none exists
  -p, --print-id         Print the ID (after inject if requested)
  -t, --print-title      Print the Title (from "# Title:" or first heading)
  -u, --update-map       Update the JSON map with this file's id/title
  -m, --map-file PATH    Use PATH instead of default ~/.projects/notes/.note_map.json
  -h, --help             Show this help and exit
EOF
  exit 1
}

# defaults
inject=false
print_id=false
print_title=false
update_map=false
map_file=""

# parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    -i|--inject)        inject=true; shift;;
    -p|--print-id)      print_id=true; shift;;
    -t|--print-title)   print_title=true; shift;;
    -u|--update-map)    update_map=true; shift;;
    -m|--map-file)      map_file="$2"; shift 2;;
    -h|--help)          usage;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      ;;
    *)
      file="$1"
      shift
      ;;
  esac
done

# validate
[[ -n "${file:-}" ]] || usage
[[ -f "$file" ]] || { echo "File not found: $file" >&2; exit 1; }

# vault & map
vault_dir="${NOTES_PATH:-$HOME/projects/notes}"
: "${map_file:=$vault_dir/.note_map.json}"

echo "📄 File: $file"
echo "🗺️  Map:  $map_file"

# read full content
content=$(<"$file")

# 1) ID detection
id_line=$(grep -m1 -E '^<!-- id: [0-9a-f]{8} -->' "$file" || true)
if [[ -n "$id_line" ]]; then
  id=$(printf '%s' "$id_line" | sed -E 's/^<!-- id: ([0-9a-f]{8}) -->$/\1/')
else
  id=""
fi

# inject if requested and none found
if [[ -z "$id" && "$inject" = true ]]; then
  id=$(printf '%08x' $((RANDOM<<15 | RANDOM)))
  echo "🔨 Injecting id: $id"
  tmp=$(mktemp)
  printf '<!-- id: %s -->\n%s' "$id" "$content" > "$tmp"
  mv "$tmp" "$file"
  content=$(<"$file")
fi

$print_id && echo "🆔 ID: ${id:-<none>}"

# 2) Title extraction
# First try "# Title: ..."
title=$(grep -m1 '^# Title:' "$file" | sed -E 's/^# Title:[[:space:]]*//')
if [[ -z "$title" ]]; then
  # fallback to first heading
  title=$(grep -m1 '^# ' "$file" | sed -E 's/^#+[[:space:]]*//')
fi
print_title && echo "🏷️  Title: ${title:-<none>}"

# 3) Update map
if [[ "$update_map" = true ]]; then
  command -v jq >/dev/null || { echo "Error: jq is required to update map" >&2; exit 1; }
  rel="${file#$vault_dir/}"
  echo "🔄 Updating map entry: id=$id, path=$rel, title=$title"
  tmp=$(mktemp)
  jq --arg id "$id" --arg path "$rel" --arg title "$title" \
     '.[$id] = {path:$path, title:$title}' "$map_file" > "$tmp"
  mv "$tmp" "$map_file"
  echo "✅ Map updated."
fi

