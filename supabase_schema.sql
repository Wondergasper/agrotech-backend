-- ============================================================
-- AgriShop API — Full Database Schema
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. USER TABLE
CREATE TABLE IF NOT EXISTS "user" (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    email               TEXT NOT NULL UNIQUE,
    hashed_password     TEXT NOT NULL,
    phone               TEXT,
    role                TEXT,                        -- 'vendor' | 'consumer'
    avatar_url          TEXT,

    -- Vendor-specific
    farm_name           TEXT,
    farm_location       TEXT,
    farm_type           TEXT,

    -- Consumer-specific
    budget              INTEGER,
    health_tags_json    TEXT NOT NULL DEFAULT '[]',
    preferences_json    TEXT NOT NULL DEFAULT '[]',

    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_user_email ON "user" (email);


-- 2. PRODUCT TABLE
CREATE TABLE IF NOT EXISTS product (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    price           FLOAT NOT NULL,
    unit            TEXT NOT NULL DEFAULT 'per kg',
    category        TEXT NOT NULL DEFAULT 'general',
    tags_json       TEXT NOT NULL DEFAULT '[]',
    freshness       INTEGER NOT NULL DEFAULT 85,
    image_url       TEXT,
    vendor_id       INTEGER NOT NULL REFERENCES "user" (id),

    -- Denormalized vendor snapshot
    vendor_name     TEXT,
    farm_name       TEXT,

    -- Denormalized rating snapshot
    rating          FLOAT NOT NULL DEFAULT 0.0,
    reviews_count   INTEGER NOT NULL DEFAULT 0,

    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);


-- 3. ORDER TABLE
CREATE TABLE IF NOT EXISTS "order" (
    id              SERIAL PRIMARY KEY,
    consumer_id     INTEGER NOT NULL REFERENCES "user" (id),
    vendor_id       INTEGER NOT NULL REFERENCES "user" (id),
    product_id      INTEGER NOT NULL REFERENCES product (id),
    product_name    TEXT,                            -- snapshot at order time
    quantity        INTEGER NOT NULL DEFAULT 1,
    total_price     FLOAT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending', -- pending | confirmed | delivered | cancelled
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);


-- 4. REVIEW TABLE
CREATE TABLE IF NOT EXISTS review (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES product (id),
    consumer_id     INTEGER NOT NULL REFERENCES "user" (id),
    order_id        INTEGER REFERENCES "order" (id), -- NULL = not purchase-verified
    rating          INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment         TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);


-- 5. PASSWORD RESET TOKEN TABLE
CREATE TABLE IF NOT EXISTS password_reset_token (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL,
    token           TEXT NOT NULL,
    expires_at      TIMESTAMP NOT NULL,
    used            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_password_reset_token_email ON password_reset_token (email);
CREATE INDEX IF NOT EXISTS ix_password_reset_token_token ON password_reset_token (token);


-- Done! ✅ All 5 tables created.
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
