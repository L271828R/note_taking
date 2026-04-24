#!/usr/bin/env python3
"""
test-bank quiz engine — spaced repetition (SM-2 algorithm)

Parses all testbank.md files in the notes folder, asks questions
in priority order (due cards first, then weakest cards), and saves
hit/miss history to a SQLite database.
"""

import argparse
import os
import re
import sqlite3
import sys
import textwrap
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional


# ── ANSI colors ──────────────────────────────────────────────────────────────

class C:
    RESET  = '\033[0m'
    BOLD   = '\033[1m'
    GREEN  = '\033[0;32m'
    RED    = '\033[0;31m'
    YELLOW = '\033[0;33m'
    BLUE   = '\033[1;34m'
    GRAY   = '\033[1;30m'
    CYAN   = '\033[0;36m'


# ── Database ──────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id          TEXT PRIMARY KEY,   -- sha of source_file + question text
    source_file TEXT NOT NULL,
    question    TEXT NOT NULL,
    answer      TEXT NOT NULL,
    -- SM-2 fields
    ease_factor REAL    NOT NULL DEFAULT 2.5,
    interval    INTEGER NOT NULL DEFAULT 0,   -- days until next review
    repetitions INTEGER NOT NULL DEFAULT 0,   -- consecutive correct answers
    due_date    TEXT    NOT NULL DEFAULT '',  -- ISO date or ''
    -- stats
    total_correct   INTEGER NOT NULL DEFAULT 0,
    total_incorrect INTEGER NOT NULL DEFAULT 0,
    last_seen       TEXT    NOT NULL DEFAULT ''
);
"""


def card_id(source_file: str, question: str) -> str:
    import hashlib
    raw = f"{source_file}||{question.strip()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_card(conn: sqlite3.Connection, source_file: str, question: str, answer: str) -> None:
    cid = card_id(source_file, question)
    conn.execute("""
        INSERT INTO cards (id, source_file, question, answer)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            source_file = excluded.source_file,
            answer      = excluded.answer
    """, (cid, source_file, question, answer))
    conn.commit()


def update_sm2(conn: sqlite3.Connection, cid: str, correct: bool) -> None:
    """Apply SM-2 update after a review."""
    row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
    ef   = row['ease_factor']
    iv   = row['interval']
    reps = row['repetitions']
    total_correct   = row['total_correct']
    total_incorrect = row['total_incorrect']

    if correct:
        total_correct += 1
        if reps == 0:
            iv = 1
        elif reps == 1:
            iv = 6
        else:
            iv = round(iv * ef)
        reps += 1
        # q=5 for correct, q=3 for "hard but correct" — we use 4 (good)
        q = 4
    else:
        total_incorrect += 1
        reps = 0
        iv   = 1
        q = 1

    # Update ease factor: EF' = EF + (0.1 − (5−q)*(0.08+(5−q)*0.02))
    ef = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ef = max(1.3, ef)

    due = (date.today() + timedelta(days=iv)).isoformat()
    now = datetime.now().isoformat(timespec='seconds')

    conn.execute("""
        UPDATE cards SET
            ease_factor     = ?,
            interval        = ?,
            repetitions     = ?,
            due_date        = ?,
            total_correct   = ?,
            total_incorrect = ?,
            last_seen       = ?
        WHERE id = ?
    """, (ef, iv, reps, due, total_correct, total_incorrect, now, cid))
    conn.commit()


# ── Markdown parser ───────────────────────────────────────────────────────────

def parse_testbank(filepath: Path) -> List[Tuple[str, str]]:
    """
    Parse a testbank.md file.
    Returns list of (question, answer) pairs.

    Format:
        # Question
        <question text, may be multiline>

        # Answer
        <answer text, may be multiline>
    """
    text = filepath.read_text(encoding='utf-8')
    pairs = []

    # Split on lines that are exactly "# Question" or "# Answer"
    parts = re.split(r'^#\s+Question\s*$', text, flags=re.MULTILINE)

    for part in parts[1:]:   # skip preamble before first question
        qa_split = re.split(r'^#\s+Answer\s*$', part, maxsplit=1, flags=re.MULTILINE)
        if len(qa_split) != 2:
            continue
        question = qa_split[0].strip()
        answer   = qa_split[1].strip()
        # Stop answer at the next # Question if any
        answer = re.split(r'^#\s+Question\s*$', answer, maxsplit=1, flags=re.MULTILINE)[0].strip()
        if question and answer:
            pairs.append((question, answer))

    return pairs


def load_all_cards(notes_dir: str, conn: sqlite3.Connection) -> None:
    """Scan notes_dir for testbank.md files and upsert all cards."""
    root = Path(notes_dir)
    found = list(root.rglob('testbank.md'))
    if not found:
        return
    for filepath in found:
        pairs = parse_testbank(filepath)
        rel = str(filepath.relative_to(root))
        for q, a in pairs:
            upsert_card(conn, rel, q, a)


# ── Card selection (spaced repetition priority) ───────────────────────────────

def pick_card(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    """
    Priority:
      1. Due today or overdue (sorted by due_date asc, then ease_factor asc)
      2. New cards (never seen, due_date = '')
      3. Not yet due — pick the one with lowest ease_factor (weakest)
    """
    today = date.today().isoformat()

    # 1. Due / overdue
    row = conn.execute("""
        SELECT * FROM cards
        WHERE due_date != '' AND due_date <= ?
        ORDER BY due_date ASC, ease_factor ASC
        LIMIT 1
    """, (today,)).fetchone()
    if row:
        return row

    # 2. New
    row = conn.execute("""
        SELECT * FROM cards
        WHERE due_date = ''
        ORDER BY RANDOM()
        LIMIT 1
    """).fetchone()
    if row:
        return row

    # 3. Not yet due — weakest
    row = conn.execute("""
        SELECT * FROM cards
        ORDER BY ease_factor ASC, due_date ASC
        LIMIT 1
    """).fetchone()
    return row


# ── UI helpers ────────────────────────────────────────────────────────────────

def wrap(text: str, width: int = 72, indent: str = '  ') -> str:
    lines = text.splitlines()
    wrapped = []
    for line in lines:
        if line.strip() == '':
            wrapped.append('')
        else:
            wrapped.extend(textwrap.wrap(line, width=width, initial_indent=indent, subsequent_indent=indent))
    return '\n'.join(wrapped)


def print_header(total: int, due: int, session_correct: int, session_total: int) -> None:
    pct = f"{session_correct}/{session_total}" if session_total else "0/0"
    print(f"\n{C.BOLD}{'─'*72}{C.RESET}")
    print(f"  {C.CYAN}Test Bank{C.RESET}  │  "
          f"cards: {C.BOLD}{total}{C.RESET}  │  "
          f"due: {C.YELLOW}{due}{C.RESET}  │  "
          f"session: {C.GREEN}{pct}{C.RESET}")
    print(f"{C.BOLD}{'─'*72}{C.RESET}\n")


def stats_for(conn: sqlite3.Connection, cid: str) -> str:
    row = conn.execute(
        "SELECT total_correct, total_incorrect, ease_factor, interval FROM cards WHERE id=?",
        (cid,)
    ).fetchone()
    tc, ti = row['total_correct'], row['total_incorrect']
    total = tc + ti
    pct = f"{tc/total*100:.0f}%" if total else "new"
    ef  = f"{row['ease_factor']:.2f}"
    iv  = row['interval']
    return f"{C.GRAY}history: {tc}✓ {ti}✗  accuracy: {pct}  ease: {ef}  interval: {iv}d{C.RESET}"


def due_count(conn: sqlite3.Connection) -> int:
    today = date.today().isoformat()
    return conn.execute(
        "SELECT COUNT(*) FROM cards WHERE due_date != '' AND due_date <= ?", (today,)
    ).fetchone()[0]


def total_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]


# ── Main quiz loop ────────────────────────────────────────────────────────────

def run_quiz(conn: sqlite3.Connection) -> None:
    session_correct = 0
    session_total   = 0

    print(f"\n{C.BOLD}{C.CYAN}Test Bank — Spaced Repetition Quiz{C.RESET}")
    print(f"{C.GRAY}Press Enter to reveal answer. Then: y = correct  n = incorrect  q = quit{C.RESET}\n")

    total = total_count(conn)
    if total == 0:
        print(f"{C.YELLOW}No cards found. Add questions to a testbank.md file and run again.{C.RESET}\n")
        return

    while True:
        card = pick_card(conn)
        if not card:
            print(f"\n{C.GREEN}All cards reviewed! Come back tomorrow.{C.RESET}\n")
            break

        print_header(total, due_count(conn), session_correct, session_total)

        cid = card['id']
        print(f"{C.BOLD}Q:{C.RESET}\n{wrap(card['question'])}\n")
        print(f"  {stats_for(conn, cid)}\n")

        try:
            input(f"  {C.GRAY}[ press Enter to reveal answer ]{C.RESET}")
        except (KeyboardInterrupt, EOFError):
            break

        print(f"\n{C.BOLD}A:{C.RESET}\n{wrap(card['answer'])}\n")

        while True:
            try:
                resp = input(f"  {C.GREEN}y{C.RESET} correct  {C.RED}n{C.RESET} incorrect  {C.YELLOW}q{C.RESET} quit › ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                resp = 'q'

            if resp in ('y', 'n', 'q'):
                break
            print("  Please enter y, n, or q.")

        if resp == 'q':
            break

        correct = resp == 'y'
        update_sm2(conn, cid, correct)
        session_total += 1
        if correct:
            session_correct += 1
            print(f"  {C.GREEN}✓ Got it!{C.RESET}")
        else:
            print(f"  {C.RED}✗ Missed.{C.RESET}  Answer saved for soon.")

        print()

    # Session summary
    if session_total > 0:
        pct = session_correct / session_total * 100
        print(f"{C.BOLD}Session summary:{C.RESET}  "
              f"{C.GREEN}{session_correct}{C.RESET} correct  "
              f"{C.RED}{session_total - session_correct}{C.RESET} incorrect  "
              f"({pct:.0f}%)\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Test Bank — spaced repetition quiz')
    parser.add_argument('--notes-dir', required=True, help='Folder containing testbank.md files')
    parser.add_argument('--db',        required=True, help='Path to SQLite progress database')
    args = parser.parse_args()

    if not Path(args.notes_dir).is_dir():
        print(f"Error: notes directory not found: {args.notes_dir}", file=sys.stderr)
        sys.exit(1)

    conn = open_db(args.db)
    load_all_cards(args.notes_dir, conn)

    total = total_count(conn)
    if total == 0:
        print(f"\n{C.YELLOW}No questions found in {args.notes_dir}{C.RESET}")
        print(f"Create a testbank.md with  # Question / # Answer  blocks.\n")
        sys.exit(0)

    run_quiz(conn)
    conn.close()


if __name__ == '__main__':
    main()
