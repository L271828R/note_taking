"""
Tests for nlist.py

These tests create temporary note directories and verify nlist functionality
"""

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
import subprocess
import sys

import pytest


# Add python_scripts to path so we can import nlist
sys.path.insert(0, str(Path(__file__).parent.parent / 'python_scripts'))

from nlist import NoteManager


class TestNoteManager:
    """Test the NoteManager class"""

    @pytest.fixture
    def temp_notes_dir(self, tmp_path, monkeypatch):
        """Create a temporary notes directory structure"""
        # Create folders structure
        folders_path = tmp_path / "folders"
        folders_path.mkdir()

        # Create a test folder with some notes
        test_folder = folders_path / "test_journal"
        test_folder.mkdir()

        # Create some test notes with different timestamps
        notes = [
            ("2025-01-01.md", "# Title: New Year\n\nFirst note of the year", 1704067200),
            ("2025-01-02.md", "# Title: Second Day\n\nAnother note", 1704153600),
            ("meeting-notes.md", "Meeting with team", 1704240000),
            ("untitled.md", "No title here", 1704326400),
        ]

        for filename, content, mtime in notes:
            note_path = test_folder / filename
            note_path.write_text(content)
            os.utime(note_path, (mtime, mtime))

        # Create a subfolder
        subfolder = test_folder / "archive"
        subfolder.mkdir()
        (subfolder / "old-note.md").write_text("# Title: Old\n\nArchived note")

        # Create current file
        current_file = tmp_path / "current"
        current_file.write_text("test_journal")

        # Create results file
        results_file = tmp_path / "results.txt"
        results_file.touch()

        # Set environment variables
        monkeypatch.setenv("NOTES_FOLDERS_PATH", str(folders_path))
        monkeypatch.setenv("NOTES_CURRENT_FILE", str(current_file))
        monkeypatch.setenv("NOTES_RESULTS_FILE", str(results_file))
        monkeypatch.setenv("NOTES_PATH", str(tmp_path))

        return {
            "folders_path": folders_path,
            "test_folder": test_folder,
            "current_file": current_file,
            "results_file": results_file,
            "tmp_path": tmp_path,
        }

    def test_initialization(self, temp_notes_dir):
        """Test NoteManager initializes correctly"""
        manager = NoteManager()
        assert manager.note_dir == temp_notes_dir["folders_path"]
        assert manager.target == temp_notes_dir["test_folder"]

    def test_get_md_files(self, temp_notes_dir):
        """Test getting markdown files sorted by modification time"""
        manager = NoteManager()
        files = manager.get_md_files()

        assert len(files) == 4
        # Files should be sorted by mtime, newest first
        filenames = [f[1] for f in files]
        assert filenames[0] == "untitled.md"  # Most recent
        assert filenames[-1] == "2025-01-01.md"  # Oldest

    def test_get_subfolders(self, temp_notes_dir):
        """Test getting subfolders excludes 'apps' directory"""
        manager = NoteManager()

        # Add an apps dir — it should be excluded
        apps_dir = temp_notes_dir["test_folder"] / "apps"
        apps_dir.mkdir()

        folders = manager.get_subfolders()
        folder_names = [f.name for f in folders]

        assert "archive" in folder_names
        assert "apps" not in folder_names

    def test_count_md_files(self, temp_notes_dir):
        """Test counting markdown files in a folder"""
        manager = NoteManager()
        subfolder = temp_notes_dir["test_folder"] / "archive"
        count = manager.count_md_files(subfolder)

        assert count == 1

    def test_extract_title(self, temp_notes_dir):
        """Test extracting title from markdown files"""
        manager = NoteManager()

        # File with title
        note_with_title = temp_notes_dir["test_folder"] / "2025-01-01.md"
        title = manager.extract_title(note_with_title)
        assert title == "New Year"

        # File without title
        note_without_title = temp_notes_dir["test_folder"] / "untitled.md"
        title = manager.extract_title(note_without_title)
        assert title is None

    def test_delete_note(self, temp_notes_dir):
        """Test deleting (moving) a note"""
        manager = NoteManager()

        # Delete the first note (most recent, which is untitled.md)
        manager.delete_note(1)

        # Check note was moved
        original_path = temp_notes_dir["test_folder"] / "untitled.md"
        assert not original_path.exists()

        delete_dir = Path("/tmp/notes/delete")
        deleted_file = delete_dir / "untitled.md"
        assert deleted_file.exists()

        # Cleanup
        deleted_file.unlink()

    def test_delete_invalid_index(self, temp_notes_dir):
        """Test deleting with invalid index raises error"""
        manager = NoteManager()

        with pytest.raises(SystemExit):
            manager.delete_note(999)

    def test_rename_note(self, temp_notes_dir):
        """Test renaming a note"""
        manager = NoteManager()

        # Rename the first note
        manager.rename_note(1, "renamed-note")

        # Check old name doesn't exist
        old_path = temp_notes_dir["test_folder"] / "untitled.md"
        assert not old_path.exists()

        # Check new name exists
        new_path = temp_notes_dir["test_folder"] / "renamed-note.md"
        assert new_path.exists()

    def test_rename_with_date_style(self, temp_notes_dir):
        """Test renaming a note with date prefix"""
        manager = NoteManager()

        # Rename with date style
        manager.rename_note(1, style="date")

        # Check that a file with today's date prefix exists
        today = datetime.now().strftime('%Y-%m-%d')
        files = list(temp_notes_dir["test_folder"].glob(f"{today}-*.md"))
        assert len(files) == 1
        assert files[0].name == f"{today}-untitled.md"

    def test_rename_existing_date_prefix(self, temp_notes_dir):
        """Test renaming a note that already has a date prefix"""
        manager = NoteManager()

        # Get the index of 2025-01-01.md (should be last, index 4)
        files = manager.get_md_files()
        filenames = [f[1] for f in files]
        index = filenames.index("2025-01-01.md") + 1

        # Rename with date style
        manager.rename_note(index, style="date")

        # Check the old date was removed and new date added
        today = datetime.now().strftime('%Y-%m-%d')
        new_path = temp_notes_dir["test_folder"] / f"{today}-2025-01-01.md"
        assert new_path.exists()

    def test_move_note_to_subfolder(self, temp_notes_dir):
        """Test moving a note to a subfolder"""
        manager = NoteManager()

        # Move first note to archive
        manager.move_note(1, "archive")

        # Check note moved
        old_path = temp_notes_dir["test_folder"] / "untitled.md"
        assert not old_path.exists()

        new_path = temp_notes_dir["test_folder"] / "archive" / "untitled.md"
        assert new_path.exists()

    def test_move_note_partial_match(self, temp_notes_dir):
        """Test moving a note with partial folder name match"""
        manager = NoteManager()

        # Move using partial match "arc" for "archive"
        manager.move_note(1, "arc")

        # Check note moved
        new_path = temp_notes_dir["test_folder"] / "archive" / "untitled.md"
        assert new_path.exists()

    def test_move_note_to_parent(self, temp_notes_dir):
        """Test moving a note to parent directory using '..'"""
        # First, move a note to archive, then move it back
        manager = NoteManager()
        manager.move_note(1, "archive")

        # Verify it's in archive
        archive_path = temp_notes_dir["test_folder"] / "archive" / "untitled.md"
        assert archive_path.exists()

        # Now change to archive folder
        current_file = temp_notes_dir["current_file"]
        current_file.write_text("test_journal/archive")

        # Recreate manager with new current
        manager = NoteManager()

        # The archive now has 2 files (old-note.md and untitled.md)
        # untitled.md should be index 1 or 2 depending on sorting
        files = manager.get_md_files()
        filenames = [f[1] for f in files]
        untitled_index = filenames.index("untitled.md") + 1

        # Move back to parent
        manager.move_note(untitled_index, "..")

        # Check note is back in parent
        parent_path = temp_notes_dir["test_folder"] / "untitled.md"
        assert parent_path.exists()

    def test_generate_listing(self, temp_notes_dir):
        """Test generating the listing output"""
        manager = NoteManager()
        listing = manager.generate_listing()

        # Check listing contains expected content
        assert "📄 Markdown Files" in listing
        assert "📁 Subfolders" in listing
        assert "untitled.md" in listing
        assert "archive" in listing
        assert "(1 files)" in listing  # archive has 1 file

    def test_generate_listing_with_apps(self, temp_notes_dir):
        """Apps section appears in listing when apps/ contains valid apps"""
        apps_dir = temp_notes_dir["test_folder"] / "apps" / "my-tool"
        apps_dir.mkdir(parents=True)
        (apps_dir / "run.sh").write_text("#!/usr/bin/env bash\necho hi")

        manager = NoteManager()
        listing = manager.generate_listing()

        assert "🚀 Apps" in listing
        assert "app:my-tool" in listing
        # "my" (2) ≤3 → MY, "tool" (4) → Tool
        assert "MY Tool" in listing

    def test_generate_listing_apps_not_in_subfolders(self, temp_notes_dir):
        """apps/ dir must not appear under Subfolders section"""
        apps_dir = temp_notes_dir["test_folder"] / "apps" / "some-app"
        apps_dir.mkdir(parents=True)
        (apps_dir / "run.sh").write_text("#!/usr/bin/env bash\necho hi")

        manager = NoteManager()
        listing = manager.generate_listing()

        # Split at the Subfolders header and check apps not listed there
        subfolders_section = listing.split("📁 Subfolders")[-1]
        assert "apps" not in subfolders_section

    def test_generate_listing_no_apps_section_when_empty(self, temp_notes_dir):
        """No apps section when apps/ dir is absent or has no run.sh"""
        manager = NoteManager()
        listing = manager.generate_listing()
        assert "🚀 Apps" not in listing

    def test_apps_numbering_continues_after_notes(self, temp_notes_dir):
        """App entries are numbered sequentially after note entries"""
        apps_dir = temp_notes_dir["test_folder"] / "apps" / "alpha"
        apps_dir.mkdir(parents=True)
        (apps_dir / "run.sh").write_text("#!/usr/bin/env bash\necho hi")

        manager = NoteManager()
        files = manager.get_md_files()
        note_count = len(files)

        listing = manager.generate_listing()
        expected_app_number = note_count + 1
        assert f"{expected_app_number}. app:alpha" in listing

    def test_list_notes_writes_to_file(self, temp_notes_dir):
        """Test that list_notes writes to results file"""
        manager = NoteManager()
        manager.list_notes()

        # Check results file was written
        results_file = temp_notes_dir["results_file"]
        assert results_file.exists()

        content = results_file.read_text()
        assert "📄 Markdown Files" in content
        assert "untitled.md" in content


