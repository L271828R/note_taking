#!/usr/bin/env python3
"""
nlist2 - Interactive list selector using 'curses' (built-in)
Raw terminal control with vim-style navigation
Supports tag filtering and deletion
No external dependencies!
"""

import curses
import os
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Add to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from nlist import NoteManager
from note_tags import TagManager


def draw_menu(stdscr, current_row, items, title, preview_lines=None, items_to_delete=None):
    """Draw the menu with highlighting and preview pane"""
    if items_to_delete is None:
        items_to_delete = set()

    stdscr.clear()
    h, w = stdscr.getmaxyx()

    # Calculate layout - split screen vertically
    # Left side: list (60% of width)
    # Right side: preview (40% of width)
    list_width = int(w * 0.6)
    preview_width = w - list_width - 1  # -1 for divider

    # Draw title
    stdscr.attron(curses.color_pair(1))
    stdscr.addstr(0, 0, title[:list_width-1])
    stdscr.attroff(curses.color_pair(1))

    # Draw instructions
    instructions = "j/k: navigate | d: mark delete | Enter: select/delete | q/Esc: quit"
    stdscr.addstr(1, 0, instructions[:list_width-1])
    stdscr.addstr(2, 0, "-" * min(list_width-1, len(instructions)))

    # Calculate how many items we can show
    max_items = h - 4  # Reserve space for title, instructions, divider

    # Draw items
    for idx, item in enumerate(items):
        y = idx + 3
        if y >= h - 1 or idx >= max_items:  # Don't draw beyond screen
            break

        # Determine styling based on selection and delete status
        if idx in items_to_delete:
            # Red for items marked for deletion
            if idx == current_row:
                stdscr.attron(curses.color_pair(4))  # Red background with black text
                prefix = "=> "
            else:
                stdscr.attron(curses.color_pair(3))  # Red text
                prefix = "   "
        elif idx == current_row:
            stdscr.attron(curses.color_pair(2))  # Cyan background
            prefix = "=> "
        else:
            prefix = "   "

        # Truncate item if too long for list pane
        display = prefix + item
        if len(display) >= list_width - 1:
            display = display[:list_width-4] + "..."

        try:
            stdscr.addstr(y, 0, display)
        except curses.error:
            pass  # Ignore if we can't write to screen edge

        # Turn off attributes
        if idx in items_to_delete:
            if idx == current_row:
                stdscr.attroff(curses.color_pair(4))
            else:
                stdscr.attroff(curses.color_pair(3))
        elif idx == current_row:
            stdscr.attroff(curses.color_pair(2))

    # Draw vertical divider
    for y in range(h - 1):
        try:
            stdscr.addstr(y, list_width, "│")
        except curses.error:
            pass

    # Draw preview pane header
    preview_x = list_width + 2
    try:
        stdscr.attron(curses.color_pair(1))
        stdscr.addstr(0, preview_x, "Preview"[:preview_width-2])
        stdscr.attroff(curses.color_pair(1))
        stdscr.addstr(2, preview_x, "─" * min(preview_width-2, 40))
    except curses.error:
        pass

    # Draw preview content
    if preview_lines:
        preview_start_y = 3
        for i, line in enumerate(preview_lines[:h-4]):  # Leave space at bottom
            y = preview_start_y + i
            if y >= h - 1:
                break

            # Truncate line to fit preview pane
            display_line = line[:preview_width-2]
            try:
                stdscr.addstr(y, preview_x, display_line)
            except curses.error:
                pass

    stdscr.refresh()


