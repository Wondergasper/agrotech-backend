from typing import Optional, List
from datetime import datetime, timezone
import json
from sqlmodel import SQLModel, Field


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    hashed_password: str
    phone: Optional[str] = None
    role: Optional[str] = None          # "vendor" | "consumer"
    avatar_url: Optional[str] = None    # Profile photo URL (Supabase Storage)

    # Vendor-specific
    farm_name: Optional[str] = None
    farm_location: Optional[str] = None
    farm_type: Optional[str] = None

    # Consumer-specific
    budget: Optional[int] = None
    health_tags_json: str = Field(default="[]")   # JSON string e.g. '["diabetes"]'
    preferences_json: str = Field(default="[]")   # JSON string e.g. '["Nearby farms"]'

    created_at: datetime = Field(default_factory=utc_now)

    # ─── Helpers ───────────────────────────────────────────────────────────────
    def get_health_tags(self) -> List[str]:
        try:
            return json.loads(self.health_tags_json)
        except Exception:
            return []

    def set_health_tags(self, tags: List[str]) -> None:
        self.health_tags_json = json.dumps(tags)

    def get_preferences(self) -> List[str]:
        try:
            return json.loads(self.preferences_json)
        except Exception:
            return []

    def set_preferences(self, prefs: List[str]) -> None:
        self.preferences_json = json.dumps(prefs)


class Product(SQLModel, table=True):
    __tablename__ = "product"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    price: float
    unit: str = Field(default="per kg")
    category: str = Field(default="general")
    tags_json: str = Field(default="[]")    # JSON string e.g. '["organic","fresh"]'
    freshness: int = Field(default=85)
    quantity: Optional[int] = None          # Stock quantity (units available)
    image_url: Optional[str] = None
    vendor_id: int = Field(foreign_key="user.id")

    # Denormalized vendor info (updated when product is created; avoids JOIN on every read)
    vendor_name: Optional[str] = None
    farm_name: Optional[str] = None

    # Ratings (denormalized from reviews table for fast reads)
    rating: float = Field(default=0.0)
    reviews_count: int = Field(default=0)

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)

    def get_tags(self) -> List[str]:
        try:
            return json.loads(self.tags_json)
        except Exception:
            return []

    def set_tags(self, tags: List[str]) -> None:
        self.tags_json = json.dumps(tags)


class Order(SQLModel, table=True):
    __tablename__ = "order"

    id: Optional[int] = Field(default=None, primary_key=True)
    consumer_id: int = Field(foreign_key="user.id")
    vendor_id: int = Field(foreign_key="user.id")
    product_id: int = Field(foreign_key="product.id")
    product_name: Optional[str] = None     # Snapshot at order time
    quantity: int = Field(default=1)
    total_price: float
    status: str = Field(default="pending")    # pending | confirmed | delivered | cancelled
    created_at: datetime = Field(default_factory=utc_now)


class Review(SQLModel, table=True):
    __tablename__ = "review"

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    consumer_id: int = Field(foreign_key="user.id")
    order_id: Optional[int] = Field(default=None, foreign_key="order.id")  # Ensures purchase-verified reviews
    rating: int = Field(ge=1, le=5)         # 1–5 stars
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class PasswordResetToken(SQLModel, table=True):
    """Stores one-time password reset codes (e.g. emailed OTP)."""
    __tablename__ = "password_reset_token"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    token: str = Field(index=True)          # 6-digit OTP or UUID
    expires_at: datetime
    used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)

