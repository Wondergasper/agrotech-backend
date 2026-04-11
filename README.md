# AgriShop Backend

FastAPI + SQLite backend for the AgriShop mobile app.

## Quick Start

```bash
# 1. Move into the backend folder
cd agrotech-backend

# 2. Install dependencies (only once)
pip install -r requirements.txt

# 3. Seed the database with sample data (only once)
python seed.py

# 4. Start the dev server
uvicorn app.main:app --reload --port 8000
```

The API will be live at **http://localhost:8000**  
Interactive docs (Swagger UI): **http://localhost:8000/docs**

---

## API Overview

### Auth
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/signup` | Register (returns JWT) |
| POST | `/api/auth/login` | Login (returns JWT) |
| POST | `/api/auth/change-password` | Change password |

### Users *(requires Bearer token)*
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/users/me` | My profile |
| PATCH | `/api/users/me` | Update name/phone |
| PATCH | `/api/users/me/preferences` | Update budget, health tags |
| PATCH | `/api/users/me/farm` | Update farm info (vendor) |

### Products *(requires Bearer token)*
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/products` | List all (`?q=&category=&sort=`) |
| GET | `/api/products/mine` | Vendor's own products |
| GET | `/api/products/{id}` | Product detail |
| POST | `/api/products` | Create product (vendor only) |
| PATCH | `/api/products/{id}` | Edit product (vendor only) |
| DELETE | `/api/products/{id}` | Soft delete (vendor only) |

### Orders *(requires Bearer token)*
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/orders` | Place order (consumer only) |
| GET | `/api/orders/my` | My order history (consumer) |
| GET | `/api/orders/vendor` | Incoming orders (vendor) |
| PATCH | `/api/orders/{id}/status` | Update status (vendor) |

---

## Test Accounts (after seeding)

| Role | Email | Password |
|---|---|---|
| Farmer | musa@farm.ng | password123 |
| Buyer | ada@buyer.ng | password123 |

---

## Folder Structure

```
agrotech-backend/
 ├ app/
 │  ├ main.py        ← FastAPI entry + CORS + static files
 │  ├ database.py    ← SQLite engine + session
 │  ├ models.py      ← User, Product, Order tables
 │  ├ schemas.py     ← Request/Response Pydantic schemas
 │  ├ deps.py        ← JWT auth + role guards
 │  └ routers/
 │     ├ auth.py
 │     ├ users.py
 │     ├ products.py
 │     └ orders.py
 ├ static/           ← Uploaded images served here
 ├ seed.py           ← Sample data loader
 ├ agrotech.db       ← SQLite file (created on first run)
 ├ requirements.txt
 └ .env              ← SECRET_KEY (change in production!)
```
