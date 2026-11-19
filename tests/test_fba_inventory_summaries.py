from app.services.amazon.fba_inventory_summaries import (
    normalize_inventory_item,
    summarize_inventory_metrics,
)


def test_summarize_inventory_metrics_from_details() -> None:
    rows = [
        {
            "inventoryDetails": {
                "fulfillableQuantity": 5,
                "inboundWorkingQuantity": 2,
                "inboundShippedQuantity": 1,
                "reservedQuantity": {"totalReservedQuantity": 3},
                "unfulfillableQuantity": {"totalUnfulfillableQuantity": 1},
            }
        },
        {
            "inventoryDetails": {
                "fulfillableQuantity": 10,
                "reservedQuantity": 4,
                "unfulfillableQuantity": 2,
            }
        },
    ]
    metrics = summarize_inventory_metrics(rows)
    assert metrics["fulfillable"] == 15
    assert metrics["reserved"] == 7
    assert metrics["inbound"] == 3
    assert metrics["unfulfillable"] == 3


def test_normalize_inventory_item() -> None:
    row = {
        "asin": "B001",
        "sellerSku": "SKU-1",
        "fnSku": "X001",
        "productName": "Test",
        "condition": "NewItem",
        "totalQuantity": 12,
        "lastUpdatedTime": "2026-10-01T00:00:00Z",
        "inventoryDetails": {
            "fulfillableQuantity": 8,
            "reservedQuantity": {"totalReservedQuantity": 2},
            "inboundShippedQuantity": 2,
            "unfulfillableQuantity": {"totalUnfulfillableQuantity": 0},
        },
    }
    item = normalize_inventory_item(row)
    assert item["asin"] == "B001"
    assert item["fulfillable"] == 8
    assert item["reserved"] == 2
    assert item["inbound"] == 2