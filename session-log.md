# Session Log — Commands Run and Why

A chronological record of every command executed this session while building the Flask
version of the app, grouped by phase. File edits (Write/Edit) aren't repeated here — the
files themselves are the record of those; this log is specifically the commands *run*.
Secrets (the ngrok authtoken, the MongoDB connection string) are redacted even though they
were typed in chat, since this file can end up in git.

## 1. Environment setup

Checked what was actually available before assuming anything, then created an isolated
environment so hackathon dependencies wouldn't pollute the system/conda Python.

```bash
python --version && python -m pip --version
# → Python 3.13.12, pip 26.0.1 (miniforge). Confirmed Python was usable before planning
# a Flask rebuild around it.

python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install flask flask-login
python -m pip freeze
# → Flask 3.1.3, Flask-Login 0.6.3 (+ Werkzeug, Jinja2, blinker, click, itsdangerous,
# MarkupSafe as their dependencies). Versions recorded into requirements.txt from this
# actual output, not guessed.
```

## 2. Building and verifying the basic Flask app

After writing `db.py`, `auth.py`, `app.py`, and the templates, ran the app for real rather
than trusting it would work.

```bash
python app.py &         # background — first live run of the new app
```

Needed a way to actually click through the app rather than just curl it, since this was a
UI-heavy rebuild. No project skill for running this app existed yet, and `chromium-cli`
wasn't installed, so fell back to a plain Playwright script:

```bash
which chromium-cli                          # not found
python -c "import playwright"               # not installed either
node --version && npx --version && npx playwright --version   # Node/npx present
python -m pip install playwright
python -m playwright install chromium --with-deps
# → downloaded Chrome for Testing + headless shell (~300MB) so screenshots could be taken
```

```bash
python verify_app.py   # Playwright: login → catalogue → buy → My Orders, screenshot each step
```

First run 500'd on the Orders page. Read the Flask traceback from the background task's
log rather than guessing:

```
TypeError: 'builtin_function_or_method' object is not iterable
  File "templates/orders.html", line 17, in block 'content'
    {% for item in entry.items %}
```

Root cause: `db.py` stored each order's line items under the dict key `"items"`, and
Jinja2's `entry.items` resolved to Python's built-in `dict.items()` method instead of that
key, since dicts have a real `.items` attribute that shadows key lookup via dot notation.
Fixed by renaming the key to `line_items` in both `db.py` and `orders.html`, then re-ran
the same script to confirm:

```bash
python verify_app.py   # re-run after the fix — full flow passed, 0 console errors
```

Cleaned up afterwards so the next real run would start from a blank slate:

```bash
ls data/
rm data/flask_shop.sqlite data/flask_credentials.sqlite   # test data was only from this run
```

## 3. Removing the R + Shiny app

Once the Flask app was confirmed working, removed the superseded R version (after showing
the user exactly what would be deleted and getting confirmation).

```bash
git ls-files | grep -E "^(app\.R|R/|tests/|data/)"
# → confirmed which R files were actually git-tracked (the two R sqlite data files
# weren't — they were already correctly gitignored) before deciding rm vs git rm.

git rm --quiet app.R R/auth.R R/db.R R/server.R R/ui.R tests/testthat.R tests/testthat/test-budget.R
rm -f data/shop.sqlite data/credentials.sqlite
rmdir R tests/testthat tests 2>/dev/null   # remove the now-empty directories
git status --short   # confirm exactly 7 files staged as deleted, nothing unexpected
```

## 4. Connecting the real MongoDB catalogue

```bash
python -m pip install "pymongo[srv]" python-dotenv
python -m pip freeze | grep -iE "pymongo|dnspython|dotenv"
# → pymongo 4.17.0, dnspython 2.8.0 (needed for mongodb+srv:// URIs), python-dotenv 1.2.2
```

Wrote `.env` (gitignored) with `MONGODB_URI=<redacted>`, `.env.example` as a template, and
added `.env` / `static/images/` to `.gitignore` *before* touching anything that would write
to those paths.

Inspected the real data before writing any mapping code — didn't want to guess field names:

```bash
python inspect_mongo.py
# first attempt: KeyError: 'MONGODB_URI' — load_dotenv() with no path searches relative to
# the calling script's own location, not the shell's cwd; the inspection script lived in
# a scratch directory, not the project root. Fixed by passing the .env path explicitly.

python inspect_mongo.py   # re-run — got 3 sample docs + a 50-doc field-name sample:
# fields: _id, category, colour_count, colours, depth, height, image_mime_type, image_url,
# item_id, link, price, product_name, width. No description field.
```

```bash
python check_mongo_quality.py
# → 762 total docs, 0 missing/null across every field, 762 distinct item_id (no dupes),
# image_mime_type always "image/jpeg", one sample image_url was 83,828 base64 chars long
# (~62KB decoded) — confirmed image_url is raw image bytes, not a URL, and estimated the
# ~47MB total before deciding to decode to files rather than store base64 in SQLite.
```

