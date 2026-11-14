from io import BytesIO

from openpyxl import load_workbook

from app.services.dashboard.report_tsv_to_xlsx import merchant_listings_tsv_to_xlsx


def test_merchant_listings_tsv_to_xlsx() -> None:
    raw = b"sku\tasin\tprice\nSKU1\tB001\t10.00\nSKU2\tB002\t20.00\n"
    xlsx = merchant_listings_tsv_to_xlsx(raw)
    wb = load_workbook(BytesIO(xlsx), read_only=True)
    ws = wb.active
    assert ws is not None
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("sku", "asin", "price")
    assert rows[1][:2] == ("SKU1", "B001")
    assert len(rows) == 3