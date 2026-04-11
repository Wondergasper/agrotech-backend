"""
Vendor-specific analytics endpoints.

GET /api/vendor/stats   — Quick KPIs for the VendorHomeScreen dashboard
GET /api/vendor/analytics — Period-based analytics for the Analytics/Payments screen
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func
from collections import defaultdict

from app.database import get_session
from app.models import Order, Product, User
from app.schemas import (
    VendorStats, VendorAnalytics, DailyRevenue, TopProduct,
)
from app.deps import require_vendor

router = APIRouter(prefix="/api/vendor", tags=["Vendor"])

VALID_PERIODS = {"today", "week", "month", "all"}


def _period_start(period: str) -> Optional[datetime]:
    now = datetime.utcnow()
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        return now - timedelta(days=7)
    elif period == "month":
        return now - timedelta(days=30)
    return None   # "all"


# ─── Quick Stats (for VendorHomeScreen) ──────────────────────────────────────

@router.get("/stats", response_model=VendorStats)
def vendor_stats(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_vendor),
):
    """
    Returns lightweight KPI summary:
    - total_earnings   : sum of all delivered order amounts
    - product_count    : active product listings
    - orders_today     : orders placed since midnight UTC
    - pending_orders   : orders awaiting confirmation
    """
    vendor_id = current_user.id
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    all_orders = session.exec(
        select(Order).where(Order.vendor_id == vendor_id)
    ).all()

    total_earnings = sum(
        o.total_price for o in all_orders if o.status == "delivered"
    )
    orders_today = sum(1 for o in all_orders if o.created_at >= today_start)
    pending_orders = sum(1 for o in all_orders if o.status == "pending")

    product_count = session.exec(
        select(func.count(Product.id)).where(
            Product.vendor_id == vendor_id,
            Product.is_active == True,
        )
    ).one()

    return VendorStats(
        total_earnings=round(total_earnings, 2),
        product_count=product_count or 0,
        orders_today=orders_today,
        pending_orders=pending_orders,
    )


# ─── Period Analytics (for Analytics/Payments screen) ────────────────────────

@router.get("/analytics", response_model=VendorAnalytics)
def vendor_analytics(
    period: str = Query("week", description="today | week | month | all"),
    session: Session = Depends(get_session),
    current_user: User = Depends(require_vendor),
):
    """
    Returns aggregated KPIs, a 7-day daily revenue breakdown,
    and the top 5 products by revenue for the selected period.
    """
    if period not in VALID_PERIODS:
        period = "week"

    vendor_id = current_user.id
    start_dt = _period_start(period)

    stmt = select(Order).where(Order.vendor_id == vendor_id)
    if start_dt:
        stmt = stmt.where(Order.created_at >= start_dt)

    orders = session.exec(stmt).all()

    revenue = sum(o.total_price for o in orders if o.status != "cancelled")
    order_count = len([o for o in orders if o.status != "cancelled"])
    avg_order = round(revenue / order_count, 2) if order_count else 0.0

    # ── Daily breakdown (last 7 days always, independent of period) ──────────
    daily_start = datetime.utcnow() - timedelta(days=6)
    daily_start = daily_start.replace(hour=0, minute=0, second=0, microsecond=0)

    daily_orders = session.exec(
        select(Order).where(
            Order.vendor_id == vendor_id,
            Order.created_at >= daily_start,
            Order.status != "cancelled",
        )
    ).all()

    day_map: dict[str, float] = defaultdict(float)
    for o in daily_orders:
        key = o.created_at.strftime("%Y-%m-%d")
        day_map[key] += o.total_price

    daily_breakdown: List[DailyRevenue] = []
    for i in range(7):
        dt = daily_start + timedelta(days=i)
        date_str = dt.strftime("%Y-%m-%d")
        daily_breakdown.append(DailyRevenue(
            day=dt.strftime("%a"),
            date=date_str,
            revenue=round(day_map.get(date_str, 0.0), 2),
        ))

    # ── Top 5 products by revenue ─────────────────────────────────────────────
    product_revenue: dict[int, dict] = defaultdict(lambda: {"revenue": 0.0, "units": 0, "name": "", "image_url": None})
    for o in orders:
        if o.status == "cancelled":
            continue
        product_revenue[o.product_id]["revenue"] += o.total_price
        product_revenue[o.product_id]["units"] += o.quantity
        if not product_revenue[o.product_id]["name"] and o.product_name:
            product_revenue[o.product_id]["name"] = o.product_name

    # Fetch missing product names from DB
    missing_ids = [pid for pid, v in product_revenue.items() if not v["name"]]
    if missing_ids:
        products = session.exec(
            select(Product).where(Product.id.in_(missing_ids))
        ).all()
        for p in products:
            product_revenue[p.id]["name"] = p.name
            product_revenue[p.id]["image_url"] = p.image_url

    top_products = sorted(
        product_revenue.items(), key=lambda x: x[1]["revenue"], reverse=True
    )[:5]

    top_product_list = [
        TopProduct(
            product_id=pid,
            product_name=data["name"] or f"Product #{pid}",
            image_url=data.get("image_url"),
            units_sold=data["units"],
            revenue=round(data["revenue"], 2),
        )
        for pid, data in top_products
    ]

    return VendorAnalytics(
        period=period,
        revenue=round(revenue, 2),
        orders=order_count,
        avg_order=avg_order,
        daily_breakdown=daily_breakdown,
        top_products=top_product_list,
    )
