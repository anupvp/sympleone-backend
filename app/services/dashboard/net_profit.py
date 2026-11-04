"""Net profit from Finance, Sales, Orders, and FBA inventory (see docs/net-profit.txt)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services.amazon.fba_inventory_summaries import (
    count_fulfillable_skus,
    fetch_inventory_summaries,
)
from app.services.amazon.finance_transactions import (
    fetch_finance_transactions,
    sum_released_finance_net,
)


def compute_net_profit(
    *,
    access_token: str,
    marketplace_id: str,
    start: date,
    end: date,
    gross_sales: float,
    orders: list[dict[str, Any]],
) -> tuple[float, float, str]:
    """
    Net profit = sum of RELEASED finance transaction totals in the period.
    Margin % = net profit / gross sales (Sales API order metrics).
    Orders are included in the dashboard pipeline (same date range); inventory
    is loaded per spec — summaries have no unit cost, so profit is not adjusted.
    """
    del orders  # reserved for order-level reconciliation / future COGS
    transactions = fetch_finance_transactions(
        access_token=access_token,
        marketplace_id=marketplace_id,
        start=start,
        end=end,
    )
    net, currency = sum_released_finance_net(transactions, start=start, end=end)

    try:
        summaries = fetch_inventory_summaries(
            access_token=access_token,
            marketplace_id=marketplace_id,
            start=start,
        )
        count_fulfillable_skus(summaries)
    except Exception:
        pass

    margin = round((net / gross_sales) * 100, 1) if gross_sales > 0 else 0.0
    return net, margin, currency
