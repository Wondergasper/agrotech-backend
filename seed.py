"""
seed.py — Populates the SQLite db with sample vendor + products for testing.
Run from: agrotech-backend/ directory
Usage: python seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import Session
from app.database import engine, create_db_and_tables
from app.models import User, Product
from app.deps import hash_password
import json

def seed():
    create_db_and_tables()

    with Session(engine) as session:
        # ── Vendor ───────────────────────────────────────────────────────────
        vendor = User(
            name="Musa Aliyu",
            email="musa@farm.ng",
            hashed_password=hash_password("password123"),
            role="vendor",
            farm_name="Green Acres Farm",
            farm_location="Kano State, Nigeria",
            farm_type="Crops & Veggies",
        )
        session.add(vendor)
        session.commit()
        session.refresh(vendor)
        print(f"✅ Vendor created: {vendor.name} (id={vendor.id})")

        # ── Consumer ─────────────────────────────────────────────────────────
        consumer = User(
            name="Ada Okafor",
            email="ada@buyer.ng",
            hashed_password=hash_password("password123"),
            role="consumer",
            budget=5000,
            health_tags_json=json.dumps(["vegan", "low_sugar"]),
            preferences_json=json.dumps(["Organic only", "Fast delivery"]),
        )
        session.add(consumer)
        session.commit()
        session.refresh(consumer)
        print(f"✅ Consumer created: {consumer.name} (id={consumer.id})")

        # ── Products ─────────────────────────────────────────────────────────
        products = [
            Product(name="Fresh Tomatoes", description="Ripe, sun-kissed tomatoes straight from the farm.", price=800, unit="per basket", category="vegetables", tags_json=json.dumps(["organic", "fresh"]), freshness=95, image_url="https://images.unsplash.com/photo-1546094096-0df4bcaad337?w=400", vendor_id=vendor.id),
            Product(name="Organic Spinach", description="Tender baby spinach, hand-picked this morning.", price=350, unit="per bunch", category="vegetables", tags_json=json.dumps(["organic", "leafy"]), freshness=90, image_url="https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=400", vendor_id=vendor.id),
            Product(name="Red Onions", description="Freshly harvested bulb onions. Perfect for stew and soups.", price=500, unit="per kg", category="vegetables", tags_json=json.dumps(["fresh"]), freshness=88, image_url="https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=400", vendor_id=vendor.id),
            Product(name="Sweet Corn", description="Sugar-sweet cobs straight from the field.", price=200, unit="per cob", category="grains", tags_json=json.dumps(["fresh", "seasonal"]), freshness=92, image_url="https://images.unsplash.com/photo-1551754655-cd27e38d2076?w=400", vendor_id=vendor.id),
            Product(name="Garden Eggs", description="Locally grown garden eggs (eggplant). Great for native soups.", price=400, unit="per dozen", category="vegetables", tags_json=json.dumps(["organic"]), freshness=85, image_url="https://images.unsplash.com/photo-1605027990121-cbae9e0642df?w=400", vendor_id=vendor.id),
            Product(name="Ugu (Fluted Pumpkin)", description="Freshly cut ugu leaves. Rich in iron and vitamins.", price=300, unit="per bunch", category="vegetables", tags_json=json.dumps(["organic", "leafy", "healthy"]), freshness=80, image_url="https://images.unsplash.com/photo-1622206151226-18ca2c9ab4a1?w=400", vendor_id=vendor.id),
        ]
        for p in products:
            session.add(p)
        session.commit()
        print(f"✅ {len(products)} products seeded for vendor '{vendor.name}'")
        print("\n🚀 DB ready. Run: uvicorn app.main:app --reload")

if __name__ == "__main__":
    seed()
