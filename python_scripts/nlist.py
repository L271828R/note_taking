#!/usr/bin/env python3
"""
nlist - List and manage notes (Python version)

Enhanced to:
1) List .md files (with timestamps and titles)
2) List subfolders and count their .md files
3) Write to $NOTES_RESULTS_FILE
4) Invoke plugins
5) Support -delete
6) Support -rename (custom or date style)
7) Support -move
8) Support -h|--help
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Set

# Logging: set NLIST_DEBUG=1 to enable timing output
_log_level = logging.DEBUG if os.getenv('NLIST_DEBUG') == '1' else logging.WARNING
logging.basicConfig(format='[nlist %(levelname)s] %(message)s', level=_log_level)
log = logging.getLogger('nlist')

# Import shared tag functionality
sys.path.insert(0, str(Path(__file__).parent))
from note_tags import TagManager
from tips import print_tip


# ANSI color codes
class Colors:
    GREEN = '\033[0;32m'
    BLUE = '\033[1;34m'
    GRAY = '\033[1;30m'
    RESET = '\033[0m'


class NoteManager:
    def __init__(self):
        self.note_dir = os.getenv('NOTES_FOLDERS_PATH')
        self.current_file = os.getenv('NOTES_CURRENT_FILE')
        self.results_file = os.getenv('NOTES_RESULTS_FILE')
        self.script_dir = Path(__file__).parent.parent / 'bin_'
        self.plugin_dir = self.script_dir / 'nlist_plugins'

        if not self.note_dir:
            raise ValueError("NOTES_FOLDERS_PATH environment variable not set")

        self.note_dir = Path(self.note_dir)
        if not self.note_dir.exists():
            raise ValueError(f"NOTE_DIR '{self.note_dir}' not found")

        self.target = self._get_target_dir()

    def _read_current_raw(self) -> str:
        if not self.current_file or not Path(self.current_file).exists():
            return ''
        with open(self.current_file, 'r') as f:
            return f.read().strip()

    def is_alias_mode(self) -> bool:
        return self._read_current_raw().startswith('alias:')

    def _get_target_dir(self) -> Path:
        """Determine the target directory based on current file"""
        current = self._read_current_raw()

        if current.startswith('alias:'):
            p = Path(current[len('alias:'):])
            if p.exists() and p.is_dir():
                return p
            raise ValueError(f"Alias path not found: {p}")

        if current:
            target = self.note_dir / current
            if target.exists() and target.is_dir():
                return target

        return self.note_dir

    def get_current_folder_name(self) -> str:
        """Get the current folder name for display"""
        raw = self._read_current_raw()
        if raw.startswith('alias:'):
            name = Path(raw[len('alias:'):]).name
            return f'{name}  \033[0;33m[alias · read-only]\033[0m'
        return raw

    def get_pdf_files(self) -> List[Tuple[float, str]]:
        """Get all .pdf files with their modification times, sorted by newest first"""
        files = []
        for f in self.target.glob('*.pdf'):
            if f.is_file():
                files.append((f.stat().st_mtime, f.name))
        files.sort(reverse=True)
        return files

    def get_md_files(self, tag_filter: Optional[Set[str]] = None) -> List[Tuple[float, str]]:
        """
        Get all .md files with their modification times, sorted by newest first

        Args:
            tag_filter: If provided, only return files with these tags
        """
        files = []

        # If tag filtering requested, get matching files
        if tag_filter:
            tag_manager = TagManager(self.target)
            matching_files = tag_filter
            # When filtering by tags, search recursively
            for f in self.target.rglob('*.md'):
                if f.is_file() and f.name in matching_files:
                    mtime = f.stat().st_mtime
                    files.append((mtime, f.name))
        else:
            # No filtering - get all files
            for f in self.target.glob('*.md'):
                if f.is_file():
                    mtime = f.stat().st_mtime
                    files.append((mtime, f.name))

        # Sort by modification time, newest first
        files.sort(reverse=True)
        return files

    def get_aliases(self) -> List[str]:
        """Read alias paths from the aliases file in the current notes folder."""
        if self.is_alias_mode():
            return []
        af = self.target / 'aliases'
        if not af.exists():
            return []
        return [l.strip() for l in af.read_text().splitlines() if l.strip()]

    def get_subfolders(self) -> List[Path]:
        """Get all subfolders in the target directory, excluding 'apps'"""
        folders = [f for f in self.target.iterdir() if f.is_dir() and f.name != 'apps']
        folders.sort()
        return folders

    @staticmethod
    def app_display_name(folder_name: str) -> str:
        """Convert a folder name like 'bva-quiz' to a display name like 'BVA Quiz'"""
        return ' '.join(
            word.upper() if len(word) <= 3 else word.capitalize()
            for word in folder_name.replace('-', ' ').replace('_', ' ').split()
        )

    def count_md_files(self, folder: Path) -> int:
        """Count .md files in a folder (recursive, using os.walk for speed)"""
        t0 = time.perf_counter()
        count = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames[:] = [d for d in dirnames if not (dirpath == str(folder) and d == 'apps')]
            count += sum(1 for f in filenames if f.endswith('.md'))
        log.debug('count_md_files(%s) = %d in %.3fs', folder.name, count, time.perf_counter() - t0)
        return count

    def get_apps(self) -> List[Path]:
        """Return subdirectories inside the 'apps' folder that have a run.sh"""
        apps_dir = self.target / 'apps'
        if not apps_dir.is_dir():
            return []
        apps = sorted(
            d for d in apps_dir.iterdir()
            if d.is_dir() and (d / 'run.sh').exists()
        )
        return apps

    def extract_title(self, filepath: Path) -> Optional[str]:
        """Extract title from a markdown file (looks for '# Title:' in first 10 lines)"""
        def _read():
            with open(filepath, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= 10:
                        break
                    match = re.match(r'^#\s*Title:\s*(.+)', line)
                    if match:
                        return match.group(1).strip()
            return None

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_read)
                return future.result(timeout=1.0)
        except (FuturesTimeoutError, Exception):
            return None

    def delete_note(self, index: int) -> None:
        """Move a note to /tmp/notes/delete"""
        files = self.get_md_files()

        if index < 1 or index > len(files):
            print(f"Error: Invalid file number '{index}'.", file=sys.stderr)
            sys.exit(1)

        _, filename = files[index - 1]
        src = self.target / filename

        if not src.exists():
            print(f"Error: File '{src}' not found.", file=sys.stderr)
            sys.exit(1)

        delete_dir = Path('/tmp/notes/delete')
        delete_dir.mkdir(parents=True, exist_ok=True)

        shutil.move(str(src), str(delete_dir))
        print(f"Moved '{src}' → '{delete_dir}/'.")

    def rename_note(self, index: int, new_name: Optional[str] = None, style: Optional[str] = None) -> None:
        """Rename a note (custom name or date style)"""
        files = self.get_md_files()

        if index < 1 or index > len(files):
            print(f"Error: Invalid file number '{index}'.", file=sys.stderr)
            sys.exit(1)

        _, oldname = files[index - 1]
        src = self.target / oldname

        if not src.exists():
            print(f"Error: File '{src}' not found.", file=sys.stderr)
            sys.exit(1)

        if style == 'date':
            # Remove existing date prefix and add new one
            base = oldname.replace('.md', '')
            base = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', base)
            prefix = datetime.now().strftime('%Y-%m-%d')
            newbase = f"{prefix}-{base}"
        elif new_name:
            newbase = new_name.replace('.md', '')
        else:
            print("Error: Missing new name or style. See -h for usage.", file=sys.stderr)
            sys.exit(1)

        dst = self.target / f"{newbase}.md"

        if dst.exists():
            print(f"Error: Destination '{newbase}.md' already exists.", file=sys.stderr)
            sys.exit(1)

        src.rename(dst)
        print(f"Renamed '{oldname}' → '{newbase}.md'.")

    def move_note(self, index: int, destination: str) -> None:
        """Move a note to a subfolder"""
        files = self.get_md_files()

        if index < 1 or index > len(files):
            print(f"Error: Invalid file number '{index}'.", file=sys.stderr)
            sys.exit(1)

        _, filename = files[index - 1]
        src = self.target / filename

        if not src.exists():
            print(f"Error: Source file '{src}' not found.", file=sys.stderr)
            sys.exit(1)

        # Handle ".." for parent directory
        if destination == "..":
            dest_dir = self.target.parent
        else:
            # Try to match partial subfolder name
            folders = self.get_subfolders()
            matched_folder = None

            for folder in folders:
                if folder.name.startswith(destination):
                    matched_folder = folder
                    break

            if not matched_folder:
                print(f"Error: No matching subfolder found for '{destination}'.", file=sys.stderr)
                sys.exit(1)

            dest_dir = matched_folder

        if not dest_dir.exists():
            print(f"Error: Destination folder '{dest_dir}' not found.", file=sys.stderr)
            sys.exit(1)

        dest = dest_dir / filename

        if dest.exists():
            print(f"Error: Destination file '{dest}' already exists.", file=sys.stderr)
            sys.exit(1)

        shutil.move(str(src), str(dest))
        print(f"Moved '{filename}' → '{dest_dir.name}/'.")

    def list_all_tags(self) -> None:
        """List all tags with counts"""
        tag_manager = TagManager(self.target)
        tags_with_counts = tag_manager.get_all_tags_with_counts()

        if not tags_with_counts:
            print("\nNo tags found in current folder.\n")
            return

        print("\n🏷️  All Tags")
        print("=" * 50)
        for tag, count in tags_with_counts:
            print(f"#{tag:<30} ({count} {'file' if count == 1 else 'files'})")
        print()

    def generate_listing(self, tag_filter: Optional[Set[str]] = None):
        """Generate the formatted listing. Returns (results_str, display_str)."""
        output_results = []   # written to results.txt (token at position 1)
        output_display = []   # printed to stdout (human-readable)
        counter = 1
        alias_mode = self.is_alias_mode()

        def _append(results_line: str, display_line: str = None) -> None:
            output_results.append(results_line)
            output_display.append(display_line if display_line is not None else results_line)

        _append("📄 Markdown Files")
        _append("----------------")

        t0 = time.perf_counter()
        files = self.get_md_files(tag_filter)
        log.debug('get_md_files: %d files in %.3fs', len(files), time.perf_counter() - t0)

        for (mtime, name) in files:
            dt = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            filepath = self.target / name
            t1 = time.perf_counter()
            title = self.extract_title(filepath)
            log.debug('extract_title(%s) in %.3fs', name, time.perf_counter() - t1)

            token = f'alias-md:{self.target / name}' if alias_mode else name
            display_name = name  # always show just the filename

            if title:
                results_line = f"{counter}. {token} — {Colors.GRAY}{title}{Colors.RESET} {Colors.GREEN}{dt}{Colors.RESET}"
                display_line = f"{counter}. {display_name} — {Colors.GRAY}{title}{Colors.RESET} {Colors.GREEN}{dt}{Colors.RESET}"
            else:
                results_line = f"{counter}. {token} {Colors.GREEN}{dt}{Colors.RESET}"
                display_line = f"{counter}. {display_name} {Colors.GREEN}{dt}{Colors.RESET}"
            _append(results_line, display_line)
            counter += 1

        # PDF section
        pdf_files = self.get_pdf_files()
        if pdf_files:
            _append("")
            _append("📕 PDF Files")
            _append("----------------")
            for (mtime, name) in pdf_files:
                dt = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                token = f'alias-pdf:{self.target / name}' if alias_mode else name
                _append(
                    f"{counter}. {token} {Colors.GREEN}{dt}{Colors.RESET}",
                    f"{counter}. {name} {Colors.GREEN}{dt}{Colors.RESET}",
                )
                counter += 1

        # Apps section — not shown in alias mode
        if not alias_mode:
            apps = self.get_apps()
            if apps:
                _append("")
                _append("🚀 Apps")
                _append("----------------")
                for app in apps:
                    display = self.app_display_name(app.name)
                    _append(f"{counter}. app:{app.name} {Colors.BLUE}{display}{Colors.RESET}")
                    counter += 1

        _append("")
        _append("📁 Subfolders")
        _append("----------------")

        t_folders = time.perf_counter()
        folders = self.get_subfolders()
        log.debug('get_subfolders: %d in %.3fs', len(folders), time.perf_counter() - t_folders)
        for folder in folders:
            count = self.count_md_files(folder)
            if alias_mode:
                _append(f"• {Colors.BLUE}{folder.name}{Colors.RESET} ({count} files)")
            else:
                apps_dir = folder / 'apps'
                has_apps = apps_dir.is_dir() and any(
                    (d / 'run.sh').exists() for d in apps_dir.iterdir() if d.is_dir()
                )
                app_icon = " 🚀" if has_apps else ""
                _append(f"• {Colors.BLUE}{folder.name}{Colors.RESET}{app_icon} ({count} files)")

        # Aliases section — only in normal notes mode
        if not alias_mode:
            aliases = self.get_aliases()
            if aliases:
                _append("")
                _append("🔗 Aliases")
                _append("----------------")
                home = str(Path.home())
                for apath in aliases:
                    name = Path(apath).name
                    exists = Path(apath).is_dir()
                    marker = '' if exists else f'  {Colors.RESET}\033[0;31m[missing]\033[0m'
                    short = '~' + apath[len(home):] if apath.startswith(home) else apath
                    _append(
                        f"{counter}. alias-nav:{apath} {name}",
                        f"{counter}. {Colors.BLUE}{name}{Colors.RESET}{marker}  {Colors.GRAY}{short}{Colors.RESET}",
                    )
                    counter += 1

        return '\n'.join(output_results), '\n'.join(output_display)

    def run_plugins(self) -> None:
        """Run any executable plugins in nlist_plugins/"""
        if not self.plugin_dir.exists():
            return

        for plugin in self.plugin_dir.glob('*.sh'):
            if plugin.is_file() and os.access(plugin, os.X_OK):
                subprocess.run([str(plugin), self.results_file, str(self.target)])

    def list_notes(self, tag_filter: Optional[Set[str]] = None) -> None:
        """Main listing function"""
        results, display = self.generate_listing(tag_filter)

        # Write to results file
        if self.results_file:
            with open(self.results_file, 'w') as f:
                f.write(results)

        # Run plugins (they may modify results.txt)
        self.run_plugins()

        # Re-read results.txt so plugin annotations appear in display
        if self.results_file and Path(self.results_file).exists():
            with open(self.results_file) as f:
                display = f.read()

        # Print to stdout
        print()
        current = self.get_current_folder_name()
        print(f"current > {current}")
        print("-" * 80)
        print(display)
        print()
        print_tip()


def main():
    parser = argparse.ArgumentParser(
        description='List and manage notes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nlist
  nlist -delete 3
  nlist -rename 2 meeting_notes
  nlist -rename 1 -style date
  nlist -move 5 research
  nlist -move 2 ..
  nlist -move 1 res      # (partial match, moves into 'research' folder)
  nlist -tags            # List all tags with counts
  nlist -tag food        # List notes tagged with #food
  nlist -tag food,recipe # List notes with #food OR #recipe

Environment Variables:
  NOTES_FOLDERS_PATH   Directory where your notes subfolders live
  NOTES_CURRENT_FILE   File containing your "current" folder name
  NOTES_RESULTS_FILE   Where the listing is written
        """
    )

    parser.add_argument('-delete', type=int, metavar='NUM',
                        help='Move the Nth Markdown file to /tmp/notes/delete')
    parser.add_argument('-rename', type=int, metavar='NUM',
                        help='Rename the Nth Markdown file')
    parser.add_argument('-style', choices=['date'],
                        help='Rename style (use with -rename)')
    parser.add_argument('-move', nargs=2, metavar=('NUM', 'FOLDER'),
                        help='Move the Nth file to FOLDER')
    parser.add_argument('-recent', nargs='?', const=0, type=int, metavar='N',
                        help='Show recent files (no arg), or open Nth recent file')
    parser.add_argument('-tags', action='store_true',
                        help='List all tags with counts')
    parser.add_argument('-tag', type=str, metavar='TAGS',
                        help='Filter by tags (comma-separated for OR logic)')
    parser.add_argument('new_name', nargs='?',
                        help='New name for file (use with -rename)')

    args = parser.parse_args()

    try:
        manager = NoteManager()

        # Handle -recent
        if args.recent is not None:
            notes_path = os.getenv('NOTES_PATH')
            notes_folders = os.getenv('NOTES_FOLDERS_PATH')
            if not notes_path:
                print("Error: NOTES_PATH not set", file=sys.stderr)
                sys.exit(1)
            file_history = Path(notes_path) / 'file_history'
            entries = [l for l in file_history.read_text().splitlines() if l.strip()] if file_history.exists() else []
            if args.recent == 0:
                # Just display with indices
                print()
                print('Recent files:')
                print('-' * 40)
                if entries:
                    for i, entry in enumerate(entries, 1):
                        print(f'  {Colors.BLUE}{i}{Colors.RESET}  {Colors.GREEN}{entry}{Colors.RESET}')
                else:
                    print('  No recent files yet.')
                print()
            else:
                # Open the Nth recent file
                idx = args.recent
                if not entries or idx < 1 or idx > len(entries):
                    print(f'Error: no recent file at index {idx}', file=sys.stderr)
                    sys.exit(1)
                rel_path = entries[idx - 1]
                fullpath = Path(notes_folders) / rel_path
                os.execvp('nvim', ['nvim', str(fullpath)])
            return

        # Handle -tags (list all tags)
        if args.tags:
            manager.list_all_tags()
            return

        # Handle -tag (filter by tags)
        tag_filter = None
        if args.tag:
            tag_manager = TagManager(manager.target)
            # Split comma-separated tags
            tags = [t.strip() for t in args.tag.split(',')]
            # Get files matching any of these tags (OR logic)
            tag_filter = tag_manager.get_files_by_tags(tags, match_all=False)

            if not tag_filter:
                print(f"\nNo notes found with tag(s): {', '.join(f'#{t}' for t in tags)}\n")
                return

        # Handle -delete
        if args.delete:
            manager.delete_note(args.delete)
            return

        # Handle -rename
        if args.rename:
            manager.rename_note(args.rename, args.new_name, args.style)
            return

        # Handle -move
        if args.move:
            index, folder = args.move
            manager.move_note(int(index), folder)
            return

        # Default: list notes (with optional tag filter)
        manager.list_notes(tag_filter)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
