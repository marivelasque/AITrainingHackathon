# CLAUDE.md — Furniture Shop Buyer App

## Project

Day 1 build for a hackathon. A buyer-facing web app for a furniture shop.

**Core flow:**

- User logs in.
- User browses a product catalogue (furniture items: name, price, image, description).
- User places orders, tracked against a set budget (running total shown, cannot exceed budget).

## Tech stack

- **R + Shiny** — the whole app (UI and logic) is one language, matching the R > Bash > Python
  preference and avoiding a separate JavaScript frontend.
- **SQLite** (`RSQLite`/`DBI`) — file-based database, no server to install or configure.
- **shinymanager** — adds the login screen and stores hashed credentials in their own SQLite
  file, separate from shop data. Avoids hand-rolled authentication.

Trade-off: Shiny reads as a dashboard rather than a polished storefront. Acceptable for a Day 1
functional MVP; can be restyled later.

## Folder structure

```
app.R                     # entry point — run this to start the app
R/
├── ui.R                  # what the user sees (catalogue, order form, orders tab)
├── server.R              # app logic (budget checks, placing orders)
├── db.R                  # shop database: products/orders (no Shiny dependency, unit-tested)
└── auth.R                # shinymanager login setup + demo user accounts
data/
├── shop.sqlite           # products + orders (gitignored, regenerated on first run)
└── credentials.sqlite    # login credentials (gitignored, regenerated on first run)
www/images/               # (unused — product images are CSS colour swatches, not files)
tests/
├── testthat.R            # test runner
└── testthat/test-budget.R
```

## Running it

```r
# from the project root, in R or RStudio:
shiny::runApp("app.R")
```

First run creates `data/shop.sqlite` (seeded with 12 sample furniture products) and
`data/credentials.sqlite` (demo accounts below). Both files are gitignored — delete them to
reset to a clean demo state.

**Demo accounts** (`R/auth.R`, `DEMO_CREDENTIALS`) — replace before using with anything real:

| user  | password | budget |
|-------|----------|--------|
| alice | alice123 | $5000  |
| bob   | bob123   | $3000  |
| carla | carla123 | $8000  |

## Tests

```r
# from the project root:
Rscript tests/testthat.R
```

Covers the budget-limit logic (`can_afford()`, `place_order()`): affordable orders succeed,
over-budget orders are blocked and not recorded, boundary case (order exactly equal to remaining
budget) succeeds, unknown product and invalid quantity are rejected.

## Verified working (2026-07-29)

Full login → browse catalogue → place order → budget updates → order appears in "My Orders" →
over-budget order blocked flow, driven headlessly via Playwright against a live `runApp()`
instance. Zero console errors. 10/10 unit tests passing.

## Reproducibility note

Built and tested against R 4.6.0. Package versions in use: shiny 1.14.0, shinymanager 1.1.0,
DBI 1.3.0, RSQLite 3.52.0, testthat 3.3.2. No `renv` lockfile yet — skipped for Day 1 speed
(teammates can `shiny::runApp()` immediately without a `renv::restore()` step first). Worth
adding `renv::init()` once the app stabilises past the hackathon.

## Owner

Mariana Velasque Borges, CSIRO. No coding background — Claude is responsible for technology
choices and implementation. Explanations should stay in plain English; code should stay simple
and well-organised over clever.
