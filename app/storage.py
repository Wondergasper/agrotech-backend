"""
Supabase client singleton used for Storage operations.
Auth & database operations still go through FastAPI / SQLModel (PostgreSQL).
"""
import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET: str = os.getenv("SUPABASE_BUCKET", "product-images")

# Lazily initialised — the app does NOT crash at import time if env vars are absent.
_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Return a cached Supabase client; raises clearly if credentials are missing."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in your .env file."
            )
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def get_public_url(path: str) -> str:
    """Return the public CDN URL for a file stored in Supabase Storage."""
    return get_supabase_client().storage.from_(SUPABASE_BUCKET).get_public_url(path)
