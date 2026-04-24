#!/usr/bin/env python3
"""
ncurrent - Current Folder Manager with .note_map.json sync + logging
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tips import print_tip


# ANSI color codes
class Colors:
    BLUE  = '\033[1;34m'
    CYAN  = '\033[0;36m'
    RESET = '\033[0m'


class FolderManager:
    def __init__(self):
        self.folders_path = Path(os.environ['NOTES_FOLDERS_PATH'])
        self.notes_path   = Path(os.environ['NOTES_PATH'])
        active = os.environ.get('NOTES_ACTIVE_FILE', '').strip()
        self.current_file  = Path(active) if active else Path(os.environ['NOTES_CURRENT_FILE'])
        self.previous_file = self.current_file.parent / (self.current_file.name + '.previous')
        self.history_file  = self.notes_path / 'history'
        self.file_history_file = self.notes_path / 'file_history'
        self.map_file      = self.notes_path / '.note_map.json'
        self.log_file      = self.notes_path / '.note_map.log'

        if not self.map_file.exists():
            self.map_file.write_text('{}')
            self._log('Created empty map')
        if not self.log_file.exists():
            self.log_file.touch()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_file, 'a') as f:
            f.write(f'{ts}  {msg}\n')

    def _read_current(self) -> str:
        """Return the current relative folder path or 'alias:<path>' (empty = root)."""
        if not self.current_file.exists():
            return ''
        return self.current_file.read_text().strip()

    def _write_current(self, value: str) -> None:
        self.current_file.write_text(value + '\n' if value else '\n')
        self._push_history(value)

    def _push_history(self, value: str) -> None:
        """Prepend value to history, keeping the last 5 unique entries."""
        entry = value.strip() if value else '[root]'
        existing = self._read_history()
        # remove duplicates of this entry, prepend, cap at 5
        deduped = [e for e in existing if e != entry]
        updated = [entry] + deduped
        self.history_file.write_text('\n'.join(updated[:5]) + '\n')

    def _read_history(self) -> list:
        if not self.history_file.exists():
            return []
        return [l for l in self.history_file.read_text().splitlines() if l.strip()]

    def push_file_history(self, relative_path: str) -> None:
        """Record a recently opened/created file (folder/filename), keeping last 5 unique."""
        entry = relative_path.strip()
        existing = self._read_file_history()
        deduped = [e for e in existing if e != entry]
        updated = [entry] + deduped
        self.file_history_file.write_text('\n'.join(updated[:5]) + '\n')

    def _read_file_history(self) -> list:
        if not self.file_history_file.exists():
            return []
        return [l for l in self.file_history_file.read_text().splitlines() if l.strip()]

    def _save_previous(self) -> None:
        """Snapshot current before entering an alias so nc .. can return."""
        current = self._read_current()
        if not self._is_alias(current):
            self.previous_file.write_text(current + '\n')

    def _restore_previous(self) -> str:
        """Return the saved pre-alias path, or '' if nothing was saved."""
        if not self.previous_file.exists():
            return ''
        return self.previous_file.read_text().strip()

    def _is_alias(self, current: str) -> bool:
        return current.startswith('alias:')

    def _alias_path(self, current: str) -> Path:
        return Path(current[len('alias:'):])

    def _target(self) -> Path:
        current = self._read_current()
        if self._is_alias(current):
            return self._alias_path(current)
        if current:
            return self.folders_path / current
        return self.folders_path

    def _aliases_file(self) -> Path:
        """Path to the aliases file in the current notes folder (not alias targets)."""
        current = self._read_current()
        if self._is_alias(current):
            # When already in an alias, aliases file belongs to parent notes folder
            # Use last known notes folder — not applicable; just return a non-writable path
            raise ValueError("Cannot manage aliases while inside an alias folder")
        base = self.folders_path / current if current else self.folders_path
        return base / 'aliases'

    def _read_aliases(self) -> list:
        """Read alias paths from the aliases file in the current notes folder."""
        current = self._read_current()
        if self._is_alias(current):
            return []
        base = self.folders_path / current if current else self.folders_path
        af = base / 'aliases'
        if not af.exists():
            return []
        lines = [l.strip() for l in af.read_text().splitlines()]
        return [l for l in lines if l]

    def _sanitize(self, path: Path) -> bool:
        """True if path is inside folders_path."""
        try:
            path.resolve().relative_to(self.folders_path.resolve())
            return True
        except ValueError:
            return False

    def _subfolders(self, target: Path):
        return sorted(f for f in target.iterdir() if f.is_dir() and f.name != 'apps')

    def _md_count(self, folder: Path) -> int:
        return sum(1 for f in folder.rglob('*.md')
                   if 'node_modules' not in f.parts)

    def _newest_mtime(self, folder: Path) -> str:
        mtimes = [f.stat().st_mtime for f in folder.rglob('*.md')
                  if 'node_modules' not in f.parts]
        if not mtimes:
            return ''
        return datetime.fromtimestamp(max(mtimes)).strftime('%Y-%m-%d %H:%M')

    # ── map sync ─────────────────────────────────────────────────────────────

    def _update_map_for_dir(self, base_dir: Path, old_rel: str) -> None:
        self._log(f'update_map_for_dir: base_dir={base_dir} old_rel={old_rel}')
        try:
            data = json.loads(self.map_file.read_text())
        except Exception:
            data = {}

        # remove old entries
        data = {k: v for k, v in data.items()
                if not v.get('path', '').startswith(old_rel)}
        self._log(f"  Removed map entries starting with '{old_rel}'")

        # re-scan new dir
        for f in base_dir.rglob('*.md'):
            note_id = None
            title   = None
            try:
                for line in f.read_text(encoding='utf-8').splitlines():
                    if m := re.match(r'^<!-- id: ([0-9a-f]+) -->', line):
                        note_id = m.group(1)
                    if m := re.match(r'^#\s*Title:\s*(.+)', line):
                        title = m.group(1).strip()
            except Exception:
                pass

            if not note_id:
                self._log(f'  Skip {f} (no id)')
                continue

            if not title:
                title = f.stem

            rel = str(f.relative_to(self.notes_path))
            data[note_id] = {'path': rel, 'title': title}
            self._log(f"  Added/updated: id={note_id} path={rel} title='{title}'")

        self.map_file.write_text(json.dumps(data, indent=2))

    def _has_apps(self, folder: Path) -> bool:
        apps_dir = folder / 'apps'
        if not apps_dir.is_dir():
            return False
        return any((d / 'run.sh').exists() for d in apps_dir.iterdir() if d.is_dir())

    # ── display ──────────────────────────────────────────────────────────────

    def _print_listing(self) -> None:
        current = self._read_current()
        target  = self._target()

        print()
        if self._is_alias(current):
            print(f'current > {self._alias_path(current).name}  \033[0;33m[alias · read-only]\033[0m')
        else:
            print(f'current > {current}')
        print('-' * 80)

        folders = self._subfolders(target)

        print('📁 Subfolders')
        print('----------------')

        for i, folder in enumerate(folders, 1):
            count     = self._md_count(folder)
            app_icon  = ' 🚀' if self._has_apps(folder) else ''
            noun      = 'file' if count == 1 else 'files'
            newest    = self._newest_mtime(folder)
            ts        = f'  {Colors.RESET}\033[0;32m{newest}\033[0m' if newest else ''
            print(
                f'{i}. {Colors.BLUE}{folder.name}{Colors.RESET}'
                f'{app_icon} ({count} {noun}){ts}'
            )

        # Show aliases only when in a regular notes folder
        if not self._is_alias(current):
            aliases = self._read_aliases()
            if aliases:
                print()
                print('🔗 Aliases')
                print('----------------')
                offset = len(folders) + 1
                for j, apath in enumerate(aliases, offset):
                    name = Path(apath).name
                    exists = Path(apath).is_dir()
                    marker = '' if exists else '  \033[0;31m[missing]\033[0m'
                    print(f'{j}. {Colors.BLUE}{name}{Colors.RESET}{marker}  \033[1;30m{apath}\033[0m')

        print()

    # ── commands ─────────────────────────────────────────────────────────────

    def cmd_root(self) -> None:
        self._write_current('')
        self._log('Reset current → [root]')
        print('Moved to: [root]')
        print_tip()

    def cmd_pwd(self) -> None:
        current = self._read_current()
        print(current if current else '[root]')
        self._log(f'Printed pwd: {current or "[root]"}')

    def cmd_cd(self, subfolder: str) -> None:
        current  = self._read_current()
        new_path = f'{current}/{subfolder}' if current else subfolder
        full     = self.folders_path / new_path
        if full.is_dir() and self._sanitize(full):
            self._write_current(new_path)
            self._log(f'cd → {new_path}')
            print(f'Moved into: {new_path}')
        else:
            print(f"Subfolder '{subfolder}' not found.", file=sys.stderr)
            sys.exit(1)
        print_tip()

    def cmd_up(self) -> None:
        current = self._read_current()
        if not current:
            print('Already at root.', file=sys.stderr)
            sys.exit(1)
        if self._is_alias(current):
            prev = self._restore_previous()
            self._write_current(prev)
            self._log(f'up from alias → {prev or "[root]"}')
            print(f'Left alias. Back to: {prev or "[root]"}')
            print_tip()
            return
        parent = current.rsplit('/', 1)[0] if '/' in current else ''
        self._write_current(parent)
        self._log(f'up → {parent or "[root]"}')
        print(f'Moved up to: {parent or "[root]"}')
        print_tip()

    def _require_notes_mode(self, op: str) -> None:
        if self._is_alias(self._read_current()):
            print(f"Error: '{op}' is not available in alias (read-only) mode. Use 'nc ..' to go back.", file=sys.stderr)
            sys.exit(1)

    def cmd_new(self, name: str) -> None:
        self._require_notes_mode('-new')
        target = self._target()
        new_dir = target / name
        new_dir.mkdir(parents=True, exist_ok=True)
        current = self._read_current()
        self._log(f"Created folder '{name}' in {current or '[root]'}")
        print(f"Folder '{name}' created")
        print_tip()

    def cmd_alias(self, cwd: str) -> None:
        """Add shell CWD as an alias in the current notes folder's aliases file."""
        src = Path(cwd).resolve()
        if not src.is_dir():
            print(f"Error: '{src}' is not a directory.", file=sys.stderr)
            sys.exit(1)
        try:
            af = self._aliases_file()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        existing = self._read_aliases()
        if str(src) in existing:
            print(f"Alias already exists: {src}")
            return
        with open(af, 'a') as f:
            f.write(str(src) + '\n')
        current = self._read_current()
        self._log(f"Added alias '{src}' to {current or '[root]'}/aliases")
        print(f"Added alias: {src.name}  →  {src}")
        print_tip()

    def cmd_select(self, idx: int) -> None:
        target  = self._target()
        folders = self._subfolders(target)
        n_folders = len(folders)

        # Check if index falls in the alias range
        aliases = self._read_aliases()
        alias_offset = n_folders + 1
        alias_end    = n_folders + len(aliases)

        if aliases and alias_offset <= idx <= alias_end:
            apath = aliases[idx - alias_offset]
            if not Path(apath).is_dir():
                print(f"Error: alias path no longer exists: {apath}", file=sys.stderr)
                sys.exit(1)
            self._save_previous()
            self._write_current(f'alias:{apath}')
            self._log(f'Selected alias: {apath}')
            print(f'Switched to alias: {Path(apath).name}  \033[0;33m[read-only]\033[0m')
            print_tip()
            return

        if idx < 1 or idx > n_folders:
            print(f"Error: index {idx} out of range.", file=sys.stderr)
            sys.exit(1)
        rel = str(folders[idx - 1].relative_to(self.folders_path))
        self._write_current(rel)
        self._log(f'Selected current: {rel}')
        print(f'Switched current to: {rel}')
        print_tip()

    def cmd_move_folder(self, from_idx: int, to: str) -> None:
        self._require_notes_mode('-move')
        target  = self._target()
        folders = self._subfolders(target)
        if from_idx < 1 or from_idx > len(folders):
            print(f"Error: index {from_idx} out of range.", file=sys.stderr)
            sys.exit(1)
        src  = folders[from_idx - 1]
        name = src.name

        if to == 'up':
            parent = target.parent
            if not self._sanitize(parent):
                print('Cannot move above root.', file=sys.stderr)
                sys.exit(1)
            dst = parent / name
        elif to.isdigit():
            to_idx = int(to)
            if to_idx < 1 or to_idx > len(folders):
                print(f"Error: destination index {to_idx} out of range.", file=sys.stderr)
                sys.exit(1)
            dst = folders[to_idx - 1] / name
        else:
            print(f"Invalid destination '{to}'.", file=sys.stderr)
            sys.exit(1)

        src.rename(dst)
        old_rel = str(src.relative_to(self.notes_path))
        print(f"Moved '{name}' → '{dst.parent}'")
        self._log(f'Moved {src} → {dst}')
        self._update_map_for_dir(dst, old_rel)
        print_tip()

    def cmd_rename_folder(self, idx: int, new_name: str) -> None:
        self._require_notes_mode('-rename')
        target  = self._target()
        folders = self._subfolders(target)
        if idx < 1 or idx > len(folders):
            print(f"Error: index {idx} out of range.", file=sys.stderr)
            sys.exit(1)
        src = folders[idx - 1]
        dst = src.parent / new_name
        old_rel = str(src.relative_to(self.notes_path))
        src.rename(dst)
        print(f"Renamed '{src.name}' → '{new_name}'")
        self._log(f'Renamed {src} → {dst}')
        self._update_map_for_dir(dst, old_rel)
        print_tip()

    def cmd_claude(self) -> None:
        config_readme = self.notes_path / '.config' / 'README.md'
        if not config_readme.exists():
            print(f'ERROR: config README not found at {config_readme}', file=sys.stderr)
            sys.exit(1)
        current     = self._read_current()
        full_path   = self.folders_path / current if current else self.folders_path
        context     = config_readme.read_text()
        context    += f'\n\n---\n## Current working directory (live)\n'
        context    += f'- current folder: {current or "[root]"}\n'
        context    += f'- full path: {full_path}\n'
        env = os.environ.copy()
        env['NOTES_ACTIVE_FILE'] = str(self.current_file)
        os.execvpe('claude', ['claude', '--append-system-prompt', context], env)

    def cmd_recent(self, idx: int = None) -> None:
        history = self._read_history()
        if not history:
            print('No recent folders yet.')
            return
        if idx is None:
            print()
            print('Recent folders:')
            print('-' * 40)
            for i, entry in enumerate(history, 1):
                print(f'  {i}. {Colors.BLUE}{entry}{Colors.RESET}')
            print()
            print('  nc -recent <i>  to navigate there')
            print()
            return
        if idx < 1 or idx > len(history):
            print(f'Error: index {idx} out of range (1–{len(history)}).', file=sys.stderr)
            sys.exit(1)
        entry = history[idx - 1]
        if entry == '[root]':
            self._write_current('')
            self._log('recent → [root]')
            print('Moved to: [root]')
        else:
            full = self.folders_path / entry
            if not full.is_dir():
                print(f"Error: folder no longer exists: {entry}", file=sys.stderr)
                sys.exit(1)
            self._write_current(entry)
            self._log(f'recent → {entry}')
            print(f'Moved to: {entry}')
        print_tip()

    def cmd_pdf(self, src_paths: list) -> None:
        """Copy one or more PDF files into the current notes folder"""
        import glob as _glob
        target  = self._target()
        current = self._read_current()

        # Expand any glob patterns that the shell didn't expand (e.g. quoted wildcards)
        expanded = []
        for pattern in src_paths:
            matches = _glob.glob(os.path.expanduser(pattern))
            expanded.extend(matches if matches else [pattern])

        if not expanded:
            print("Error: no files matched.", file=sys.stderr)
            sys.exit(1)

        copied = skipped = errors = 0
        for src_str in expanded:
            src = Path(src_str).resolve()
            if not src.exists():
                print(f"  skip: not found: {src.name}", file=sys.stderr)
                errors += 1
                continue
            if src.suffix.lower() != '.pdf':
                print(f"  skip: not a PDF: {src.name}", file=sys.stderr)
                skipped += 1
                continue
            dst = target / src.name
            if dst.exists():
                print(f"  skip: already exists: {src.name}", file=sys.stderr)
                skipped += 1
                continue
            shutil.copy2(str(src), str(dst))
            self._log(f"Copied PDF '{src}' → '{dst}'")
            print(f"  copied: {src.name}")
            copied += 1

        print(f"\n{copied} copied, {skipped} skipped, {errors} errors  → {current or '[root]'}/")
        print_tip()

    def cmd_testbank(self) -> None:
        """Create or open the test-bank app for the current notes folder."""
        self._require_notes_mode('-testbank')
        target   = self._target()
        app_dir  = target / 'apps' / 'test-bank'
        tb_file  = target / 'testbank.md'
        template = self.notes_path / 'templates' / 'testbank.md'

        if not app_dir.exists():
            # First run: scaffold the app directory
            app_dir.mkdir(parents=True)

            # Copy run.sh and quiz.py from the notes project templates
            app_template_dir = self.notes_path / 'templates' / 'test-bank-app'
            if app_template_dir.exists():
                for f in app_template_dir.iterdir():
                    shutil.copy2(str(f), str(app_dir / f.name))
            else:
                print(f"  Note: app template not found at {app_template_dir}")
                print(f"  App directory created at {app_dir}")
                print(f"  Add run.sh and quiz.py manually.")

            # Make run.sh executable if copied
            run_sh = app_dir / 'run.sh'
            if run_sh.exists():
                run_sh.chmod(run_sh.stat().st_mode | 0o111)

            self._log(f"Created test-bank app at {app_dir}")
            print(f"Created app: {app_dir}")

        # Create testbank.md in the notes folder if missing
        if not tb_file.exists():
            if template.exists():
                shutil.copy2(str(template), str(tb_file))
            else:
                tb_file.write_text(
                    "# Question\n\n\n# Answer\n\n\n---\n\n# Question\n\n\n# Answer\n\n\n"
                )
            self._log(f"Created testbank.md at {tb_file}")
            print(f"Created: {tb_file.name}")

        print(f"Opening {tb_file.name} ...")
        subprocess.run(['nvim', str(tb_file)])

    def cmd_list(self) -> None:
        self._print_listing()
        print_tip()

    def cmd_help(self) -> None:
        print("""
📝 ncurrent — Current Folder Manager
------------------------------------
Usage: ncurrent [option] or [index]

🔍 Navigation
  -pwd                Show current folder path.
  -cd <subfolder>     Enter a subfolder by name.
  -up / ..            Move up one folder level.
  -recent             Show last 5 visited folders.
  -recent <i>         Jump to recent folder #i.
  <number>            Set current folder by selecting from list (by index).

📁 Folder Operations
  -new <name>         Create a new subfolder under current.
  -move <i> -to <j>   Move folder #i into folder #j.
  -move <i> -to up    Move folder #i up one level.
  -rename <i> <name>  Rename folder #i to a new name.
  -pdf <file>         Copy a PDF file into the current folder.
  -alias              Add shell CWD as a linked alias folder (read-only).
  -testbank           Create or open the test-bank quiz app for this folder.

🧭 Display
  (no arguments)      List folders and subfolder note counts.
  ROWS=<n> ncurrent   Set rows per column for list display.

🆘 Help
  -help               Show this help message.
  -claude             Print app context/README for Claude (current folder + rules).

Notes:
  • Moves and renames automatically update your .note_map.json file.
  • All changes are logged to .note_map.log for debugging.
  • The "current" folder determines the target for most other scripts.
""")


