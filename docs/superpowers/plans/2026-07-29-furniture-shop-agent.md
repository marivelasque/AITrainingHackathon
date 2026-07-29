# Furniture Shop Chat Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/ask` chat page where a logged-in buyer types plain-English requests
("find me a cheap mustard chair", "buy the first one") and an Azure-OpenAI-backed agent
picks the right furniture-shop API action, reasoning over plain results for anything the
API can't filter on itself.

**Architecture:** A new `agent.py` module owns four tool schemas, four tool-dispatch
wrappers around the existing `furniture_api.py`, and a `run_agent_turn()` loop against
Azure OpenAI's native tool-calling. A new `/ask` Flask route stores the conversation in
`session["chat_history"]` so multi-turn references ("the first one") and the
confirm-before-buying flow both work across requests.

**Tech Stack:** `openai` Python package (`AzureOpenAI` client, native `tools=[...]`
tool-calling), Flask session (existing signed-cookie session, same one `Flask-Login`
already uses), Jinja2 template matching the existing card/colour design in
`static/style.css`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-29-furniture-shop-agent-design.md` — every task
  below implements one section of it.
- `place_order` is never called by the agent without the user first confirming the exact
  item and price in a prior assistant turn (two-turn chat confirmation, prompt-enforced).
- Tool results going back to the model must never include a product's base64 image
  (`image_url`/`image_mime_type`) — strip it in the wrapper, not the prompt.
- All Azure OpenAI config comes from `.env` (`AZURE_OPENAI_ENDPOINT`,
  `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY`) — already
  present, confirmed working with a live test call during planning. Never hardcode these.
- New chat UI must visually match the existing app (`static/style.css`'s `--bg`, `--ink`,
  `--muted`, `--accent`, `--accent-dark`, `--card`, `--border` variables) — no bare
  unstyled form.
- Match existing code conventions: `furniture_api.py` functions have no unit tests in
  this repo (verified live against the real API instead, per `session-log.md`) — don't
  add one now either. `agent.py`'s tool wrappers *do* get unit tests, per the spec's
  Testing section.

---

### Task 1: `furniture_api.get_product_detail()` + `openai` dependency

**Files:**
- Modify: `requirements.txt`
- Modify: `furniture_api.py` (add function after `get_catalogue`, before `get_orders`)

**Interfaces:**
- Produces: `furniture_api.get_product_detail(item_id: str) -> dict | None` — full
  product detail (`item_id`, `product_name`, `price`, `category`, `colours`,
  `colour_count`, `width`, `height`, `depth`, `image_url`, `image_mime_type`, `link`), or
  `None` if the item doesn't exist or the request fails. `image_url` here is the raw
  base64 image (large) — callers that pass this to an LLM must strip it (see Task 2).

- [ ] **Step 1: Add the pinned dependency**

Already installed into `.venv` during planning (confirmed working against the real Azure
deployment). Add the same pinned version to `requirements.txt`:

```text
Flask==3.1.3
Flask-Login==0.6.3
pymongo==4.17.0
python-dotenv==1.2.2
requests==2.34.2
openai==2.50.0
```

- [ ] **Step 2: Add `get_product_detail` to `furniture_api.py`**

Insert immediately after `get_catalogue()` (before `def get_orders():`):

```python
def get_product_detail(item_id):
    """Full detail for one specific product — GET /catalogue/{item_id}. No auth needed
    (catalogue endpoints are public). Includes the product's image as raw base64 in
    `image_url` — callers passing this to an LLM must strip that field first.

    Returns the full detail dict, or None if the item doesn't exist or the request fails.
    """
    if not BASE_URL:
        return None
    try:
        response = requests.get(f"{BASE_URL}/catalogue/{item_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None
```

- [ ] **Step 3: Verify live against the real API**

Run:

```bash
.venv/Scripts/python.exe -c "
import furniture_api
print(furniture_api.get_product_detail('9325047')['product_name'])
print(furniture_api.get_product_detail('does-not-exist'))
"
```

Expected: prints a real product name (e.g. `Wardrobe combination`), then `None`.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt furniture_api.py
git commit -m "Add furniture_api.get_product_detail() and openai dependency"
```

---

### Task 2: `agent.py` — tools, wrappers, and the agent loop

**Files:**
- Create: `agent.py`
- Create: `tests/test_agent.py`

**Interfaces:**
- Consumes: `furniture_api.get_catalogue()`, `furniture_api.get_product_detail(item_id)`,
  `furniture_api.get_balance()`, `furniture_api.place_order(item_id, quantity=1)` (all
  existing, from Task 1 and before).
- Produces:
  - `agent.TOOLS` — list of 4 OpenAI tool-schema dicts.
  - `agent.TOOL_FUNCTIONS` — dict `{name: callable}`, one entry per tool in `TOOLS`.
  - `agent.run_agent_turn(history: list[dict], user_message: str) -> list[dict]` — the
    full updated message history (OpenAI chat-message format) after one turn, including
    the new user message, any tool round-trips, and the final assistant reply. Later
    tasks (the `/ask` route) store this return value straight into
    `session["chat_history"]`.

- [ ] **Step 1: Write the failing tests for the tool wrappers**

Create `tests/test_agent.py`:

```python
"""Tests for agent.py's tool-wrapper functions (mocking furniture_api, not the API)."""

import agent


def test_search_catalogue_returns_everything_with_no_category(monkeypatch):
    monkeypatch.setattr(agent.furniture_api, "get_catalogue", lambda: [
        {"item_id": "1", "category": "Chairs", "price": 100},
        {"item_id": "2", "category": "Tables", "price": 200},
    ])
    result = agent.TOOL_FUNCTIONS["search_catalogue"]()
    assert len(result) == 2


def test_search_catalogue_filters_by_exact_category_case_insensitively(monkeypatch):
    monkeypatch.setattr(agent.furniture_api, "get_catalogue", lambda: [
        {"item_id": "1", "category": "Chairs", "price": 100},
        {"item_id": "2", "category": "Tables", "price": 200},
    ])
    result = agent.TOOL_FUNCTIONS["search_catalogue"](category="chairs")
    assert result == [{"item_id": "1", "category": "Chairs", "price": 100}]


def test_get_product_detail_strips_image_fields(monkeypatch):
    monkeypatch.setattr(agent.furniture_api, "get_product_detail", lambda item_id: {
        "item_id": item_id,
        "product_name": "Chair",
        "price": 100,
        "image_url": "a-huge-base64-string",
        "image_mime_type": "image/jpeg",
    })
    result = agent.TOOL_FUNCTIONS["get_product_detail"](item_id="CHR-1")
    assert "image_url" not in result
    assert "image_mime_type" not in result
    assert result["product_name"] == "Chair"


def test_get_product_detail_reports_unknown_item(monkeypatch):
    monkeypatch.setattr(agent.furniture_api, "get_product_detail", lambda item_id: None)
    result = agent.TOOL_FUNCTIONS["get_product_detail"](item_id="does-not-exist")
    assert "error" in result


def test_check_balance_wraps_furniture_api(monkeypatch):
    monkeypatch.setattr(agent.furniture_api, "get_balance", lambda: 500.0)
    assert agent.TOOL_FUNCTIONS["check_balance"]() == {"balance": 500.0}


def test_check_balance_reports_failure(monkeypatch):
    monkeypatch.setattr(agent.furniture_api, "get_balance", lambda: None)
    result = agent.TOOL_FUNCTIONS["check_balance"]()
    assert "error" in result


def test_place_order_passes_through_furniture_api_result(monkeypatch):
    monkeypatch.setattr(
        agent.furniture_api,
        "place_order",
        lambda item_id, quantity=1: {"success": True, "message": "Order placed: $100.00."},
    )
    result = agent.TOOL_FUNCTIONS["place_order"](item_id="CHR-1")
    assert result == {"success": True, "message": "Order placed: $100.00."}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent.py -v`
Expected: `ModuleNotFoundError: No module named 'agent'` (or collection error) — `agent.py`
doesn't exist yet.

- [ ] **Step 3: Write `agent.py`**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent.py -v`
Expected: 7 passed.

- [ ] **Step 5: Verify the full loop live against Azure OpenAI**

Run:

```bash
.venv/Scripts/python.exe -c "
import agent
history = agent.run_agent_turn([], 'How much money do I have left?')
print(history[-1]['content'])
"
```

Expected: a plain-English sentence stating a real dollar balance (confirms the tool call,
the real `furniture_api.get_balance()` call, and the follow-up reply all worked together).

- [ ] **Step 6: Commit**

```bash
git add agent.py tests/test_agent.py
git commit -m "Add agent.py: tool-calling shopping assistant over furniture_api"
```

---

### Task 3: `/ask` Flask route with session-persisted chat history

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: `agent.run_agent_turn(history, user_message)` (Task 2).
- Produces: `GET/POST /ask` route (Flask endpoint name `ask`), reading/writing
  `session["chat_history"]` (list of OpenAI-format message dicts). `templates/ask.html`
  (Task 4) receives this as `history`.

- [ ] **Step 1: Add the `session` import and `agent` import**

In `app.py`, change:

```python
from flask import Flask, flash, redirect, render_template, request, url_for
```

to:

```python
from flask import Flask, flash, redirect, render_template, request, session, url_for
```

and add, alongside the other local imports:

```python
import agent
```

so the import block reads:

```python
import agent
import auth
import db
import furniture_api
```

- [ ] **Step 2: Add the `/ask` route**

Insert after the `orders()` route (before `if __name__ == "__main__":`):

```python
@app.route("/ask", methods=["GET", "POST"])
@login_required
def ask():
    if request.method == "POST":
        user_message = request.form["message"]
        history = session.get("chat_history", [])
        session["chat_history"] = agent.run_agent_turn(history, user_message)
        return redirect(url_for("ask"))
    return render_template("ask.html", history=session.get("chat_history", []))
```

- [ ] **Step 3: Clear chat history on logout**

Change:

```python
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))
```

to:

```python
@app.route("/logout")
@login_required
def logout():
    session.pop("chat_history", None)
    logout_user()
    return redirect(url_for("login"))
