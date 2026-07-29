"""One-off sync: load the shared MongoDB furniture catalogue into our own database,
replacing whatever is currently in the `products` table (placeholders or a previous sync).

Read-only against MongoDB — this never writes back to it. Run it again any time to
refresh the local catalogue from the source.

Usage: python sync_catalogue.py
"""

import base64
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.read_preferences import ReadPreference

import db

load_dotenv()

STATIC_IMAGES_DIR = Path(__file__).parent / "static" / "images"
MIME_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png"}


def safe_filename(item_id):
    return re.sub(r"[^A-Za-z0-9_-]", "_", item_id)


def build_description(doc):
    """A short, human-readable description built from the fields the source data
    actually has (there's no free-text description field to draw on)."""
    parts = [doc["category"]]
    colours = doc.get("colours") or []
    if colours:
        parts.append(f"in {', '.join(colours)}")
    description = " ".join(parts) + "."

    dims = [
        f"{doc[key]:g}cm {label}"
        for key, label in (("width", "wide"), ("depth", "deep"), ("height", "high"))
        if doc.get(key)
    ]
    if dims:
        description += " " + ", ".join(dims).capitalize() + "."
    return description


def save_image(doc):
    """Decode the embedded base64 image (the `image_url` field is misleadingly named —
    it holds raw image bytes, not a URL) to a real file, and return its static path."""
    ext = MIME_EXTENSIONS.get(doc["image_mime_type"], "jpg")
    filename = f"{safe_filename(doc['item_id'])}.{ext}"
    STATIC_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    (STATIC_IMAGES_DIR / filename).write_bytes(base64.b64decode(doc["image_url"]))
    return f"images/{filename}"


def main():
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise SystemExit("Set MONGODB_URI in .env before running this script (see .env.example).")

    print("Connecting to MongoDB...")
    # This shared cluster currently has no primary (secondaries only) — read_preference
    # must say so explicitly, or the default (primary) read fails with
    # ServerSelectionTimeoutError even though the secondaries are reachable.
    client = MongoClient(
        mongo_uri,
        read_preference=ReadPreference.SECONDARY_PREFERRED,
        serverSelectionTimeoutMS=8000,
    )
    catalog = client.get_default_database()["catalog"]
    documents = list(catalog.find())
    print(f"Fetched {len(documents)} products from the `catalog` collection.")

    db.init_shop_db()

    products = []
    for i, doc in enumerate(documents, start=1):
        products.append({
            "item_id": doc["item_id"],
            "name": doc["product_name"],
            "category": doc["category"],
            "price": doc["price"],
            "description": build_description(doc),
            "image_path": save_image(doc),
            "product_url": doc.get("link"),
        })
        if i % 100 == 0 or i == len(documents):
            print(f"  processed {i}/{len(documents)}")

    db.replace_products(products)
    print(f"Done. {len(products)} products loaded into {db.SHOP_DB_PATH}.")


if __name__ == "__main__":
    main()
