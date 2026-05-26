from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import Order, Product, User
from app.schemas import OrderCreate, OrderPublic, UpdateOrderStatus
from app.deps import get_current_user, require_consumer, require_vendor

router = APIRouter(prefix="/api/orders", tags=["Orders"])

VALID_STATUSES = {"pending", "confirmed", "delivered", "cancelled"}


def _order_to_public(o: Order) -> OrderPublic:
    product = o.__dict__.get("_product_snapshot")
    return OrderPublic(
        id=o.id,
        consumer_id=o.consumer_id,
        vendor_id=o.vendor_id,
        product_id=o.product_id,
        product_name=o.product_name,
        vendor_name=getattr(product, "vendor_name", None),
        farm_name=getattr(product, "farm_name", None),
        image_url=getattr(product, "image_url", None),
        vendor_phone=o.__dict__.get("_vendor_phone"),
        quantity=o.quantity,
        total_price=o.total_price,
        status=o.status,
        created_at=o.created_at,
    )


@router.post("/", response_model=List[OrderPublic], status_code=201)
def create_order(
    body: OrderCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_consumer),
):
    """
    Place one or more orders from the consumer's cart.
    Each item in `body.items` creates a separate Order row.
    """
    if not body.items:
        raise HTTPException(status_code=400, detail="Order must contain at least one item")

    created_orders = []
    product_snapshots: dict[int, Product] = {}
    for item in body.items:
        product = session.get(Product, item.product_id)
        if not product or not product.is_active:
            raise HTTPException(
                status_code=404, detail=f"Product {item.product_id} not found or unavailable"
            )
        if item.quantity < 1:
            raise HTTPException(status_code=400, detail="Quantity must be at least 1")
        product_snapshots[item.product_id] = product

        order = Order(
            consumer_id=current_user.id,
            vendor_id=product.vendor_id,
            product_id=product.id,
            product_name=product.name,      # snapshot for history display
            quantity=item.quantity,
            total_price=round(product.price * item.quantity, 2),
            status="pending",
        )
        session.add(order)
        created_orders.append(order)

    session.commit()
    for order in created_orders:
        session.refresh(order)
        order._product_snapshot = product_snapshots.get(order.product_id)

    _attach_vendor_phones(created_orders, session)
    return [_order_to_public(o) for o in created_orders]


@router.get("/my", response_model=List[OrderPublic])
def my_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_consumer),
):
    """Consumer: full order history, newest first."""
    orders = session.exec(
        select(Order)
        .where(Order.consumer_id == current_user.id)
        .order_by(Order.created_at.desc())
    ).all()
    _attach_product_snapshots(orders, session)
    _attach_vendor_phones(orders, session)
    return [_order_to_public(o) for o in orders]


@router.get("/vendor", response_model=List[OrderPublic])
def vendor_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_vendor),
):
    """Vendor: all incoming orders, newest first."""
    orders = session.exec(
        select(Order)
        .where(Order.vendor_id == current_user.id)
        .order_by(Order.created_at.desc())
    ).all()
    _attach_product_snapshots(orders, session)
    _attach_vendor_phones(orders, session)
    return [_order_to_public(o) for o in orders]


@router.patch("/{order_id}/status", response_model=OrderPublic)
def update_order_status(
    order_id: int,
    body: UpdateOrderStatus,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),  # both roles can update status (vendor confirms, consumer cancels)
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Status must be one of: {', '.join(VALID_STATUSES)}"
        )

    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Vendors can confirm/deliver; consumers can only cancel their own pending orders
    if current_user.active_role == "vendor":
        if order.vendor_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your order")
        if body.status == "cancelled":
            raise HTTPException(status_code=403, detail="Vendors cannot cancel orders — use the consumer cancellation flow")
    elif current_user.active_role == "consumer":
        if order.consumer_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your order")
        if body.status != "cancelled":
            raise HTTPException(status_code=403, detail="Consumers can only cancel orders")
        if order.status != "pending":
            raise HTTPException(status_code=400, detail="Only pending orders can be cancelled")

    order.status = body.status
    session.add(order)
    session.commit()
    session.refresh(order)
    _attach_product_snapshots([order], session)
    _attach_vendor_phones([order], session)
    return _order_to_public(order)


def _attach_product_snapshots(orders: List[Order], session: Session) -> None:
    if not orders:
        return

    product_ids = sorted({order.product_id for order in orders})
    products = session.exec(select(Product).where(Product.id.in_(product_ids))).all()
    product_map = {product.id: product for product in products}

    for order in orders:
        order._product_snapshot = product_map.get(order.product_id)


def _attach_vendor_phones(orders: List[Order], session: Session) -> None:
    if not orders:
        return

    vendor_ids = sorted({order.vendor_id for order in orders})
    vendors = session.exec(select(User).where(User.id.in_(vendor_ids))).all()
    vendor_map = {vendor.id: vendor.phone for vendor in vendors}

    for order in orders:
        order._vendor_phone = vendor_map.get(order.vendor_id)
