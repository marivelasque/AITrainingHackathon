# Furniture Shop Chat Agent — Design

## Purpose

Add a text box where a logged-in buyer can type a plain-English request ("find me a
cheap mustard chair", "what's my balance", "buy the first one") and an AI agent figures
out which of the furniture shop API's four actions to take, reasoning over plain results
for anything the API itself can't do (price, colour, "cheap", pronoun references to
earlier results).

This is Step 6 of the course (`Step 6 - Build Your Agent.md`): tool-calling over the same
four API actions the rest of the app already uses via `furniture_api.py`.

## Tools

Four tools, matching the API's four real actions (names/descriptions as agreed
conversationally before this spec):

1. **`search_catalogue(category=None)`** — wraps `furniture_api.get_catalogue()`
   (`/catalogue/search-index`). Returns item_id, name, price, category, colours for every
   match. **Exact category match only** — no price range, no colour filter, no free-text
   search at the API level. The agent must fetch (by category or everything) and then
   filter/sort/reason over the plain list itself.
2. **`get_product_detail(item_id)`** — new `furniture_api.py` function, wraps
   `GET /catalogue/{item_id}`. Full detail for one already-identified item. Not for
   browsing — needs a known `item_id`. The tool result **strips the base64 image** before
   it goes back to the model; images never belong in an LLM's context (per the Step 4
   guide's own warning).
3. **`check_balance()`** — wraps `furniture_api.get_balance()`. Always the current user;
   no user_id param.
4. **`place_order(item_id, quantity=1)`** — wraps `furniture_api.place_order()`. Real,
   irreversible, debits real money. See Confirmation flow, below.

## Architecture

- New Flask route `/ask` (GET renders the chat page + history; POST takes a message, runs
  one agent turn, redirects back to GET — same POST-then-redirect pattern already used by
  `/buy`).
- New module `agent.py`: tool schemas (`TOOLS`), tool-dispatch functions (`TOOL_FUNCTIONS`,
  wrapping `furniture_api.py`), and the loop (`run_agent_turn(history, message)`) that
  talks to Azure OpenAI.
- Conversation history lives in `session["chat_history"]` — the same signed-cookie Flask
  session `Flask-Login` already uses. Persists across messages and page reloads within a
  login session; clears on logout. This is what makes "buy the first one" (referring back
  to an earlier search) work.
- New template `templates/ask.html`: chat transcript (user/assistant bubbles) + a text
  input form. New nav link in `base.html`. Styled to match the app's existing look
  (`static/style.css`'s card/colour language) — distinct user/assistant bubble styling,
  not a bare unstyled form; this should feel like a real shopping-assistant chat, not a
  debug console.

## Azure OpenAI integration

- `openai` Python package's `AzureOpenAI` client (official SDK, matches "always use
  validated, established packages" — no hand-rolled JSON-prompting or extra agent
  framework).
- Config from `.env` (already present): `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`,
  `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY`. Never hardcoded, never logged.
- `run_agent_turn`: append the user message to history, call `chat.completions.create(...,
  tools=TOOLS)`. If the response has `tool_calls`, execute each via `TOOL_FUNCTIONS`,
  append the results as `tool`-role messages, call the model again. Loop capped at 4
  rounds (backstop against a runaway tool-calling loop) before forcing a plain-text reply.

## Data flow example

"find me a cheap mustard chair":
1. Model calls `search_catalogue(category="Chairs")`.
2. Tool returns every chair's item_id/name/price/colours.
3. Model reasons over that plain list itself — "cheap" (its own judgement of the price
   range) and "mustard" (matching the `colours` field) — the API never sees either term.
4. Model replies in English listing matches with price. Loop ends (no further tool call).

## Confirmation flow (spending real money)

`place_order` is never called straight off a request. The system prompt instructs the
model to:
- State the specific item and price it's about to buy, and explicitly ask the user to
  confirm, whenever a request would lead to placing an order.
- Only call `place_order` after the user's *next* message clearly confirms (e.g. "yes",
  "confirm", "go ahead").

This is a **two-turn chat confirmation**, prompt-enforced rather than a hard state
machine — a plain conversational back-and-forth, no separate confirm button/UI element.
See Risks, below, for the limitation this implies.

## Error handling

- Tool wrappers pass through `furniture_api.py`'s existing graceful failures (empty
  list / `None` / `{"success": False, "message": ...}`) as tool results.
- The system prompt instructs the model to explain failures in plain language and
  **suggest what to try instead** — e.g. "want to look for something cheaper?" on
  insufficient balance, "want me to search for something similar?" on an unknown item —
  not surface a raw error or API status code.
- The Azure OpenAI call itself is try/excepted; a network or auth failure becomes a plain
  chat reply ("Sorry, I couldn't reach the AI service right now"), not a 500 page.

## Testing

- Light `pytest` coverage of the tool-wrapper functions in `agent.py` (mocking
  `furniture_api`), confirming each wrapper calls the right underlying function with the
  right arguments and shapes its result correctly (e.g. `get_product_detail`'s wrapper
  actually strips the image field).
- Primary verification is manual and live, per Step 6's own checklist: "what's my
  balance", "find me a chair under $500", "buy the first one" (tests session memory), and
  one deliberately-failing case (unknown product or overspend). Run against the live app
  after building; report the actual transcripts, not just "should work."

## Risks / known limitations

- **Confirmation is prompt-enforced, not code-enforced.** A confused or adversarial model
  turn could in principle call `place_order` without having asked first. Acceptable for
  hackathon scope; if this app ever handled real customer money outside the event, this
  would need a hard state machine (e.g. a server-side "pending order" token) instead.
- `gpt-5-mini` on Azure `australiaeast` — quota/rate-limit behaviour untested until run
  live.
- No streaming: a full agent turn (possibly 2–3 model calls plus tool calls) completes
  before the page reloads with the reply. Fine at hackathon/demo scale; would feel slow at
  higher latency or larger conversations.
- Chat history stored in the Flask session cookie has no size cap enforced yet — a very
  long conversation could in principle bump into Flask's session cookie size limit. Not
  expected to matter for a hackathon demo; flagging rather than solving now (YAGNI).
