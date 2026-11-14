"""
KNMI'23 climate scenarios as a what-if on the dashboards' meteorology.

The Klimaateffectatlas (klimaateffectatlas.nl) shows the KNMI'23 scenarios as
the current climate, 2050 high and 2100 high in its map viewer, and the low
scenarios in its climate statistics. KNMI'23 splits each
emission level into a dry and a wet variant: Ld, Ln (low emissions) and
Hd, Hn (high), for the horizons 2050 (2036-2065) and 2100 (2086-2115). A
scenario here is one of these, keyed ``"<horizon>_<pathway>"`` (``"2050_Hd"``),
plus ``"current"`` (the 1991-2020 reference, no change).

The changes are the national averages of Table 1 of KNMI (2023), *KNMI'23
climate scenarios for the Netherlands*, KNMI Publication 23-03 (pp. 3-4),
relative to 1991-2020. They are applied with the delta-change method: the
observed weather (live, station or a KNMI year) plus the change of its
season. Pure: no queries, no clock.

Heat: Table 1 gives 30-year seasonal means, and the hottest days of the year
warm more than the *average* daily maximum (KNMI'23, "Extreme temperatures").
Two heat modes therefore exist (HEAT_MODES):

- "average" (default): the season's change of the average daily maximum by
  day and minimum by night (Table 1). Understates heat-wave stress.
- "warmest" (heat-wave day): the change of the warmest day of the year at
  the nearest of KNMI's five KNMI'23 key-figure stations (De Bilt, Den
  Helder, Groningen, Maastricht, Vlissingen; KNMI'23 data portal,
  STATION_EXTREMES), by day and night, with the summer changes of
  humidity, wind and radiation. Apply it to a hot observed day.

Table 1 has no national warmest-day figure, hence the stations. Rain
extremes do have one and the design rain event uses it (design_rain_mm).

DAG edge: Climate_Change -> Meteorology (what-if only, never stored)
"""
import math

KNMI23_SOURCE = (
    "KNMI (2023), KNMI'23 climate scenarios for the Netherlands, KNMI Publication 23-03, "
    "Table 1 (country averages, change relative to 1991-2020)"
)
KNMI23_URL = "https://www.knmi.nl/klimaatscenarios"

CURRENT = "current"
HORIZONS = {"2050": "2036-2065", "2100": "2086-2115"}
PATHWAYS = {
    "Ld": {"emissions": "low", "variant": "dry", "label": "Low, dry"},
    "Ln": {"emissions": "low", "variant": "wet", "label": "Low, wet"},
    "Hd": {"emissions": "high", "variant": "dry", "label": "High, dry"},
    "Hn": {"emissions": "high", "variant": "wet", "label": "High, wet"},
}
# The three choices of the Klimaateffectatlas map viewer. Its "high" is the
# high-emission pair; the dry variant (Hd) is the default here because it is
# the heat and drought stress case, the wet one (Hn) the heavy-rain case.
KEA_PRESETS = (CURRENT, "2050_Hd", "2100_Hd")
KEA_LABELS = {CURRENT: "Current", "2050_Hd": "2050 high", "2100_Hd": "2100 high"}

SEASONS = ("winter", "spring", "summer", "autumn")
# Meteorological seasons: DJF, MAM, JJA, SON.
SEASON_OF_MONTH = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}

# Reference climate 1991-2020 (Table 1): solar radiation is needed to turn a
# W/m² change of the seasonal mean into a factor on an instantaneous value.
REFERENCE_KDOWN_WM2 = {"year": 120, "winter": 34, "spring": 161, "summer": 206, "autumn": 77}

