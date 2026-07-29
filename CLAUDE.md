# CLAUDE.md — Furniture Shop Buyer App

## Project

Day 1 build for a hackathon. A buyer-facing web app for a furniture shop.

**Core flow:**

- User logs in.
- User browses a product catalogue (furniture items: name, price, photo, description).
- User places orders, saved against their account. Budget is tracked per user but not yet
  enforced — see Tests, below.

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

## Folder structure

```text
app.py                       # entry point — run this to start the app
db.py                        # shop database: products, orders, order_items (no Flask dependency)
auth.py                      # Flask-Login setup, password hashing, demo user accounts
templates/
├── base.html                 # shared layout: nav, flash messages
├── login.html
├── catalogue.html            # home page — product card grid
└── orders.html               # "My Orders" page
static/
└── style.css                 # card grid, hover states, colour palette
data/
├── flask_shop.sqlite         # products + orders (gitignored, regenerated on first run)
└── flask_credentials.sqlite  # login credentials (gitignored, regenerated on first run)
requirements.md               # what the app needs to do
architecture.md               # how it's built, including the Customer/Product/Order/OrderItem data model
```

## Running it

```powershell
.venv\Scripts\Activate.ps1     # or: source .venv/Scripts/activate  (Git Bash)
python app.py
```

Open `http://127.0.0.1:5000`. First run creates `data/flask_shop.sqlite` (seeded with 12
placeholder furniture products) and `data/flask_credentials.sqlite` (demo accounts below).
Both files are gitignored — delete them to reset to a clean demo state.

**Demo accounts** (`auth.py`, `DEMO_USERS`) — replace before using with anything real:

| user  | password | budget |
| --- | --- | --- |
| alice | alice123 | $5000  |
| bob   | bob123   | $3000  |
| carla | carla123 | $8000  |

## Tests

None yet. The R version had a full `testthat` suite for the budget-limit logic
(`can_afford()`/`place_order()`); that logic hasn't been ported because budget enforcement
itself isn't wired up in the Flask version yet (see Verified working, below). Add a
`pytest` suite alongside whichever function replaces the current one-line `place_order()`
once that lands — same cases as the R suite: affordable orders succeed, over-budget orders
are blocked and not recorded, the exact-remaining-budget boundary case succeeds, unknown
product and invalid quantity are rejected.

## Verified working (2026-07-29)

Login → catalogue (12 placeholder products, card grid with photos) → "Add to order" saves
an order → order appears on "My Orders" with the correct item and total, driven headlessly
via Playwright against a live `python app.py` instance. Zero console errors. Budget shows
per user but is not yet enforced — an order can currently be placed for more than the
budget allows.

## Reproducibility note

Built and tested against Python 3.13.12. Package versions in `requirements.txt`: Flask
3.1.3, Flask-Login 0.6.3 (Werkzeug and Jinja2 come along as Flask's own dependencies).
Installed into a project-local `.venv` (gitignored), not the system/conda Python:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1        # or: source .venv/Scripts/activate  (Git Bash)
pip install -r requirements.txt
```

## Owner

Mariana Velasque Borges, CSIRO. No coding background — Claude is responsible for technology
choices and implementation. Explanations should stay in plain English; code should stay simple
and well-organised over clever.
