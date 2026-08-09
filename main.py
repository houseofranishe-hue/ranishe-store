"""
House of Ranishè — store backend (v2)
=====================================
Full shop system: storefront API + admin CRUD + reports (incl. P&L).

Database:
  * If DATABASE_URL is set (Render Postgres), uses Postgres  -> data is PERMANENT.
  * Otherwise falls back to local SQLite (for testing on your computer).

Env vars to set in Render:
  DATABASE_URL   -> auto-provided when you attach a Render Postgres
  ADMIN_TOKEN    -> your secret admin password
  UPI_ID         -> your UPI id shown to customers
  WHATSAPP       -> your WhatsApp number, e.g. 919167629547
"""

import os
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "change-me")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
PUBLIC_CONFIG = {
    "upi_id": os.environ.get("UPI_ID", "anishmathew131@okicici"),
    "whatsapp": os.environ.get("WHATSAPP", "919167629547"),
    "store_name": "House of Ranishe",
}

USING_PG = DATABASE_URL.startswith("postgres")

if USING_PG:
    import psycopg2
    import psycopg2.extras
    def get_conn():
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
else:
    import sqlite3
    DB_PATH = os.environ.get("DB_PATH", "store.db")
    def get_conn():
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        return c

app = FastAPI(title="House of Ranishè Store")


def q(sql: str) -> str:
    return sql if USING_PG else sql.replace("%s", "?")


def init_db():
    conn = get_conn(); cur = conn.cursor()
    if USING_PG:
        cur.execute("""CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY, sort_order INTEGER DEFAULT 0)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
            cost_price INTEGER NOT NULL DEFAULT 0, price INTEGER NOT NULL, sale_price INTEGER NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0, image_url TEXT DEFAULT '', description TEXT DEFAULT '',
            archived BOOLEAN DEFAULT FALSE)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, customer_name TEXT NOT NULL,
            phone TEXT NOT NULL, address TEXT NOT NULL, items_json TEXT NOT NULL,
            total INTEGER NOT NULL, cost_total INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'new')""")
    else:
        cur.execute("""CREATE TABLE IF NOT EXISTS categories (name TEXT PRIMARY KEY, sort_order INTEGER DEFAULT 0)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
            cost_price INTEGER NOT NULL DEFAULT 0, price INTEGER NOT NULL, sale_price INTEGER NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0, image_url TEXT DEFAULT '', description TEXT DEFAULT '',
            archived INTEGER DEFAULT 0)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, customer_name TEXT NOT NULL,
            phone TEXT NOT NULL, address TEXT NOT NULL, items_json TEXT NOT NULL,
            total INTEGER NOT NULL, cost_total INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'new')""")

    cur.execute("SELECT COUNT(*) AS c FROM products")
    row = cur.fetchone()
    count = row["c"] if isinstance(row, dict) else row[0]
    if count == 0 and os.path.exists("seed_products.json"):
        with open("seed_products.json", encoding="utf-8") as f:
            seed = json.load(f)
        for name, order in {"Earrings":0,"Chains":1,"Bracelets":2,"Gift Sets":3,"Under 499":4}.items():
            if USING_PG:
                cur.execute("INSERT INTO categories (name, sort_order) VALUES (%s,%s) ON CONFLICT DO NOTHING", (name, order))
            else:
                cur.execute("INSERT OR IGNORE INTO categories (name, sort_order) VALUES (?,?)", (name, order))
        for p in seed:
            cur.execute(q("""INSERT INTO products (sku,name,category,cost_price,price,sale_price,stock,image_url,description)
                             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"""),
                        (p["sku"], p["name"], p["category"], p.get("cost_price",0),
                         p["price"], p["sale_price"], p["stock"], p.get("image_url",""), p.get("description","")))
    conn.commit(); cur.close(); conn.close()


init_db()


def require_admin(token: Optional[str]):
    if token != ADMIN_TOKEN:
        raise HTTPException(401, "Invalid admin token.")


