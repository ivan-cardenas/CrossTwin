"""
Colormap + value-range resolution for raster tile rendering.

Previously every raster on the map was rendered with a single hardcoded
colormap and rescale ('viridis', '0,40') via `getattr(instance, 'colormap',
'viridis')` in core/views.py — an attribute that doesn't exist on any model,
so every raster silently fell back to the same default regardless of what it
actually contained. NDVI (-1..1) or UTCI (-40..46) collapsed to a sliver near
the bottom of a 0..40 scale, which is why the map showed no visible color
range.

This module picks a colormap and value range from the satellite/process
metadata added onto the raster models (`index`, `satellite_type`/`source` —
see common/models.py, urban_heat/models.py), falling back to per-model
defaults, and to live statistics from TiTiler when no fixed range is known
for the data (e.g. population density, nighttime lights).
"""
import logging
from urllib.parse import quote

import requests
from django.conf import settings
from rio_tiler.colormap import cmap as rio_cmap

logger = logging.getLogger(__name__)

# Spectral index / product -> (colormap_name, (min, max) | None, label, unit).
# Matched against the raster's `index` field (case-insensitive), which holds
# the openEO process / WCS layer / GEE band that produced it — see
# importer/external_data.py::load_raster_into_target_model.
# `None` for the range means "compute it from the actual pixel data" (used
# for products with no fixed physical bounds, e.g. population density).
INDEX_STYLES = {
    "NDVI": ("rdylgn", (-1, 1), "NDVI (Vegetation Index)", ""),
    "NDWI": ("rdbu", (-1, 1), "NDWI (Water Index)", ""),
    "MOISTURE_INDEX": ("ylgnbu", (-1, 1), "Moisture Index", ""),
    # Multi-band RGB composite — no colormap, but it still needs a rescale:
    # openEO's TRUE_COLOR download is float32 reflectance-like DNs (observed
    # range ~700-20000 after the *2.5 brightening in fetch_openeo), not the
    # 0-255 a renderer expects, so without this every tile request came back
    # essentially blank/black — this was the actual cause of "downloads fine
    # but isn't visible on the map".
    "TRUE_COLOR": (None, (0, 8000), "True Color", ""),
    "LGN2021": ("tab20", None, "Land Cover (LGN2021)", ""),
    "WORLDCOVER_2021_MAP": ("tab20", None, "ESA WorldCover", ""),
    "SEASONALITY": ("blues", (0, 12), "Water Seasonality", "months/yr"),
    "LOSSYEAR": ("ylorrd", (1, 23), "Forest Loss Year", "since 2000"),
    "GAIN": ("greens", (0, 1), "Forest Gain (2000-2012)", ""),
    "LABEL": ("tab20", (0, 8), "Dynamic World Land Cover", ""),
    "SM_SURFACE": ("blues", (0, 1), "Soil Moisture", "m³/m³"),
    "POPULATION": ("ylorrd", None, "Population Density", "people/ha"),
    "AVG_RAD": ("inferno", None, "Nighttime Lights", "nW/cm²/sr"),
}

# Categorical products: legend still shows a gradient over the value range,
# but callers can use this to skip drawing a continuous scale if desired.
CATEGORICAL_INDICES = {"LGN2021", "WORLDCOVER_2021_MAP", "LABEL"}

# Fallback by "app_label.model_name", used when the raster has no `index`
# value (SOLWEIG thermal-comfort outputs, elevation models, etc).
MODEL_STYLES = {
    "urban_heat.meanradianttemperature": ("inferno", (0, 70), "Mean Radiant Temperature", "°C"),
    "urban_heat.utci": ("rdylbu_r", (-40, 46), "UTCI", "°C"),
    "urban_heat.skyviewfactor": ("viridis", (0, 1), "Sky View Factor", ""),
    "urban_heat.pet": ("rdylbu_r", (4, 41), "PET", "°C"),
    "urban_heat.landsurfacetemperature": ("inferno", (0, 50), "Land Surface Temperature", "°C"),
    "urban_heat.surfaceurbanheatislandintensity": ("rdylbu_r", (-2, 8), "SUHII", "°C"),
    "common.digitalelevationmodel": ("terrain", None, "Elevation", "m"),
    "common.digitalsurfacemodel": ("terrain", None, "Surface Height", "m"),
}

DEFAULT_STYLE = ("viridis", None, "Value", "")


def _lookup_style(instance, registry_key):
    """Shared index/model lookup used by both the tile colormap and the
    display name, so a raster is labeled the same way everywhere."""
    index_value = (getattr(instance, "index", None) or "").strip().upper()
    style = INDEX_STYLES.get(index_value)
    categorical = index_value in CATEGORICAL_INDICES
    if style is None:
        style = MODEL_STYLES.get(registry_key, DEFAULT_STYLE)
    return style, categorical


def raster_display_name(instance, registry_key, fallback=None):
    """
    Build a display name matching the legend label plus the acquisition
    date as MM-YY, e.g. 'NDVI (Vegetation Index) - 09-26', instead of the
    generic '<Model verbose name> <id>' (e.g. 'Land Cover Raster 4') used
    when a raster has no `name` field of its own.
    """
    style, _ = _lookup_style(instance, registry_key)
    label = style[2]
    if label == DEFAULT_STYLE[2] and fallback:
        label = fallback

    date_value = getattr(instance, "date", None) or getattr(instance, "date_time", None)
    if date_value:
        return f"{label} - {date_value.strftime('%m-%y')}"
    return label


def _cog_statistics(cog_path):
    """Fetch band-1 min/max from TiTiler for products with no fixed range."""
    try:
        cog_url = f"file://{cog_path}"
        encoded_url = quote(cog_url, safe="/:")
        resp = requests.get(
            f"{settings.TITILER_BASE_URL}/cog/statistics",
            params={"url": encoded_url},
            timeout=15,
        )
        resp.raise_for_status()
        stats = resp.json()
        band_stats = next(iter(stats.values()))
        return float(band_stats["min"]), float(band_stats["max"])
    except Exception as e:
        logger.warning(f"Could not fetch raster statistics for {cog_path}: {e}")
        return None


def resolve_raster_style(instance, registry_key):
    """
    Returns {colormap, rescale: (min, max) | None, label, unit, categorical}
    for a raster instance. `colormap` is None for multi-band RGB composites
    (e.g. true-color imagery), where TiTiler renders the bands directly and
    a colormap would be meaningless.
    """
    style, categorical = _lookup_style(instance, registry_key)
    colormap, rescale, label, unit = style

    if colormap is not None and rescale is None:
        rescale = _cog_statistics(instance.cog_path)

    return {
        "colormap": colormap,
        "rescale": rescale,
        "label": label,
        "unit": unit,
        "categorical": categorical,
    }


def colormap_legend_stops(colormap_name, rescale, steps=6):
    """
    Sample `steps` evenly spaced (value, '#rrggbb') stops directly from the
    rio-tiler colormap lookup table, so the legend gradient is guaranteed to
    match what TiTiler actually paints (rather than approximating it with a
    separately maintained JS palette).
    """
    if not colormap_name or not rescale:
        return []

    table = rio_cmap.get(colormap_name)
    vmin, vmax = rescale
    stops = []
    for i in range(steps):
        frac = i / (steps - 1) if steps > 1 else 0
        idx = round(frac * 255)
        r, g, b = table.get(idx, (0, 0, 0, 255))[:3]
        value = vmin + frac * (vmax - vmin)
        stops.append({"value": round(value, 3), "color": f"#{r:02x}{g:02x}{b:02x}"})
    return stops
