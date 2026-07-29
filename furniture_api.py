"""Client for the event's real furniture-shop API (balance, orders) — see requirements.md.

Separate from sync_catalogue.py, which reads the shared read-only MongoDB catalogue
instead. This module talks to the actual per-participant REST API.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ.get("FURNITURE_API_BASE_URL")
USER_ID = os.environ.get("FURNITURE_API_USER_ID")
API_KEY = os.environ.get("FURNITURE_API_KEY")


def get_balance():
    """The real, event-tracked balance for this API account.

    Returns the balance as a float, or None if it couldn't be fetched (missing config,
    network error, non-200 response) so the caller can show a fallback instead of crashing.
    """
    if not (BASE_URL and USER_ID and API_KEY):
        return None
    try:
        response = requests.get(
            f"{BASE_URL}/users/{USER_ID}",
            headers={"X-Api-Key": API_KEY},
            timeout=5,
        )
        response.raise_for_status()
        return response.json()["balance"]
    except (requests.RequestException, ValueError, KeyError):
        return None


def place_order(item_id, quantity=1):
    """Place a real order for one product through the API. This really debits the balance.

    Returns a dict with `success` (bool) and `message` (str) ready to show the user, plus
    `remaining_balance` on success.
    """
    if not (BASE_URL and USER_ID and API_KEY):
        return {"success": False, "message": "The furniture shop API isn't configured."}

    try:
        response = requests.post(
            f"{BASE_URL}/orders",
            headers={"X-Api-Key": API_KEY},
            json={"user_id": USER_ID, "items": [{"item_id": item_id, "quantity": quantity}]},
            timeout=10,
        )
    except requests.RequestException:
        return {"success": False, "message": "Couldn't reach the furniture shop API. Try again shortly."}

    if response.status_code == 200:
        try:
            data = response.json()
            return {
                "success": True,
                "message": (
                    f"Order placed: ${data['total_price']:.2f}. "
                    f"${data['remaining_balance']:.2f} left in your balance."
                ),
                "remaining_balance": data["remaining_balance"],
            }
        except (ValueError, KeyError):
            return {"success": False, "message": "The order may have gone through, but we couldn't confirm it. Check My Orders."}
    if response.status_code == 402:
        return {"success": False, "message": "Insufficient balance: that order costs more than you have left."}
    if response.status_code == 404:
        return {"success": False, "message": "This item is no longer available."}
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "a few seconds")
        return {"success": False, "message": f"Too many requests — try again in {retry_after}."}
    return {"success": False, "message": "The order couldn't be placed. Please try again."}


def get_catalogue():
    """All products from the real catalogue API, for the home page.

    Uses `/catalogue/search-index` (name, category, price only — fast, no images) rather
    than plain `/catalogue`, which embeds every product's image as base64 and can take
    20+ seconds against the real 762-product event catalogue. Paginates via `skip` in case
    the API caps how many rows a single request returns.
    """
    if not BASE_URL:
        return []
    products = []
    skip = 0
    page_size = 200
    try:
        while True:
            response = requests.get(
                f"{BASE_URL}/catalogue/search-index",
                params={"limit": page_size, "skip": skip},
                timeout=10,
            )
            response.raise_for_status()
            page = response.json()
            products.extend(page)
            if len(page) < page_size:
                break
            skip += page_size
    except (requests.RequestException, ValueError):
        return []
    return products


def get_orders():
    """This account's real order history from the API, most recent first."""
    if not (BASE_URL and USER_ID and API_KEY):
        return []
    try:
        response = requests.get(
            f"{BASE_URL}/orders/{USER_ID}",
            headers={"X-Api-Key": API_KEY},
            timeout=5,
        )
        response.raise_for_status()
        return sorted(response.json(), key=lambda order: order["timestamp"], reverse=True)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return []
