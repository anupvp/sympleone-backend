from app.services.orders.fulfillment_type import (
    FULFILLMENT_FBA,
    FULFILLMENT_FBM,
    FULFILLMENT_SELF_SHIP,
    classify_fulfillment_type,
    summarize_fulfillment_types,
)


def test_fba_afn() -> None:
    assert classify_fulfillment_type({"FulfillmentChannel": "AFN"}) == FULFILLMENT_FBA


def test_fbm_mfn() -> None:
    assert classify_fulfillment_type({"FulfillmentChannel": "MFN"}) == FULFILLMENT_FBM


def test_self_ship_easyship_status() -> None:
    assert (
        classify_fulfillment_type(
            {"FulfillmentChannel": "MFN", "EasyShipShipmentStatus": "PendingPickUp"}
        )
        == FULFILLMENT_SELF_SHIP
    )


def test_summary_counts() -> None:
    orders = [
        {"fulfillment_type": FULFILLMENT_FBA},
        {"fulfillment_type": FULFILLMENT_FBM},
        {"fulfillment_type": FULFILLMENT_SELF_SHIP},
    ]
    s = summarize_fulfillment_types(orders)
    assert s["total"] == 3
    assert s["fba"] == 1
    assert s["fbm"] == 1
    assert s["self_ship"] == 1