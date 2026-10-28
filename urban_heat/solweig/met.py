"""
Meteorological forcing of one SOLWEIG run: one hour, uniform over the view.

Three sources fill the same record (Met); the map's tool shows the values so
the user can still change them before calculating:

    manual  the user's own values
    knmi    the KNMI station closest to the centre of the view that measured
            that hour (validated hourly data, daggegevens.knmi.nl/klimatologie/
            uurgegevens; no key, not stored)
    era5    ECMWF ERA5 hourly at the view centre, through Earth Engine
            (ECMWF/ERA5/HOURLY; ~5 days behind real time)

write_umep() writes the record as a UMEP met file (the format SOLWEIG reads).

DAG edge: Meteorology -> Tmrt, UTCI, PET (the inputs).
"""
import logging
import math
from dataclasses import asdict, dataclass
from datetime import timedelta, timezone

logger = logging.getLogger(__name__)

KNMI_URL = "https://www.daggegevens.knmi.nl/klimatologie/uurgegevens"
ERA5_ASSET = "ECMWF/ERA5/HOURLY"
DEFAULT_PRESSURE_KPA = 101.3
SOURCES = ("manual", "knmi", "era5")

# UMEP met-file columns (solweig_gpu/preprocessor.py writes the same header;
# "Td" holds the air temperature). SOLWEIG reads Wind (9), RH (10), Td (11),
# press (12, kPa), Kdn (14), Kdiff (21), Kdir (22), Wd (23); -999 = missing.
UMEP_COLUMNS = ("iy id it imin Q* QH QE Qs Qf Wind RH Td press rain Kdn snow ldown fcld "
                "wuh xsmd lai_hr Kdiff Kdir Wd").split()


class MetError(ValueError):
    """An expected failure the map tool shows as-is (no station data, ERA5 not yet available...)."""


@dataclass
class Met:
    ta_c: float
    rh_pct: float
    wind_ms: float
    wind_dir_deg: float
    kdown_wm2: float
    pressure_kpa: float = DEFAULT_PRESSURE_KPA
    source: str = "manual"

    def as_dict(self):
        return asdict(self)


def write_umep(met, when_local, path):
    """
    The UMEP met file of one run: the hour before and the analysed hour, both
    with `met` (SOLWEIG reads the file with np.loadtxt, which turns a single
    row into a 1-D array it cannot index; the extra hour also lets the ground
    temperature settle). Times are local: SOLWEIG converts them with the
    timezone of the raster centre. The result is band 2 of its outputs.
    """
    rows = []
    for when in (when_local - timedelta(hours=1), when_local):
        values = dict.fromkeys(UMEP_COLUMNS, -999)
        values.update({
            "iy": when.year, "id": when.timetuple().tm_yday, "it": when.hour, "imin": 0,
            "Wind": met.wind_ms, "RH": met.rh_pct, "Td": met.ta_c, "press": met.pressure_kpa,
            "rain": 0, "Kdn": met.kdown_wm2, "Wd": met.wind_dir_deg,
        })
        rows.append(" ".join(f"{values[c]:g}" for c in UMEP_COLUMNS))
    with open(path, "w") as f:
        f.write(" ".join(UMEP_COLUMNS) + "\n" + "\n".join(rows) + "\n")


