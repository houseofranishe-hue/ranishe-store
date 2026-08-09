# House of Ranishè — Complete Store (Final)

Full storefront + admin dashboard + policy pages, ready to deploy.

## What's inside
- Storefront: banner hero, 5 categories, FAQ, WhatsApp+Instagram buttons
- Admin dashboard (/admin): add/edit/delete products, photos, categories, stock; orders; P&L reports
- 6 policy pages: About, Contact, Refund, Shipping, Terms, Privacy
- 178 products pre-loaded (your wife can edit all of these in the admin)
- Persistent PostgreSQL support (data never resets)

## ============================================
## DEPLOYMENT — upgrading your LIVE Render site
## ============================================

### STEP 1 — Add a free PostgreSQL database (data persistence)
1. Render dashboard → New → Postgres
2. Name: ranishe-db → Plan: Free → Create Database
3. Wait ~1 min for it to be ready
4. Open it → find "Internal Database URL" → click Copy

### STEP 2 — Add environment variables to your web service
1. Render → your ranishe-store web service → Environment (left menu)
2. Add these (click "Add Environment Variable" for each):
   - DATABASE_URL = (paste the Internal Database URL from step 1)
   - ADMIN_TOKEN  = (a secret password only you & your wife know)
   - UPI_ID       = anishmathew131@okicici
   - WHATSAPP     = 919167629547
3. Save

### STEP 3 — Update the files on GitHub
Replace/add these files in your GitHub repo (Add file → Upload files,
or edit each). Upload the WHOLE ranishe-app contents:
   - main.py                    (updated)
   - requirements.txt           (updated)
   - seed_products.json         (updated)
   - static/index.html          (new design)
   - static/admin.html          (new admin dashboard)
   - static/images/hero-cover.jpg   (the banner)
   - static/pages/*.html        (6 policy pages)
Commit changes.

### STEP 4 — Render auto-deploys
Render rebuilds automatically when GitHub updates (2–5 min).
First boot seeds all products + categories into the new database.

### STEP 5 — Verify
- Visit houseofranishe.in → new design should show
- Visit houseofranishe.in/admin → sign in with ADMIN_TOKEN
- Place a test order → check it appears in admin Orders tab

## ============================================
## FOR YOUR WIFE — managing the shop
## ============================================
Go to houseofranishe.in/admin, sign in with the ADMIN_TOKEN.
- Products tab: + Add Product (name, category, cost, price, sale price,
  stock, upload photo, description). Edit or delete any product.
  * Keep photos under ~800KB each (compress big phone photos at tinypng.com)
- Categories tab: add/edit/delete categories
- Orders tab: see orders, update status
- Reports tab: revenue, profit (P&L), stock value, top sellers, low stock

Cost price is used for profit reports and is NEVER shown to customers.

## Payments
Customer checks out → pays your UPI → confirms on WhatsApp with order number.
You match payment to order in the admin Orders tab.

## Notes
- Free Render web service sleeps when idle; first visit after a nap
  takes ~30–60s to wake. Normal for free tier.
- With DATABASE_URL set, all data (products, edits, orders) is permanent.
