# Requirements — Furniture Shop Buyer App

What the app needs to do. See `architecture.md` for how it's built.

## Purpose

A buyer-facing web app for a furniture shop: log in, browse the catalogue, build an order
across multiple products, and stay within a set budget.

## User roles

Each buyer logs in with their own account and has an individual budget ceiling. Demo accounts
live in `auth.py` (`DEMO_USERS`) — replace before using this with anything real.

## Functional requirements

### 1. Login
- Buyer logs in with username and password.
- Each account has its own budget.

### 2. Browse the catalogue
- Products shown as a grid of cards: photo, name, price, description.
- Replaces the current plain table + colour-swatch view.

### 3. Build an order (multi-select)
- Buyer can select several different products, one at a time, each with its own quantity,
  and add each to an in-progress order — like a shopping cart.
- Replaces the current one-product-at-a-time dropdown form.

### 4. Review and submit the order
- A dedicated "Your Order" page/tab lists everything added so far: item, quantity, line
  total, running total, remaining budget.
- Buyer can remove an item or change its quantity before submitting.
- One "Submit order" action places the whole order at once.

### 5. Budget enforcement
- An order (or an addition to one) that would exceed the buyer's budget is blocked, with a
  clear message.
- An order that exactly uses the remaining budget is allowed (boundary case).
- This is the same rule the app already enforces per line item — it now applies to the
  order/cart total.

### 6. Order history
- "My Orders" tab: past orders with date, items, quantities, and totals.

## Non-functional / design requirements

### Visual style
- Clean, modern, e-commerce-like — Squarespace-inspired, not a copy of any specific site.
- Generous white space, large clear product photography, simple typography, minimal visual
  clutter, card-based layout, subtle hover states, muted/neutral colour palette.
- Replaces the current default-Shiny "dashboard" look.

### Product photography
- One photo per product, consistent size and aspect ratio across all cards.
- Resolved: real photos come from the shared MongoDB furniture catalogue (762 IKEA
  products), synced into our own database — see `architecture.md`.

### Platform
- Moves to Python (Flask + Jinja2 templates), replacing the original build's R + Shiny
  choice — chosen specifically for direct HTML/CSS control over the card-grid, photo-led
  catalogue and cart (see `architecture.md` for the reasoning).
- Stays SQLite for storage.

### Scale
- Hackathon/demo scale: a handful of concurrent buyers. No high-traffic requirement.

### Deployment / accessibility
- Must be reachable by someone outside the local network, not just `localhost` — resolved
  via an ngrok tunnel for the hackathon demo (see `architecture.md`). Not a persistent
  deployment: the public URL only stays live while both the app and the tunnel keep running.
- Exposes a lightweight, unauthenticated health-check endpoint so a tunnelling or
  monitoring tool has something to confirm the app is actually up.

## Out of scope (for now)

- Real payment processing.
- An admin UI for adding/editing products (the catalogue is seeded in code).
- Multiple photos per product, photo zoom, or galleries.
- Guest checkout without login.
- Inventory/stock tracking (stock is assumed unlimited).

## Open questions

Decisions still needed:

- **Quantity** — adjustable on the catalogue card itself, or only after the item is in the
  order/cart page?
- **Cart persistence** — should an in-progress order survive a logout/login, or is it fine
  for it to reset each session?