def _distance_km(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _knmi_hour(when_utc):
    """KNMI date + hour field: HH (1-24) is the UT hour the observation ends, 24 = midnight."""
    if when_utc.hour == 0:
        return (when_utc - timedelta(days=1)).strftime("%Y%m%d"), 24
    return when_utc.strftime("%Y%m%d"), when_utc.hour


def parse_knmi(text):
    """
    KNMI uurgegevens CSV -> ({stn: (lon, lat, name)}, [{stn, T, U, FF, DD, Q, P}, ...]).
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
                    stations[int(parts[0])] = (float(parts[1]), float(parts[2]), " ".join(parts[4:]))
                except ValueError:
                    pass
        elif line.strip() and columns:
            fields = [f.strip() for f in line.split(",")]
            row = {c: (int(v) if v.lstrip("-").isdigit() else None) for c, v in zip(columns, fields)}
            rows.append(row)
    return stations, rows


def knmi_hourly(when_utc, lon, lat):
    """
    Met of the KNMI station closest to (lon, lat) that measured temperature,
    humidity, wind and global radiation in the hour ending at `when_utc`.
    Returns (Met, {"id", "name", "distance_km"}).
    """
    import requests

    day, hh = _knmi_hour(when_utc.astimezone(timezone.utc))
    try:
        response = requests.post(KNMI_URL, data={
            "start": f"{day}{hh:02d}", "end": f"{day}{hh:02d}", "vars": "T:U:FF:DD:Q:P", "stns": "ALL",
        }, timeout=60)
        response.raise_for_status()
    except requests.RequestException as e:
        raise MetError(f"KNMI hourly data could not be retrieved: {e}") from None
    stations, rows = parse_knmi(response.text)
    candidates = []
    for row in rows:
        stn = row.get("STN")
        if stn not in stations or any(row.get(k) is None for k in ("T", "U", "FF", "Q")):
            continue
        s_lon, s_lat, name = stations[stn]
        candidates.append((_distance_km(lon, lat, s_lon, s_lat), stn, name, row))
    if not candidates:
        raise MetError(f"No KNMI station has hourly data for {day} hour {hh} UT (validated data lag a few days).")
    distance, stn, name, row = min(candidates, key=lambda c: c[0])
    direction = row.get("DD")
    met = Met(
        ta_c=row["T"] / 10.0,
        rh_pct=float(row["U"]),
        wind_ms=row["FF"] / 10.0,
        # 0 = calm, 990 = variable: no direction (SOLWEIG's -999).
        wind_dir_deg=float(direction) % 360 if direction not in (None, 0, 990) else -999.0,
        kdown_wm2=round(row["Q"] * 1e4 / 3600.0, 1),  # J/cm2 per hour -> W/m2
        pressure_kpa=row["P"] / 100.0 if row.get("P") else DEFAULT_PRESSURE_KPA,  # 0.1 hPa -> kPa
        source=f"KNMI {stn} {name}"[:60],
    )
    return met, {"id": stn, "name": name, "distance_km": round(distance, 1)}


def relative_humidity(t_c, td_c):
    """RH (%) from air and dew-point temperature (Magnus, Alduchov & Eskridge 1996)."""
    def es(t):
        return 6.1094 * math.exp(17.625 * t / (t + 243.04))
    return max(0.0, min(100.0, 100.0 * es(td_c) / es(t_c)))


def wind_from(u, v):
    """Speed (m/s) and meteorological direction the wind blows FROM (0 = N, 90 = E) of u/v components."""
    return math.hypot(u, v), (math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0


def era5_from_values(values):
    """ERA5 hourly band values (K, Pa, m/s, J/m2 per hour) -> Met."""
    t_c = values["temperature_2m"] - 273.15
    td_c = values["dewpoint_temperature_2m"] - 273.15
    speed, direction = wind_from(values["u_component_of_wind_10m"], values["v_component_of_wind_10m"])
    return Met(
        ta_c=round(t_c, 2),
        rh_pct=round(relative_humidity(t_c, td_c), 1),
        wind_ms=round(speed, 2),
        wind_dir_deg=round(direction, 1),
        kdown_wm2=round(max(values["surface_solar_radiation_downwards"], 0.0) / 3600.0, 1),
        pressure_kpa=round(values["surface_pressure"] / 1000.0, 2),
        source="ERA5",
    )


ERA5_BANDS = ("temperature_2m", "dewpoint_temperature_2m", "surface_pressure",
              "u_component_of_wind_10m", "v_component_of_wind_10m", "surface_solar_radiation_downwards")


def era5_hourly(when_utc, lon, lat):
    """ERA5 at (lon, lat) for the hour ending at `when_utc` (ssrd is accumulated over that hour)."""
    import ee

    from urban_heat.lst import gee

    gee.initialize()
    start = when_utc.astimezone(timezone.utc)
    image = (ee.ImageCollection(ERA5_ASSET)
             .filterDate(ee.Date(start.isoformat()), ee.Date((start + timedelta(minutes=30)).isoformat()))
             .first())
    try:
        values = ee.Algorithms.If(
            image, ee.Image(image).select(list(ERA5_BANDS)).reduceRegion(
                ee.Reducer.first(), ee.Geometry.Point([lon, lat]), 1000), None).getInfo()
    except ee.EEException as e:
        raise MetError(f"ERA5 could not be read from Earth Engine: {e}") from None
    if not values or any(values.get(b) is None for b in ERA5_BANDS):
        raise MetError(f"ERA5 has no data for {start:%Y-%m-%d %H}:00 UT yet (it runs ~5 days behind).")
    return era5_from_values(values), None
