from app.services.amazon.sales_traffic_report import parse_sales_and_traffic_by_asin


def test_parse_sales_and_traffic_by_asin_defensive() -> None:
    payload = {
        "salesAndTrafficByAsin": [
            {
                "sku": "WB-2041",
                "childAsin": "B0EXAMPLE01",
                "salesByAsin": {
                    "unitsOrdered": 10,
                    "unitsShipped": 8,
                    "totalOrderItems": 9,
                    "orderedProductSales": {"amount": 240000, "currencyCode": "INR"},
                    "shippedProductSales": {"amount": 210000, "currencyCode": "INR"},
                },
            },
            {"not_a_sku_row": True},
        ],
    }
    rows = parse_sales_and_traffic_by_asin(payload)
    assert len(rows) == 1
    row = rows[0]
    assert row.sku == "WB-2041"
    assert row.asin == "B0EXAMPLE01"
    assert row.ordered_sales == 240000
    assert row.shipped_sales == 210000
    assert row.units_ordered == 10
    assert row.currency == "INR"


def test_parse_missing_section() -> None:
    assert parse_sales_and_traffic_by_asin({}) == []