```

- [ ] **Step 4: Verify the existing test suite still passes**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: all previously-passing tests still pass (this task only adds a route, touches
nothing `tests/test_budget.py` or `tests/test_agent.py` cover).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "Add /ask route with session-persisted chat history"
```

---

### Task 4: `templates/ask.html`, nav link, and chat styling

**Files:**
- Create: `templates/ask.html`
- Modify: `templates/base.html`
- Modify: `static/style.css`

**Interfaces:**
- Consumes: `history` (list of message dicts, from Task 3's `render_template("ask.html",
  history=...)`), `url_for('ask')` (Flask endpoint from Task 3).

- [ ] **Step 1: Add the nav link**

In `templates/base.html`, change:

```html
        <a href="{{ url_for('home') }}">Catalogue</a>
        <a href="{{ url_for('orders') }}">My Orders</a>
```

to:

```html
        <a href="{{ url_for('home') }}">Catalogue</a>
        <a href="{{ url_for('ask') }}">Ask</a>
        <a href="{{ url_for('orders') }}">My Orders</a>
```

- [ ] **Step 2: Create `templates/ask.html`**

```html
{% extends "base.html" %}
{% block title %}Ask — Furniture Shop{% endblock %}
{% block content %}
  <h1 class="page-title">Ask</h1>
  <p class="page-subtitle">Ask for what you're after, in your own words.</p>

  <div class="chat-transcript">
    {% for message in history %}
      {% if message.role == "user" %}
        <div class="chat-bubble chat-user">{{ message.content }}</div>
      {% elif message.role == "assistant" and message.content %}
        <div class="chat-bubble chat-assistant">{{ message.content }}</div>
      {% endif %}
    {% endfor %}
  </div>

  <form method="post" class="chat-form">
    <input type="text" name="message" placeholder="e.g. Can I get a cheap mustard chair?" required autofocus>
    <button type="submit">Send</button>
  </form>
{% endblock %}
```

- [ ] **Step 3: Add chat styling to `static/style.css`**

Append after the `/* Login */` section (end of file):

```css
/* Ask (chat agent) --------------------------------------------------- */

