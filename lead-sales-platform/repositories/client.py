"""
Supabase client initialization.

This module contains *only* the database connection setup and exposes a single
`supabase` client object for other repository modules to import and use.

Environment variables required:
- SUPABASE_URL: Your Supabase project URL
- SUPABASE_KEY: Your Supabase API key (use a server-side key only on the backend)
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# The dependency is `supabase` (supabase-py). If your editor can't resolve it,
# install it in your environment: `pip install supabase`.
from supabase import Client, create_client  # type: ignore[import-not-found]

# Load environment variables from .env file
# Look for .env in the lead-sales-platform directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Read credentials from the environment to avoid hard-coding secrets in code.
SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
SUPABASE_KEY: str | None = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise RuntimeError(
        "Missing environment variable: SUPABASE_URL. "
        "Set SUPABASE_URL to your Supabase project URL."
    )

if not SUPABASE_KEY:
    raise RuntimeError(
        "Missing environment variable: SUPABASE_KEY. "
        "Set SUPABASE_KEY to your Supabase API key."
    )

# Official Supabase Python client instance to be imported by other modules.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

__all__ = ["supabase"]
