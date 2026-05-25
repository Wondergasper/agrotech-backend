import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from app.main import app
from app.database import get_session
from app.models import Product, User
from app.deps import hash_password

# Setup in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite://"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

def override_get_session():
    with Session(test_engine) as session:
        yield session

app.dependency_overrides[get_session] = override_get_session
SQLModel.metadata.create_all(test_engine)

client = TestClient(app)

def test_list_products_shuffle():
    """Verify that shuffle=true returns products in random order."""
    # 1. Setup: Create some products
    with Session(test_engine) as session:
        # Create a vendor first
        vendor = User(
            name="Vendor One",
            email="v1@test.com",
            hashed_password=hash_password("pass"),
            active_role="vendor",
            farm_name="Farm One"
        )
        session.add(vendor)
        session.commit()
        session.refresh(vendor)

        # Add multiple products
        products = []
        for i in range(10):
            p = Product(
                name=f"Product {i}",
                price=10.0 + i,
                vendor_id=vendor.id,
                is_active=True,
                freshness=50 + i,
                vendor_name=vendor.name,
                farm_name=vendor.farm_name
            )
            session.add(p)
            products.append(p)
        session.commit()

    # 2. Login to get a token (needed if it's still requiring auth, 
    # but we made it optional in the previous task)
    signup_res = client.post("/auth/signup", json={
        "name": "Consumer",
        "email": "c1@test.com",
        "password": "pass",
        "role": "consumer"
    })
    token = signup_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Get products without shuffle
    res1 = client.get("/api/products/", headers=headers)
    assert res1.status_code == 200
    p_ids1 = [p["id"] for p in res1.json()]

    # 4. Get products with shuffle=true multiple times and check if order differs
    order_changed = False
    for _ in range(5):
        res2 = client.get("/api/products/?shuffle=true", headers=headers)
        assert res2.status_code == 200
        p_ids2 = [p["id"] for p in res2.json()]
        if p_ids2 != p_ids1:
            order_changed = True
            break
    
    # In a list of 10 items, the chance of getting the same order is 1/10! (very small)
    assert order_changed, "Shuffle did not change the order of products"
