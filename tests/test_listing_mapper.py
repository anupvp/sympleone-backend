from app.services.products.listing_mapper import classify_listing_bucket, map_listing_item


def test_map_buyable_active() -> None:
    item = {
        "sku": "SKU-1",
        "summaries": [
            {
                "marketplaceId": "A21TJRUUN4KGV",
                "asin": "B0123",
                "status": ["BUYABLE"],
                "itemName": "Travel Mug",
                "productType": "DRINKWARE",
                "lastUpdatedDate": "2026-11-28T10:00:00Z",
            }
        ],
        "fulfillmentAvailability": [
            {"marketplaceId": "A21TJRUUN4KGV", "fulfillmentChannelCode": "DEFAULT", "quantity": 10}
        ],
    }
    row = map_listing_item(
        item,
        marketplace_id="A21TJRUUN4KGV",
        fba_qty_by_sku={},
        performance_pct_by_sku={"SKU-1": 8.4},
    )
    assert row["listing_status"] == "active"
    assert row["inventory_available"] == 10
    assert row["performance_percent"] == 8.4


def test_out_of_stock_when_buyable_zero_qty() -> None:
    assert classify_listing_bucket({"BUYABLE"}, has_issues=False, inventory=0) == "out_of_stock"


def test_suppressed_when_issues() -> None:
    item = {
        "sku": "SKU-2",
        "issues": [{"code": "90220"}],
        "summaries": [{"marketplaceId": "A1", "status": ["BUYABLE"], "itemName": "X"}],
    }
    row = map_listing_item(
        item,
        marketplace_id="A1",
        fba_qty_by_sku={},
        performance_pct_by_sku={},
    )
    assert row["listing_status"] == "suppressed"