# ------------------------------------------------------- models
class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    cost_price: int = Field(ge=0)
    price: int = Field(ge=0)
    sale_price: int = Field(ge=0)
    stock: int = Field(ge=0)
    image_url: str = ""
    description: str = ""


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    sort_order: int = 0


class OrderItem(BaseModel):
    sku: str
    qty: int = Field(gt=0, le=50)


class OrderIn(BaseModel):
    customer_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=8, max_length=15)
    address: str = Field(min_length=10, max_length=500)
    items: List[OrderItem]


# ------------------------------------------------------- storefront API
@app.get("/api/config")
def config():
    return PUBLIC_CONFIG


@app.get("/api/categories")
def list_categories():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT name, sort_order FROM categories ORDER BY sort_order, name")
    rows = cur.fetchall(); cur.close(); conn.close()
    return [dict(r) for r in rows]


@app.get("/api/products")
def list_products():
    conn = get_conn(); cur = conn.cursor()
    af = "FALSE" if USING_PG else "0"
    cur.execute(f"SELECT * FROM products WHERE archived={af} ORDER BY category, name")
    rows = cur.fetchall(); cur.close(); conn.close()
    out = []
    for r in rows:
        d = dict(r); d.pop("cost_price", None); d.pop("archived", None); out.append(d)
    return out


