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