Ran the real sync (after extending `db.py`'s schema and writing `sync_catalogue.py`):

```bash
python sync_catalogue.py
# → fetched 762 products, decoded + wrote 762 image files, replaced the products table.

du -sh static/images/ data/flask_shop.sqlite && ls static/images/ | wc -l
# → 68M of images, 180K database (confirms images-as-files kept the DB itself small)
python -c "import db; print(dict(db.get_products()[0]))"   # spot-checked one real row
```

Verified in a browser, not just via the sync script's own success message:

```bash
python app.py &
python verify_catalogue.py
# first pass: dozens of net::ERR_ABORTED on /static/images/*.jpg — investigated rather
# than assuming the sync was broken:
ls -la static/images/00102065.jpg && file static/images/00102065.jpg
# → file existed, correct size, valid JPEG. The aborts were Chromium cancelling in-flight
# image requests when the test script navigated away (762 images on one page take a few
# seconds) — not real breakage. Confirmed properly:
python -c "... page.wait_for_load_state('networkidle') ... naturalWidth === 0 ..."
# → 0 broken images once the page was actually given time to finish loading.
```

Cleared out the test purchase and stale credentials db afterward, kept the synced products:

```bash
python -c "
import db
conn = db.get_shop_conn()
with conn:
    conn.execute('DELETE FROM order_items')
    conn.execute('DELETE FROM orders')
"
rm -f data/flask_credentials.sqlite
```

## 5. Remaining-budget display

```bash
python app.py &
python -c "... page.locator('.budget-pill').inner_text() ..."
# → before: $2784.00 remaining of $5000.00 (alice already had order history); bought a
# $78.00 item; after: $2706.00 remaining — exact match confirmed the calculation.
```

While checking this, queried the orders table directly and noticed alice had 9 orders
(~$2216) with timestamps in rapid human-like succession that predated this session's own
test runs — flagged to the user as likely their own manual testing rather than silently
clearing it:

```bash
python -c "import db; conn = db.get_shop_conn(); [print(dict(r)) for r in conn.execute('SELECT * FROM orders ORDER BY id').fetchall()]"
```

## 6. Category grouping and filter tabs

```bash
python -c "
import db
conn = db.get_shop_conn()
for r in conn.execute('SELECT category, COUNT(*) as n FROM products GROUP BY category ORDER BY category'):
    print(r['category'], r['n'])
"
# → 17 real categories (Bar furniture, Beds, ... Wardrobes) before deciding how to group —
# informed adding a jump-nav, later upgraded to real filter tabs.
```

```bash
python app.py &
python -c "... .category-nav a ... .category-section ... jump-link scroll check ..."
# → 17 nav links, 17 sections, correct per-category counts, anchor scroll landed at the
# expected offset.
```

Noticed "Café furniture" printed as `Caf� furniture` in this terminal's own output and
verified it wasn't real data corruption before moving on:

```bash
python -c "
import db
row = db.get_shop_conn().execute(\"SELECT DISTINCT category FROM products WHERE category LIKE 'Caf%'\").fetchone()
print(row['category'].encode('utf-8'))   # → b'Caf\xc3\xa9 furniture' — correct UTF-8 for é
"
# confirmed via the browser DOM too (inner_text().encode('utf-8').hex()) — the "�" was
# this Bash terminal's own print encoding limitation, not a bug in the app.
```

After switching the jump-nav to real filter tabs (`?category=...`):

```bash
python app.py &
python -c "... click 'Chairs' tab ... assert URL == '/?category=Chairs', 117 cards, 1 section, active class ..."
python -c "... click 'All' tab again ... assert back to 762/17 sections ..."
```

## 7. Budget enforcement + test suite

```bash
python -m pip install pytest
python -m pytest tests/ -v
# → 6/6 passed: can_afford at the boundary and just past it; place_order succeeds and
# updates spend; over-budget refused and not recorded; unknown product rejected.
```

Checked real account state before designing a live (not just unit-tested) demonstration:

```bash
python -c "import db; [print(u, db.get_spent(u), len(db.get_orders(u))) for u in ('alice','bob','carla')]"
# → bob and carla were both untouched ($0 spent) — picked bob for a clean test.
python -c "import db; [print(dict(r)) for r in db.get_shop_conn().execute('SELECT id,name,price FROM products ORDER BY price DESC LIMIT 3')]"
# → found a $2722 item (under bob's $3000 budget) and a $2672 item (over what would be left)
```

```bash
python app.py &
python -c "
... buy product 754 ($2722) → 'Order placed...', remaining drops to $278.00
... buy product 586 ($2672) → 'That order is $2672.00 but you only have $278.00 left in
    your budget.', remaining STAYS at $278.00 — confirms the blocked order wrote nothing.
"
```

## 8. Public access via ngrok

```bash
which ngrok                                    # → already on PATH
find ~/ -iname "ngrok*"; find Downloads -iname "ngrok*"   # also found an unextracted zip in Downloads
ngrok version                                  # → 3.39.9 — the PATH one was real and working, used that
ngrok config add-authtoken <redacted>
# → "Authtoken saved to configuration file: C:\Users\vel044\AppData\Local\ngrok\ngrok.yml"
# (ngrok's own config directory — never written into this repo)
```

Diagnosed the reported "ngrok not working" issue before touching anything:

```bash
curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/health   # → 404
netstat -ano | grep ":5000"                                            # → something WAS listening
# → the app was fine; it simply never had a /health route. Added one (no @login_required,
# since health checks shouldn't need a session), confirmed the running dev server's
# auto-reloader picked it up without a manual restart:
curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/health   # → 200
```

```bash
ngrok http 5000 --log stdout > /tmp/ngrok.log &
disown
sleep 3
curl -s http://127.0.0.1:4040/api/tunnels
# → public_url: https://almighty-pessimist-vanilla.ngrok-free.dev
curl -sS -o /dev/null -w "%{http_code}" https://almighty-pessimist-vanilla.ngrok-free.dev/health
# → 200 — confirmed end-to-end through the tunnel, not just localhost, before handing the
# URL back.
```
