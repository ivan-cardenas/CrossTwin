from django.shortcuts import render
from django.db.models import Avg

from common.models import Province as PM
from .calculations import (
    calculate_vegetation_coverage,
    calculate_urban_morphology,
    get_thermal_indices,
    classify_pet,
    classify_utci,
    calculate_nbs_coverage,
    get_latest_meteorology,
)


# ── constants ─────────────────────────────────────────────────────────
MAX_UTCI = 46       # extreme heat stress threshold
MAX_PET  = 41       # extreme heat stress threshold
MAX_LST  = 50       # upper display bound for LST gauge

# ── shared helper ─────────────────────────────────────────────────────
def _get_province_data(location):
    """Fetch all urban-heat-related data for a province. Returns a dict."""
    try:
        province = PM.objects.get(ProvinceName=location)
    except PM.DoesNotExist:
        return None

    vegetation = calculate_vegetation_coverage(province)
    morphology = calculate_urban_morphology(province)
    thermal = get_thermal_indices(province)
    nbs = calculate_nbs_coverage(province)
    meteo = get_latest_meteorology(province)

    return {
        'province': province,
        'vegetation': vegetation,
        'morphology': morphology,
        'thermal': thermal,
        'nbs': nbs,
        'meteorology': meteo,
    }


MOCK_DATA = {
    'province': type('Province', (), {
        'ProvinceName': 'Demo', 'area_km2': 150,
        'currentPopulation': 500_000,
    })(),
    'vegetation': {
        'park_area_km2': 8.5,
        'green_lc_km2': 22.3,
        'total_green_km2': 30.8,
        'vegetation_coverage_pct': 20.5,
    },
    'morphology': {
        'building_count': 12_400,
        'avg_building_height_m': 9.2,
        'max_building_height_m': 42.0,
        'total_footprint_km2': 4.8,
        'street_count': 3_200,
        'avg_street_width_m': 8.5,
        'aspect_ratio': 1.08,
    },
    'thermal': {
        'lst':   {'min': 22.1, 'max': 38.5, 'mean': 30.2, 'stddev': 3.1, 'count': 48000},
        'tmrt':  {'min': 18.5, 'max': 55.2, 'mean': 38.7, 'stddev': 8.2, 'count': 48000},
        'pet':   {'min': 14.0, 'max': 42.3, 'mean': 28.6, 'stddev': 5.4, 'count': 48000},
        'utci':  {'min': 12.5, 'max': 39.8, 'mean': 26.4, 'stddev': 4.8, 'count': 48000},
        'svf':   {'min': 0.12, 'max': 0.98, 'mean': 0.62, 'stddev': 0.18, 'count': 48000},
        'suhii': {'min': 0.5, 'max': 5.2, 'mean': 2.8, 'stddev': 1.1, 'count': 48000},
    },
    'nbs': {
        'polygon_count': 45,
        'point_count': 120,
        'total_count': 165,
        'total_area_km2': 1.25,
        'total_area_m2': 1_250_000,
    },
    'meteorology': {
        'temperature_C': 22.5,
        'humidity_pct': 65.0,
        'wind_speed_m_s': 3.2,
        'precipitation_mm': 0.0,
        'solar_radiation_W_m2': 580.0,
        'datetime': None,
    },
}


