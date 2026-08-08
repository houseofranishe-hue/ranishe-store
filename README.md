# House of Ranishè — Online Store (frontend + backend)

A complete small store: browsable catalog with a real multi-item cart,
checkout that saves orders and reduces stock, and an admin page to see orders.

## What's inside
- `main.py` — FastAPI backend (products API, orders API, admin API)
- `static/index.html` — the storefront customers see
- `static/admin.html` — your private orders page (visit /admin)
- `seed_products.json` — all 178 products with your real prices & stock
- `requirements.txt` — Python dependencies

## Before deploying — edit 2 lines
Open `static/index.html`, near the bottom find:
- `WHATSAPP_NUMBER` — your WhatsApp number with country code (no +)
- `UPI_ID` — your UPI ID (customers pay here after ordering)

## Run on your computer (optional test)
    pip install -r requirements.txt
    uvicorn main:app --reload
Then open http://localhost:8000

## Deploy free on Render.com
1. Put this folder in a GitHub repository (github.com → New repository → upload files)
2. On render.com: New → Web Service → connect that repo
3. Settings:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Environment variable: `ADMIN_TOKEN` = a secret only you know
4. Deploy. Your store is live at the URL Render gives you.
5. Connect your GoDaddy domain in Render's "Custom Domains" settings.

## How orders work
Customer adds items → checks out with name/phone/address → order is saved,
stock reduces, they get an order number → they pay your UPI ID and confirm
on WhatsApp. You see every order at `/admin` using your ADMIN_TOKEN.

## Known limits (honest notes)
- Payment is UPI + WhatsApp confirmation, not automatic gateway capture.
  To automate later, add Razorpay/Instamojo API keys — the order flow is ready for it.
- On Render's free tier the SQLite database resets when the service redeploys
  or sleeps long enough. Orders also reach you via WhatsApp confirmation, so
  nothing is lost operationally — but check /admin regularly, and upgrade to
  Render's paid disk (or a free Postgres) when order volume grows.
