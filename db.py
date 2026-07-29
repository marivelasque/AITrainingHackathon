"""Shop database: products, orders, order_items. No Flask dependency."""

import sqlite3
from pathlib import Path
from urllib.parse import quote

DATA_DIR = Path(__file__).parent / "data"
SHOP_DB_PATH = DATA_DIR / "flask_shop.sqlite"

# Placeholder catalogue until a real product feed is connected (see requirements.md).
PLACEHOLDER_PRODUCTS = [
    ("Bergen 3-Seater Sofa", "Sofas", 1299.00, "Three-seater sofa in grey wool blend fabric."),
    ("Kobe Armchair", "Sofas", 649.00, "Compact armchair with oak legs."),
    ("Nordvik Coffee Table", "Tables", 249.00, "Round coffee table in solid oak."),
    ("Aalto Dining Table", "Tables", 899.00, "Extendable dining table, seats up to 8."),
    ("Lund Dining Chair", "Chairs", 129.00, "Upholstered dining chair with beech frame."),
    ("Tromso Bookshelf", "Storage", 379.00, "Five-shelf bookcase in white oak veneer."),
    ("Espen Wardrobe", "Storage", 699.00, "Two-door wardrobe with hanging rail and shelves."),
    ("Skagen Bed Frame", "Bedroom", 999.00, "Queen-size bed frame with upholstered headboard."),
    ("Halden Floor Lamp", "Lighting", 89.00, "Adjustable floor lamp with linen shade."),
    ("Rovaniemi Sideboard", "Storage", 549.00, "Sideboard with three drawers and cabinet storage."),
    ("Malmo Bar Stool", "Chairs", 99.00, "Counter-height bar stool with footrest."),
    ("Kiruna TV Unit", "Storage", 429.00, "TV unit with cable management, fits up to 65-inch screens."),
]


def _placeholder_image(name):
    """A warm-toned placeholder tile standing in for a real product photo."""
    return f"https://placehold.co/500x350/e8e2d9/6b5544?text={quote(name)}"


def get_shop_conn():
    conn = sqlite3.connect(SHOP_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_shop_db():
    DATA_DIR.mkdir(exist_ok=True)
    conn = get_shop_conn()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                item_id TEXT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT NOT NULL,
                image_path TEXT NOT NULL,
                product_url TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                ordered_at TEXT NOT NULL,
                order_total REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id),
                product_id INTEGER NOT NULL REFERENCES products(id),
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL
            )
        """)

        already_seeded = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if already_seeded == 0:
            conn.executemany(
                "INSERT INTO products (name, category, price, description, image_path) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (name, category, price, description, _placeholder_image(name))
                    for name, category, price, description in PLACEHOLDER_PRODUCTS
                ],
            )
    conn.close()


def replace_products(products):
    """Wipe the catalogue and load a new one (e.g. from sync_catalogue.py).

    Each item in `products` is a dict with keys: item_id, name, category, price,
    description, image_path, product_url.
    """
    conn = get_shop_conn()
    with conn:
        conn.execute("DELETE FROM products")
        conn.executemany(
            "INSERT INTO products (item_id, name, category, price, description, image_path, product_url) "
            "VALUES (:item_id, :name, :category, :price, :description, :image_path, :product_url)",
            products,
        )
    conn.close()


def get_products():
    """All products in the catalogue."""
    conn = get_shop_conn()
    rows = conn.execute("SELECT * FROM products ORDER BY category, name").fetchall()
    conn.close()
    return rows


def get_product(product_id):
    """A single product by id, or None if it doesn't exist."""
    conn = get_shop_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return row


def place_order(username, product_id, quantity=1):
    """Record a one-line order. Returns the new order id, or None if the product is unknown."""
    product = get_product(product_id)
    if product is None:
        return None

    order_total = product["price"] * quantity
    conn = get_shop_conn()
    with conn:
        cursor = conn.execute(
            "INSERT INTO orders (username, ordered_at, order_total) VALUES (?, datetime('now'), ?)",
            (username, order_total),
        )
        order_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total) "
            "VALUES (?, ?, ?, ?, ?)",
            (order_id, product_id, quantity, product["price"], order_total),
        )
    conn.close()
    return order_id


def get_orders(username):
    """Orders placed by a given user, most recent first, each with its line items."""
    conn = get_shop_conn()
    orders = conn.execute(
        "SELECT * FROM orders WHERE username = ? ORDER BY id DESC", (username,)
    ).fetchall()

    result = []
    for order in orders:
        items = conn.execute(
            """
            SELECT order_items.*, products.name AS product_name
            FROM order_items
            JOIN products ON products.id = order_items.product_id
            WHERE order_items.order_id = ?
            """,
            (order["id"],),
        ).fetchall()
        result.append({"order": order, "line_items": items})

    conn.close()
    return result
