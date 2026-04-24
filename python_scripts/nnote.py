#!/usr/bin/env python3
"""
nnote - Create or open a note (Python version)

Features:
1) Auto-adds .md extension if not provided
2) Creates notes from template with unique ID
3) Auto-journal support for journal folders
4) Zettelkasten mode for ideas folders
5) Plugin hook system
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from secrets import token_hex


class NoteCreator:
    def __init__(self):
        self.note_dir = os.getenv('NOTES_FOLDERS_PATH')
        self.current_file = os.getenv('NOTES_CURRENT_FILE')
        self.notes_path = os.getenv('NOTES_PATH')

        if not self.note_dir:
            raise ValueError("NOTES_FOLDERS_PATH environment variable not set")
        if not self.current_file:
            raise ValueError("NOTES_CURRENT_FILE environment variable not set")
        if not self.notes_path:
            raise ValueError("NOTES_PATH environment variable not set")

        self.note_dir = Path(self.note_dir)
        self.current_file = Path(self.current_file)
        self.default_template = Path(self.notes_path) / 'templates' / 'default.md'

        # Get script directory for plugins
        self.script_dir = Path(__file__).parent.parent / 'bin_'
        self.plugin_dir = self.script_dir / 'nnote_plugins'

        if not self.note_dir.exists():
            raise ValueError(f"NOTE_DIR '{self.note_dir}' not found")
        if not self.current_file.exists():
            raise ValueError(f"Cannot read current file pointer: {self.current_file}")
        if not self.default_template.exists():
            raise ValueError(f"Default template not found: {self.default_template}")

    def get_current_folder(self) -> str:
        """Read the current folder from the current file"""
        with open(self.current_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:  # First non-empty line
                    return line
        raise ValueError("Current file is empty")

    def run_plugins(self, args: list) -> None:
        """Run any executable plugins in nnote_plugins/"""
        if not self.plugin_dir.exists():
            return

        for plugin in sorted(self.plugin_dir.glob('*')):
            if plugin.is_file() and os.access(plugin, os.X_OK):
                # Call plugin with same arguments
                subprocess.run([str(plugin)] + args)

    def generate_id(self) -> str:
        """Generate a random 8-character hex ID"""
        # Equivalent to: xxd -l4 -p /dev/urandom
        return token_hex(4)

    @staticmethod
    def filename_to_title(filename: str) -> str:
        """Convert 'some-file-name' or 'some_file_name' to 'Some File Name'"""
        stem = Path(filename).stem
        return ' '.join(w.capitalize() for w in stem.replace('-', ' ').replace('_', ' ').split())

    def inject_title(self, file_path: Path, title: str) -> None:
        """Replace '# Title:' line with '# Title: <title>'"""
        content = file_path.read_text(encoding='utf-8')
        content = content.replace('# Title:\n', f'# Title: {title}\n', 1)
        file_path.write_text(content, encoding='utf-8')

    def inject_id(self, file_path: Path) -> None:
        """Inject ID at the top of the file if not present"""
        with open(file_path, 'r') as f:
            content = f.read()

        # Check if ID already exists
        if content.startswith('<!-- id:'):
            return

        # Generate and prepend ID
        note_id = self.generate_id()
        new_content = f"<!-- id: {note_id} -->\n{content}"

        with open(file_path, 'w') as f:
            f.write(new_content)

    def add_md_extension(self, filename: str) -> str:
        """Add .md extension if not already present"""
        if not filename:
            return filename

        # Check if it already has an extension
        _, ext = os.path.splitext(filename)
        if not ext:
            return f"{filename}.md"
        return filename

    def create_note(self, filename: str) -> Path:
        """
        Create or open a note.

        Args:
            filename: The note filename (will auto-add .md if no extension)

        Returns:
            Path to the note file
        """
        current = self.get_current_folder()

        # Auto-journal: if in journal folder and no filename, use today's date
        if not filename and 'journal' in current:
            filename = f"{datetime.now().strftime('%Y-%m-%d')}.md"

        # Zettelkasten mode: if in ideas folder, add random suffix
        if 'ideas' in current:
            # Generate filename with random suffix
            date_str = datetime.now().strftime('%Y-%m-%d')
            random_suffix = token_hex(3)
            filename = f"{date_str}-{random_suffix}.md"

        # Require filename
        if not filename:
            raise ValueError("Usage: nnote <filename>")

        # Add .md extension if not present
        filename = self.add_md_extension(filename)

        # Build full path
        file_path = self.note_dir / current / filename

        # Create file if it doesn't exist
        if not file_path.exists():
            # Create directory if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy from template
            import shutil
            shutil.copy2(self.default_template, file_path)

            # Inject ID
            self.inject_id(file_path)

            # Inject title derived from filename
            title = self.filename_to_title(filename)
            self.inject_title(file_path, title)

        return file_path

    def push_file_history(self, file_path: Path) -> None:
        """Record recently opened/created file in file_history (last 5 unique)."""
        file_history = Path(self.notes_path) / 'file_history'
        # Make path relative to NOTES_FOLDERS_PATH
        try:
            entry = str(file_path.relative_to(self.note_dir))
        except ValueError:
            return
        existing = [l for l in file_history.read_text().splitlines() if l.strip()] if file_history.exists() else []
        deduped = [e for e in existing if e != entry]
        file_history.write_text('\n'.join(([entry] + deduped)[:5]) + '\n')

    def open_in_editor(self, file_path: Path) -> None:
        """Open file in nvim"""
        print("Opening nvim")
        os.execvp('nvim', ['nvim', str(file_path)])


def main():
    parser = argparse.ArgumentParser(
        description='Create or open a note with auto .md extension',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nnote my_note          # Creates/opens my_note.md
  nnote my_note.md       # Creates/opens my_note.md
  nnote my_note.txt      # Creates/opens my_note.txt (keeps .txt)

Special behaviors:
  - In journal folders: no filename defaults to today's date (YYYY-MM-DD.md)
  - In ideas folders: auto-generates unique filename with date and random suffix
  - Auto-adds .md extension if no extension provided
        """
    )

    parser.add_argument(
        'filename',
        nargs='?',
        help='Note filename (auto-adds .md if no extension)'
    )

    args = parser.parse_args()

    try:
        creator = NoteCreator()

        # Run plugins first (with original arguments)
        creator.run_plugins(sys.argv[1:])

        # Check if plugin took control
        if os.getenv('NNOTE_EXIT_AFTER_PLUGIN') == '1':
            sys.exit(0)

        # Create/open note
        file_path = creator.create_note(args.filename)

        # Record in file history
        creator.push_file_history(file_path)

        # Open in editor
        creator.open_in_editor(file_path)

    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