def _build_indicators(data):
    """Pure function: takes raw data dict, returns display-ready indicators."""
    thermal = data.get('thermal', {})
    vegetation = data.get('vegetation', {})
    morphology = data.get('morphology', {})
    nbs = data.get('nbs', {})
    meteo = data.get('meteorology') or {}

    # Extract mean values from thermal indices (or None)
    lst_stats  = thermal.get('lst')
    tmrt_stats = thermal.get('tmrt')
    pet_stats  = thermal.get('pet')
    utci_stats = thermal.get('utci')
    svf_stats  = thermal.get('svf')
    suhii_stats = thermal.get('suhii')

    lst_mean  = lst_stats['mean']  if lst_stats  else None
    tmrt_mean = tmrt_stats['mean'] if tmrt_stats else None
    pet_mean  = pet_stats['mean']  if pet_stats  else None
    utci_mean = utci_stats['mean'] if utci_stats else None
    svf_mean  = svf_stats['mean']  if svf_stats  else None
    suhii_mean = suhii_stats['mean'] if suhii_stats else None

    return {
        # ── Thermal indices ──
        'lst_mean':   lst_mean,
        'lst_min':    lst_stats['min']  if lst_stats  else None,
        'lst_max':    lst_stats['max']  if lst_stats  else None,
        'lst_pct':    round(min(lst_mean / MAX_LST * 100, 100), 1) if lst_mean else 0,

        'tmrt_mean':  tmrt_mean,
        'tmrt_min':   tmrt_stats['min'] if tmrt_stats else None,
        'tmrt_max':   tmrt_stats['max'] if tmrt_stats else None,

        'pet_mean':   pet_mean,
        'pet_min':    pet_stats['min']  if pet_stats  else None,
        'pet_max':    pet_stats['max']  if pet_stats  else None,
        'pet_pct':    round(min(pet_mean / MAX_PET * 100, 100), 1) if pet_mean else 0,
        'pet_category': classify_pet(pet_mean),

        'utci_mean':  utci_mean,
        'utci_min':   utci_stats['min'] if utci_stats else None,
        'utci_max':   utci_stats['max'] if utci_stats else None,
        'utci_pct':   round(min(utci_mean / MAX_UTCI * 100, 100), 1) if utci_mean else 0,
        'utci_category': classify_utci(utci_mean),

        'svf_mean':   svf_mean,
        'svf_min':    svf_stats['min']  if svf_stats  else None,
        'svf_max':    svf_stats['max']  if svf_stats  else None,
        'svf_pct':    round(svf_mean * 100, 1) if svf_mean else 0,

        'suhii_mean': suhii_mean,
        'suhii_min':  suhii_stats['min'] if suhii_stats else None,
        'suhii_max':  suhii_stats['max'] if suhii_stats else None,

        # ── Vegetation ──
        'vegetation_pct':     vegetation.get('vegetation_coverage_pct', 0),
        'park_area_km2':      vegetation.get('park_area_km2', 0),
        'green_lc_km2':       vegetation.get('green_lc_km2', 0),
        'total_green_km2':    vegetation.get('total_green_km2', 0),

        # ── Urban morphology ──
        'building_count':     morphology.get('building_count', 0),
        'avg_height_m':       morphology.get('avg_building_height_m', 0),
        'max_height_m':       morphology.get('max_building_height_m', 0),
        'footprint_km2':      morphology.get('total_footprint_km2', 0),
        'avg_street_width_m': morphology.get('avg_street_width_m', 0),
        'aspect_ratio':       morphology.get('aspect_ratio', 0),

        # ── NBS (response) ──
        'nbs_count':          nbs.get('total_count', 0),
        'nbs_area_km2':       nbs.get('total_area_km2', 0),
        'nbs_area_m2':        nbs.get('total_area_m2', 0),

        # ── Meteorology ──
        'air_temp_C':         meteo.get('temperature_C'),
        'humidity_pct':       meteo.get('humidity_pct'),
        'wind_speed_m_s':     meteo.get('wind_speed_m_s'),
        'solar_radiation':    meteo.get('solar_radiation_W_m2'),
    }


# ── views ─────────────────────────────────────────────────────────────
def heat_indicators(request, location):
    """Main urban heat dashboard view.

    Serves the full page on normal requests, or just the panel
    partial on HTMX requests (for embedding in the main map sidebar).
    """
    data = _get_province_data(location)
    if data is None:
        data = MOCK_DATA

    context = {
        'Province': data['province'],
        'indicators': _build_indicators(data),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'urban_heat/partials/indicators_panel.html', context)
    return render(request, 'urban_heat/heat_indicators.html', context)


def recalculate_indicators(request, location):
    """HTMX endpoint: recalculate with optional vegetation override.

    This allows what-if analysis: "what if vegetation coverage were X%?"
    """
    data = _get_province_data(location)
    if data is None:
        data = MOCK_DATA

    # Allow vegetation override for scenario analysis
    veg_override = request.GET.get('vegetation_pct')
    indicators = _build_indicators(data)

    if veg_override is not None:
        indicators['vegetation_pct'] = float(veg_override)

    return render(request, 'urban_heat/partials/indicators_grid.html', {'indicators': indicators})
