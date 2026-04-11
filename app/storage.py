"""
Supabase client singleton used for Storage operations.
Auth & database operations still go through FastAPI / SQLModel (PostgreSQL).
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "product-images")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in your .env file."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_public_url(path: str) -> str:
    """Return the public CDN URL for a file stored in Supabase Storage."""
    res = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(path)
    return res
