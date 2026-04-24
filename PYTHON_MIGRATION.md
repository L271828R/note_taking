# Python Migration Guide

## Overview

We've started migrating bash scripts to Python for better maintainability and error handling. The first script to be migrated is `nlist`.

## What's Been Done

### 1. Created Python Version
- **Location**: `python_scripts/nlist.py`
- **Features**: All features from bash version:
  - List markdown files with timestamps and titles
  - List subfolders with file counts
  - Delete notes
  - Rename notes (custom name or date style)
  - Move notes (with partial folder matching)
  - Plugin support

### 2. Virtual Environment Setup
- **Location**: `python_scripts/venv/`
- **Setup Script**: `python_scripts/setup_venv.sh`
- **Requirements**: `python_scripts/requirements.txt`
- No manual activation needed!

### 3. Wrapper Script
- **Location**: `bin_/nlist-py`
- Automatically uses venv Python
- No need to run `source venv/bin/activate`
- Just call `nlist-py` like any other command

## Usage

### First Time Setup
```bash
cd python_scripts
./setup_venv.sh
```

### Using the Script
```bash
# List notes (replace nlist with nlist-py)
nlist-py

# Delete a note
nlist-py -delete 3

# Rename a note
nlist-py -rename 2 meeting_notes

# Rename with date prefix
nlist-py -rename 1 -style date

# Move a note
nlist-py -move 5 research
nlist-py -move 2 ..         # Move to parent
nlist-py -move 1 res        # Partial match
```

## How the Wrapper Works

The `bin_/nlist-py` wrapper:
1. Locates the venv Python binary
2. Checks if venv exists (shows setup instructions if not)
3. Executes the Python script with all arguments
4. Uses `exec` so it replaces itself (clean process tree)

No activation required - it just works!

## Advantages of Python Version

1. **Better error handling** - Clear exception messages
2. **Type safety** - Type hints throughout
3. **Easier to maintain** - Object-oriented design
4. **More robust** - Proper path handling with `pathlib`
5. **Better testing** - Can easily add unit tests
6. **Cross-platform** - Works on Linux, macOS, Windows

## Migration Strategy

### Phase 1 (Current)
- ✅ Migrate `nlist` to Python
- ✅ Create venv setup
- ✅ Create wrapper pattern
- Test in parallel with bash version

### Phase 2 (Future)
- Migrate `ncurrent` to Python
- Migrate `nnote` to Python
- Add proper testing framework
- Consider using Click or Typer for better CLI

### Phase 3 (Later)
- Unified Python package
- Single venv for all scripts
- Entry points instead of wrappers
- PyPI package (optional)

## Both Versions Available

The bash version still exists as `nlist` and works exactly as before. The Python version is available as `nlist-py`. You can:

1. **Test the Python version** alongside the bash version
2. **Switch gradually** by creating an alias: `alias nlist=nlist-py`
3. **Keep both** if you prefer

## Adding New Python Scripts

1. Write script in `python_scripts/`
2. Add dependencies to `requirements.txt` (if needed)
3. Run `./setup_venv.sh` to install
4. Create wrapper in `bin_/` following the `nlist-py` pattern
5. Make executable with `chmod +x`

## Example Wrapper Template

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/python_scripts/venv/bin/python3"
SCRIPT="$PROJECT_DIR/python_scripts/your_script.py"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Run python_scripts/setup_venv.sh first" >&2
    exit 1
fi

exec "$VENV_PYTHON" "$SCRIPT" "$@"
```

## Files Added

```
.gitignore                           # Added venv/, __pycache__/, *.pyc
python_scripts/
├── README.md                        # Python scripts documentation
├── requirements.txt                 # Python dependencies
├── setup_venv.sh                    # Venv setup script
├── venv/                           # Virtual environment (gitignored)
└── nlist.py                        # Python version of nlist
bin_/
└── nlist-py                        # Wrapper script
PYTHON_MIGRATION.md                 # This file
```

## Testing

Before fully switching, test the Python version:

```bash
# Run both versions and compare output
nlist > /tmp/bash_output.txt
nlist-py > /tmp/python_output.txt
diff /tmp/bash_output.txt /tmp/python_output.txt
```

## Rollback

If issues arise, just use the original bash version:
```bash
nlist  # Original bash version still works
```

The Python version is completely separate and doesn't affect the bash scripts.
