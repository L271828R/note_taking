"""
Pytest configuration and shared fixtures
"""

import pytest
import sys
from pathlib import Path

# Add python_scripts to path for imports
project_root = Path(__file__).parent.parent
python_scripts = project_root / 'python_scripts'
sys.path.insert(0, str(python_scripts))
