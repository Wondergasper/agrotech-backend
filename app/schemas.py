from typing import Optional, List
from pydantic import BaseModel, EmailStr
from datetime import datetime


# ─── Auth ────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "consumer"   # "vendor" | "consumer"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str           # OTP / reset code sent to the user's email
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ─── Users ───────────────────────────────────────────────────────────────────

class UserPublic(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    role: Optional[str]
    avatar_url: Optional[str]
    farm_name: Optional[str]
    farm_location: Optional[str]
    farm_type: Optional[str]
    budget: Optional[int]
    health_tags: List[str] = []
    preferences: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

class UpdatePreferencesRequest(BaseModel):
    budget: Optional[int] = None
    health_tags: Optional[List[str]] = None
    preferences: Optional[List[str]] = None

class UpdateFarmRequest(BaseModel):
    farm_name: Optional[str] = None
    farm_location: Optional[str] = None
    farm_type: Optional[str] = None

class UpdateRoleRequest(BaseModel):
    role: str   # "vendor" | "consumer"


# ─── Products ────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    unit: str = "per kg"
    category: str = "general"
    tags: List[str] = []
    freshness: int = 85
    image_url: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    freshness: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class ProductImageAnalysisRequest(BaseModel):
    image: str

class ProductPublic(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    unit: str
    category: str
    tags: List[str]
    freshness: int
    image_url: Optional[str]
    vendor_id: int
    vendor_name: Optional[str]
    farm_name: Optional[str]
    rating: float
    reviews_count: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Orders ──────────────────────────────────────────────────────────────────

class OrderItem(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    items: List[OrderItem]

class OrderPublic(BaseModel):
    id: int
    consumer_id: int
    vendor_id: int
    product_id: int
    product_name: Optional[str]
    vendor_name: Optional[str] = None
    farm_name: Optional[str] = None
    image_url: Optional[str] = None
    quantity: int
    total_price: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class UpdateOrderStatus(BaseModel):
    status: str   # "pending" | "confirmed" | "delivered" | "cancelled"


# ─── Reviews ────────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    product_id: int
    order_id: Optional[int] = None
    rating: int          # 1–5
    comment: Optional[str] = None

class ReviewPublic(BaseModel):
    id: int
    product_id: int
    consumer_id: int
    order_id: Optional[int]
    rating: int
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Vendor Analytics ────────────────────────────────────────────────────────

class DailyRevenue(BaseModel):
    day: str          # e.g. "Mon", "Tue"
    date: str         # e.g. "2026-03-17"
    revenue: float

class TopProduct(BaseModel):
    product_id: int
    product_name: str
    image_url: Optional[str]
    units_sold: int
    revenue: float

class VendorStats(BaseModel):
    total_earnings: float
    product_count: int
    orders_today: int
    pending_orders: int

class VendorAnalytics(BaseModel):
    period: str
    revenue: float
    orders: int
    avg_order: float
    daily_breakdown: List[DailyRevenue]
    top_products: List[TopProduct]
