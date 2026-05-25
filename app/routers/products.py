import json
import uuid
import base64
import random
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlmodel import Session, select
from app.database import get_session
from app.models import Product, User
from app.schemas import (
    ProductCreate,
    ProductImageAnalysisRequest,
    ProductPublic,
    ProductUpdate,
)
from app.deps import get_current_user, get_current_user_optional, require_vendor
from app.storage import (
    ensure_storage_bucket,
    get_public_url,
    get_supabase_client,
    SUPABASE_BUCKET,
)
from app.ai_client import analyze_product_image

router = APIRouter(prefix="/api/products", tags=["Products"])


def _to_public(p: Product) -> ProductPublic:
    return ProductPublic(
        id=p.id,
        name=p.name,
        description=p.description,
        price=p.price,
        unit=p.unit,
        category=p.category,
        tags=p.get_tags(),
        freshness=p.freshness,
        quantity=p.quantity,
        image_url=p.image_url,
        vendor_id=p.vendor_id,
        vendor_name=p.vendor_name,
        farm_name=p.farm_name,
        rating=p.rating,
        reviews_count=p.reviews_count,
        is_active=p.is_active,
        created_at=p.created_at,
    )


# ─── Image Upload ─────────────────────────────────────────────────────────────

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
_EXT_MAP = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/upload-image", tags=["Products"])
async def upload_product_image(
    file: UploadFile = File(...),
    analyze: bool = Query(default=False, description="Run AI analysis on the uploaded image"),
    current_user: User = Depends(require_vendor),
):
    """
    Upload a product image to Supabase Storage.
    Returns the public CDN URL to be stored as `image_url` on the product.

    If `analyze=true`, the image is also sent to the AI analysis service
    and the results (category, tags, freshness_score, defects) are returned
    alongside the URL for use during product creation.
    """
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type}'. Use JPEG, PNG, or WEBP.",
        )

    ext = _EXT_MAP[content_type]

    # Read with a 1-byte overage to detect files that exceed the limit
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image must be under 5 MB.")

    storage_path = f"vendors/{current_user.id}/{uuid.uuid4().hex}{ext}"

    try:
        client = get_supabase_client()
        ensure_storage_bucket(client)
        client.storage.from_(SUPABASE_BUCKET).upload(
            path=storage_path, file=data, file_options={"content-type": content_type},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Image upload failed: {exc}")

    image_url = get_public_url(storage_path)
    response: dict = {"image_url": image_url, "path": storage_path}

    # Optional AI analysis
    if analyze:
        base64_image = base64.b64encode(data).decode("utf-8")
        ai_result = await analyze_product_image(base64_image)
        if ai_result:
            response["analysis"] = ai_result

    return response


@router.post("/analyze-image", tags=["Products"])
async def analyze_product_image_route(
    body: ProductImageAnalysisRequest,
    current_user: User = Depends(require_vendor),
):
    """
    Proxy AI image analysis through the main backend so the mobile client only
    depends on one authenticated API surface for the product upload flow.
    """
    ai_result = await analyze_product_image(body.image)
    if not ai_result:
        raise HTTPException(status_code=502, detail="Image analysis is unavailable right now.")
    return ai_result


# ─── Product CRUD ─────────────────────────────────────────────────────────────

@router.get("/", response_model=List[ProductPublic])
def list_products(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    sort: Optional[str] = Query(None, description="freshness | price | name | rating"),
    shuffle: bool = Query(False, description="Randomize the order of products"),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    stmt = select(Product).where(Product.is_active == True)
    if category:
        stmt = stmt.where(Product.category == category)
    products = list(session.exec(stmt).all())

    if q:
        ql = q.lower()
        products = [
            p for p in products
            if ql in p.name.lower() or (p.description and ql in p.description.lower())
        ]

    if shuffle:
        random.shuffle(products)
    elif sort == "price":
        products.sort(key=lambda p: p.price)
    elif sort == "name":
        products.sort(key=lambda p: p.name)
    elif sort == "rating":
        products.sort(key=lambda p: p.rating, reverse=True)
    else:
        # Default sort by freshness if not shuffling
        products.sort(key=lambda p: p.freshness, reverse=True)

    return [_to_public(p) for p in products]


@router.get("/mine", response_model=List[ProductPublic])
def my_products(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_vendor),
):
    """Vendor: list only their own products (incl. inactive)."""
    products = session.exec(
        select(Product).where(Product.vendor_id == current_user.id)
    ).all()
    return [_to_public(p) for p in products]


@router.get("/{product_id}", response_model=ProductPublic)
def get_product(
    product_id: int,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    product = session.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    return _to_public(product)


@router.post("/", response_model=ProductPublic, status_code=201)
def create_product(
    body: ProductCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_vendor),
):
    product = Product(
        name=body.name,
        description=body.description,
        price=body.price,
        unit=body.unit,
        category=body.category,
        tags_json=json.dumps(body.tags),
        freshness=body.freshness,
        quantity=body.quantity,
        image_url=body.image_url,
        vendor_id=current_user.id,
        # Denormalize vendor info at creation time
        vendor_name=current_user.name,
        farm_name=current_user.farm_name,
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return _to_public(product)


@router.patch("/{product_id}", response_model=ProductPublic)
def update_product(
    product_id: int,
    body: ProductUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_vendor),
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.vendor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your product")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "tags":
            product.set_tags(value)
        else:
            setattr(product, field, value)

    session.add(product)
    session.commit()
    session.refresh(product)
    return _to_public(product)


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_vendor),
):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.vendor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your product")

    session.delete(product)
    session.commit()
    return {"message": "Product deleted successfully"}
