#!/usr/bin/env python3
"""
nopen - Open a note or run an app by its list number

Reads the results file written by nlist and:
- If the entry is a regular note (.md): opens it in nvim and
  stamps last_visited in .note_map.json afterwards
- If the entry is an app (app:<name>): runs apps/<name>/run.sh
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


class NoteOpener:
    def __init__(self):
        self.note_dir = os.getenv('NOTES_FOLDERS_PATH')
        self.current_file = os.getenv('NOTES_CURRENT_FILE')
        self.results_file = os.getenv('NOTES_RESULTS_FILE')
        self.notes_path = os.getenv('NOTES_PATH')

        if not self.note_dir:
            raise ValueError("NOTES_FOLDERS_PATH environment variable not set")
        if not self.current_file:
            raise ValueError("NOTES_CURRENT_FILE environment variable not set")
        if not self.results_file:
            raise ValueError("NOTES_RESULTS_FILE environment variable not set")

        self.note_dir = Path(self.note_dir)
        self.current_file = Path(self.current_file)
        self.results_file = Path(self.results_file)
        self.map_file = Path(self.notes_path) / '.note_map.json' if self.notes_path else None

    def get_current_folder(self) -> str:
        if not self.current_file.exists():
            raise ValueError(f"Current-file pointer not found at {self.current_file}")
        with open(self.current_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    return line
        raise ValueError(f"Could not read current folder from {self.current_file}")

    def resolve_entry(self, number: int) -> str:
        """Return the raw second token on line 'N.' from results.txt"""
        if not self.results_file.exists():
            raise ValueError(f"Results file not found: {self.results_file} (run nl first)")
        with open(self.results_file) as f:
            for line in f:
                # Strip ANSI escape codes before parsing
                clean = re.sub(r'\033\[[0-9;]*m', '', line)
                parts = clean.split()
                if parts and parts[0] == f"{number}.":
                    if len(parts) < 2:
                        raise ValueError(f"Malformed entry #{number} in results file")
                    return parts[1]
        raise ValueError(f"No entry #{number} in results file (run nl first)")

    # ------------------------------------------------------------------ #
    #  App handling
    # ------------------------------------------------------------------ #

    def run_app(self, app_name: str, current: str) -> None:
        app_dir = self.note_dir / current / 'apps' / app_name
        run_script = app_dir / 'run.sh'

        if not app_dir.is_dir():
            raise ValueError(f"App directory not found: {app_dir}")
        if not run_script.exists():
            raise ValueError(f"run.sh not found in: {app_dir}")

        print(f"▶  Running app: {app_name}")
        # Replace this process with the app's run.sh
        os.execv('/bin/bash', ['/bin/bash', str(run_script)])

    # ------------------------------------------------------------------ #
    #  Note handling
    # ------------------------------------------------------------------ #

    def open_note(self, filename: str, current: str) -> None:
        fullpath = self.note_dir / current / filename
        if not fullpath.exists():
            raise ValueError(f"Note not found: {fullpath}")

        # exec into nvim — control returns here only if exec fails
        os.execvp('nvim', ['nvim', str(fullpath)])

    def push_file_history(self, filename: str, current: str) -> None:
        """Record recently opened file in file_history (last 5 unique)."""
        if not self.notes_path:
            return
        file_history = Path(self.notes_path) / 'file_history'
        entry = f"{current}/{filename}"
        existing = [l for l in file_history.read_text().splitlines() if l.strip()] if file_history.exists() else []
        deduped = [e for e in existing if e != entry]
        file_history.write_text('\n'.join(([entry] + deduped)[:5]) + '\n')

    def stamp_last_visited(self, filename: str, current: str) -> None:
        """Update last_visited in .note_map.json for the given note."""
        if not self.map_file or not self.map_file.exists():
            return

        suffix = f"{current}/{filename}"
        try:
            with open(self.map_file) as f:
                note_map = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        note_id = next(
            (k for k, v in note_map.items()
             if isinstance(v, dict) and v.get('path', '').endswith(suffix)),
            None
        )
        if not note_id:
            return

        note_map[note_id]['last_visited'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        tmp = self.map_file.with_suffix('.tmp')
        with open(tmp, 'w') as f:
            json.dump(note_map, f, indent=2)
        tmp.replace(self.map_file)

    # ------------------------------------------------------------------ #
    #  Entry point
    # ------------------------------------------------------------------ #

    def open(self, number: int) -> None:
        current = self.get_current_folder()
        entry = self.resolve_entry(number)

        if entry.startswith('alias-nav:'):
            apath = entry[len('alias-nav:'):]
            if not Path(apath).is_dir():
                raise ValueError(f"Alias path no longer exists: {apath}")
            # Save current notes path so nc .. can return to it
            previous_file = self.current_file.parent / (self.current_file.name + '.previous')
            if not current.startswith('alias:'):
                previous_file.write_text(current + '\n')
            self.current_file.write_text(f'alias:{apath}\n')
            print(f"Entered alias: {Path(apath).name}  \033[0;33m[read-only]\033[0m")
            print("Run 'nl' to list files, 'nc ..' to go back.")
            sys.exit(0)

        elif entry.startswith('alias-pdf:'):
            fullpath = Path(entry[len('alias-pdf:'):])
            if not fullpath.exists():
                raise ValueError(f"PDF not found: {fullpath}")
            print(f"Opening PDF: {fullpath.name}")
            result = subprocess.run(['open', str(fullpath)])
            sys.exit(result.returncode)

        elif entry.startswith('alias-md:'):
            fullpath = Path(entry[len('alias-md:'):])
            if not fullpath.exists():
                raise ValueError(f"Note not found: {fullpath}")
            # Read-only in alias mode
            result = subprocess.run(['nvim', '-R', str(fullpath)])
            sys.exit(result.returncode)

        elif entry.startswith('app:'):
            app_name = entry[len('app:'):]
            self.run_app(app_name, current)
            # exec above replaces process; code below only runs for notes

        elif entry.endswith('.pdf'):
            filename = entry
            fullpath = self.note_dir / current / filename
            if not fullpath.exists():
                raise ValueError(f"PDF not found: {fullpath}")
            print(f"Opening PDF: {filename}")
            result = subprocess.run(['open', str(fullpath)])
            sys.exit(result.returncode)

        else:
            filename = entry
            fullpath = self.note_dir / current / filename
            if not fullpath.exists():
                raise ValueError(f"Note not found: {fullpath}")

            # Fork: open nvim as child so we can stamp last_visited after it exits
            result = subprocess.run(['nvim', str(fullpath)])

            self.stamp_last_visited(filename, current)
            self.push_file_history(filename, current)
            sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description='Open a note or run an app by list number',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nopen       # open entry #1
  nopen 3     # open entry #3
  nopen 5     # if #5 is an app, runs its run.sh

Environment Variables:
  NOTES_FOLDERS_PATH   Directory where note subfolders live
  NOTES_CURRENT_FILE   File containing the current folder name
  NOTES_RESULTS_FILE   Output of nlist (maps numbers to filenames)
  NOTES_PATH           Root of the notes project (for .note_map.json)
        """
    )
    parser.add_argument(
        'number',
        nargs='?',
        type=int,
        default=1,
        help='Entry number from nlist output (default: 1)'
    )

    args = parser.parse_args()

    try:
        NoteOpener().open(args.number)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
