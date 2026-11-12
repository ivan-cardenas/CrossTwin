"""
Heat stress from the weather alone, for the heat panel's weather what-if.

Pure functions, no ORM: urban_heat/views.py::_build_indicators calls them
with the live weather (weather/live.py) or the panel's override values, and
nothing is written. They are screening estimates for a person outdoors,
not a replacement for the stored SOLWEIG rasters (Tmrt/UTCI/PET), which
resolve shade, walls and wind per cell.

    e      = RH/100 x 6.105 x exp(17.27 Ta / (237.7 + Ta))          [hPa]
    AT     = Ta + 0.348 e - 0.70 ws + 0.70 Q / (ws + 10) - 4.25      [°C]
             (Steadman 1994, Australian BoM form; Q = 0 in the shade)
    Q      = a x fp x K                                              [W/m²]
             absorbed shortwave per unit body surface: absorptivity
             a = 0.7, projected-area factor of a standing person
             fp = 0.25 (ISO 7726 / Fanger); longwave balance ignored
    WBGT   = 0.567 Ta + 0.393 e + 3.94                               [°C]
             (BoM approximation for average daytime conditions; no wind
             or radiation term)

DAG edges: Meteorology -> UTCI, Meteorology -> PET (weather-only proxies;
dashboard what-if, never stored)
"""
import math

ABSORPTIVITY = 0.7
PROJECTED_AREA_FACTOR = 0.25

# Ranges of the panel's what-if inputs (the server clamps overrides to them).
WEATHER_LIMITS = {
    "ta_c": (-20.0, 45.0),
    "rh_pct": (0.0, 100.0),
    "wind_ms": (0.0, 25.0),
    "kdown_wm2": (0.0, 1100.0),
}


def clamp_weather(name, value):
    low, high = WEATHER_LIMITS[name]
    return min(max(float(value), low), high)


def vapour_pressure_hpa(ta_c, rh_pct):
    """Water vapour pressure (hPa) from air temperature and relative humidity."""
    return rh_pct / 100 * 6.105 * math.exp(17.27 * ta_c / (237.7 + ta_c))


def absorbed_radiation_w_m2(kdown_wm2):
    """Q of the apparent temperature: shortwave absorbed per unit body surface."""
    return ABSORPTIVITY * PROJECTED_AREA_FACTOR * max(kdown_wm2 or 0.0, 0.0)


def apparent_temperature_c(ta_c, rh_pct, wind_ms, q_w_m2=0.0):
    """Steadman apparent temperature (°C); q_w_m2 = 0 gives the shade value."""
    e = vapour_pressure_hpa(ta_c, rh_pct)
    ws = max(wind_ms or 0.0, 0.0)
    return ta_c + 0.348 * e - 0.70 * ws + 0.70 * q_w_m2 / (ws + 10) - 4.25


def wbgt_estimate_c(ta_c, rh_pct):
    """BoM approximate WBGT (°C) from air temperature and humidity."""
    return 0.567 * ta_c + 0.393 * vapour_pressure_hpa(ta_c, rh_pct) + 3.94


def weather_heat_stress(ta_c, rh_pct, wind_ms, kdown_wm2):
    """
    {'apparent_shade_c', 'apparent_sun_c', 'wbgt_estimate_c'} for one set
    of weather values, or None when air temperature or humidity is missing.
    """
    if ta_c is None or rh_pct is None:
        return None
    wind = wind_ms or 0.0
    return {
        "apparent_shade_c": round(apparent_temperature_c(ta_c, rh_pct, wind), 1),
        "apparent_sun_c": round(apparent_temperature_c(
            ta_c, rh_pct, wind, absorbed_radiation_w_m2(kdown_wm2)), 1),
        "wbgt_estimate_c": round(wbgt_estimate_c(ta_c, rh_pct), 1),
    }
