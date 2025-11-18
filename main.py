import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Furniture Store API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------
# Utils
# ----------------------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = {**doc}
    if d.get("_id"):
        d["id"] = str(d.pop("_id"))
    # convert decimals/ObjectId in nested lists if any
    return d


# ----------------------
# Schemas
# ----------------------
class ProductIn(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category: str
    rating: float = Field(4.0, ge=0, le=5)
    materials: List[str] = []
    images: List[str] = []
    is_new: bool = False
    is_top_seller: bool = False

class Product(ProductIn):
    id: Optional[str] = None

class Testimonial(BaseModel):
    name: str
    message: str
    rating: int = Field(5, ge=1, le=5)
    avatar: Optional[str] = None

class Customer(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: str

class OrderItem(BaseModel):
    product_id: str
    title: str
    price: float
    quantity: int = Field(1, ge=1)
    image: Optional[str] = None

class OrderIn(BaseModel):
    customer: Customer
    items: List[OrderItem]
    payment_method: str = Field(..., description="COD | Stripe | SSLCommerz")

class Order(OrderIn):
    id: Optional[str] = None


# ----------------------
# Startup: seed data if empty
# ----------------------
@app.on_event("startup")
async def seed_data():
    if db is None:
        return
    # Products
    if db["product"].count_documents({}) == 0:
        sample_products = [
            {
                "title": "Aero Lounge Chair",
                "description": "Premium leather lounge chair with oak base.",
                "price": 499.0,
                "category": "Chair",
                "rating": 4.6,
                "materials": ["Leather", "Oak"],
                "images": [
                    "https://images.unsplash.com/photo-1549187774-b4e9b0445b41?q=80&w=1200",
                ],
                "is_new": False,
                "is_top_seller": True,
            },
            {
                "title": "Cloud XL Sofa",
                "description": "Deep, ultra-comfy 3-seater fabric sofa.",
                "price": 1299.0,
                "category": "Sofa",
                "rating": 4.8,
                "materials": ["Fabric", "Pine"],
                "images": [
                    "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?q=80&w=1200",
                ],
                "is_new": True,
                "is_top_seller": True,
            },
            {
                "title": "Nordic Queen Bed",
                "description": "Minimal solid wood queen bed frame.",
                "price": 899.0,
                "category": "Bed",
                "rating": 4.5,
                "materials": ["Walnut"],
                "images": [
                    "https://images.unsplash.com/photo-1505691723518-36a5ac3be353?q=80&w=1200",
                ],
                "is_new": True,
                "is_top_seller": False,
            },
            {
                "title": "Arc Dining Table",
                "description": "Round marble dining table with steel base.",
                "price": 999.0,
                "category": "Table",
                "rating": 4.7,
                "materials": ["Marble", "Steel"],
                "images": [
                    "https://images.unsplash.com/photo-1600491030793-4bd19ae2c909?q=80&w=1200",
                ],
                "is_new": False,
                "is_top_seller": True,
            },
            {
                "title": "Halo Pendant Light",
                "description": "Matte brass ring pendant lighting.",
                "price": 199.0,
                "category": "Decor",
                "rating": 4.3,
                "materials": ["Brass"],
                "images": [
                    "https://images.unsplash.com/photo-1505691938895-1758d7feb511?q=80&w=1200",
                ],
                "is_new": True,
                "is_top_seller": False,
            },
        ]
        for p in sample_products:
            create_document("product", p)

    if db["testimonial"].count_documents({}) == 0:
        testimonials = [
            {
                "name": "Amelia R.",
                "message": "Beautiful designs and outstanding quality. My living room feels brand new!",
                "rating": 5,
            },
            {
                "name": "Noah P.",
                "message": "Fast delivery and great customer service. The sofa is insanely comfy.",
                "rating": 5,
            },
            {
                "name": "Sophia L.",
                "message": "Minimal yet luxurious. Exactly the vibe I wanted.",
                "rating": 4,
            },
        ]
        for t in testimonials:
            create_document("testimonial", t)


# ----------------------
# Basic
# ----------------------
@app.get("/")
def read_root():
    return {"message": "Furniture Store API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = os.getenv("DATABASE_NAME") or "❌ Not Set"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# ----------------------
# Products
# ----------------------
@app.get("/api/categories")
def get_categories():
    if db is None:
        return {"categories": []}
    cats = db["product"].distinct("category")
    # ensure featured order
    featured = ["Chair", "Sofa", "Bed", "Table", "Decor"]
    ordered = featured + [c for c in cats if c not in featured]
    return {"categories": ordered}

@app.get("/api/products")
def list_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    materials: Optional[str] = Query(None, description="Comma separated materials"),
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    rating_min: Optional[float] = None,
    page: int = 1,
    page_size: int = 12,
):
    if db is None:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    q: Dict[str, Any] = {}
    if search:
        q["title"] = {"$regex": search, "$options": "i"}
    if category:
        q["category"] = category
    if materials:
        mats = [m.strip() for m in materials.split(",") if m.strip()]
        if mats:
            q["materials"] = {"$in": mats}
    if price_min is not None or price_max is not None:
        rng: Dict[str, Any] = {}
        if price_min is not None:
            rng["$gte"] = price_min
        if price_max is not None:
            rng["$lte"] = price_max
        q["price"] = rng
    if rating_min is not None:
        q["rating"] = {"$gte": rating_min}

    total = db["product"].count_documents(q)
    skip = (page - 1) * page_size
    cursor = db["product"].find(q).skip(skip).limit(page_size)
    items = [serialize_doc(d) for d in cursor]
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@app.get("/api/products/top-selling")
def top_selling():
    cursor = db["product"].find({"is_top_seller": True}).limit(8) if db else []
    items = [serialize_doc(d) for d in cursor]
    return {"items": items}

@app.get("/api/products/new-arrivals")
def new_arrivals():
    cursor = db["product"].find({"is_new": True}).limit(8) if db else []
    items = [serialize_doc(d) for d in cursor]
    return {"items": items}

@app.get("/api/products/{product_id}")
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    prod = serialize_doc(doc)
    # related products by category
    rel_cursor = db["product"].find({"category": prod.get("category"), "_id": {"$ne": ObjectId(product_id)}}).limit(4)
    related = [serialize_doc(d) for d in rel_cursor]
    return {"item": prod, "related": related}


# ----------------------
# Testimonials
# ----------------------
@app.get("/api/testimonials")
def get_testimonials():
    cursor = db["testimonial"].find({}).limit(8) if db else []
    items = [serialize_doc(d) for d in cursor]
    return {"items": items}


# ----------------------
# Orders
# ----------------------
@app.post("/api/orders")
def create_order(order: OrderIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    order_dict = order.model_dump()
    order_id = create_document("order", order_dict)
    return {"id": order_id, "status": "received"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