# Table 1, one tuple per indicator in the column order
# 2050 Ld, Ln, Hd, Hn, 2100 Ld, Ln, Hd, Hn.
#   t_c       average temperature, °C
#   tx_c      average daily maximum temperature, °C
#   tn_c      average daily minimum temperature, °C
#   precip_pct precipitation amount, %
#   kdown_wm2 average solar radiation, W/m²
#   rh_pp     average relative humidity, percentage points
#   wind_ms   average wind speed, m/s
#   et_pct    potential evaporation (Makkink), %
#   rain_1d_10y_pct summer 1-day precipitation exceeded once every 10 years, % (central value)
#   rain_1h_1y_pct  summer hourly precipitation exceeded once per year, % (central value)
_COLUMNS = ("2050_Ld", "2050_Ln", "2050_Hd", "2050_Hn", "2100_Ld", "2100_Ln", "2100_Hd", "2100_Hn")
_TABLE_1 = {
    "year": {
        "t_c":        (0.9, 0.9, 1.6, 1.5, 0.9, 0.9, 4.4, 4.1),
        "precip_pct": (0, 3, -2, 3, 0, 3, -3, 8),
        "kdown_wm2":  (5.8, 4.8, 5.4, 2.5, 5.8, 4.8, 7.1, 1.3),
        "rh_pp":      (-1, -1, -1, 0, -1, -1, -1, 1),
        "et_pct":     (7, 6, 9, 6, 7, 6, 17, 11),
        "wind_ms":    (-0.1, -0.1, 0.0, 0.0, -0.1, -0.1, -0.1, -0.1),
    },
    "winter": {
        "t_c":        (0.7, 0.7, 1.2, 1.3, 0.7, 0.7, 3.7, 3.9),
        "tx_c":       (0.7, 0.7, 1.1, 1.2, 0.7, 0.7, 3.5, 3.6),
        "tn_c":       (0.7, 0.7, 1.2, 1.4, 0.7, 0.7, 4.0, 4.2),
        "precip_pct": (4, 5, 4, 7, 4, 5, 14, 24),
        "kdown_wm2":  (1.2, 1.5, 0.8, 0.4, 1.2, 1.5, -0.7, -1.5),
        "rh_pp":      (0, 0, 1, 1, 0, 0, 1, 2),
        "wind_ms":    (-0.1, -0.1, 0.0, 0.1, -0.1, -0.1, 0.1, 0.2),
    },
    "spring": {
        "t_c":        (0.8, 0.7, 1.3, 1.1, 0.8, 0.7, 3.6, 3.3),
        "tx_c":       (0.9, 0.8, 1.2, 1.0, 0.9, 0.8, 3.3, 2.9),
        "tn_c":       (0.7, 0.7, 1.4, 1.3, 0.7, 0.7, 3.9, 3.7),
        "precip_pct": (1, 3, 0, 4, 1, 3, 4, 10),
        "kdown_wm2":  (6.6, 5.2, 3.2, 0.8, 6.6, 5.2, -0.2, -4.8),
        "rh_pp":      (-1, -1, 0, 0, -1, -1, 1, 2),
        "et_pct":     (6, 5, 6, 4, 6, 5, 10, 6),
        "wind_ms":    (-0.1, -0.1, 0.0, 0.0, -0.1, -0.1, 0.1, 0.0),
    },
    "summer": {
        "t_c":        (1.2, 1.1, 2.1, 1.7, 1.2, 1.1, 5.1, 4.7),
        "tx_c":       (1.4, 1.2, 2.2, 1.7, 1.4, 1.2, 5.4, 4.7),
        "tn_c":       (1.0, 1.0, 1.9, 1.8, 1.0, 1.0, 5.0, 4.9),
        "precip_pct": (-8, -2, -13, -5, -8, -2, -29, -12),
        "rain_1d_10y_pct": (4, 5, 6, 9, 4, 5, 15, 26),
        "rain_1h_1y_pct":  (4, 6, 6, 11, 4, 6, 15, 31),
        "kdown_wm2":  (12, 9.1, 14, 7.4, 12, 9.1, 24, 11),
        "rh_pp":      (-2, -1, -2, -1, -2, -1, -4, -1),
        "et_pct":     (8, 6, 11, 7, 8, 6, 22, 14),
        "wind_ms":    (-0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.2, -0.2),
    },
    "autumn": {
        "t_c":        (1.0, 0.9, 1.8, 1.6, 1.0, 0.9, 5.0, 4.8),
        "tx_c":       (1.1, 1.1, 1.9, 1.6, 1.1, 1.1, 5.1, 4.6),
        "tn_c":       (0.9, 0.9, 1.8, 1.7, 0.9, 0.9, 5.1, 5.1),
        "precip_pct": (4, 5, 1, 4, 4, 5, 1, 13),
        "kdown_wm2":  (3.7, 3.5, 3.7, 1.4, 3.7, 3.5, 5.4, 1.0),
        "rh_pp":      (-1, 0, -1, 0, -1, 0, -1, 0),
        "wind_ms":    (-0.1, -0.1, -0.1, 0.0, -0.1, -0.1, -0.2, -0.1),
    },
}
# Global warming of each scenario relative to 1850-1900 (Table 1), for the labels.
GLOBAL_WARMING_C = dict(zip(_COLUMNS, (1.7, 1.7, 2.4, 2.4, 1.7, 1.7, 4.9, 4.9)))

DELTAS = {
    key: {
        period: {name: values[i] for name, values in indicators.items()}
        for period, indicators in _TABLE_1.items()
    }
    for i, key in enumerate(_COLUMNS)
}
SCENARIOS = (CURRENT,) + _COLUMNS

