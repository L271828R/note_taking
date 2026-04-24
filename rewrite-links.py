#!/usr/bin/env python3
"""
rewrite-links.py – update stale [[id|title]] links so they match the
current .note_map.json.  Run after duplicate-ID reseeding.
"""
import os, re, json, argparse
from pathlib import Path

DIR  = Path(os.environ.get("NOTES_PATH",
           "/Users/luisrueda/projects/notes")).resolve()
ROOT = Path(os.environ.get("NOTES_FOLDERS_PATH", DIR / "folders")).resolve()
MAP  = DIR / ".note_map.json"

ap = argparse.ArgumentParser()
ap.add_argument("--dry-run",    action="store_true")
ap.add_argument("--no-backups", action="store_true")
args = ap.parse_args()

note_map = json.loads(MAP.read_text())
id_by_title = {v["title"]: k for k, v in note_map.items()}

MD_RE   = re.compile(r'\[\[([0-9a-f]{8})\|([^\]]+?)]]')
changed = 0

for fp in ROOT.rglob("*.md"):
    txt  = fp.read_text()
    new  = txt
    def repl(m):
        old_id, old_title = m.group(1), m.group(2)
        if old_id in note_map and note_map[old_id]["title"] == old_title:
            return m.group(0)                      # already correct
        # maybe the title matches another note that received a new id
        new_id = id_by_title.get(old_title)
        if new_id:
            return f"[[{new_id}|{old_title}]]"     # rewrite!
        return m.group(0)                          # cannot resolve
    new = MD_RE.sub(repl, txt)
    if new != txt:
        changed += 1
        if not args.dry_run:
            if not args.no_backups:
                Path(f"{fp}.bak").write_text(txt)
            fp.write_text(new)

print(f"✅ rewrote links in {changed} files" +
      (" (dry-run)" if args.dry_run else ""))

