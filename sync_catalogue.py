"""One-off sync: decode product photos from the shared, read-only MongoDB furniture
catalogue into local files under `static/images/`, keyed by `item_id`.

Product name/category/price come live from the real event API instead (see
`furniture_api.get_catalogue()`) — this script only supplies photos, since that API's
`search-index` endpoint never returns them. Uses the shared `MONGODB_URI` credential — not
the personal `FURNITURE_API_KEY`, which is unrelated and stays scoped to balance/orders.

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


def get_client():
    """A MongoClient for the shared catalog cluster, or None if MONGODB_URI isn't set.

    read_preference is set explicitly to SECONDARY_PREFERRED because this shared cluster
    currently has no primary (secondaries only) — the default (primary) read fails with
    ServerSelectionTimeoutError even though the secondaries are reachable.
    """
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        return None
    return MongoClient(
        mongo_uri,
        read_preference=ReadPreference.SECONDARY_PREFERRED,
        serverSelectionTimeoutMS=8000,
    )


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
    print("Connecting to MongoDB...")
    client = get_client()
    if client is None:
        raise SystemExit("Set MONGODB_URI in .env before running this script (see .env.example).")
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
