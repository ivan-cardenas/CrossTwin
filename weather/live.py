"""
Live weather at a point from Open-Meteo's forecast API (current conditions,
a model nowcast updated every 15 minutes; no key). Shown in the map's
weather pill (core/static/js/WeatherPill.js) and used as the baseline of the
heat panel's weather what-if (urban_heat/views.py). Nothing is stored.

Answers are cached per ~2 km grid cell for CACHE_TTL seconds, so panning the
map or reopening a panel does not call the API again. OPEN_METEO_URL in
.env overrides the endpoint; LIVE_WEATHER=false (tests, offline use) turns
the lookup off, and callers fall back to stored station data.
"""
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

DEFAULT_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_TTL = 600            # seconds
GRID_DEG = 0.02            # cache cell (~2 km)
TIMEOUT = 8                # seconds
CURRENT = ("temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,"
           "shortwave_radiation,precipitation,weather_code,is_day")

# WMO weather interpretation codes (Open-Meteo docs) -> (label, day icon, night icon)
WEATHER_CODES = {
    0: ("Clear sky", "☀️", "🌙"),
    1: ("Mainly clear", "🌤️", "🌙"),
    2: ("Partly cloudy", "⛅", "☁️"),
    3: ("Overcast", "☁️", "☁️"),
    45: ("Fog", "🌫️", "🌫️"),
    48: ("Rime fog", "🌫️", "🌫️"),
    51: ("Light drizzle", "🌦️", "🌧️"),
    53: ("Drizzle", "🌦️", "🌧️"),
    55: ("Dense drizzle", "🌧️", "🌧️"),
    56: ("Freezing drizzle", "🌧️", "🌧️"),
    57: ("Freezing drizzle", "🌧️", "🌧️"),
    61: ("Light rain", "🌦️", "🌧️"),
    63: ("Rain", "🌧️", "🌧️"),
    65: ("Heavy rain", "🌧️", "🌧️"),
    66: ("Freezing rain", "🌧️", "🌧️"),
    67: ("Freezing rain", "🌧️", "🌧️"),
    71: ("Light snow", "🌨️", "🌨️"),
    73: ("Snow", "🌨️", "🌨️"),
    75: ("Heavy snow", "❄️", "❄️"),
    77: ("Snow grains", "🌨️", "🌨️"),
    80: ("Rain showers", "🌦️", "🌧️"),
    81: ("Rain showers", "🌧️", "🌧️"),
    82: ("Violent rain showers", "⛈️", "⛈️"),
    85: ("Snow showers", "🌨️", "🌨️"),
    86: ("Snow showers", "🌨️", "🌨️"),
    95: ("Thunderstorm", "⛈️", "⛈️"),
    96: ("Thunderstorm with hail", "⛈️", "⛈️"),
    99: ("Thunderstorm with hail", "⛈️", "⛈️"),
}


class LiveWeatherError(RuntimeError):
    """Open-Meteo could not be reached or answered without current values."""


def enabled():
    return getattr(settings, "LIVE_WEATHER", True)


def describe(code, is_day=True):
    """(label, icon) of a WMO weather code."""
    label, day, night = WEATHER_CODES.get(code, ("Unknown", "🌡️", "🌡️"))
    return label, day if is_day else night


def parse_current(payload):
    """Open-Meteo JSON -> the values CrossTwin uses (SI units; None when missing)."""
    current = (payload or {}).get("current")
    if not current or current.get("temperature_2m") is None:
        raise LiveWeatherError("Open-Meteo answered without current weather.")
    code = current.get("weather_code")
    is_day = bool(current.get("is_day", 1))
    label, icon = describe(code, is_day)
    return {
        "ta_c": current.get("temperature_2m"),
        "rh_pct": current.get("relative_humidity_2m"),
        "wind_ms": current.get("wind_speed_10m"),
        "wind_dir_deg": current.get("wind_direction_10m"),
        "kdown_wm2": current.get("shortwave_radiation"),
        "precip_mm": current.get("precipitation"),
        "weather_code": code,
        "description": label,
        "icon": icon,
        "time": current.get("time"),
        "timezone": payload.get("timezone"),
        "lat": payload.get("latitude"),
        "lon": payload.get("longitude"),
        "source": "Open-Meteo",
    }


def current_weather(lat, lon):
    """Current weather at (lat, lon), WGS84. Raises LiveWeatherError."""
    import requests

    if not enabled():
        raise LiveWeatherError("Live weather is turned off (LIVE_WEATHER=false).")
    cell = (round(lat / GRID_DEG) * GRID_DEG, round(lon / GRID_DEG) * GRID_DEG)
    key = f"live-weather:{cell[0]:.2f}:{cell[1]:.2f}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    url = getattr(settings, "OPEN_METEO_URL", None) or DEFAULT_URL
    try:
        response = requests.get(url, params={
            "latitude": f"{cell[0]:.4f}", "longitude": f"{cell[1]:.4f}",
            "current": CURRENT, "wind_speed_unit": "ms", "timezone": "auto",
        }, timeout=TIMEOUT)
        response.raise_for_status()
        values = parse_current(response.json())
    except (requests.RequestException, ValueError) as e:
        raise LiveWeatherError(f"Live weather could not be retrieved: {e}") from None
    cache.set(key, values, CACHE_TTL)
    return values


def current_weather_or_none(lat, lon):
    """current_weather(), or None (logged) when it fails or is turned off."""
    if not enabled():
        return None
    try:
        return current_weather(lat, lon)
    except LiveWeatherError as e:
        logger.info("%s", e)
        return None
