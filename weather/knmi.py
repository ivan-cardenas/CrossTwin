"""
KNMI station data from daggegevens.knmi.nl (validated climatological data;
no API key, unlike the KNMI Data Platform the importer's other KNMI entries use).

parse_knmi() reads the CSV both endpoints answer with: the hourly one
(urban_heat/solweig/met.py, one hour for the Thermal Comfort tool, not
stored) and the daily one used here, whose precipitation (RH) and Makkink
reference evapotranspiration (EV24) are stored as daily Meteorology rows for
the yearly water balance of watersupply.AvailableFreshWater.

store_daily() writes with bulk_create, which fires no post_save, so it sends
daily_water_balance_changed with the station ids instead (downstream apps
subscribe; weather never imports them).

DAG edge: Meteorology -> Available_FW (the input side)
"""
import logging
import math
from datetime import date, datetime, timezone

from django.dispatch import Signal

logger = logging.getLogger(__name__)

KNMI_DAILY_URL = "https://www.daggegevens.knmi.nl/klimatologie/daggegevens"
DAILY_VARS = "RH:EV24"
# Stations within this distance of the area of interest are imported; when
# none is, the nearest one is.
STATION_BUFFER_KM = 25.0
# Daily rows are stored at noon UTC, so the calendar day (and year) of a row
# is the same in every time zone the project might switch to.
DAILY_HOUR_UTC = 12

# sender = WeatherStation, station_ids = ids whose daily rows were written
daily_water_balance_changed = Signal()


class KNMIError(ValueError):
    """An expected failure shown to the user as-is (KNMI unreachable, no station data)."""


def distance_km(lon1, lat1, lon2, lat2):
    """Great-circle distance between two WGS84 points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def parse_knmi(text):
    """
    KNMI daggegevens/uurgegevens CSV -> ({stn: (lon, lat, alt, name)}, [{column: int|None}, ...]).
    Station coordinates come from the '# STN LON LAT ALT NAME' header block;
    empty fields are None.
    """
    stations, rows, columns = {}, [], None
    for line in text.splitlines():
        if line.startswith("#"):
            body = line[1:].strip()
            parts = body.split()
            if body.startswith("STN,"):
                columns = [c.strip() for c in body.split(",")]
            elif len(parts) >= 5 and parts[0].isdigit():
                try:
                    stations[int(parts[0])] = (float(parts[1]), float(parts[2]), float(parts[3]),
                                               " ".join(parts[4:]))
                except ValueError:
                    pass
        elif line.strip() and columns:
            fields = [f.strip() for f in line.split(",")]
            rows.append({c: (int(v) if v.lstrip("-").isdigit() else None) for c, v in zip(columns, fields)})
    return stations, rows


def rain_mm(rh):
    """KNMI RH (0.1 mm; -1 = less than 0.05 mm) -> mm."""
    if rh is None:
        return None
    return 0.0 if rh < 0 else rh / 10.0


def fetch_daily(start, end):
    """Raw CSV of RH and EV24 for every KNMI station between two dates (inclusive)."""
    import requests

    try:
        response = requests.post(KNMI_DAILY_URL, data={
            "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
            "vars": DAILY_VARS, "stns": "ALL",
        }, timeout=120)
        response.raise_for_status()
    except requests.RequestException as e:
        raise KNMIError(f"KNMI daily data could not be retrieved: {e}") from None
    return response.text


def select_stations(stations, bbox_wgs84):
    """
    Station numbers within STATION_BUFFER_KM of the bbox (minLng, minLat,
    maxLng, maxLat), or the nearest station to its centre when none is.
    """
    if not stations:
        return []
    min_lng, min_lat, max_lng, max_lat = bbox_wgs84

    def to_bbox(lon, lat):
        # distance to the nearest point of the bbox (0 inside)
        return distance_km(lon, lat, min(max(lon, min_lng), max_lng), min(max(lat, min_lat), max_lat))

    near = [stn for stn, (lon, lat, _alt, _name) in stations.items() if to_bbox(lon, lat) <= STATION_BUFFER_KM]
    if near:
        return sorted(near)
    c_lng, c_lat = (min_lng + max_lng) / 2, (min_lat + max_lat) / 2
    return [min(stations, key=lambda s: distance_km(c_lng, c_lat, stations[s][0], stations[s][1]))]


def store_daily(text, bbox_wgs84):
    """
    Upsert the stations near the bbox and their daily precipitation and
    reference ET as Meteorology rows (one per station and day, at noon UTC).
    Returns (station_count, row_count). Sends daily_water_balance_changed.
    """
    from django.conf import settings
    from django.contrib.gis.geos import Point
    from django.db import transaction

    from .models import Meteorology, WeatherStation

    stations, rows = parse_knmi(text)
    wanted = select_stations(stations, bbox_wgs84)
    if not wanted:
        raise KNMIError("KNMI returned no stations for this period.")

    with transaction.atomic():
        by_stn = {}
        for stn in wanted:
            lon, lat, alt, name = stations[stn]
            geom = Point(lon, lat, srid=4326)
            geom.transform(settings.COORDINATE_SYSTEM)
            station, _ = WeatherStation.objects.update_or_create(
                knmi_id=stn,
                defaults={"name": f"KNMI {stn} {name}"[:200], "geom": geom, "elevation_m": alt},
            )
            by_stn[stn] = station

        records = []
        for row in rows:
            station = by_stn.get(row.get("STN"))
            day = row.get("YYYYMMDD")
            if station is None or day is None:
                continue
            et = row.get("EV24")
            d = date(day // 10000, day // 100 % 100, day % 100)
            records.append(Meteorology(
                station=station,
                date=datetime(d.year, d.month, d.day, DAILY_HOUR_UTC, tzinfo=timezone.utc),
                precipitation_mm=rain_mm(row.get("RH")),
                reference_et_mm=None if et is None else et / 10.0,
            ))
        Meteorology.objects.bulk_create(
            records, batch_size=1000, update_conflicts=True,
            unique_fields=["station", "date"], update_fields=["precipitation_mm", "reference_et_mm"],
        )

    station_ids = [s.pk for s in by_stn.values()]
    daily_water_balance_changed.send(sender=WeatherStation, station_ids=station_ids)
    return len(station_ids), len(records)
