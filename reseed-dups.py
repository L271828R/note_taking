#!/usr/bin/env python3
"""
clean_and_reseed_ids.py
───────────────────────
1) Per-file: drop any extra <!-- id: … --> lines beyond the first.
2) Whole vault: if an ID still appears in >1 file, keep the first file,
   auto-assign a fresh random ID to the rest.

usage:
    python3 clean_and_reseed_ids.py               # real run, backups on
    python3 clean_and_reseed_ids.py --dry-run     # preview, no changes
    python3 clean_and_reseed_ids.py --verbose     # chatty
    python3 clean_and_reseed_ids.py --no-backups  # don't create .bak
"""

import os, re, json, argparse, datetime
from pathlib import Path
from secrets import token_hex

# ────────── CLI ──────────
ap = argparse.ArgumentParser()
ap.add_argument("--dry-run",    action="store_true")
ap.add_argument("--verbose",    action="store_true")
ap.add_argument("--no-backups", action="store_true")
args = ap.parse_args()

# ────────── paths ──────────
DIR = Path(os.environ.get("NOTES_PATH",
           "/Users/luisrueda/projects/notes")).resolve()
ROOT = Path(os.environ.get("NOTES_FOLDERS_PATH", DIR / "folders")).resolve()
LOG  = DIR / ".clean_ids.log"

def ts(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def log(msg):
    line = f"{ts()}  {msg}"
    if args.verbose: print(line)
    LOG.write_text(LOG.read_text() + line + "\n" if LOG.exists() else line + "\n")

log("=== clean_and_reseed_ids.py start ===")
log(f"vault = {DIR}")
log(f"dry_run={args.dry_run}, backups={not args.no_backups}")

ID_RE = re.compile(r'^<!-- id: ([0-9a-f]{8}) -->', re.MULTILINE)
files = list(ROOT.rglob("*.md"))
log(f"Scanning {len(files)} markdown files")

# ────────── 1) per-file de-duplication ──────────
def keep_first_id(text):
    """Return (clean_text, kept_id) after removing all extra id lines."""
    ids = ID_RE.findall(text)
    if not ids:
        return text, None
    kept, extras = ids[0], ids[1:]
    if not extras:
        return text, kept
    # remove extra lines:
    clean = []
    seen_first = False
    for line in text.splitlines(keepends=True):
        if not seen_first and line.startswith("<!-- id:"):
            seen_first = True
            clean.append(line)          # keep first
            continue
        if seen_first and line.startswith("<!-- id:"):
            continue                    # drop extras
        clean.append(line)
    return "".join(clean), kept

changed_per_file = []

for f in files:
    txt = f.read_text()
    new_txt, kept_id = keep_first_id(txt)
    if txt != new_txt:
        changed_per_file.append(str(f.relative_to(ROOT)))
        if not args.dry_run:
            if not args.no_backups:
                Path(f"{f}.bak").write_text(txt)
            f.write_text(new_txt)
        log(f"Trimmed extra id lines in {f.relative_to(ROOT)}")

log(f"Per-file cleanup done; {len(changed_per_file)} files trimmed")

# ────────── 2) vault-wide duplicate resolution ──────────
id_owner = {}           # id -> first path
dupes    = {}           # id -> [paths...]

for f in files:
    text = f.read_text()
    m = ID_RE.search(text)
    if not m: continue
    nid = m.group(1)
    if nid in id_owner:
        dupes.setdefault(nid, []).append(f)
    else:
        id_owner[nid] = f

if not dupes:
    log("No global duplicate IDs found.")
    log("=== finished ===")
    exit()

log(f"Global duplicates: {len(dupes)} IDs have multiple files")

def new_id(existing):
    while True:
        n = token_hex(4)
        if n not in existing: return n

reseed_report = []

for old_id, dup_paths in dupes.items():
    for f in dup_paths:                # reseed every duplicate after the first
        txt = f.read_text()
        fresh = new_id(id_owner.keys() | dupes.keys())
        new_txt = ID_RE.sub(f"<!-- id: {fresh} -->", txt, count=1)
        if not args.dry_run:
            if not args.no_backups:
                Path(f"{f}.bak").write_text(txt)
            f.write_text(new_txt)
        reseed_report.append({"file": str(f.relative_to(ROOT)),
                              "old": old_id, "new": fresh})
        log(f"Re-seeded {f.relative_to(ROOT)}  {old_id} → {fresh}")

# write JSON report
report_path = DIR / "duplicate_id_changes.json"
report_path.write_text(json.dumps(reseed_report, indent=2))
log(f"✅ Reseeded {len(reseed_report)} files   report: {report_path}")
log("=== finished ===")