.chat-transcript {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
}

.chat-bubble {
  max-width: 70%;
  padding: 10px 16px;
  border-radius: 16px;
  line-height: 1.4;
  white-space: pre-wrap;
}

.chat-user {
  align-self: flex-end;
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.chat-assistant {
  align-self: flex-start;
  background: var(--card);
  border: 1px solid var(--border);
  color: var(--ink);
  border-bottom-left-radius: 4px;
}

.chat-form {
  display: flex;
  gap: 8px;
}

.chat-form input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 10px 18px;
  font-size: 1rem;
}

.chat-form button {
  border-radius: 999px;
}
```

- [ ] **Step 4: Commit**

```bash
git add templates/ask.html templates/base.html static/style.css
git commit -m "Add chat UI for the shopping-assistant agent"
```

---

### Task 5: Live end-to-end verification

**Files:**
- Modify: `CLAUDE.md` (record the verification, matching the existing "Verified working" convention)

No new code — this task drives the running app exactly as a person would, per the spec's
Testing section and Step 6's own checklist.

- [ ] **Step 1: Start the app**

```bash
.venv/Scripts/python.exe app.py
```

- [ ] **Step 2: Log in and drive the four scenarios**

Using a session-cookie curl flow (or a browser), logged in as any demo user
(`alice`/`alice123`), against `POST /ask` with `message=<text>`, followed by `GET /ask` to
read the reply, confirm:

1. **"What's my balance?"** → reply states the real dollar balance (matches
   `GET /users/{user_id}` for this account).
2. **"Find me a chair under $500."** → reply lists real chair products actually priced
   under $500 (verify against the live `/catalogue/search-index` data, not just that a
   reply came back).
3. **"Buy the first one."** (sent right after scenario 2, same session) → reply
   references the correct product from the *prior* reply's list, states its exact price,
   and asks for confirmation — proving `session["chat_history"]` carried context across
   the two requests.
4. Reply **"Yes"** to the confirmation from scenario 3 → `place_order` actually fires;
   reply confirms the purchase and states the updated balance. Cross-check
   `GET /users/{user_id}` shows the balance actually dropped by that amount.
5. **A deliberately-failing case** — ask for a product you know isn't in the catalogue,
   or try to buy something after intentionally exhausting the balance — confirm the
   reply explains the failure in plain language and suggests an alternative, with no raw
   error text or stack trace, and the page still returns `200` (no crash).

- [ ] **Step 3: Record the verification**

Add a new `## Verified working` entry to `CLAUDE.md` (following the existing dated-entry
convention) stating exactly what was tested and the real observed results (balance
figures, product names, actual reply text) — not "should work."

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "Verify the shopping-assistant agent end-to-end against the live app"
```

---

## Self-Review Notes

- **Spec coverage:** all four tools (Task 2), Azure OpenAI wiring (Task 2), session-based
  memory (Task 3), two-turn confirmation + plain-language failure handling (Task 2's
  `SYSTEM_PROMPT`), chat UI matching existing look (Task 4), tool-wrapper tests (Task 2),
  manual live verification (Task 5) — every spec section maps to a task.
- **Type consistency:** `agent.run_agent_turn(history, user_message)` in Task 2 matches
  its call site in Task 3's `/ask` route exactly; `agent.TOOL_FUNCTIONS` keys match the
  `name` field of every `agent.TOOLS` entry.
- No placeholders — every step has real code or an exact command to run.