def main():
    args = sys.argv[1:]

    try:
        mgr = FolderManager()
    except KeyError as e:
        print(f'Error: environment variable {e} not set.', file=sys.stderr)
        sys.exit(1)

    mgr._log(f'=== ncurrent invoked with: {" ".join(args)} ===')

    # ── dispatch ─────────────────────────────────────────────────────────────

    if not args:
        mgr.cmd_list()
        return

    if args[0] in ('root', '~'):
        mgr.cmd_root()

    elif args[0] in ('-help', '--help', '-h'):
        mgr.cmd_help()

    elif args[0] == '-pwd':
        mgr.cmd_pwd()

    elif args[0] == '-claude':
        mgr.cmd_claude()

    elif args[0] in ('..', '-up'):
        mgr.cmd_up()

    elif args[0] == '-cd':
        if len(args) < 2:
            print('Error: -cd requires a subfolder name.', file=sys.stderr)
            sys.exit(1)
        mgr.cmd_cd(args[1])

    elif args[0] == '-new':
        if len(args) < 2:
            print('Error: -new requires a folder name.', file=sys.stderr)
            sys.exit(1)
        mgr.cmd_new(args[1])

    elif args[0] == '-move':
        # -move <i> -to <j|up>
        if len(args) < 4 or args[2] != '-to':
            print('Usage: ncurrent -move <i> -to <j|up>', file=sys.stderr)
            sys.exit(1)
        if not args[1].isdigit():
            print('Error: index must be a number.', file=sys.stderr)
            sys.exit(1)
        mgr.cmd_move_folder(int(args[1]), args[3])

    elif args[0] == '-rename':
        if len(args) < 3 or not args[1].isdigit():
            print('Usage: ncurrent -rename <i> <new_name>', file=sys.stderr)
            sys.exit(1)
        mgr.cmd_rename_folder(int(args[1]), args[2])

    elif args[0] == '-recent':
        idx = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        mgr.cmd_recent(idx)

    elif args[0] == '-testbank':
        mgr.cmd_testbank()

    elif args[0] == '-alias':
        cwd = os.environ.get('PWD', os.getcwd())
        mgr.cmd_alias(cwd)

    elif args[0] == '-pdf':
        if len(args) < 2:
            print('Error: -pdf requires at least one file path or glob pattern.', file=sys.stderr)
            sys.exit(1)
        mgr.cmd_pdf(args[1:])

    elif args[0].isdigit():
        mgr.cmd_select(int(args[0]))

    else:
        print(f"Unknown argument: {args[0]}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
