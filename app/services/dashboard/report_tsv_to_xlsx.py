"""Convert Amazon tab-delimited report bytes to Excel (.xlsx)."""

from __future__ import annotations

import csv
import io

from openpyxl import Workbook

MAX_EXCEL_ROWS = 1_048_576


def _decode_report_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def merchant_listings_tsv_to_xlsx(raw: bytes) -> bytes:
    """
    Amazon GET_MERCHANT_LISTINGS_ALL_DATA is tab-separated with a header row.
    """
    text = _decode_report_text(raw)
    reader = csv.reader(io.StringIO(text), delimiter="\t")

    wb = Workbook()
    ws = wb.active
    if ws is not None:
        ws.title = "Listings"

    row_count = 0
    for row in reader:
        if not row:
            continue
        row_count += 1
        if row_count > MAX_EXCEL_ROWS:
            break
        if ws is not None:
            ws.append(row)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def merchant_listings_xlsx_filename(start_iso: str, end_iso: str) -> str:
    return f"merchant-listings-{start_iso}-to-{end_iso}.xlsx"