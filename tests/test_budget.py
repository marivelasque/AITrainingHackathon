"""Tests for the budget-limit logic: can_afford() and place_order()."""

import pytest

import db


@pytest.fixture
def shop_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SHOP_DB_PATH", tmp_path / "test_shop.sqlite")
    db.init_shop_db()
    return db


def test_can_afford_allows_order_that_exactly_uses_remaining_budget():
    assert db.can_afford(budget=100, spent=60, order_total=40)


def test_can_afford_blocks_order_that_exceeds_remaining_budget():
    assert not db.can_afford(budget=100, spent=60, order_total=40.01)


def test_place_order_records_an_order_and_updates_spend(shop_db):
    product = shop_db.get_products()[0]

    result = shop_db.place_order("test_user", product["id"], budget=1_000_000)

    assert result["success"]
    assert shop_db.get_spent("test_user") == product["price"]
    assert len(shop_db.get_orders("test_user")) == 1


def test_place_order_refuses_an_order_over_budget_and_does_not_record_it(shop_db):
    product = shop_db.get_products()[0]

    result = shop_db.place_order("test_user", product["id"], budget=product["price"] - 1)

    assert not result["success"]
    assert shop_db.get_spent("test_user") == 0
    assert len(shop_db.get_orders("test_user")) == 0


def test_place_order_allows_an_order_exactly_at_the_budget_boundary(shop_db):
    product = shop_db.get_products()[0]

    result = shop_db.place_order("test_user", product["id"], budget=product["price"])

    assert result["success"]


def test_place_order_rejects_an_unknown_product(shop_db):
    result = shop_db.place_order("test_user", product_id=999999, budget=1_000_000)

    assert not result["success"]
