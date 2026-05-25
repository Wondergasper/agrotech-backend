"""
Backend test suite — uses an in-memory SQLite database so tests
run locally without needing any Supabase / network connection.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# ── Build a fresh in-memory SQLite engine for tests ─────────────────────────
TEST_DATABASE_URL = "sqlite://"          # in-memory, no file needed

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,                # single connection shared across threads
)

# ── Import app AFTER engine is ready so we can override the dependency ───────
from app.main import app
from app.database import get_session

def override_get_session():
    """Replace Supabase Postgres with in-memory SQLite during tests."""
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session

app.dependency_overrides[get_session] = override_get_session

# Create all tables once
SQLModel.metadata.create_all(test_engine)

client = TestClient(app)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_healthcheck():
    """GET / must return 200 and the expected JSON."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "AgriShop API is running" in data["message"]
    assert data["version"] == "2.1.0"
    assert data["docs"] == "/docs"


def test_signup_new_user():
    """POST /api/auth/signup creates a user and returns a token."""
    res = client.post("/auth/signup", json={
        "name": "Alice Farmer",
        "email": "alice@farm.com",
        "password": "securepass123",
        "role": "vendor"
    })
    assert res.status_code == 201
    body = res.json()
    assert "access_token" in body


def test_signup_duplicate_email():
    """Signing up with the same email twice returns 400."""
    payload = {
        "name": "Bob Buyer",
        "email": "bob@buy.com",
        "password": "pass1234",
        "role": "consumer"
    }
    client.post("/auth/signup", json=payload)          # first — should succeed
    res = client.post("/auth/signup", json=payload)    # second — must fail
    assert res.status_code == 400
    assert "Email already registered" in res.json()["detail"]


def test_login_valid_credentials():
    """POST /api/auth/login with valid credentials returns a token."""
    # First create the user
    client.post("/auth/signup", json={
        "name": "Carol Consumer",
        "email": "carol@consumer.com",
        "password": "mypassword",
        "role": "consumer"
    })
    res = client.post("/auth/login", json={
        "email": "carol@consumer.com",
        "password": "mypassword"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password():
    """POST /api/auth/login with wrong password returns 401."""
    client.post("/auth/signup", json={
        "name": "Dave Dev",
        "email": "dave@dev.com",
        "password": "realpass",
        "role": "consumer"
    })
    res = client.post("/auth/login", json={
        "email": "dave@dev.com",
        "password": "wrongpass"
    })
    assert res.status_code == 401


def test_login_nonexistent_user():
    """POST /api/auth/login for unknown email returns 401."""
    res = client.post("/auth/login", json={
        "email": "ghost@nobody.com",
        "password": "whatever"
    })
    assert res.status_code == 401


def test_forgot_password_unknown_email():
    """Forgot-password returns the deprecation message."""
    res = client.post("/auth/forgot-password", json={"email": "unknown@x.com"})
    assert res.status_code == 200
    assert "use the reset-password endpoint" in res.json()["message"]


def test_reset_password_direct():
    """Test the insecure dev-only reset-password flow."""
    email = "reset@test.com"
    client.post("/auth/signup", json={
        "name": "Reset User",
        "email": email,
        "password": "oldpassword",
        "role": "consumer"
    })

    # Reset directly (no OTP needed in this dev version)
    reset_res = client.post("/auth/reset-password", json={
        "email": email,
        "new_password": "newpassword123"
    })
    assert reset_res.status_code == 200

    # Login with new password
    login_res = client.post("/auth/login", json={
        "email": email,
        "password": "newpassword123"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()


def test_switch_role():
    """PATCH /auth/switch-role changes the active role."""
    # Create a user with both roles (manually or via onboarding)
    email = "switcher@test.com"
    signup_res = client.post("/auth/signup", json={
        "name": "Switcher",
        "email": email,
        "password": "password",
        "role": "consumer"
    })
    token = signup_res.json()["access_token"]
    
    # First, become a vendor to have both roles
    client.post("/auth/become-vendor", 
        json={"farm_name": "Test Farm", "farm_location": "Local", "farm_type": "Crop"},
        headers={"Authorization": f"Bearer {token}"}
    )

    # Switch back to consumer
    res = client.patch("/auth/switch-role", 
        json={"role": "consumer"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json()["activeRole"] == "consumer"

    # Switch to vendor
    res = client.patch("/auth/switch-role", 
        json={"role": "vendor"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json()["activeRole"] == "vendor"