def main_curses(stdscr, tag_filter=None):
    """Main curses application"""
    # Initialize colors
    curses.curs_set(0)  # Hide cursor
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)  # Red text for delete
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_RED)  # Red background for selected delete

    # Get notes
    manager = NoteManager()

    # Track items marked for deletion
    items_to_delete = set()

    def refresh_items():
        """Refresh the file list and display items"""
        files = manager.get_md_files(tag_filter)

        if not files:
            return [], []

        items = []
        for i, (mtime, name) in enumerate(files, 1):
            dt = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            filepath = manager.target / name
            title = manager.extract_title(filepath)

            if title:
                display = f"{i}. {name} — {title} ({dt})"
            else:
                display = f"{i}. {name} ({dt})"

            items.append(display)

        return files, items

    files, items = refresh_items()

    if not files:
        stdscr.addstr(0, 0, "No notes found in current folder.")
        stdscr.addstr(1, 0, "Press any key to exit...")
        stdscr.getch()
        return None

    current = manager.get_current_folder_name() or 'root'
    title = f"📄 Notes in {current}"
    current_row = 0

    def get_preview(index):
        """Get preview lines for the selected note"""
        try:
            _, filename = files[index]
            filepath = manager.target / filename
            with open(filepath, 'r', encoding='utf-8') as f:
                # Read first 50 lines for preview
                lines = []
                for i, line in enumerate(f):
                    if i >= 50:
                        break
                    lines.append(line.rstrip('\n'))
                return lines
        except Exception as e:
            return [f"Error loading preview: {e}"]

    while True:
        preview = get_preview(current_row)
        draw_menu(stdscr, current_row, items, title, preview, items_to_delete)
        key = stdscr.getch()

        # Navigation
        if key == ord('j') or key == curses.KEY_DOWN:
            current_row = min(current_row + 1, len(items) - 1)
        elif key == ord('k') or key == curses.KEY_UP:
            current_row = max(current_row - 1, 0)
        elif key == ord('g'):  # Go to top
            current_row = 0
        elif key == ord('G'):  # Go to bottom
            current_row = len(items) - 1

        # Toggle delete mark
        elif key == ord('d'):
            if current_row in items_to_delete:
                items_to_delete.remove(current_row)
            else:
                items_to_delete.add(current_row)

        # Selection or Delete
        elif key == ord('\n') or key == curses.KEY_ENTER or key == 10 or key == 13:
            if items_to_delete:
                # Delete marked files
                files_to_delete = []
                for idx in sorted(items_to_delete, reverse=True):
                    _, filename = files[idx]
                    filepath = manager.target / filename
                    files_to_delete.append(filepath)

                # Perform deletion
                for filepath in files_to_delete:
                    try:
                        filepath.unlink()
                    except Exception as e:
                        # Show error briefly
                        stdscr.addstr(0, 0, f"Error deleting {filepath.name}: {e}")
                        stdscr.refresh()
                        stdscr.getch()

                # Clear delete set and refresh
                items_to_delete.clear()
                files, items = refresh_items()

                if not files:
                    stdscr.addstr(0, 0, "No notes remaining in current folder.")
                    stdscr.addstr(1, 0, "Press any key to exit...")
                    stdscr.refresh()
                    stdscr.getch()
                    return None

                # Adjust current_row if needed
                current_row = min(current_row, len(items) - 1)
            else:
                # Return the selected file
                _, filename = files[current_row]
                return manager.target / filename

        # Quit
        elif key == ord('q') or key == 27:  # 27 is ESC
            return None


def main():
    """Wrapper to run curses application"""
    parser = argparse.ArgumentParser(
        description='Interactive note selector with vim-style navigation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  nlist2                 # Interactive selector for all notes
  nlist2 -tags           # List all tags with counts
  nlist2 -tag food       # Interactive selector for notes with #food
  nlist2 -tag food,recipe # Interactive selector for notes with #food OR #recipe

Interactive Keys:
  j/k         Navigate down/up
  g/G         Jump to top/bottom
  d           Toggle delete mark (red highlight)
  Enter       Open selected file (or delete marked files)
  q/Esc       Quit
        """
    )

    parser.add_argument('-tags', action='store_true',
                        help='List all tags with counts (non-interactive)')
    parser.add_argument('-tag', type=str, metavar='TAGS',
                        help='Filter by tags (comma-separated for OR logic)')

    args = parser.parse_args()

    try:
        manager = NoteManager()

        # Handle -tags (list all tags)
        if args.tags:
            tag_manager = TagManager(manager.target)
            tags_with_counts = tag_manager.get_all_tags_with_counts()

            if not tags_with_counts:
                print("\nNo tags found in current folder.\n")
                return

            print("\n🏷️  All Tags")
            print("=" * 50)
            for tag, count in tags_with_counts:
                print(f"#{tag:<30} ({count} {'file' if count == 1 else 'files'})")
            print()
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

        # Run interactive curses interface
        selected_file = curses.wrapper(main_curses, tag_filter)

        if selected_file:
            # Open in nvim
            subprocess.run(['nvim', str(selected_file)])

    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
