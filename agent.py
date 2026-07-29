"""AI shopping-assistant agent: tool-calling over furniture_api.py via Azure OpenAI."""

import json
import os

from openai import APIError, AzureOpenAI

import furniture_api

DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT")

SYSTEM_PROMPT = (
    "You are a friendly shopping assistant for a furniture shop. You have four tools: "
    "search_catalogue, get_product_detail, check_balance, and place_order.\n\n"
    "- search_catalogue only filters by exact category name (case-insensitive). It has "
    "no price, colour, or fuzzy-match filter. For requests like 'cheap', 'under $X', or "
    "a colour, call search_catalogue yourself, then judge which results fit by reading "
    "the price and colours fields it returns.\n"
    "- Before calling place_order, always state the exact product name and price you're "
    "about to buy, and ask the user to confirm. Only call place_order after the user's "
    "next message clearly confirms (e.g. 'yes', 'confirm', 'go ahead'). Never call "
    "place_order straight off a request without this confirmation step first.\n"
    "- If place_order fails with insufficient balance, tell the user plainly and suggest "
    "they look for something cheaper. If it fails because the item no longer exists, "
    "tell them plainly and offer to search for something similar instead. Never show a "
    "raw error message or status code.\n"
    "- Keep replies short and conversational."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalogue",
            "description": (
                "Search the furniture catalogue by exact category name to browse or "
                "narrow down products; returns item_id, name, price, category, and "
                "colours for each match. Omit category to return everything. Category "
                "matching is exact (case-insensitive) only — no price, colour, or "
                "free-text filtering happens here; reason over the returned list "
                "yourself for anything like 'cheap' or a specific colour."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Exact category name, e.g. 'Chairs'. Omit to get every product.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_detail",
            "description": (
                "Get full detail for one specific product you already have the item_id "
                "for (e.g. from a prior search_catalogue result). Not for browsing or "
                "searching — it needs a known item_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "The product's item_id."},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_balance",
            "description": "Check how much money the current logged-in user has left to spend.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": (
                "Buy one specific item (by item_id) for the current user. This really "
                "debits their real balance — only call this after the user has "
                "explicitly confirmed the exact item and price."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "description": "The product's item_id to buy."},
                    "quantity": {"type": "integer", "description": "How many to buy. Defaults to 1."},
                },
                "required": ["item_id"],
            },
        },
    },
]


def _search_catalogue(category=None):
    products = furniture_api.get_catalogue()
    if category:
        products = [p for p in products if p["category"].lower() == category.lower()]
    return products


def _get_product_detail(item_id):
    detail = furniture_api.get_product_detail(item_id)
    if detail is None:
        return {"error": "That product doesn't exist or couldn't be fetched."}
    return {k: v for k, v in detail.items() if k not in ("image_url", "image_mime_type")}


def _check_balance():
    balance = furniture_api.get_balance()
    if balance is None:
        return {"error": "Couldn't fetch the balance right now."}
    return {"balance": balance}


def _place_order(item_id, quantity=1):
    return furniture_api.place_order(item_id, quantity=quantity)


TOOL_FUNCTIONS = {
    "search_catalogue": _search_catalogue,
    "get_product_detail": _get_product_detail,
    "check_balance": _check_balance,
    "place_order": _place_order,
}

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
    return _client


def run_agent_turn(history, user_message):
    """Run one full agent turn: append the user's message, let the model call tools as
    many times as it needs (capped), and return the complete updated history including
    the final plain-text assistant reply.
    """
    messages = history + [{"role": "user", "content": user_message}]
    client = _get_client()

    for _ in range(4):
        try:
            response = client.chat.completions.create(
                model=DEPLOYMENT,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                tools=TOOLS,
            )
        except APIError:
            messages.append({
                "role": "assistant",
                "content": "Sorry, I couldn't reach the AI service right now. Try again shortly.",
            })
            return messages

        message = response.choices[0].message

        if not message.tool_calls:
            messages.append({"role": "assistant", "content": message.content})
            return messages

        tool_calls = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in message.tool_calls
        ]
        messages.append({"role": "assistant", "content": message.content, "tool_calls": tool_calls})

        for tc in message.tool_calls:
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            result = TOOL_FUNCTIONS[tc.function.name](**args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    messages.append({
        "role": "assistant",
        "content": "Sorry, that took too many steps — could you rephrase your request?",
    })
    return messages
