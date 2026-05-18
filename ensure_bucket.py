from app.storage import SUPABASE_BUCKET, ensure_storage_bucket


def ensure_bucket():
    print(f"Checking bucket: {SUPABASE_BUCKET}")
    ensure_storage_bucket()
    print(f"Bucket '{SUPABASE_BUCKET}' is ready.")


if __name__ == "__main__":
    try:
        ensure_bucket()
    except Exception as exc:
        raise SystemExit(f"Bucket setup failed: {exc}") from exc
