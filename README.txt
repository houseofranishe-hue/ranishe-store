HOUSE OF RANISHÈ — FLAT DEPLOYMENT (easy upload)
=================================================
All files are at the top level — NO folders to worry about.

TO DEPLOY:
1. In GitHub, upload ALL these files to the top level of your repo
   (Add file -> Upload files -> drag them all in -> Commit).
   They will overwrite the old main.py, index.html, admin.html,
   requirements.txt, seed_products.json.
2. DELETE any old file named "static" folder contents if they conflict
   (not needed anymore — everything is flat now).
3. Make sure these 4 environment variables are set on the web service:
   DATABASE_URL, ADMIN_TOKEN, UPI_ID, WHATSAPP
4. Render auto-redeploys. Done.

FILES:
- main.py               backend (serves flat files)
- index.html           storefront (hero image embedded inside)
- admin.html           admin dashboard
- page_about.html      About Us
- page_contact.html    Contact
- page_refund.html     Refund & Returns
- page_shipping.html   Shipping
- page_privacy.html    Privacy Policy
- page_terms.html      Terms of Service
- seed_products.json   178 products
- requirements.txt     dependencies