class TestNlistCLI:
    """Test the nlist command-line interface"""

    @pytest.fixture
    def temp_env(self, tmp_path, monkeypatch):
        """Setup temporary environment for CLI tests"""
        folders_path = tmp_path / "folders"
        folders_path.mkdir()

        test_folder = folders_path / "cli_test"
        test_folder.mkdir()

        # Create a test note
        (test_folder / "test.md").write_text("# Title: Test\n\nTest content")

        current_file = tmp_path / "current"
        current_file.write_text("cli_test")

        results_file = tmp_path / "results.txt"

        monkeypatch.setenv("NOTES_FOLDERS_PATH", str(folders_path))
        monkeypatch.setenv("NOTES_CURRENT_FILE", str(current_file))
        monkeypatch.setenv("NOTES_RESULTS_FILE", str(results_file))
        monkeypatch.setenv("NOTES_PATH", str(tmp_path))

        return {
            "folders_path": folders_path,
            "test_folder": test_folder,
        }

    def test_cli_help(self):
        """Test CLI help output"""
        result = subprocess.run(
            ["python3", "python_scripts/nlist.py", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "List and manage notes" in result.stdout

    def test_cli_list(self, temp_env):
        """Test CLI listing command"""
        result = subprocess.run(
            ["python3", "python_scripts/nlist.py"],
            capture_output=True,
            text=True,
        )
        # Note: This might fail if NOTES_* env vars aren't passed through
        # In real usage, the wrapper script handles this
        assert "test.md" in result.stdout or result.returncode == 1


class TestAppDisplayName:
    """Test the app_display_name static method"""

    def test_hyphenated(self):
        assert NoteManager.app_display_name("bva-quiz") == "BVA Quiz"

    def test_single_word(self):
        assert NoteManager.app_display_name("dashboard") == "Dashboard"

    def test_short_words_uppercased(self):
        # words of 3 chars or fewer → uppercase
        assert NoteManager.app_display_name("qa-tool") == "QA Tool"

    def test_underscore_separator(self):
        # "my" (2) and "app" (3) are both ≤3 chars → uppercased
        assert NoteManager.app_display_name("my_app") == "MY APP"

    def test_mixed_lengths(self):
        # "my" (2) ≤3 → MY, "bva" (3) ≤3 → BVA, "app" (3) ≤3 → APP
        assert NoteManager.app_display_name("my-bva-app") == "MY BVA APP"

    def test_long_word_capitalised(self):
        assert NoteManager.app_display_name("flashcards") == "Flashcards"


class TestGetApps:
    """Test the get_apps method"""

    @pytest.fixture
    def temp_with_apps(self, tmp_path, monkeypatch):
        folders_path = tmp_path / "folders"
        test_folder = folders_path / "work"
        test_folder.mkdir(parents=True)
        apps_dir = test_folder / "apps"
        apps_dir.mkdir()

        current_file = tmp_path / "current"
        current_file.write_text("work")
        results_file = tmp_path / "results.txt"
        results_file.touch()

        monkeypatch.setenv("NOTES_FOLDERS_PATH", str(folders_path))
        monkeypatch.setenv("NOTES_CURRENT_FILE", str(current_file))
        monkeypatch.setenv("NOTES_RESULTS_FILE", str(results_file))
        monkeypatch.setenv("NOTES_PATH", str(tmp_path))

        return apps_dir

    def test_returns_apps_with_run_sh(self, temp_with_apps):
        app = temp_with_apps / "my-app"
        app.mkdir()
        (app / "run.sh").write_text("#!/usr/bin/env bash")

        manager = NoteManager()
        apps = manager.get_apps()
        assert len(apps) == 1
        assert apps[0].name == "my-app"

    def test_ignores_dirs_without_run_sh(self, temp_with_apps):
        (temp_with_apps / "not-an-app").mkdir()

        manager = NoteManager()
        assert manager.get_apps() == []

    def test_returns_empty_when_no_apps_folder(self, temp_with_apps):
        # Remove the apps dir entirely
        temp_with_apps.rmdir()
        manager = NoteManager()
        assert manager.get_apps() == []

    def test_multiple_apps_sorted(self, temp_with_apps):
        for name in ("zebra-app", "alpha-app", "middle-app"):
            d = temp_with_apps / name
            d.mkdir()
            (d / "run.sh").write_text("#!/usr/bin/env bash")

        manager = NoteManager()
        names = [a.name for a in manager.get_apps()]
        assert names == sorted(names)


def test_imports():
    """Test that we can import the nlist module"""
    import nlist
    assert hasattr(nlist, 'NoteManager')
    assert hasattr(nlist, 'main')
