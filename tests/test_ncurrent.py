"""
Tests for ncurrent.py
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'python_scripts'))

from ncurrent import FolderManager


# ── shared fixture ────────────────────────────────────────────────────────────

@pytest.fixture
def env(tmp_path, monkeypatch):
    """Minimal notes directory wired to FolderManager."""
    folders = tmp_path / 'folders'
    folders.mkdir()

    current_file = tmp_path / 'current'
    current_file.write_text('\n')           # empty = root

    monkeypatch.setenv('NOTES_FOLDERS_PATH', str(folders))
    monkeypatch.setenv('NOTES_PATH', str(tmp_path))

    # tips off — keeps stdout clean
    config_dir = tmp_path / '.config'
    config_dir.mkdir()
    (config_dir / 'settings.ini').write_text('[tips]\nenabled = false\n')

    return {'folders': folders, 'current_file': current_file, 'tmp': tmp_path}


def _make_folder(env, name, md_count=0):
    """Create a subfolder under folders root, optionally with .md files."""
    d = env['folders'] / name
    d.mkdir(parents=True, exist_ok=True)
    for i in range(md_count):
        (d / f'note-{i}.md').write_text(f'# Title: Note {i}\n')
    return d


# ── FolderManager.read/write current ─────────────────────────────────────────

class TestCurrentFile:
    def test_read_empty_is_root(self, env):
        mgr = FolderManager()
        assert mgr._read_current() == ''

    def test_write_and_read_back(self, env):
        mgr = FolderManager()
        mgr._write_current('work/projects')
        assert mgr._read_current() == 'work/projects'

    def test_write_empty_returns_root(self, env):
        mgr = FolderManager()
        mgr._write_current('something')
        mgr._write_current('')
        assert mgr._read_current() == ''


# ── FolderManager._target ─────────────────────────────────────────────────────

class TestTarget:
    def test_root_target_is_folders_path(self, env):
        mgr = FolderManager()
        assert mgr._target() == env['folders']

    def test_subfolder_target(self, env):
        _make_folder(env, 'work')
        mgr = FolderManager()
        mgr._write_current('work')
        assert mgr._target() == env['folders'] / 'work'


# ── FolderManager._subfolders ─────────────────────────────────────────────────

class TestSubfolders:
    def test_sorted_alphabetically(self, env):
        for name in ('zebra', 'alpha', 'middle'):
            _make_folder(env, name)
        mgr = FolderManager()
        names = [f.name for f in mgr._subfolders(env['folders'])]
        assert names == sorted(names)

    def test_empty_when_no_dirs(self, env):
        mgr = FolderManager()
        assert mgr._subfolders(env['folders']) == []

    def test_excludes_files(self, env):
        (env['folders'] / 'a-file.md').write_text('content')
        mgr = FolderManager()
        assert mgr._subfolders(env['folders']) == []


# ── FolderManager._md_count ───────────────────────────────────────────────────

class TestMdCount:
    def test_counts_recursively(self, env):
        d = _make_folder(env, 'work', md_count=3)
        sub = d / 'sub'
        sub.mkdir()
        (sub / 'nested.md').write_text('nested')
        mgr = FolderManager()
        assert mgr._md_count(d) == 4

    def test_zero_when_empty(self, env):
        d = _make_folder(env, 'empty')
        mgr = FolderManager()
        assert mgr._md_count(d) == 0


# ── FolderManager._newest_mtime ───────────────────────────────────────────────

class TestNewestMtime:
    def test_returns_empty_string_for_empty_folder(self, env):
        d = _make_folder(env, 'empty')
        mgr = FolderManager()
        assert mgr._newest_mtime(d) == ''

    def test_returns_formatted_string(self, env):
        d = _make_folder(env, 'work', md_count=1)
        mgr = FolderManager()
        result = mgr._newest_mtime(d)
        # format: YYYY-MM-DD HH:MM
        assert len(result) == 16
        assert result[4] == '-' and result[7] == '-'


# ── FolderManager._has_apps ───────────────────────────────────────────────────

class TestHasApps:
    def test_true_when_run_sh_present(self, env):
        d = _make_folder(env, 'work')
        app = d / 'apps' / 'my-app'
        app.mkdir(parents=True)
        (app / 'run.sh').write_text('#!/usr/bin/env bash')
        mgr = FolderManager()
        assert mgr._has_apps(d) is True

    def test_false_when_no_apps_dir(self, env):
        d = _make_folder(env, 'work')
        mgr = FolderManager()
        assert mgr._has_apps(d) is False

    def test_false_when_apps_dir_has_no_run_sh(self, env):
        d = _make_folder(env, 'work')
        (d / 'apps' / 'not-an-app').mkdir(parents=True)
        mgr = FolderManager()
        assert mgr._has_apps(d) is False


# ── cmd_root ──────────────────────────────────────────────────────────────────

class TestCmdRoot:
    def test_resets_current_to_root(self, env, capsys):
        mgr = FolderManager()
        mgr._write_current('work')
        mgr.cmd_root()
        assert mgr._read_current() == ''

    def test_prints_confirmation(self, env, capsys):
        mgr = FolderManager()
        mgr.cmd_root()
        assert 'root' in capsys.readouterr().out


# ── cmd_pwd ───────────────────────────────────────────────────────────────────

class TestCmdPwd:
    def test_prints_root(self, env, capsys):
        mgr = FolderManager()
        mgr.cmd_pwd()
        assert '[root]' in capsys.readouterr().out

    def test_prints_current_folder(self, env, capsys):
        _make_folder(env, 'work')
        mgr = FolderManager()
        mgr._write_current('work')
        mgr.cmd_pwd()
        assert 'work' in capsys.readouterr().out


# ── cmd_cd ────────────────────────────────────────────────────────────────────

class TestCmdCd:
    def test_enters_existing_subfolder(self, env):
        _make_folder(env, 'work')
        mgr = FolderManager()
        mgr.cmd_cd('work')
        assert mgr._read_current() == 'work'

    def test_fails_on_missing_subfolder(self, env):
        mgr = FolderManager()
        with pytest.raises(SystemExit):
            mgr.cmd_cd('nonexistent')

    def test_nested_cd(self, env):
        _make_folder(env, 'work/projects')
        mgr = FolderManager()
        mgr._write_current('work')
        mgr.cmd_cd('projects')
        assert mgr._read_current() == 'work/projects'


# ── cmd_up ────────────────────────────────────────────────────────────────────

class TestCmdUp:
    def test_moves_up_one_level(self, env):
        _make_folder(env, 'work/projects')
        mgr = FolderManager()
        mgr._write_current('work/projects')
        mgr.cmd_up()
        assert mgr._read_current() == 'work'

    def test_moves_to_root_from_top_level(self, env):
        _make_folder(env, 'work')
        mgr = FolderManager()
        mgr._write_current('work')
        mgr.cmd_up()
        assert mgr._read_current() == ''

    def test_fails_when_already_at_root(self, env):
        mgr = FolderManager()
        with pytest.raises(SystemExit):
            mgr.cmd_up()


# ── cmd_new ───────────────────────────────────────────────────────────────────

class TestCmdNew:
    def test_creates_subfolder(self, env):
        mgr = FolderManager()
        mgr.cmd_new('projects')
        assert (env['folders'] / 'projects').is_dir()

    def test_creates_nested_subfolder(self, env):
        _make_folder(env, 'work')
        mgr = FolderManager()
        mgr._write_current('work')
        mgr.cmd_new('projects')
        assert (env['folders'] / 'work' / 'projects').is_dir()


# ── cmd_select ────────────────────────────────────────────────────────────────

class TestCmdSelect:
    def test_selects_folder_by_index(self, env):
        _make_folder(env, 'alpha')
        _make_folder(env, 'beta')
        mgr = FolderManager()
        mgr.cmd_select(2)           # sorted: alpha=1, beta=2
        assert mgr._read_current() == 'beta'

    def test_invalid_index_exits(self, env):
        mgr = FolderManager()
        with pytest.raises(SystemExit):
            mgr.cmd_select(99)


# ── cmd_rename_folder ─────────────────────────────────────────────────────────

class TestCmdRenameFolder:
    def test_renames_folder(self, env):
        _make_folder(env, 'old-name')
        mgr = FolderManager()
        mgr.cmd_rename_folder(1, 'new-name')
        assert not (env['folders'] / 'old-name').exists()
        assert (env['folders'] / 'new-name').is_dir()

    def test_invalid_index_exits(self, env):
        mgr = FolderManager()
        with pytest.raises(SystemExit):
            mgr.cmd_rename_folder(5, 'anything')


# ── cmd_move_folder ───────────────────────────────────────────────────────────

class TestCmdMoveFolder:
    def test_moves_folder_into_another(self, env):
        _make_folder(env, 'alpha')
        _make_folder(env, 'beta')
        mgr = FolderManager()
        # sorted: alpha=1, beta=2 → move alpha into beta
        mgr.cmd_move_folder(1, '2')
        assert not (env['folders'] / 'alpha').exists()
        assert (env['folders'] / 'beta' / 'alpha').is_dir()

    def test_moves_folder_up(self, env):
        parent = _make_folder(env, 'parent')
        child = parent / 'child'
        child.mkdir()
        mgr = FolderManager()
        mgr._write_current('parent')
        mgr.cmd_move_folder(1, 'up')   # child is index 1 inside parent
        assert not child.exists()
        assert (env['folders'] / 'child').is_dir()

    def test_invalid_index_exits(self, env):
        mgr = FolderManager()
        with pytest.raises(SystemExit):
            mgr.cmd_move_folder(99, '1')

    def test_invalid_destination_exits(self, env):
        _make_folder(env, 'alpha')
        mgr = FolderManager()
        with pytest.raises(SystemExit):
            mgr.cmd_move_folder(1, 'bad-dest')


# ── map sync ──────────────────────────────────────────────────────────────────

class TestMapSync:
    def _note_with_id(self, path, note_id, title):
        path.write_text(f'<!-- id: {note_id} -->\n# Title: {title}\n')

    def test_update_map_adds_entries(self, env):
        d = _make_folder(env, 'work')
        self._note_with_id(d / 'a.md', 'abc123', 'Note A')
        mgr = FolderManager()
        mgr._update_map_for_dir(d, 'folders/work')
        data = json.loads(env['tmp'] / '.note_map.json').read_text() \
            if False else json.loads((env['tmp'] / '.note_map.json').read_text())
        assert 'abc123' in data
        assert data['abc123']['title'] == 'Note A'

    def test_update_map_removes_old_entries(self, env):
        d = _make_folder(env, 'work')
        self._note_with_id(d / 'a.md', 'abc123', 'Note A')
        mgr = FolderManager()
        # seed an existing entry with the old rel path
        (env['tmp'] / '.note_map.json').write_text(
            json.dumps({'old999': {'path': 'folders/work/old.md', 'title': 'Old'}})
        )
        mgr._update_map_for_dir(d, 'folders/work')
        data = json.loads((env['tmp'] / '.note_map.json').read_text())
        assert 'old999' not in data

    def test_skips_notes_without_id(self, env):
        d = _make_folder(env, 'work')
        (d / 'no-id.md').write_text('# Title: No ID\n')
        mgr = FolderManager()
        mgr._update_map_for_dir(d, 'folders/work')
        data = json.loads((env['tmp'] / '.note_map.json').read_text())
        assert data == {}


# ── _print_listing output ─────────────────────────────────────────────────────

class TestPrintListing:
    def test_header_shows_current(self, env, capsys):
        _make_folder(env, 'work')
        mgr = FolderManager()
        mgr._write_current('work')
        mgr._print_listing()
        out = capsys.readouterr().out
        assert 'current > work' in out

    def test_separator_is_80_chars(self, env, capsys):
        mgr = FolderManager()
        mgr._print_listing()
        out = capsys.readouterr().out
        assert '-' * 80 in out

    def test_folders_listed_with_numbers(self, env, capsys):
        _make_folder(env, 'alpha', md_count=2)
        _make_folder(env, 'beta',  md_count=0)
        mgr = FolderManager()
        mgr._print_listing()
        out = capsys.readouterr().out
        assert '1.' in out
        assert '2.' in out
        assert 'alpha' in out
        assert 'beta' in out

    def test_file_count_shown(self, env, capsys):
        _make_folder(env, 'work', md_count=3)
        mgr = FolderManager()
        mgr._print_listing()
        out = capsys.readouterr().out
        assert '3 files' in out

    def test_singular_file_noun(self, env, capsys):
        _make_folder(env, 'solo', md_count=1)
        mgr = FolderManager()
        mgr._print_listing()
        out = capsys.readouterr().out
        assert '1 file' in out
        assert '1 files' not in out

    def test_rocket_icon_when_has_apps(self, env, capsys):
        d = _make_folder(env, 'work')
        app = d / 'apps' / 'my-app'
        app.mkdir(parents=True)
        (app / 'run.sh').write_text('#!/usr/bin/env bash')
        mgr = FolderManager()
        mgr._print_listing()
        out = capsys.readouterr().out
        assert '🚀' in out

    def test_no_rocket_when_no_apps(self, env, capsys):
        _make_folder(env, 'plain')
        mgr = FolderManager()
        mgr._print_listing()
        out = capsys.readouterr().out
        assert '🚀' not in out
