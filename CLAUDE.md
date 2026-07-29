# CLAUDE.md — Furniture Shop Buyer App

## Project

Day 1 build for a hackathon. A buyer-facing web app for a furniture shop.

**Core flow:**

- User logs in (local demo account — see Demo accounts, below).
- User browses a product catalogue (762 real IKEA furniture products) pulled live from the
  event's own furniture-shop REST API: category, name, price per product. No photos on this
  page — the fast `search-index` endpoint this uses doesn't return them (see `furniture_api.py`).
- User places orders. These are real orders against the event's shared training API: it
  really debits a real per-account balance. Remaining budget is read live from that same
  API and shown in the nav; an order that would exceed it is blocked by the API itself
  (`402`) with a clear message and never recorded locally. See Tests, below.

**Important:** every demo login shares the *same* real balance and order history, because
the app's real budget/orders/catalogue all go through one API key (`FURNITURE_API_KEY` in
`.env`). The local per-demo-user `budget` column in `auth.py` is vestigial — it's no longer
read anywhere; only which account you log in as changes, not whose money you spend.

## Documentation habit

Whenever a configuration change lands (new data source, new external service, new env var,
swapping which system is authoritative for something), update `README.md`, `architecture.md`,
and `requirements.md` in the same pass — don't leave them describing the old wiring.

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
- **requests** — HTTP client `furniture_api.py` uses to call the event's real
  furniture-shop REST API: live catalogue search, balance, orders.
- **pymongo** + **python-dotenv** — `pymongo` is only used by `sync_catalogue.py`, a legacy/
  optional script (see Folder structure) that is no longer part of the running app's
  catalogue path. `python-dotenv` loads `.env` for both that script and `furniture_api.py`.

## Folder structure

```text
app.py                       # entry point — run this to start the app
furniture_api.py             # client for the event's real REST API — catalogue, balance, orders
db.py                        # local shop database (no Flask dependency) — see note below
auth.py                      # Flask-Login setup, password hashing, demo user accounts
sync_catalogue.py            # legacy/optional: load the shared MongoDB catalogue into SQLite
.env                          # FURNITURE_API_BASE_URL/USER_ID/KEY, MONGODB_URI (gitignored — see .env.example)
templates/
├── base.html                 # shared layout: nav, flash messages
├── login.html
├── catalogue.html            # home page — live product grid from furniture_api.get_catalogue()
└── orders.html               # "My Orders" page — from furniture_api.get_orders()
static/
├── style.css                 # card grid, hover states, colour palette
└── images/                   # unused by the running app now (sync_catalogue.py's legacy output)
data/
├── flask_shop.sqlite         # legacy local catalogue/orders — only touched by tests/test_budget.py now
└── flask_credentials.sqlite  # login credentials (gitignored, regenerated on first run)
tests/
└── test_budget.py            # can_afford() / place_order() — pytest, against db.py's local logic
requirements.md               # what the app needs to do
architecture.md               # how it's built, including the Customer/Product/Order/OrderItem data model
```

**Note on `db.py`/`sync_catalogue.py`:** the running app no longer uses these for the
catalogue, budget, or orders — that's all live through `furniture_api.py` now (see Core
flow, above). They're kept because `tests/test_budget.py` still exercises `db.py`'s local
`can_afford()`/`place_order()` as a pure-function unit test of the budget rule itself,
independent of the real API being reachable.

## Running it

```powershell
.venv\Scripts\Activate.ps1     # or: source .venv/Scripts/activate  (Git Bash)
python app.py
```

Open `http://127.0.0.1:5000`. First run creates `data/flask_credentials.sqlite` (demo
accounts below) and a `data/flask_shop.sqlite` that the running app no longer reads from
(see the `db.py` note above) — both gitignored.

**Required for the catalogue/balance/orders to actually work:** set
`FURNITURE_API_BASE_URL`, `FURNITURE_API_USER_ID`, and `FURNITURE_API_KEY` in `.env` (copy
`.env.example`) — the real event API credentials. Without these, `furniture_api.py`'s
functions return empty/`None` and the app degrades gracefully (empty catalogue, no
balance shown) rather than crashing.

`MONGODB_URI` + `python sync_catalogue.py` still work (legacy path: loads the shared
training MongoDB catalogue into the local, now-unused `products` table) but nothing in the
running app reads that table for the catalogue anymore — the home page is always live from
the real API's `search-index` endpoint.

**Demo accounts** (`auth.py`, `DEMO_USERS`) — replace before using with anything real. The
`budget` column is vestigial (see Core flow, above) — every account shares the one real
balance behind `FURNITURE_API_KEY`:

| user  | password |
| --- | --- |
| alice | alice123 |
| bob   | bob123   |
| carla | carla123 |

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

## Verified working (2026-07-29, catalogue → live API)

Home page swapped from the local placeholder/synced SQLite catalogue to
`furniture_api.get_catalogue()` (paginated `GET /catalogue/search-index`, not plain
`/catalogue` — the guide's own warning about the latter embedding base64 images and being
much slower). Logged in as bob against a live `python app.py`: home page loaded all 762
real products across 17 categories (category, name, price per card, no photos), bought a
$78.00 bar stool, and it showed up correctly on "My Orders" with the real API confirming
the order. `db.py`/`tests/test_budget.py` untouched — they exercise the local budget
function in isolation and don't depend on the catalogue source.

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
