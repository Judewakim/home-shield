"""
Pytest configuration for domain tests.

This file adds the parent directory to the Python path so that tests
can import from the domain, repositories, and src modules.
"""

import sys
from pathlib import Path

# Add the lead-sales-platform directory to the Python path
# so tests can import domain, repositories, etc.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
