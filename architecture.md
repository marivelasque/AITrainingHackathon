# Architecture — Furniture Shop Buyer App

How the app is built, and what's still ahead to reach the full sleek, photo-led catalogue
and cart described in `requirements.md`.

## Previous version (R + Shiny, removed)

Day 1 started as an R + Shiny app: one language for UI and logic, SQLite via `DBI`/
`RSQLite`, `shinymanager` for login. It was a complete, tested app — login, single-product
ordering, budget enforcement, order history — but was replaced partway through Day 1: a
real photo card grid, hover states, and a snappy multi-select cart meant writing raw
HTML/CSS against Shiny's reactive component model rather than with it. See
`requirements.md` for the full reasoning.

The R version has been removed from the working tree. It's recoverable from git history
(`git log`, then `git checkout <commit> -- app.R R/ tests/`) if ever needed for reference —
its budget-enforcement logic (`can_afford()`) in particular is a direct model for the
Python equivalent described below, once that's built.

## Stack

- **Flask** — Python micro web framework: routes, request handling, sessions.
- **Jinja2** (bundled with Flask) — server-rendered HTML templates.
- **SQLite**, via Python's built-in `sqlite3` — file-based database, no server to install
  or run.
- **Flask-Login** + `werkzeug.security` (bundled with Flask) — session-based login and
  password hashing. The shop-data/credentials database split carries over from the
  original design.
- Hand-written CSS (`static/style.css`) for the card grid and overall look — no CSS/JS
  framework.
- **pymongo** + **python-dotenv** — used only by `sync_catalogue.py`, a one-off/on-demand
  script that loads the shared training MongoDB catalogue into SQLite. The running Flask
  app never talks to MongoDB directly; it only ever reads the local SQLite `products`
  table, so the app doesn't depend on that external database being reachable.

## File structure

```text
app.py                       # entry point — Flask app, routes
db.py                        # SQLite access: products, orders, order_items
auth.py                      # Flask-Login setup, password hashing, demo user accounts
sync_catalogue.py            # one-off: load the MongoDB catalogue into SQLite, replacing placeholders
.env                          # MONGODB_URI (gitignored; see .env.example for the shape)
templates/
├── base.html                 # shared layout: nav, flash messages
├── login.html
├── catalogue.html            # home page — product card grid
└── orders.html               # "My Orders" page
static/
├── style.css                 # card grid, hover states, colour palette
└── images/                   # product photos decoded by sync_catalogue.py (gitignored)
data/
├── flask_shop.sqlite         # products + orders (gitignored, regenerated on first run)
└── flask_credentials.sqlite  # login credentials (gitignored, regenerated on first run)
```

One file per responsibility, same shape the R version used.

## Data model

```mermaid
classDiagram
    class Customer {
        String username
        Number budget
    }

    class Product {
        Number id
        String itemId
        String name
        String category
        Number price
        String description
        String imagePath
        String productUrl
    }

    class Order {
        Number id
        String username
        DateTime orderedAt
        Number orderTotal
    }

    class OrderItem {
        Number id
        Number quantity
        Number unitPrice
        Number lineTotal
    }

    Customer "1" --> "0..*" Order : places
    Order "1" *-- "1..*" OrderItem : contains
    OrderItem "0..*" --> "1" Product : refers to
```

Four things the app needs to remember, in plain English:

- **Customer** — a logged-in buyer: their username and their budget ceiling. Their password
  isn't shown here — that's handled by Flask-Login and a separate credentials database.
- **Product** — one catalogue item: name, category, price, description, and a photo. The
  `itemId` and `productUrl` fields are the source catalogue's own product code and a link
  back to its original listing — carried through as-is rather than invented.
- **Order** — one submitted "shopping trip": who placed it, when, and its total.
- **OrderItem** — one product within an order, and how many of it — e.g. "2 × Lund Dining
  Chair" on a particular order. One Order can have several OrderItems, each pointing at a
  different Product — this is what makes multi-product orders possible once they're built
  (see Still ahead, below; today each order only ever has one OrderItem).

How they connect:

