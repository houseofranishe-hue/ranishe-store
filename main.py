"""
House of Ranishè — full-stack store backend
-------------------------------------------
FastAPI app that:
  * serves the storefront (static/index.html) and admin page (static/admin.html)
  * exposes /api/products        -> live product list with stock
  * exposes /api/orders  (POST)  -> places an order, decrements stock
  * exposes /api/orders  (GET)   -> lists orders (requires ADMIN_TOKEN header)

Run locally:
  pip install -r requirements.txt
  uvicorn main:app --reload

Deploy (Render.com free tier):
  Build command:  pip install -r requirements.txt
  Start command:  uvicorn main:app --host 0.0.0.0 --port $PORT
  Environment:    ADMIN_TOKEN=<pick-a-secret>   (protects the orders list)
"""

import os
import sqlite3
import json
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional

DB_PATH = os.environ.get("DB_PATH", "store.db")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "change-me")

app = FastAPI(title="House of Ranishè Store API")


# ---------------------------------------------------------------- database
@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price INTEGER NOT NULL,
                sale_price INTEGER NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0,
                image_url TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                items_json TEXT NOT NULL,
                total INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'new'
            )
        """)
        # seed products on first run only
        count = conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
        if count == 0 and os.path.exists("seed_products.json"):
            with open("seed_products.json") as f:
                for p in json.load(f):
                    conn.execute(
                        "INSERT INTO products (sku,name,category,price,sale_price,stock,image_url) VALUES (?,?,?,?,?,?,?)",
                        (p["sku"], p["name"], p["category"], p["price"], p["sale_price"], p["stock"], p.get("image_url", "")),
                    )


init_db()


# ---------------------------------------------------------------- models
class OrderItem(BaseModel):
    sku: str
    qty: int = Field(gt=0, le=20)


class OrderIn(BaseModel):
    customer_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=8, max_length=15)
    address: str = Field(min_length=10, max_length=500)
    items: List[OrderItem]


# ---------------------------------------------------------------- api
@app.get("/api/products")
def list_products():
    with db() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY category, name").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/orders")
def create_order(order: OrderIn):
    if not order.items:
        raise HTTPException(400, "Cart is empty.")

    with db() as conn:
        total = 0
        detailed = []
        for item in order.items:
            row = conn.execute("SELECT * FROM products WHERE sku=?", (item.sku,)).fetchone()
            if row is None:
                raise HTTPException(400, f"Unknown product: {item.sku}")
            if row["stock"] < item.qty:
                raise HTTPException(
                    409, f"Only {row['stock']} left of {row['name']} — please adjust your cart."
                )
            total += row["sale_price"] * item.qty
            detailed.append({
                "sku": row["sku"], "name": row["name"],
                "qty": item.qty, "unit_price": row["sale_price"],
            })

        # decrement stock only after every line passed validation
        for item in order.items:
            conn.execute("UPDATE products SET stock = stock - ? WHERE sku=?", (item.qty, item.sku))

        order_id = "RAN-" + uuid.uuid4().hex[:8].upper()
        conn.execute(
            "INSERT INTO orders (id,created_at,customer_name,phone,address,items_json,total) VALUES (?,?,?,?,?,?,?)",
            (
                order_id,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                order.customer_name.strip(),
                order.phone.strip(),
                order.address.strip(),
                json.dumps(detailed),
                total,
            ),
        )

    return {"order_id": order_id, "total": total, "items": detailed}


@app.get("/api/orders")
def list_orders(x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid admin token.")
    with db() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["items"] = json.loads(d.pop("items_json"))
        out.append(d)
    return out


@app.post("/api/orders/{order_id}/status")
def update_status(order_id: str, request: Request, x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid admin token.")
    status = request.query_params.get("status", "")
    if status not in ("new", "confirmed", "shipped", "delivered", "cancelled"):
        raise HTTPException(400, "Invalid status.")
    with db() as conn:
        cur = conn.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Order not found.")
    return {"ok": True, "order_id": order_id, "status": status}


# ---------------------------------------------------------------- pages
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/admin")
def admin_page():
    return FileResponse("static/admin.html")
