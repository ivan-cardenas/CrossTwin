"""
CBS "Kerncijfers wijken en buurten" -> housing.WOZValue (catalog entries CBS_WOZ_<year>).

One table per year (2019-2024: 84583NED, 84799NED, 85039NED, 85318NED, 85618NED,
85984NED). The tables list gemeenten, wijken and buurten in one column,
`WijkenEnBuurten` (buurt codes "BU" + gemeente + wijk + buurt, the same code as
administrative.Neighborhood.id). The mean WOZ value (x 1 000 EUR, valuation date
1 January of the year before) and the dwelling stock sit in columns whose key
number changes between years; the catalog entry names them in
`params.woz_key` / `params.stock_key`.

CBS gives no value for a buurt with fewer than 20 dwellings or without a WOZ
value for 85 % of them; those rows are stored with an empty value so the gap
stays visible. Only neighborhoods already stored are written.

After the rows the mean dwelling area (BAG) and the accessibility baseline are
filled from the database (housing/calculations/woz.py), so the per-m2 value and
the baseline are frozen with the import.
"""
import logging

import requests
from django.contrib.gis.geos import Polygon
from django.db import transaction

from .console import say

logger = logging.getLogger(__name__)

API = "https://opendata.cbs.nl/ODataApi/OData/{table_id}/TypedDataSet"
PAGE_SIZE = 10000
WOZ_UNIT_EUR = 1000   # CBS publishes the mean WOZ value in x 1 000 EUR


def _result(status, message, created=0, updated=0):
    from .external_data import ImportResult

    return ImportResult(status, message, created, updated)


def parse_rows(rows, woz_key, stock_key):
    """
    {buurt code: (mean WOZ in EUR or None, dwellings or None)} from CBS rows.
    Only "BU" codes are kept (gemeenten "GM" and wijken "WK" are dropped); a
    missing or non-numeric value is None.
    """
    parsed = {}
    for row in rows:
        code = str(row.get("WijkenEnBuurten", "")).strip()
        if not code.startswith("BU"):
            continue
        woz = row.get(woz_key)
        stock = row.get(stock_key)
        parsed[code] = (
            woz * WOZ_UNIT_EUR if isinstance(woz, (int, float)) else None,
            int(stock) if isinstance(stock, (int, float)) else None,
        )
    return parsed


def fetch(dataset, bbox=None):
    """Import the WOZ value of every stored neighborhood of the cities inside `bbox` (WGS84)."""
    from administrative.models import City, Neighborhood
    from housing.calculations import woz
    from housing.models import WOZValue

    params = dataset.get("params", {})
    table_id, year = dataset["table_id"], params["year"]
    woz_key, stock_key = params["woz_key"], params["stock_key"]

    cities = City.objects.all()
    if bbox:
        area = Polygon.from_bbox(bbox)
        area.srid = 4326
        area.transform(City._meta.get_field("geom").srid)
        cities = cities.filter(geom__intersects=area.buffer(1))
    city_pks = list(cities.values_list("pk", flat=True))
    if not city_pks:
        return _result("success", "No cities found within the selected area.")
    stored = set(Neighborhood.objects.filter(district__city_id__in=city_pks).values_list("pk", flat=True))
    if not stored:
        return _result("success", "No neighborhoods stored for these cities; import neighborhoods first.")

    region_filter = " or ".join(f"startswith(WijkenEnBuurten,'BU{pk:04d}')" for pk in city_pks)
    query = {"$format": "json", "$top": PAGE_SIZE, "$filter": f"({region_filter})",
             "$select": f"WijkenEnBuurten,{woz_key},{stock_key}"}
    say("cbs", f"Fetching CBS {table_id} (WOZ {year}) for {len(city_pks)} municipality(ies) ...")
    try:
        response = requests.get(API.format(table_id=table_id), params=query, timeout=120)
        response.raise_for_status()
        rows = response.json().get("value", [])
    except requests.RequestException as exc:
        return _result("error", f"CBS OData request failed: {exc}")
    if len(rows) >= PAGE_SIZE:
        say("WARNING", f"CBS {table_id}: hit the {PAGE_SIZE}-row cap, results may be truncated")

    parsed = {code: values for code, values in parse_rows(rows, woz_key, stock_key).items() if code in stored}
    if not parsed:
        return _result("success", "No stored neighborhood matched a CBS row.")

    created = updated = 0
    with transaction.atomic():
        existing = {w.neighborhood_id: w for w in WOZValue.objects.filter(year=year, neighborhood_id__in=parsed)}
        saved = []
        for code, (avg_woz, stock) in parsed.items():
            row = existing.get(code) or WOZValue(neighborhood_id=code, year=year)
            created += row.pk is None
            updated += row.pk is not None
            row.avgWOZ_EUR, row.dwellings, row.cbs_table_id = avg_woz, stock, table_id
            saved.append(row)
        woz.fill_areas(saved)
        for row in saved:
            row.save()
        frozen = woz.freeze_baselines(saved)
    return _result("success", f"Imported {len(parsed)} neighborhood WOZ value(s) of {year} from CBS {table_id}: "
                              f"created {created}, updated {updated}; accessibility baseline frozen for {len(frozen)}.",
                   created, updated)