- A **Customer places** any number of **Orders** over time — that's their order history.
- An **Order contains** one or more **OrderItems**. An order can't be empty, and an item
  can't exist without its order (shown as the filled diamond).
- Each **OrderItem refers to** exactly one **Product**, but keeps its own `quantity` and
  `unitPrice` rather than looking the price up fresh each time — so a later catalogue price
  change can't silently rewrite the value of a past order.

**Deliberately not modelled: a cart.** Nothing today holds an in-progress, multi-item
selection — "Add to order" places a complete one-item Order immediately. A real cart would
live in the Flask session (a signed cookie holding `{product_id: quantity}`) until
submitted, at which point it becomes an Order plus its OrderItems, same as today. If it's
later decided carts should survive a logout, the cart would need to persist server-side
instead, and it would become a fifth entity.

## Built so far

- Login: Flask-Login + `werkzeug` password hashing, three demo users seeded on first run.
- Catalogue: card grid, one photo/name/description/price per product, grouped into
  sections by category (17 categories across the real catalogue) — built with
  `itertools.groupby` in `app.py` over `get_products()`'s already-`category`-sorted rows,
  not a template-level grouping filter.
- **Category filter tabs**: `GET /?category=<name>` (via `db.get_products(category=...)`)
  filters to one category server-side; the "All" tab is just `GET /` with no param. The
  tab bar itself always lists every category (`db.get_categories()`), independent of
  which one is currently selected, so switching categories is a normal link, not JS.
- "Add to order": one click places a one-item order immediately, saved as one `orders` row
  plus one `order_items` row.
- "My Orders": a logged-in user's own past orders, with items and totals, read straight
  from the database.
- Two-database separation (shop data vs. credentials), matching the original design.
- **Real catalogue**: `sync_catalogue.py` connects to the shared training MongoDB instance
  (`MONGODB_URI` in `.env`, read-only, never written to), pulls its `catalog` collection —
  762 real IKEA products — and replaces whatever's in the local `products` table. Two things
  the source data needed massaging for:
  - `image_url` is a misleading field name — it's actually the image's raw bytes,
    base64-encoded, not a URL. The sync script decodes each one to a real file under
    `static/images/` and stores that file's path, rather than stuffing ~47MB of base64 text
    into SQLite (which would bloat the database and slow down every catalogue query).
  - There's no free-text description field in the source data, so `description` is
    synthesised from the fields that do exist (category, colour, dimensions) rather than
    invented.
  - Re-running the script wipes and reloads `products` from scratch, which orphans any
    existing `order_items` that reference a deleted product (its `JOIN` in `get_orders()`
    then silently drops that line from history). Not yet fixed — re-sync sparingly once
    real orders exist.
- **Remaining-budget display**: a Flask `context_processor` computes `spent` (sum of a
  user's past `order_total`s) on every request and exposes `remaining_budget` to every
  template, so the nav pill decreases immediately after each order without each route
  needing to compute it. Turns red if it goes negative.

## Still ahead

- **Budget enforcement** — remaining budget is now tracked and displayed (see Built so
  far), and turns red once negative, but nothing yet blocks the order that pushes it there.
  Needs a `can_afford()` equivalent (see the R version's, still in git history) evaluated
  before `place_order()` commits.
- **Multi-select cart** — a session cart, a review/checkout page, and a `place_cart_order()`
  that writes one `orders` row plus several `order_items` rows in a single transaction.
  Today's "Add to order" is instant and single-item; there's no cart to review first.
- **Tests** — none yet. Add a `pytest` suite once budget enforcement exists (see
  `CLAUDE.md`).

## Risks / things to know

- Multi-image or zoom galleries are explicitly out of scope in `requirements.md` — one
  photo per product keeps the image-sourcing problem manageable.
- Without a JS interactivity layer, every action (add to order, in future: cart changes)
  is a normal full-page reload — functional, but not as snappy as a single-page app would
  feel. A small `static/cart.js` using `fetch()` would recover that, as an enhancement on
  top of a working server-rendered flow, once there's a cart to make snappy.
