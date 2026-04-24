#!/usr/bin/env python3
"""
sync-map.py  ── rebuild .note_map.json and/or Backlinks blocks
adds _very_ chatty TRACE logging so you can see exactly
why each backlink block is or isn't rewritten.

modes:
  --strip-only   remove every "#### Backlinks:" block
  --map-only     rebuild map & exit
  --inject-only  use existing map, inject backlinks
  (none)         run full pipeline  (default)
"""

import os, re, json, argparse, datetime, sys, difflib
from pathlib import Path

# ───────────── CLI ─────────────
cli = argparse.ArgumentParser()
mode = cli.add_mutually_exclusive_group()
mode.add_argument("--strip-only", action="store_true")
mode.add_argument("--map-only",   action="store_true")
mode.add_argument("--inject-only",action="store_true")
cli.add_argument("--dry-run",    action="store_true")
cli.add_argument("--verbose",    action="store_true")
cli.add_argument("--no-backups", action="store_true")
args = cli.parse_args()

# ───────────── CONST / PATHS ─────────────
DIR   = Path(os.environ.get("NOTES_PATH",
             "/Users/luisrueda/projects/notes")).resolve()
ROOT  = Path(os.environ.get("NOTES_FOLDERS_PATH", DIR / "folders")).resolve()
MAP_F = DIR / ".note_map.json"
LOG_F = DIR / ".note_map.log"

BACK_HDR = "#### Backlinks:"
BACK_SPLIT = re.compile(rf"\n?\s*{re.escape(BACK_HDR)}\s*\n", re.I)
ID_RE = re.compile(r'^<!-- id: ([0-9a-f]{8}) -->', re.M)
LINK_RE = re.compile(r'\[\[([0-9a-f]{8})\|')

def ts(): return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def log(msg):
    line = f"{ts()}  {msg}"
    if args.verbose:
        print(line)
    with open(LOG_F, "a") as fh: fh.write(line + "\n")

mode_name = ("strip" if args.strip_only else
             "map"   if args.map_only   else
             "inject"if args.inject_only else
             "full")
log(f"=== sync-map.py start — mode={mode_name} dry={args.dry_run} backup={not args.no_backups}")

FILES = [p for p in ROOT.rglob("*.md") if not p.suffix.endswith(".bak")]
log(f"Found {len(FILES)} markdown files (excluding backups)")

# ───────────── utilities ─────────────
def save_backup(path: Path, content: str, suffix=".bak"):
    if args.no_backups or args.dry_run:
        return
    bp = Path(f"{path}{suffix}")
    if not bp.exists():
        bp.write_text(content)

# ───────────── STRIP-ONLY ─────────────
if args.strip_only:
    removed = 0
    for fp in FILES:
        txt  = fp.read_text()
        base = BACK_SPLIT.split(txt, 1)[0].rstrip("\n")
        if base != txt:
            removed += 1
            log(f"STRIP-ONLY: {fp.relative_to(DIR)}")
            if not args.dry_run:
                save_backup(fp, txt)
                fp.write_text(base)
    log(f"✅ strip-only finished — {removed} blocks removed")
    sys.exit()

# ───────────── MAP BUILD ─────────────
def build_map() -> dict:
    note_map, dups = {}, {}
    for fp in FILES:
        m = ID_RE.search(fp.read_text())
        if not m: continue
        nid = m.group(1)
        if nid in note_map:
            dups.setdefault(nid, []).append(str(fp.relative_to(ROOT)))
            continue
        h1 = (re.search(r'^# *Title: *(.+)', fp.read_text(), re.M)
              or re.search(r'^# (.+)', fp.read_text(), re.M))
        title = h1.group(1).strip() if h1 else fp.stem
        note_map[nid] = {"path": str(fp.relative_to(ROOT)),
                         "title": title}
        log(f"MAP: {nid} → {note_map[nid]['path']}")
    MAP_F.write_text(json.dumps(note_map, indent=2, sort_keys=True))
    return note_map, dups

if args.inject_only:
    if not MAP_F.exists():
        log("❌ inject-only but map missing")
        sys.exit(1)
    note_map = json.loads(MAP_F.read_text())
else:
    note_map, dups = build_map()
    if args.map_only:
        log(f"✅ map-only finished — {len(note_map)} ids, "
            f"dups={len(dups)}")
        sys.exit()

# ───────────── SCAN LINKS ─────────────
links_to = {nid: [] for nid in note_map}
broken   = {}

for fp in FILES:
    txt = fp.read_text()
    me  = ID_RE.search(txt)
    if not me: continue
    sid = me.group(1)

    body = BACK_SPLIT.split(txt)[0]  # ignore backlinks section
    for m in LINK_RE.finditer(body):
        tid = m.group(1)
        if tid == sid: continue
        log(f"SCAN: {sid} → {tid}  ({fp.relative_to(ROOT)}:{m.start()})")
        if tid in links_to:
            links_to[tid].append(sid)
        else:
            broken.setdefault(tid, []).append(str(fp.relative_to(ROOT)))

# ───────────── INJECT ─────────────
rewritten = 0
for tid, srcs in links_to.items():
    path = ROOT / note_map[tid]["path"]
    txt  = path.read_text()
    base = BACK_SPLIT.split(txt, 1)[0].rstrip("\n")

    new_block = ""
    if srcs:
        new_block += f"\n\n{BACK_HDR}\n"
        for sid in sorted(set(srcs)):
            new_block += f" - [[{sid}|{note_map[sid]['title']}]]\n"

    decision = "NO_LINKS" if not srcs else "UNCHANGED"
    if base + new_block != txt:
        decision = "WRITE"
        if not args.dry_run:
            save_backup(path, txt)
            path.write_text(base + new_block)
        rewritten += 1

    log(f"DECIDE: {note_map[tid]['path']}  inbound={len(srcs)}  action={decision}")

log(f"✅ injection complete — {rewritten} files rewritten")

# ───────────── BROKEN REPORT ─────────────
if broken:
    out = DIR / "broken_links.log"
    with open(out, "w") as fh:
        for bid, lst in broken.items():
            fh.write(f"{bid} referenced from:\n")
            fh.writelines(f"  - {p}\n" for p in lst)
            fh.write("\n")
    print(f"⚠️ Broken links report: {out}")

log("=== sync-map.py finished ===")

