"""
Tests for nopen.py

Covers note resolution, app dispatch, last_visited stamping,
and error handling.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'python_scripts'))

from nopen import NoteOpener


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def env(tmp_path, monkeypatch):
    """Minimal notes environment with one note and one app."""
    folders_path = tmp_path / "folders"
    work = folders_path / "work"
    work.mkdir(parents=True)

    # A regular note
    (work / "note-one.md").write_text("# Title: Note One\n\nHello")

    # An app
    app_dir = work / "apps" / "my-app"
    app_dir.mkdir(parents=True)
    run_sh = app_dir / "run.sh"
    run_sh.write_text("#!/usr/bin/env bash\necho running")
    run_sh.chmod(0o755)

    # current file
    current_file = tmp_path / "current"
    current_file.write_text("work")

    # results.txt — mirrors what nlist would write
    results_file = tmp_path / "results.txt"
    results_file.write_text(
        "📄 Markdown Files\n"
        "----------------\n"
        "1. note-one.md  2026-01-01 00:00:00\n"
        "\n"
        "🚀 Apps\n"
        "----------------\n"
        "2. app:my-app  My App\n"
    )

    # note_map.json
    map_file = tmp_path / ".note_map.json"
    map_file.write_text(json.dumps({
        "abc123": {
            "path": "folders/work/note-one.md",
            "title": "Note One",
            "last_visited": "2020-01-01T00:00:00Z"
        }
    }))

    monkeypatch.setenv("NOTES_FOLDERS_PATH", str(folders_path))
    monkeypatch.setenv("NOTES_CURRENT_FILE", str(current_file))
    monkeypatch.setenv("NOTES_RESULTS_FILE", str(results_file))
    monkeypatch.setenv("NOTES_PATH", str(tmp_path))

    return {
        "folders_path": folders_path,
        "work": work,
        "current_file": current_file,
        "results_file": results_file,
        "map_file": map_file,
        "tmp_path": tmp_path,
    }


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestNoteOpenerInit:
    def test_initialises_paths(self, env):
        opener = NoteOpener()
        assert opener.note_dir == env["folders_path"]
        assert opener.current_file == env["current_file"]
        assert opener.results_file == env["results_file"]

    def test_missing_env_var_raises(self, monkeypatch):
        monkeypatch.delenv("NOTES_FOLDERS_PATH", raising=False)
        monkeypatch.delenv("NOTES_CURRENT_FILE", raising=False)
        monkeypatch.delenv("NOTES_RESULTS_FILE", raising=False)
        monkeypatch.delenv("NOTES_PATH", raising=False)
        with pytest.raises(ValueError, match="NOTES_FOLDERS_PATH"):
            NoteOpener()


# ---------------------------------------------------------------------------
# get_current_folder
# ---------------------------------------------------------------------------

class TestGetCurrentFolder:
    def test_reads_current_file(self, env):
        opener = NoteOpener()
        assert opener.get_current_folder() == "work"

    def test_skips_blank_lines(self, env):
        env["current_file"].write_text("\n\nwork\n")
        opener = NoteOpener()
        assert opener.get_current_folder() == "work"

    def test_missing_current_file_raises(self, env):
        env["current_file"].unlink()
        opener = NoteOpener()
        with pytest.raises(ValueError, match="not found"):
            opener.get_current_folder()

    def test_empty_current_file_raises(self, env):
        env["current_file"].write_text("   \n")
        opener = NoteOpener()
        with pytest.raises(ValueError, match="Could not read"):
            opener.get_current_folder()


# ---------------------------------------------------------------------------
# resolve_entry
# ---------------------------------------------------------------------------

class TestResolveEntry:
    def test_resolves_note_entry(self, env):
        opener = NoteOpener()
        assert opener.resolve_entry(1) == "note-one.md"

    def test_resolves_app_entry(self, env):
        opener = NoteOpener()
        assert opener.resolve_entry(2) == "app:my-app"

    def test_missing_entry_raises(self, env):
        opener = NoteOpener()
        with pytest.raises(ValueError, match="No entry #99"):
            opener.resolve_entry(99)

    def test_missing_results_file_raises(self, env):
        env["results_file"].unlink()
        opener = NoteOpener()
        with pytest.raises(ValueError, match="Results file not found"):
            opener.resolve_entry(1)

    def test_strips_ansi_codes(self, env):
        """Entry is resolved correctly even when ANSI colour codes are present"""
        env["results_file"].write_text(
            "1. \033[0;32mnote-one.md\033[0m 2026-01-01\n"
        )
        opener = NoteOpener()
        assert opener.resolve_entry(1) == "note-one.md"


# ---------------------------------------------------------------------------
# run_app
# ---------------------------------------------------------------------------

class TestRunApp:
    def test_execs_run_sh(self, env):
        opener = NoteOpener()
        with patch("os.execv") as mock_exec:
            opener.run_app("my-app", "work")
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert args[0] == "/bin/bash"
            assert str(args[1][-1]).endswith("my-app/run.sh")

    def test_missing_app_dir_raises(self, env):
        opener = NoteOpener()
        with pytest.raises(ValueError, match="App directory not found"):
            opener.run_app("nonexistent-app", "work")

    def test_missing_run_sh_raises(self, env):
        # Create app dir without run.sh
        (env["work"] / "apps" / "no-script").mkdir(parents=True)
        opener = NoteOpener()
        with pytest.raises(ValueError, match="run.sh not found"):
            opener.run_app("no-script", "work")


# ---------------------------------------------------------------------------
# stamp_last_visited
# ---------------------------------------------------------------------------

class TestStampLastVisited:
    def test_updates_timestamp(self, env):
        opener = NoteOpener()
        opener.stamp_last_visited("note-one.md", "work")

        data = json.loads(env["map_file"].read_text())
        ts = data["abc123"]["last_visited"]
        assert ts != "2020-01-01T00:00:00Z"
        assert "T" in ts  # ISO format

    def test_no_op_when_map_missing(self, env):
        env["map_file"].unlink()
        opener = NoteOpener()
        # Should not raise
        opener.stamp_last_visited("note-one.md", "work")

    def test_no_op_when_note_not_in_map(self, env):
        opener = NoteOpener()
        opener.stamp_last_visited("unknown.md", "work")
        # Map should be unchanged
        data = json.loads(env["map_file"].read_text())
        assert data["abc123"]["last_visited"] == "2020-01-01T00:00:00Z"

    def test_writes_atomically_via_tmp(self, env):
        """Ensure the map file is replaced, not partially written."""
        opener = NoteOpener()
        opener.stamp_last_visited("note-one.md", "work")
        # tmp file should be gone
        tmp = env["map_file"].with_suffix(".tmp")
        assert not tmp.exists()


# ---------------------------------------------------------------------------
# open() integration — note path
# ---------------------------------------------------------------------------

class TestOpenNote:
    def test_opens_note_in_nvim(self, env):
        opener = NoteOpener()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            with pytest.raises(SystemExit):
                opener.open(1)
            called_args = mock_run.call_args[0][0]
            assert called_args[0] == "nvim"
            assert "note-one.md" in called_args[1]

    def test_stamps_last_visited_after_nvim(self, env):
        opener = NoteOpener()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            with pytest.raises(SystemExit):
                opener.open(1)
        data = json.loads(env["map_file"].read_text())
        assert data["abc123"]["last_visited"] != "2020-01-01T00:00:00Z"

    def test_note_not_found_raises(self, env):
        env["results_file"].write_text("1. ghost.md 2026-01-01\n")
        opener = NoteOpener()
        with pytest.raises(ValueError, match="Note not found"):
            opener.open(1)


# ---------------------------------------------------------------------------
# open() integration — app path
# ---------------------------------------------------------------------------

class TestOpenApp:
    def test_runs_app_for_app_entry(self, env):
        opener = NoteOpener()
        with patch("os.execv") as mock_exec:
            opener.open(2)
            mock_exec.assert_called_once()
            assert "run.sh" in str(mock_exec.call_args[0][1][-1])

    def test_invalid_entry_number_raises(self, env):
        opener = NoteOpener()
        with pytest.raises(ValueError, match="No entry #50"):
            opener.open(50)
