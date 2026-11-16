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


# ── WBGT per cell from SOLWEIG's Tmrt (stored scenario runs) ──────────
#
#   WBGT = 0.7 Tnwb + 0.2 Tg + 0.1 Ta                    ISO 7243 (outdoors, in the sun)
#   Tg   : globe temperature that gives the cell's Tmrt with the ISO 7726
#          forced-convection globe equation (standard 150 mm black globe),
#            Tmrt⁴ = (Tg + 273.15)⁴ + 1.1e8 v^0.6 / (ε D^0.4) (Tg − Ta)
#          solved for Tg by Newton's method (monotone in Tg)
#   Tnwb : approximated by the psychrometric wet-bulb temperature of
#          Stull (2011), J. Appl. Meteor. Climatol. 50, 2267-2269 (valid for
#          RH 5-99 %, Ta −20-50 °C); the natural wet bulb is ~0.5-1 °C
#          warmer in the sun, so WBGT is slightly underestimated.
# v is the 10 m wind of the met, at least WBGT_MIN_WIND_MS.

WBGT_WEIGHTS = (0.7, 0.2, 0.1)          # Tnwb, Tg, Ta (ISO 7243)
GLOBE_EMISSIVITY = 0.95                 # ISO 7726
GLOBE_DIAMETER_M = 0.15                 # ISO 7726 standard globe
GLOBE_CONVECTION = 1.1e8                # ISO 7726 forced-convection coefficient
WBGT_MIN_WIND_MS = 0.1
KELVIN = 273.15
NEWTON_STEPS = 30


def stull_wet_bulb_c(ta_c, rh_pct):
    """Psychrometric wet-bulb temperature (°C), Stull (2011); scalars or numpy arrays."""
    import numpy as np

    t, rh = np.asarray(ta_c, dtype="float64"), np.asarray(rh_pct, dtype="float64")
    return (t * np.arctan(0.151977 * np.sqrt(rh + 8.313659)) + np.arctan(t + rh)
            - np.arctan(rh - 1.676331) + 0.00391838 * rh ** 1.5 * np.arctan(0.023101 * rh) - 4.686035)


def globe_temperature_c(tmrt_c, ta_c, wind_ms):
    """Globe temperature (°C) that gives `tmrt_c` (ISO 7726 forced convection), per cell."""
    import numpy as np

    tmrt = np.asarray(tmrt_c, dtype="float64")
    ta = np.asarray(ta_c, dtype="float64")
    v = max(float(wind_ms), WBGT_MIN_WIND_MS)
    k = GLOBE_CONVECTION * v ** 0.6 / (GLOBE_EMISSIVITY * GLOBE_DIAMETER_M ** 0.4)
    target = (tmrt + KELVIN) ** 4
    tg = np.broadcast_to(ta, tmrt.shape).astype("float64").copy()
    for _ in range(NEWTON_STEPS):
        f = (tg + KELVIN) ** 4 + k * (tg - ta) - target
        tg = tg - f / (4 * (tg + KELVIN) ** 3 + k)
    return tg


def wbgt_outdoor_c(ta_c, rh_pct, wind_ms, tmrt_c):
    """
    Outdoor WBGT (°C) per cell from the met (scalars) and SOLWEIG's Tmrt
    (array): 0.7 Tnwb + 0.2 Tg + 0.1 Ta (see above). NaN cells stay NaN.

    DAG edges: Meteorology -> WBGT, Tmrt -> WBGT (stored scenario runs)
    """
    w_nwb, w_g, w_a = WBGT_WEIGHTS
    tg = globe_temperature_c(tmrt_c, ta_c, wind_ms)
    return w_nwb * stull_wet_bulb_c(ta_c, rh_pct) + w_g * tg + w_a * ta_c