@app.post("/api/orders")
def create_order(order: OrderIn):
    if not order.items:
        raise HTTPException(400, "Cart is empty.")
    conn = get_conn(); cur = conn.cursor()
    try:
        total = 0; cost_total = 0; detailed = []
        for item in order.items:
            cur.execute(q("SELECT * FROM products WHERE sku=%s"), (item.sku,))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(400, f"Unknown product: {item.sku}")
            row = dict(row)
            if row["stock"] < item.qty:
                raise HTTPException(409, f"Only {row['stock']} left of {row['name']} — please adjust your cart.")
            total += row["sale_price"] * item.qty
            cost_total += row["cost_price"] * item.qty
            detailed.append({"sku":row["sku"],"name":row["name"],"qty":item.qty,"unit_price":row["sale_price"]})
        for item in order.items:
            cur.execute(q("UPDATE products SET stock = stock - %s WHERE sku=%s"), (item.qty, item.sku))
        order_id = "RAN-" + uuid.uuid4().hex[:8].upper()
        cur.execute(q("""INSERT INTO orders (id,created_at,customer_name,phone,address,items_json,total,cost_total)
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""),
                    (order_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     order.customer_name.strip(), order.phone.strip(), order.address.strip(),
                     json.dumps(detailed), total, cost_total))
        conn.commit()
    finally:
        cur.close(); conn.close()
    return {"order_id": order_id, "total": total, "items": detailed}


# ------------------------------------------------------- admin: products
@app.get("/api/admin/products")
def admin_products(x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    conn = get_conn(); cur = conn.cursor()
    af = "FALSE" if USING_PG else "0"
    cur.execute(f"SELECT * FROM products WHERE archived={af} ORDER BY category, name")
    rows = cur.fetchall(); cur.close(); conn.close()
    return [dict(r) for r in rows]


@app.post("/api/admin/products")
def upsert_product(p: ProductIn, x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(q("SELECT sku FROM products WHERE sku=%s"), (p.sku,))
    exists = cur.fetchone()
    if exists:
        cur.execute(q("""UPDATE products SET name=%s,category=%s,cost_price=%s,price=%s,sale_price=%s,
                         stock=%s,image_url=%s,description=%s WHERE sku=%s"""),
                    (p.name,p.category,p.cost_price,p.price,p.sale_price,p.stock,p.image_url,p.description,p.sku))
    else:
        cur.execute(q("""INSERT INTO products (sku,name,category,cost_price,price,sale_price,stock,image_url,description)
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"""),
                    (p.sku,p.name,p.category,p.cost_price,p.price,p.sale_price,p.stock,p.image_url,p.description))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True, "sku": p.sku}


@app.delete("/api/admin/products/{sku}")
def delete_product(sku: str, x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(q("DELETE FROM products WHERE sku=%s"), (sku,))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}


# ------------------------------------------------------- admin: categories
@app.post("/api/admin/categories")
def upsert_category(c: CategoryIn, x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(q("SELECT name FROM categories WHERE name=%s"), (c.name,))
    if cur.fetchone():
        cur.execute(q("UPDATE categories SET sort_order=%s WHERE name=%s"), (c.sort_order, c.name))
    else:
        cur.execute(q("INSERT INTO categories (name,sort_order) VALUES (%s,%s)"), (c.name, c.sort_order))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}


@app.delete("/api/admin/categories/{name}")
def delete_category(name: str, x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(q("DELETE FROM categories WHERE name=%s"), (name,))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}


# ------------------------------------------------------- admin: orders + reports
@app.get("/api/admin/orders")
def admin_orders(x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
    rows = cur.fetchall(); cur.close(); conn.close()
    out = []
    for r in rows:
        d = dict(r); d["items"] = json.loads(d.pop("items_json")); out.append(d)
    return out


@app.post("/api/admin/orders/{order_id}/status")
def order_status(order_id: str, request: Request, x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    status = request.query_params.get("status", "")
    if status not in ("new","confirmed","shipped","delivered","cancelled"):
        raise HTTPException(400, "Invalid status.")
    conn = get_conn(); cur = conn.cursor()
    cur.execute(q("UPDATE orders SET status=%s WHERE id=%s"), (status, order_id))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True, "status": status}


@app.get("/api/admin/reports")
def reports(x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    conn = get_conn(); cur = conn.cursor()

    cur.execute("SELECT total, cost_total, status FROM orders")
    orders = [dict(r) for r in cur.fetchall()]
    valid = [o for o in orders if o["status"] != "cancelled"]
    revenue = sum(o["total"] for o in valid)
    cogs = sum(o["cost_total"] for o in valid)
    order_count = len(valid)

    af = "FALSE" if USING_PG else "0"
    cur.execute(f"SELECT sku,name,category,cost_price,sale_price,stock FROM products WHERE archived={af}")
    prods = [dict(r) for r in cur.fetchall()]
    stock_value_cost = sum(p["cost_price"]*p["stock"] for p in prods)
    stock_value_retail = sum(p["sale_price"]*p["stock"] for p in prods)
    out_of_stock = [p for p in prods if p["stock"] == 0]
    low_stock = [p for p in prods if 0 < p["stock"] <= 2]

    cur.execute("SELECT items_json, status FROM orders")
    sold = {}
    for r in cur.fetchall():
        r = dict(r)
        if r["status"] == "cancelled":
            continue
        for it in json.loads(r["items_json"]):
            sold[it["sku"]] = sold.get(it["sku"], 0) + it["qty"]
    top_sellers = sorted(
        [{"sku":p["sku"],"name":p["name"],"units":sold.get(p["sku"],0)} for p in prods],
        key=lambda x: x["units"], reverse=True)[:10]

    cur.close(); conn.close()
    return {
        "revenue": revenue, "cogs": cogs, "gross_profit": revenue - cogs,
        "order_count": order_count,
        "avg_order_value": round(revenue/order_count) if order_count else 0,
        "product_count": len(prods),
        "stock_value_cost": stock_value_cost, "stock_value_retail": stock_value_retail,
        "out_of_stock_count": len(out_of_stock),
        "low_stock": low_stock,
        "out_of_stock": [{"sku":p["sku"],"name":p["name"]} for p in out_of_stock],
        "top_sellers": top_sellers,
    }


# ------------------------------------------------------- pages
@app.get("/")
def home(): return FileResponse("index.html")

@app.get("/about")
def page_about(): return FileResponse("page_about.html")

@app.get("/contact")
def page_contact(): return FileResponse("page_contact.html")

@app.get("/refund-policy")
def page_refund(): return FileResponse("page_refund.html")

@app.get("/shipping-policy")
def page_shipping(): return FileResponse("page_shipping.html")

@app.get("/privacy-policy")
def page_privacy(): return FileResponse("page_privacy.html")

@app.get("/terms")
def page_terms(): return FileResponse("page_terms.html")

@app.get("/admin")
def admin_page(): return FileResponse("admin.html")
