from app.models.dashboard_orders import NormalizedOrderStatus
from app.services.order_status.classifier import classify_amazon_order
from app.services.order_status.percentages import integer_percentages


def test_cancelled_order() -> None:
    status, _ = classify_amazon_order({"OrderStatus": "Canceled"})
    assert status == NormalizedOrderStatus.CANCELLED


def test_shipped_without_delivery_is_in_transit() -> None:
    status, tracking = classify_amazon_order(
        {
            "OrderStatus": "Shipped",
            "NumberOfItemsUnshipped": 0,
        }
    )
    assert status == NormalizedOrderStatus.IN_TRANSIT
    assert tracking is False


def test_easyship_delivered() -> None:
    status, tracking = classify_amazon_order(
        {
            "OrderStatus": "Shipped",
            "EasyShipShipmentStatus": "Delivered",
        }
    )
    assert status == NormalizedOrderStatus.DELIVERED
    assert tracking is True


def test_partially_shipped_is_processing() -> None:
    status, _ = classify_amazon_order(
        {"OrderStatus": "PartiallyShipped", "NumberOfItemsUnshipped": 2}
    )
    assert status == NormalizedOrderStatus.PROCESSING


def test_integer_percentages_sum_to_100() -> None:
    counts = {
        NormalizedOrderStatus.DELIVERED: 1437,
        NormalizedOrderStatus.IN_TRANSIT: 221,
        NormalizedOrderStatus.PROCESSING: 129,
        NormalizedOrderStatus.CANCELLED: 55,
    }
    total = sum(counts.values())
    pct = integer_percentages(counts, total)
    assert sum(pct.values()) == 100