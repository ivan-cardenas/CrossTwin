"""
CBS StatLine 85773ENG "Existing own homes; purchase prices, price indices 2020=100" -> housing.HousePriceIndex
(catalog entry CBS_HPI).

National, one row per calendar year (the table's annual periods "YYYYJJ00"): the price index of the selling
prices (2020 = 100), its change against the previous year, the homes sold and the average purchase price. CBS
publishes no finer index, so every area shows the same one. The dashboard rebases it to 2019 = 100 and
extrapolates it (housing/calculations/chain.py::hpi_curve).
"""
import logging

import requests
from django.db import transaction

from .console import say

logger = logging.getLogger(__name__)

TABLE_ID = "85773ENG"
API = f"https://opendata.cbs.nl/ODataApi/OData/{TABLE_ID}/TypedDataSet"
COLUMNS = {"index": "PriceIndexSellingPrices_1", "change": "ChangesComparedToThePreviousYear_3",
           "sold": "SoldHomes_4", "price": "AveragePurchasePrice_7"}


def _result(status, message, created=0, updated=0):
    from .external_data import ImportResult

    return ImportResult(status, message, created, updated)


def parse_rows(rows):
    """{year: {index, change, sold, price}} from CBS rows; only annual periods with an index are kept."""
    parsed = {}
    for row in rows:
        period = str(row.get("Periods", "")).strip()
        value = row.get(COLUMNS["index"])
        if not period.endswith("JJ00") or not isinstance(value, (int, float)):
            continue
        parsed[int(period[:4])] = {name: row.get(key) for name, key in COLUMNS.items()}
    return parsed


def fetch(dataset, bbox=None):
    """Import every annual value of the national price index."""
    from housing.models import HousePriceIndex

    say("cbs", f"Fetching CBS {TABLE_ID} (national house price index) ...")
    query = {"$format": "json", "$filter": "endswith(Periods,'JJ00')", "$select": "Periods," + ",".join(COLUMNS.values())}
    try:
        response = requests.get(API, params=query, timeout=60)
        response.raise_for_status()
        rows = response.json().get("value", [])
    except requests.RequestException as exc:
        return _result("error", f"CBS OData request failed: {exc}")
    parsed = parse_rows(rows)
    if not parsed:
        return _result("error", f"CBS {TABLE_ID} returned no annual index values.")

    created = updated = 0
    with transaction.atomic():
        for year, v in sorted(parsed.items()):
            _, was_created = HousePriceIndex.objects.update_or_create(year=year, defaults={
                "index_value": v["index"], "changeYoY_pct": v["change"],
                "soldHomes": int(v["sold"]) if isinstance(v["sold"], (int, float)) else None,
                "avgPurchasePrice_EUR": v["price"] if isinstance(v["price"], (int, float)) else None,
                "cbsTable": TABLE_ID})
            created += was_created
            updated += not was_created
    return _result("success", f"Imported the house price index of {len(parsed)} year(s) ({min(parsed)}-{max(parsed)}) "
                              f"from CBS {TABLE_ID}: created {created}, updated {updated}.", created, updated)
