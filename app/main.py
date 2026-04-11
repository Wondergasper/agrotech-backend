from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import create_db_and_tables
from app.routers import auth, users, products, orders, reviews, vendor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    create_db_and_tables()
    yield


app = FastAPI(
    title="AgriShop API",
    description="Backend for the AgriShop mobile app — farmers & buyers.",
    version="2.1.0",
    lifespan=lifespan,
)

# Allow Expo/React Native dev client to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(reviews.router)
app.include_router(vendor.router)


@app.get("/")
def root():
    return {
        "message": "AgriShop API is running 🌿",
        "version": "2.1.0",
        "docs": "/docs",
    }
