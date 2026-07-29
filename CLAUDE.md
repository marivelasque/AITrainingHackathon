# CLAUDE.md — Furniture Shop Buyer App

## Project

Day 1 build for a hackathon. A buyer-facing web app for a furniture shop.

**Core flow:**

- User logs in.
- User browses a product catalogue (762 real IKEA furniture products, synced from a shared
  training MongoDB instance: name, price, photo, description).
- User places orders, saved against their account. Remaining budget is tracked and shown
  live (decreases with each order), and enforced: an order that would exceed it is blocked
  with a clear message and never recorded. See Tests, below.

Originally built in R + Shiny; rebuilt in Python partway through Day 1 for a sleeker,
photo-led catalogue design that Shiny's component model fought against. See
`requirements.md` and `architecture.md` for the full reasoning and the data model. The R
version has been removed from the working tree; it's recoverable from git history if ever
needed.

## Tech stack

- **Flask** — Python micro web framework: routes, request handling, sessions.
- **Jinja2** (bundled with Flask) — server-rendered HTML templates.
- **SQLite**, via Python's built-in `sqlite3` — file-based database, no server to install.
- **Flask-Login** + `werkzeug.security` — session-based login and password hashing.
  Credentials live in their own SQLite file, separate from shop data.
- Hand-written CSS (`static/style.css`) for the card-grid catalogue look — no CSS/JS
  framework.
- **pymongo** + **python-dotenv** — used only by `sync_catalogue.py` (see below), not by
  the running app itself.

## Folder structure

```text
app.py                       # entry point — run this to start the app
db.py                        # shop database: products, orders, order_items (no Flask dependency)
auth.py                      # Flask-Login setup, password hashing, demo user accounts
sync_catalogue.py            # one-off: load the real MongoDB catalogue into SQLite
.env                          # MONGODB_URI (gitignored — see .env.example)
templates/
├── base.html                 # shared layout: nav, flash messages
├── login.html
├── catalogue.html            # home page — product card grid
└── orders.html               # "My Orders" page
static/
├── style.css                 # card grid, hover states, colour palette
└── images/                   # product photos from sync_catalogue.py (gitignored)
data/
├── flask_shop.sqlite         # products + orders (gitignored, regenerated on first run)
└── flask_credentials.sqlite  # login credentials (gitignored, regenerated on first run)
tests/
└── test_budget.py            # can_afford() / place_order() — pytest
requirements.md               # what the app needs to do
architecture.md               # how it's built, including the Customer/Product/Order/OrderItem data model
```

## Running it

```powershell
.venv\Scripts\Activate.ps1     # or: source .venv/Scripts/activate  (Git Bash)
python app.py
```

Open `http://127.0.0.1:5000`. First run creates `data/flask_shop.sqlite` (seeded with 12
placeholder furniture products, until the catalogue is synced — see below) and
`data/flask_credentials.sqlite` (demo accounts below). Both files are gitignored — delete
them to reset to a clean demo state.

**To load the real catalogue** (762 IKEA products from the shared training MongoDB
instance, replacing the placeholders): set `MONGODB_URI` in `.env` (copy `.env.example`),
then:

```powershell
python sync_catalogue.py
```

Safe to re-run any time to refresh the catalogue. Read-only against MongoDB — it only ever
writes to the local SQLite database.

**Demo accounts** (`auth.py`, `DEMO_USERS`) — replace before using with anything real:

| user  | password | budget |
| --- | --- | --- |
| alice | alice123 | $5000  |
| bob   | bob123   | $3000  |
| carla | carla123 | $8000  |

## Tests

```powershell
python -m pytest tests/ -v
```

`tests/test_budget.py` covers the budget-limit logic (`can_afford()`/`place_order()`) —
ported from the R version's `testthat` suite: affordable orders succeed and update spend,
over-budget orders are blocked and not recorded, the exact-remaining-budget boundary case
succeeds, unknown product is rejected. 6/6 passing. Not ported: the R suite's
invalid-quantity case — there's no quantity input in this UI yet (`buy()` always passes
`quantity=1`), so add it once a quantity selector exists.

## Verified working (2026-07-29)

Login → catalogue → "Add to order" saves an order → order appears on "My Orders" with the
correct item and total, driven headlessly via Playwright against a live `python app.py`
instance. Zero console errors, zero broken images. Checked with both the 12 placeholder
products and, after running `sync_catalogue.py`, the real 762-product MongoDB catalogue
(all photos load; verified via `naturalWidth` on every `<img>`, not just absence of
console errors). Remaining budget decreases by the exact order total after each purchase.
Enforcement checked end-to-end: bought a $2722.00 item against bob's $3000 budget (left
$278.00), then attempted a $2672.00 item — blocked with "That order is $2672.00 but you
only have $278.00 left in your budget," remaining budget unchanged, nothing written to
`orders`/`order_items`.

## Reproducibility note

Built and tested against Python 3.13.12. Package versions in `requirements.txt`: Flask
3.1.3, Flask-Login 0.6.3, pymongo 4.17.0, python-dotenv 1.2.2 (Werkzeug, Jinja2, and
dnspython come along as dependencies of those). `pytest` 9.1.1 is a test-only dependency,
not in `requirements.txt` (install separately: `pip install pytest`). Installed into a
project-local `.venv` (gitignored), not the system/conda Python:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1        # or: source .venv/Scripts/activate  (Git Bash)
pip install -r requirements.txt
```

## Owner

Mariana Velasque Borges, CSIRO. No coding background — Claude is responsible for technology
choices and implementation. Explanations should stay in plain English; code should stay simple
and well-organised over clever.
