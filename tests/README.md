# Tests for Notes Management System

This directory contains pytest tests for the Python scripts.

## Running Tests

### Quick Start

```bash
# From the project root
./run_tests.sh
```

### With Coverage Report

```bash
./run_tests.sh --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`.

### Run Specific Tests

```bash
# Run a specific test file
./run_tests.sh tests/test_nlist.py

# Run a specific test class
./run_tests.sh tests/test_nlist.py::TestNoteManager

# Run a specific test method
./run_tests.sh tests/test_nlist.py::TestNoteManager::test_delete_note

# Run tests matching a pattern
./run_tests.sh -k "delete"
```

### Verbose Output

```bash
./run_tests.sh -v
```

### See Print Statements

```bash
./run_tests.sh -s
```

## Test Structure

### test_nlist.py

Tests for the `nlist.py` script covering:

**TestNoteManager class:**
- ✅ Initialization and configuration
- ✅ Getting markdown files (sorted by modification time)
- ✅ Getting subfolders
- ✅ Counting markdown files in folders
- ✅ Extracting titles from markdown
- ✅ Deleting notes (moving to /tmp/notes/delete)
- ✅ Renaming notes (custom name)
- ✅ Renaming notes (date style)
- ✅ Moving notes to subfolders
- ✅ Moving notes with partial folder match
- ✅ Moving notes to parent directory (..)
- ✅ Generating formatted listings
- ✅ Writing to results file

**TestNlistCLI class:**
- ✅ CLI help output
- ✅ CLI list command

**Module tests:**
- ✅ Import verification

## Current Coverage

```
Name                      Stmts   Miss  Cover   Missing
-------------------------------------------------------
python_scripts/nlist.py     200     52    74%
```

Most uncovered lines are error handling paths and the CLI main() function.

## Adding New Tests

1. Create a new test file in `tests/` with prefix `test_`
2. Import the module you want to test
3. Write test functions with prefix `test_`
4. Use pytest fixtures for setup/teardown
5. Run `./run_tests.sh` to verify

Example:

```python
import pytest

def test_something():
    # Arrange
    value = 42

    # Act
    result = value * 2

    # Assert
    assert result == 84
```

## Pytest Features Used

- **Fixtures** - Setup/teardown for tests (e.g., `temp_notes_dir`)
- **Monkeypatch** - Mock environment variables
- **tmp_path** - Temporary directories for test isolation
- **Parametrize** - Run same test with different inputs (not yet used, but available)
- **Markers** - Tag tests (e.g., slow, integration)

## Dependencies

Tests use the same venv as the Python scripts:
- pytest
- pytest-cov

Install with:
```bash
python_scripts/venv/bin/pip install pytest pytest-cov
```

Or just run `./run_tests.sh` which auto-installs if needed.

## CI/CD

These tests can be integrated into CI/CD pipelines:

```bash
# Exit with error code if tests fail
./run_tests.sh
```

## Future Improvements

- [ ] Add tests for `ncurrent` when migrated to Python
- [ ] Add tests for `nnote` when migrated to Python
- [ ] Integration tests for the full workflow
- [ ] Performance tests for large note collections
- [ ] Mock file system operations for faster tests
- [ ] Parametrized tests for edge cases
