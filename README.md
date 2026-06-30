# Spicearog — Django Full-Stack Port

An organic spices, masalas & wellness e-commerce platform. This is a complete
Django port of the original **Next.js 14 + Prisma + NextAuth + MUI** application,
preserving the data model, business logic, brand design and both surfaces:

- **Storefront** — landing page, catalog, product detail, cart, checkout, orders,
  favourites, reviews, account, journal/blogs, FAQ, testimonials, policy pages and
  a contact/enquiry form.
- **Admin dashboard** — a rich custom admin panel (`/admin-panel`) with KPI cards,
  a 12-month revenue chart, order pipeline, recent orders, inventory health, top
  sellers and low-stock alerts, plus management pages for products, categories,
  variants, inventory, orders and customers. Long-tail content (banners, blogs,
  testimonials, FAQ, policies, enquiries, reviews, offers) is managed through the
  built-in Django admin (`/admin/`), linked from the sidebar.

## Tech stack

- Django 5/6 (server-rendered Django templates + a little vanilla JS for AJAX
  cart/favourites)
- Tailwind (via CDN) with the original brand tokens (forest-green + gold on cream,
  Fraunces display / Inter body)
- SQLite by default; switches to MySQL automatically when `DATABASE_URL` is a
  `mysql://` DSN
- Custom user model with **email-or-mobile** login and bcrypt-compatible password
  hashing (so hashes are interchangeable with the original Node/bcrypt app)

## Quick start

```bash
# 1. (optional) create a virtualenv
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. (optional) configure environment — defaults work without this
cp .env.example .env

# 4. create the database schema
python manage.py migrate

# 5. load demo data (categories, products, variants, banners, blogs, etc.)
python manage.py seed

# 6. run
python manage.py runserver
```

Then open http://127.0.0.1:8000

### Demo credentials (created by `seed`)

| Role     | Login                    | Password   | Where to sign in            |
|----------|--------------------------|------------|-----------------------------|
| Admin    | `admin@spicearog.com`    | `admin123` | `/admin-login` → `/admin-panel` |
| Customer | `priya@example.com`      | `user123`  | `/login`                    |

You can log in with either the email **or** the mobile number tied to an account.

## Key routes

Storefront: `/` · `/products` · `/categories` · `/product/<slug>` · `/cart` ·
`/checkout` · `/orders` · `/favourites` · `/account` · `/notifications` ·
`/blogs` · `/blogs/<slug>` · `/faq` · `/testimonials` · `/about-us` · `/terms` ·
`/privacy-policy` · `/help-support`

Auth: `/login` · `/signup` · `/admin-login` · `/logout`

Admin panel (ADMIN only): `/admin-panel` (dashboard) · `/admin-panel/products` ·
`/admin-panel/products/new` · `/admin-panel/products/<id>/edit` ·
`/admin-panel/categories` · `/admin-panel/variants` · `/admin-panel/inventory` ·
`/admin-panel/orders` · `/admin-panel/users`

Django admin (long-tail content): `/admin/`

Storefront actions (AJAX/JSON): `POST /api/cart/add` · `POST /api/cart/remove` ·
`POST /api/favourites/toggle` · `POST /api/reviews`

## Business rules preserved from the original

- **Cart** upserts by `(cart, variant)`; item price is the variant's selling price.
- **Checkout** computes `subTotal = Σ(price × qty)`, shipping is **free over ₹499**
  otherwise **₹49**, order codes are generated as `SPG-XXXXXXXX`. COD clears the
  cart immediately; Razorpay creates a gateway order first.
- **Favourites** toggle on/off per `(user, product)`.
- **Reviews** are purchase-gated (must have an order item for the product) and
  limited to one per user per product.
- **Admin login** is scoped: only `ADMIN` users can authenticate at `/admin-login`.
- Table and column names mirror the original Prisma schema (`product_varients`,
  `product_cart_items`, `company_policies`, `varient_id`, etc.) so the schema maps
  onto the same MySQL layout.

## Notes

- **Images:** the original product/category/banner artwork isn't bundled. The seed
  references `/seed/*.jpg` placeholder images (generated on-brand and included under
  `static/seed/`). Every `<img>` also has a graceful fallback, so missing images
  degrade to a styled brand placeholder rather than a broken icon. Replace the files
  in `static/seed/` (or point the records at your own URLs) to use real photography.
- **MySQL:** set `DATABASE_URL=mysql://user:pass@host:3306/spicearog` in `.env` and
  install the MySQL client (`pip install mysqlclient`), then run `migrate` + `seed`.
- **Razorpay:** online payment at checkout requires `RAZORPAY_KEY_ID` /
  `RAZORPAY_KEY_SECRET`. Without them, COD works fully and the online option simply
  reports the gateway isn't configured.
- **Production:** set `DEBUG=False`, a real `SECRET_KEY`, proper `ALLOWED_HOSTS`,
  and run `python manage.py collectstatic`.

## Project layout

```
spicearog_django/
├── manage.py
├── requirements.txt
├── .env.example
├── spicearog/            # project: settings, urls, wsgi/asgi
├── accounts/             # custom User + UserAddress, auth views, email/mobile backend
├── store/                # all catalog/cart/order/content models, storefront views,
│                         #   template tags, and the `seed` management command
├── core/                 # custom admin panel (dashboard + CRUD), utils, context processor
├── templates/
│   ├── site/             # storefront templates
│   ├── registration/     # login / signup / admin login
│   └── admin/            # custom admin-panel templates
└── static/seed/          # generated placeholder imagery
```