# Below this solar radiation (W/m²) the weather counts as night: the
# temperature change is then the daily minimum's, otherwise the daily maximum's.
NIGHT_KDOWN_WM2 = 1.0

# ── Heat-wave day: KNMI'23 key figures per station ─────────────────────
STATIONS_SOURCE = (
    "KNMI (2023), KNMI'23 climate scenarios, key figures per station "
    "(klimaatscenarios-data.knmi.nl, table 'Temperatuur', change relative to 1991-2020; "
    "retrieved 2026-11-14)"
)
STATIONS_URL = "https://klimaatscenarios-data.knmi.nl"

HEAT_AVERAGE = "average"
HEAT_WARMEST = "warmest"
HEAT_MODES = {
    HEAT_AVERAGE: "Average day",
    HEAT_WARMEST: "Warmest day of the year",
}

# The five stations of KNMI's key-figure tables (KNMI station number and
# location; De Kooy for Den Helder, Eelde for Groningen, Beek for Maastricht).
STATIONS = {
    "De Bilt": {"knmi_id": 260, "lat": 52.100, "lng": 5.180},
    "Den Helder": {"knmi_id": 235, "lat": 52.928, "lng": 4.781},
    "Groningen": {"knmi_id": 280, "lat": 53.125, "lng": 6.585},
    "Maastricht": {"knmi_id": 380, "lat": 50.906, "lng": 5.762},
    "Vlissingen": {"knmi_id": 310, "lat": 51.442, "lng": 3.596},
}
DEFAULT_STATION = "De Bilt"

# Per station: (1991-2020 value, changes in the column order of _COLUMNS).
#   warmest_day_c    warmest day of the year ("warmste dag per jaar"), °C.
#                    The portal does not define it; its 1991-2020 values
#                    (De Bilt 25.5 °C) are those of the warmest daily mean,
#                    so the change is applied to the day and the night alike.
#   days_tx30        days with maximum ≥ 30 °C per year
#   days_tx35        days with maximum ≥ 35 °C per year
#   tropical_nights  nights with minimum ≥ 20 °C per year
_STATION_TABLE = {
    "De Bilt": {
        "warmest_day_c": (25.5, (1.7, 1.5, 3.0, 2.3, 1.7, 1.5, 6.9, 5.6)),
        "days_tx30": (5.0, (4.9, 3.9, 8.7, 5.4, 4.9, 3.9, 34, 23)),
        "days_tx35": (0.2, (0.5, 0.3, 1.4, 0.8, 0.5, 0.3, 8.1, 4.1)),
        "tropical_nights": (0.3, (0.9, 0.9, 3.1, 2.1, 0.9, 0.9, 24, 20)),
    },
    "Den Helder": {
        "warmest_day_c": (24.2, (1.2, 1.2, 1.8, 1.7, 1.2, 1.2, 4.6, 4.3)),
        "days_tx30": (1.3, (0.7, 0.7, 1.2, 1.0, 0.7, 0.7, 5.8, 4.8)),
        "days_tx35": (0.0, (0.1, 0.1, 0.2, 0.2, 0.1, 0.1, 1.2, 0.8)),
        "tropical_nights": (1.0, (1.6, 1.6, 3.9, 2.8, 1.6, 1.6, 26, 23)),
    },
    "Groningen": {
        "warmest_day_c": (24.9, (1.6, 1.5, 2.5, 1.9, 1.6, 1.5, 6.0, 5.1)),
        "days_tx30": (5.1, (5.2, 5.2, 7.4, 5.0, 5.2, 5.2, 27, 18)),
        "days_tx35": (0.2, (0.9, 0.6, 1.2, 0.7, 0.9, 0.6, 5.4, 3.3)),
        "tropical_nights": (0.1, (0.4, 0.5, 1.6, 1.3, 0.4, 0.5, 14, 13)),
    },
    "Maastricht": {
        "warmest_day_c": (26.9, (1.5, 1.2, 3.0, 2.3, 1.5, 1.2, 7.4, 6.0)),
        "days_tx30": (7.7, (8.2, 6.5, 12, 8.3, 8.2, 6.5, 47, 34)),
        "days_tx35": (0.7, (1.6, 1.1, 2.7, 1.6, 1.6, 1.1, 15, 7.8)),
        "tropical_nights": (0.7, (1.3, 1.1, 5.5, 4.1, 1.3, 1.1, 37, 30)),
    },
    "Vlissingen": {
        "warmest_day_c": (24.5, (1.5, 1.3, 2.2, 1.9, 1.5, 1.3, 5.5, 4.8)),
        "days_tx30": (2.3, (1.7, 1.3, 3.6, 2.3, 1.7, 1.3, 13, 10)),
        "days_tx35": (0.1, (0.3, 0.2, 0.5, 0.4, 0.3, 0.2, 3.2, 1.7)),
        "tropical_nights": (1.4, (1.8, 1.5, 5.5, 3.5, 1.8, 1.5, 41, 35)),
    },
}
STATION_EXTREMES = {
    station: {
        name: {"reference": ref, **dict(zip(_COLUMNS, changes))}
        for name, (ref, changes) in table.items()
    }
    for station, table in _STATION_TABLE.items()
}
STATION_ROWS = (
    ("warmest_day_c", "Warmest day", "°C"),
    ("days_tx30", "Days ≥ 30 °C", "/yr"),
    ("days_tx35", "Days ≥ 35 °C", "/yr"),
    ("tropical_nights", "Tropical nights", "/yr"),
)


