# Python Scripts for Notes Management

This directory contains Python versions of note management scripts.

## Setup

Run the setup script to create the virtual environment:

```bash
./setup_venv.sh
```

This creates a `venv/` directory with Python 3 and all required dependencies.

## Scripts

### nlist.py

Python version of the `nlist` command with all the same features:
- List markdown files with timestamps and titles
- List subfolders with file counts
- Delete notes (`-delete <num>`)
- Rename notes (`-rename <num> <name>` or `-rename <num> -style date`)
- Move notes (`-move <num> <folder>`)

## Usage

You don't need to activate the venv manually. Use the wrapper script:

```bash
# From anywhere (if bin_ is in your PATH)
nlist-py

# Or directly
bin_/nlist-py
```

The wrapper (`bin_/nlist-py`) automatically uses the venv Python binary.

## Adding New Python Scripts

1. Create your script in this directory
2. Add any dependencies to `requirements.txt`
3. Run `./setup_venv.sh` to install new dependencies
4. Create a wrapper in `bin_/` similar to `nlist-py`

## Directory Structure

```
python_scripts/
├── README.md           # This file
├── requirements.txt    # Python dependencies
├── setup_venv.sh      # Setup script
├── venv/              # Virtual environment (created by setup)
└── nlist.py           # Python version of nlist
```

## Why Python?

- Better error handling
- Easier to maintain and extend
- More robust file operations
- Type hints and better IDE support
- No need to deal with bash array quirks
