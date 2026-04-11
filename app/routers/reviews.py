"""
Reviews router — purchase-verified product ratings.

Flow:
  1. Consumer places an order → order.status eventually becomes "delivered"
  2. Consumer posts a review with their order_id (optional but validates purchase)
  3. Backend recomputes product.rating and product.reviews_count (denormalized)
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func
from app.database import get_session
from app.models import Review, Product, Order, User
from app.schemas import ReviewCreate, ReviewPublic
from app.deps import get_current_user, require_consumer

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])


def _recompute_product_rating(product: Product, session: Session) -> None:
    """Recompute and persist the denormalized rating fields on a product."""
    result = session.exec(
        select(func.avg(Review.rating), func.count(Review.id))
        .where(Review.product_id == product.id)
    ).one()
    avg_rating, count = result
    product.rating = round(float(avg_rating or 0), 2)
    product.reviews_count = count or 0
    session.add(product)
    session.commit()


@router.post("/", response_model=ReviewPublic, status_code=201)
def create_review(
    body: ReviewCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_consumer),
):
    """Submit a product review (optionally linked to an order for verification)."""
    product = session.get(Product, body.product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")

    # Optional: verify the consumer actually ordered this product
    if body.order_id is None:
        raise HTTPException(status_code=400, detail="order_id is required for verified reviews")

    order = session.get(Order, body.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.consumer_id != current_user.id:
        raise HTTPException(status_code=403, detail="This is not your order")
    if order.product_id != body.product_id:
        raise HTTPException(status_code=400, detail="Order does not match this product")
    if order.status != "delivered":
        raise HTTPException(status_code=400, detail="You can only review delivered orders")

    # Prevent duplicate reviews per product per consumer
    existing = session.exec(
        select(Review).where(
            Review.order_id == body.order_id,
            Review.consumer_id == current_user.id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You have already reviewed this order")

    if not (1 <= body.rating <= 5):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    review = Review(
        product_id=body.product_id,
        consumer_id=current_user.id,
        order_id=body.order_id,
        rating=body.rating,
        comment=body.comment,
    )
    session.add(review)
    session.commit()
    session.refresh(review)

    # Update product's denormalized rating fields
    _recompute_product_rating(product, session)

    return ReviewPublic(
        id=review.id,
        product_id=review.product_id,
        consumer_id=review.consumer_id,
        order_id=review.order_id,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
    )


@router.get("/product/{product_id}", response_model=List[ReviewPublic])
def get_product_reviews(
    product_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all reviews for a product, newest first."""
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    reviews = session.exec(
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
    ).all()

    return [
        ReviewPublic(
            id=r.id,
            product_id=r.product_id,
            consumer_id=r.consumer_id,
            order_id=r.order_id,
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at,
        )
        for r in reviews
    ]


@router.delete("/{review_id}")
def delete_review(
    review_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_consumer),
):
    """Consumer can delete their own review."""
    review = session.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.consumer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your review")

    product = session.get(Product, review.product_id)
    session.delete(review)
    session.commit()

    if product:
        _recompute_product_rating(product, session)

    return {"message": "Review deleted"}