def normalize_heat(mode):
    """A valid heat mode, HEAT_AVERAGE for anything else."""
    return mode if mode in HEAT_MODES else HEAT_AVERAGE


def nearest_station(lat=None, lng=None):
    """
    The key-figure station closest to a WGS84 point (equirectangular
    distance, enough at the scale of the Netherlands); DEFAULT_STATION
    without a point.
    """
    if lat is None or lng is None:
        return DEFAULT_STATION
    cos_lat = math.cos(math.radians(lat))
    return min(
        STATIONS,
        key=lambda s: (STATIONS[s]["lat"] - lat) ** 2 + ((STATIONS[s]["lng"] - lng) * cos_lat) ** 2,
    )


def warmest_day_change(key, station=DEFAULT_STATION):
    """Change of the warmest day of the year (°C) at a station; 0 for CURRENT."""
    key = normalize(key)
    if key == CURRENT:
        return 0.0
    station = station if station in STATION_EXTREMES else DEFAULT_STATION
    return STATION_EXTREMES[station]["warmest_day_c"][key]


def station_table(key, station=None):
    """
    The heat key figures of a scenario as display rows, one per station
    (`station` first when given): [{'station', 'cells': [{'label', 'unit',
    'reference', 'change', 'future'}]}]; [] for CURRENT.
    """
    key = normalize(key)
    if key == CURRENT:
        return []
    order = sorted(STATION_EXTREMES, key=lambda s: (s != station, s))
    rows = []
    for name in order:
        cells = []
        for indicator, label, unit in STATION_ROWS:
            values = STATION_EXTREMES[name][indicator]
            cells.append({
                "indicator": indicator, "label": label, "unit": unit,
                "reference": values["reference"], "change": values[key],
                "future": round(values["reference"] + values[key], 1),
            })
        rows.append({"station": name, "nearest": name == station, "cells": cells})
    return rows


def normalize(key):
    """A valid scenario key, or CURRENT for anything else (None, '', unknown)."""
    return key if key in DELTAS else CURRENT


def describe(key):
    """Display data of a scenario: key, horizon, pathway, labels, global warming."""
    key = normalize(key)
    if key == CURRENT:
        return {
            "key": CURRENT, "horizon": None, "pathway": None, "active": False,
            "label": "Current climate", "short": "Current", "period": "1991-2020",
            "emissions": None, "variant": None, "global_warming_c": None,
            "kea_preset": True,
        }
    horizon, pathway = key.split("_")
    info = PATHWAYS[pathway]
    return {
        "key": key, "horizon": horizon, "pathway": pathway, "active": True,
        "label": f"{horizon} {info['label']} ({pathway})",
        "short": f"{horizon} {info['label']}",
        "period": HORIZONS[horizon],
        "emissions": info["emissions"], "variant": info["variant"],
        "global_warming_c": GLOBAL_WARMING_C[key],
        "kea_preset": key in KEA_PRESETS,
    }


# Rows of the Scenarios panel's table: (indicator, label, unit, format).
TABLE_ROWS = (
    ("t_c", "Temperature", "°C", "{:+.1f}"),
    ("tx_c", "Daily maximum", "°C", "{:+.1f}"),
    ("tn_c", "Daily minimum", "°C", "{:+.1f}"),
    ("precip_pct", "Precipitation", "%", "{:+.0f}"),
    ("kdown_wm2", "Solar radiation", "W/m²", "{:+.1f}"),
    ("rh_pp", "Relative humidity", "%-pt", "{:+.0f}"),
    ("wind_ms", "Wind speed", "m/s", "{:+.1f}"),
    ("et_pct", "Evaporation (Makkink)", "%", "{:+.0f}"),
)
TABLE_PERIODS = ("year",) + SEASONS


