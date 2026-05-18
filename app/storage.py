"""
Supabase client singleton used for Storage operations.
Auth and database operations still go through FastAPI / SQLModel.
"""
import base64
import binascii
import json
import os
import re
from threading import Lock
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY_ENV_NAME: str = (
    "SUPABASE_SECRET_KEY" if os.getenv("SUPABASE_SECRET_KEY") else "SUPABASE_SERVICE_KEY"
)
SUPABASE_SERVICE_KEY: str = (
    os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
).strip()
SUPABASE_BUCKET: str = os.getenv("SUPABASE_BUCKET", "product-images").strip()
_VALID_BUCKET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# Lazily initialized so the app does not crash at import time if env vars are absent.
_client: Optional[Client] = None
_bucket_ready = False
_bucket_lock = Lock()


def _validate_bucket_name() -> None:
    if not SUPABASE_BUCKET:
        raise RuntimeError("SUPABASE_BUCKET must be set in your .env file.")
    if not _VALID_BUCKET_ID.fullmatch(SUPABASE_BUCKET):
        raise RuntimeError(
            "SUPABASE_BUCKET must contain only letters, numbers, '.', '_' or '-'. "
            f"Current value: {SUPABASE_BUCKET!r}"
        )


def _bucket_name(bucket) -> Optional[str]:
    return getattr(bucket, "name", None) or getattr(bucket, "id", None)


def _classify_supabase_key(key: str) -> str:
    if key.startswith("sb_secret_"):
        return "secret"
    if key.startswith("sb_publishable_"):
        return "publishable"
    if key.count(".") == 2:
        try:
            payload = key.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")))
        except (binascii.Error, ValueError, json.JSONDecodeError):
            return "jwt"
        return str(claims.get("role") or "jwt")
    return "unknown"


def _validate_backend_key() -> None:
    key_kind = _classify_supabase_key(SUPABASE_SERVICE_KEY)
    if key_kind in {"secret", "service_role"}:
        return

    if key_kind in {"publishable", "anon"}:
        raise RuntimeError(
            f"{SUPABASE_KEY_ENV_NAME} is a {key_kind} key, but product image uploads "
            "run through the backend and need a server-only Supabase secret key "
            "(`sb_secret_...`) or legacy service_role key. Do not use this key in "
            "the mobile app or browser."
        )

    raise RuntimeError(
        f"{SUPABASE_KEY_ENV_NAME} must be a Supabase secret key (`sb_secret_...`) "
        "or legacy service_role key for backend image uploads."
    )


def get_supabase_client() -> Client:
    """Return a cached Supabase client; raises clearly if credentials are missing."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SECRET_KEY must be set in your .env file. "
                "SUPABASE_SERVICE_KEY is still accepted as a legacy fallback."
            )
        _validate_backend_key()
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def ensure_storage_bucket(client: Optional[Client] = None) -> None:
    """Create the configured public storage bucket if it does not exist yet."""
    global _bucket_ready
    if _bucket_ready:
        return

    with _bucket_lock:
        if _bucket_ready:
            return

        _validate_bucket_name()
        client = client or get_supabase_client()
        bucket_names = {_bucket_name(bucket) for bucket in client.storage.list_buckets()}

        if SUPABASE_BUCKET not in bucket_names:
            try:
                client.storage.create_bucket(SUPABASE_BUCKET, options={"public": True})
            except Exception as exc:
                if "already exists" not in str(exc).lower():
                    if _is_bucket_create_permission_error(exc):
                        raise RuntimeError(
                            f"Storage bucket '{SUPABASE_BUCKET}' does not exist, and "
                            f"the configured {SUPABASE_KEY_ENV_NAME} is not allowed to "
                            "create buckets. Use a Supabase secret key (`sb_secret_...`) "
                            "or legacy service_role key on the backend, or create a public "
                            "bucket with this exact name in the Supabase dashboard."
                        ) from exc
                    raise

        _bucket_ready = True


def get_public_url(path: str) -> str:
    """Return the public CDN URL for a file stored in Supabase Storage."""
    ensure_storage_bucket()
    return get_supabase_client().storage.from_(SUPABASE_BUCKET).get_public_url(path)


def _is_bucket_create_permission_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "row-level security policy" in message
        or "unauthorized" in message
        or "403" in message
    )