def scenario_table(key):
    """
    The Table 1 changes of a scenario as display rows:
    [{'label', 'unit', 'cells': [text or '—' per TABLE_PERIODS]}]; [] for CURRENT.
    """
    key = normalize(key)
    if key == CURRENT:
        return []
    rows = []
    for name, label, unit, fmt in TABLE_ROWS:
        cells = [DELTAS[key][p].get(name) for p in TABLE_PERIODS]
        rows.append({
            "label": label, "unit": unit,
            "cells": ["—" if v is None else fmt.format(v) for v in cells],
        })
    return rows


def season_of_month(month):
    """Meteorological season of a month (1-12); summer when unknown."""
    return SEASON_OF_MONTH.get(month, "summer")


def deltas(key, period):
    """The Table 1 changes of a scenario for 'year' or a season ({} for CURRENT)."""
    key = normalize(key)
    if key == CURRENT:
        return {}
    return dict(DELTAS[key][period])


def apply_to_weather(weather, key, month=None, heat=HEAT_AVERAGE, station=DEFAULT_STATION):
    """
    Observed weather (ta_c, rh_pct, wind_ms, kdown_wm2) moved into a scenario
    with the delta-change of its season (`month`, 1-12; summer when None):

        ta    + ΔTx (day, kdown > NIGHT_KDOWN_WM2) or ΔTn (night)
        rh    + ΔRH (percentage points), within 0-100
        wind  + Δwind, at least 0
        kdown × (K_ref + ΔK) / K_ref   (K_ref = the season's 1991-2020 mean)

    heat = HEAT_WARMEST (heat-wave day): ta + ΔT of the warmest day of the
    year at `station` (day and night), the other changes those of summer.

    Missing values stay missing; other keys are copied. CURRENT returns the
    weather unchanged.
    """
    if weather is None:
        return None
    key = normalize(key)
    out = dict(weather)
    if key == CURRENT:
        return out
    warmest = normalize_heat(heat) == HEAT_WARMEST
    season = "summer" if warmest else season_of_month(month)
    d = DELTAS[key][season]
    kdown = weather.get("kdown_wm2")
    if weather.get("ta_c") is not None:
        if warmest:
            change = warmest_day_change(key, station)
        else:
            daytime = kdown is not None and kdown > NIGHT_KDOWN_WM2
            change = d["tx_c"] if daytime else d["tn_c"]
        out["ta_c"] = round(weather["ta_c"] + change, 1)
    if weather.get("rh_pct") is not None:
        out["rh_pct"] = round(min(100.0, max(0.0, weather["rh_pct"] + d["rh_pp"])), 1)
    if weather.get("wind_ms") is not None:
        out["wind_ms"] = round(max(0.0, weather["wind_ms"] + d["wind_ms"]), 1)
    if kdown is not None:
        ref = REFERENCE_KDOWN_WM2[season]
        out["kdown_wm2"] = round(kdown * (ref + d["kdown_wm2"]) / ref, 1)
    return out


def design_rain_mm(rain_mm, key):
    """
    A summer design rain event in a scenario: rain × (1 + Δ), Δ = the change
    of the summer 1-day precipitation exceeded once every 10 years (central
    value of Table 1).
    """
    key = normalize(key)
    if key == CURRENT:
        return rain_mm
    return round(rain_mm * (100 + DELTAS[key]["summer"]["rain_1d_10y_pct"]) / 100, 1)


def apply_to_daily_rain(daily_rain_mm, months, key):
    """
    A year of daily rain in a scenario: each day × (1 + its season's change of
    the precipitation amount). Without `months` (one per day) the yearly
    change is used. Extremes are not scaled separately (delta-change on the
    seasonal mean).
    """
    key = normalize(key)
    if key == CURRENT:
        return list(daily_rain_mm)
    table = DELTAS[key]
    if not months or len(months) != len(daily_rain_mm):
        factor = 1 + table["year"]["precip_pct"] / 100
        return [p * factor if p else p for p in daily_rain_mm]
    return [
        p * (1 + table[season_of_month(m)]["precip_pct"] / 100) if p else p
        for p, m in zip(daily_rain_mm, months)
    ]


def apply_to_et(et_ref_mm_yr, key):
    """Yearly Makkink reference ET in a scenario: × (1 + the yearly change)."""
    key = normalize(key)
    if key == CURRENT or et_ref_mm_yr is None:
        return et_ref_mm_yr
    return et_ref_mm_yr * (1 + DELTAS[key]["year"]["et_pct"] / 100)
