from django.shortcuts import render, redirect

import re
import json
from django.http import HttpResponse, JsonResponse, Http404
from django.core.serializers import serialize
from django.contrib.gis.db import models as gis_models
from django.db import connection, transaction
from django.apps import apps

from django.conf import settings
from django.urls import reverse

from core.utils import VECTOR_REGISTRY, WMS_REGISTRY, RASTER_REGISTRY, MODEL_REGISTRY
from core.rasterStyles import raster_display_name
from core.landCoverStyles import build_landcover_style_and_legend


# Ordered from most specific to least — first match wins
_UNIT_PATTERNS = [
    (r'\bppl/km[²2]\b|people per square kilo',      'ppl/km²'),
    (r'\bMm[³3]/(?:day|d)\b|Million cubic meters? per day',  'Mm³/day'),
    (r'\bMm[³3]/(?:yr|year)\b|Million cubic meters? per year', 'Mm³/yr'),
    (r'\bm[³3]/(?:yr|year)\b|cubic meters? per year',          'm³/yr'),
    (r'\bm[³3]/(?:day|d)\b|cubic meters? per day',             'm³/day'),
    (r'\bL/person/day\b|liters? per person per day',            'L/person/day'),
    (r'\bEUR/m[³3]\b|EUR per cubic met',             '€/m³'),
    (r'\bcm/h\b|centimeters? per hour',              'cm/h'),
    (r'\bkg[_ ]CO2/h\b|kg CO2 per hour',             'kg CO₂/h'),
    (r'\bkm[²2]\b|square kilo',                      'km²'),
    (r'\bm[²2]\b|square met',                        'm²'),
    (r'\bkm\b|kilometer',                            'km'),
    (r'\b(?:EUR|euro)\b',                            '€'),
    (r'\bh(?:ours?)? per day\b',                     'h/day'),
    (r'\bhours?\b',                                  'h'),
    (r'%\s*per\s*year|percent.*per\s*year',          '%/yr'),
    (r'\bin\s*%\b|percent(?:age)?',                  '%'),
]


def _extract_unit(help_text: str) -> str | None:
    if not help_text:
        return None
    for pattern, unit in _UNIT_PATTERNS:
        if re.search(pattern, help_text, re.IGNORECASE):
            return unit
    return None


def _field_metadata(model) -> dict:
    """Return {field_name: {label, help_text, unit}} for simple (non-geometry) fields."""
    meta = {}
    for f in model._meta.get_fields():
        if f.many_to_many or f.one_to_many:
            continue
        if isinstance(f, gis_models.GeometryField):
            continue
        if not hasattr(f, 'column'):
            continue
        help_text = getattr(f, 'help_text', '') or ''
        field_class = type(f).__name__
        if 'DateTime' in field_class:
            field_type = 'datetime'
        elif 'Date' in field_class:
            field_type = 'date'
        else:
            field_type = 'other'
        meta[f.name] = {
            'label': f.verbose_name.title() if hasattr(f, 'verbose_name') else f.name.replace('_', ' ').title(),
            'help_text': str(help_text),
            'unit': _extract_unit(str(help_text)),
            'type': field_type,
        }
    return meta



def _display_field(related_model):
    """Pick the field on a related model that best represents it in a popup:
    the first plain CharField (e.g. cityName, districtName), falling back to the PK."""
    for mf in related_model._meta.get_fields():
        if not hasattr(mf, 'column') or mf.is_relation or mf.primary_key:
            continue
        if mf.get_internal_type() == 'CharField':
            return mf
    return related_model._meta.pk


def map_view(request):
    """Display the map page."""
    context = {
        'mapbox_access_token': settings.MAPBOX_ACCESS_TOKEN,
    }
    return render(request, 'mainMap.html', context)

def admin_unit_at_point(request):
    """
    Point-in-polygon lookup for the map center: resolve the smallest
    administrative unit (Neighborhood > District > City > Province)
    containing the given WGS84 point and return its level, name, and
    population.
    URL: /api/admin-unit/?lng=<lng>&lat=<lat>
    """
    from administrative.admin_units import ADMIN_LEVELS, resolve_admin_unit_at_point

    try:
        lng = float(request.GET.get('lng'))
        lat = float(request.GET.get('lat'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'lng and lat query params are required'}, status=400)

    level, unit = resolve_admin_unit_at_point(lng, lat)
    if unit is None:
        return JsonResponse({'level': None, 'location': None, 'population': None})

    name_field = ADMIN_LEVELS[level][1]
    return JsonResponse({
        'level': level,
        'location': getattr(unit, name_field),
        'population': unit.currentPopulation,
    })

def _resolve_summary_unit(request):
    """
    The administrative unit the population views talk about, as
    (level, unit, is_selection).

    `level`/`location` are the unit the user explicitly picked. Without them (or
    if they match no record) the WGS84 `lng`/`lat` of the map center is resolved
    to its smallest unit and then to that unit's City (a Province has none, so a
    point that only falls inside a province reports the province).
    """
    from administrative.admin_units import city_of, resolve_admin_unit, resolve_admin_unit_at_point

    level = request.GET.get('level')
    if level and request.GET.get('location'):
        try:
            unit = resolve_admin_unit(level, request.GET['location'])
        except Exception:  # e.g. duplicate names: treat as "nothing selected"
            unit = None
        if unit is not None:
            return level, unit, True

    try:
        lng = float(request.GET.get('lng'))
        lat = float(request.GET.get('lat'))
    except (TypeError, ValueError):
        return None, None, False

    level, unit = resolve_admin_unit_at_point(lng, lat)
    city = city_of(unit) if unit is not None else None
    if city is not None:
        return 'city', city, False
    return level, unit, False


def _unit_context(level, unit, is_selection):
    from administrative.admin_units import ADMIN_LEVELS

    if unit is None:
        return {'unit': None, 'is_selection': is_selection}
    model, name_field = ADMIN_LEVELS[level]
    return {
        'unit': unit,
        'is_selection': is_selection,
        'level_label': model._meta.verbose_name.title(),
        'name': getattr(unit, name_field),
    }


def dashboard_summary(request):
    """
    HTMX partial for the Dashboard panel: total population of the selected
    administrative unit, or of the city around the map center when nothing is
    selected. (The forecast graph and what-if controls live in the bottom dock,
    see population_panel.)
    URL: /api/dashboard/summary/?level=<level>&location=<name>[&lng=<lng>&lat=<lat>]
    """
    level, unit, is_selection = _resolve_summary_unit(request)
    return render(request, 'mainMap/partials/dashboard_summary.html',
                  _unit_context(level, unit, is_selection))


def population_panel(request):
    """
    HTML for the bottom dock opened from the Population pill: today's population,
    the projection for the selected year, the forecast graph and the what-if
    controls. It is separate from the side panel so an indicator panel can stay
    open next to it.
    URL: /api/population/panel/?level=&location=&lng=&lat=&year=&pop_scenario=&pop_growth=
    """
    from administrative.population import population_params
    from .charts import build_population_chart, build_population_stats

    level, unit, is_selection = _resolve_summary_unit(request)
    pop_scenario, pop_growth = population_params(request.GET)
    try:
        year = int(request.GET.get('year'))
    except (TypeError, ValueError):
        year = None

    context = _unit_context(level, unit, is_selection)
    context.update({'pop_scenario': pop_scenario, 'pop_growth': pop_growth, 'year': year})
    if unit is not None:
        current = unit.currentPopulation or 0
        context['chart'] = build_population_chart(unit, pop_scenario, pop_growth, year, current)
        context['stats'] = build_population_stats(unit, pop_scenario, pop_growth, year, current)
    return render(request, 'mainMap/partials/population_panel.html', context)


# ── GeoJSON endpoint tuning (docs/PERFORMANCE.md §1) ─────────────────────────
# 6 decimal places of a degree is ~10 cm, well below one screen pixel at any
# zoom Mapbox renders; PostGIS's default of 9 only makes the payload bigger.
GEOJSON_PRECISION = 6
# Below this zoom, lines and polygons are simplified to about one screen pixel.
GEOJSON_SIMPLIFY_BELOW_ZOOM = 14
# Metres per pixel at zoom 0 on the equator for Mapbox GL's 512 px tiles.
_MAPBOX_METRES_PER_PIXEL_Z0 = 78271.517
_METRES_PER_DEGREE = 111_320.0
GEOJSON_CACHE_ALIAS = 'geojson'
# Short on purpose: edits made outside Django (QGIS, psql, other people's
# scripts) don't invalidate the cache, so this bounds how stale the map can get.
GEOJSON_CACHE_TTL = 120
# Whole-table responses of large layers are not cached: a local-memory cache
# would hold every one of them per process. Those layers load by viewport.
GEOJSON_CACHE_MAX_BYTES = 8 * 1024 * 1024


def _parse_bbox(raw):
    """`minLng,minLat,maxLng,maxLat` (WGS84) -> tuple of floats; ValueError if malformed."""
    parts = [float(v) for v in raw.split(',')]
    if len(parts) != 4:
        raise ValueError("bbox needs 4 comma-separated numbers")
    min_lng, min_lat, max_lng, max_lat = parts
    if not (-180 <= min_lng < max_lng <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValueError("bbox must be minLng,minLat,maxLng,maxLat in WGS84")
    return min_lng, min_lat, max_lng, max_lat


def _simplify_tolerance(zoom, lat, geodetic):
    """About one screen pixel at `zoom`, in the storage CRS's units (metres, or degrees if geodetic)."""
    import math
    metres = _MAPBOX_METRES_PER_PIXEL_Z0 * math.cos(math.radians(lat)) / (2 ** zoom)
    return metres / _METRES_PER_DEGREE if geodetic else metres


def _geojson_sql(model, geom_field, bbox=None, zoom=None):
    """
    (sql, params) returning the layer as one FeatureCollection JSON text.

    - FK columns come from LEFT JOINs on the related table (one hash join
      per FK) instead of a correlated sub-SELECT evaluated once per row.
    - `bbox` restricts the rows with `&&`, which uses the geometry's GiST index.
    - `zoom` below GEOJSON_SIMPLIFY_BELOW_ZOOM simplifies lines/polygons to
      about one pixel before reprojecting.
    """
    table = model._meta.db_table
    joins = []
    parts = []
    for f in model._meta.get_fields():
        if isinstance(f, gis_models.GeometryField):
            continue
        if f.many_to_many or f.one_to_many or not hasattr(f, 'column'):
            continue
        if f.is_relation and f.many_to_one:
            # FK fields: show the related object's name instead of its raw id
            related_model = f.related_model
            alias = f"j{len(joins)}"
            joins.append(
                f'LEFT JOIN "{related_model._meta.db_table}" {alias} '
                f'ON {alias}."{related_model._meta.pk.column}" = t."{f.column}"'
            )
            parts.append(f"'{f.name}', {alias}.\"{_display_field(related_model).column}\"")
        else:
            parts.append(f"'{f.name}', t.\"{f.column}\"")
    props_expr = f"json_build_object({', '.join(parts)})" if parts else "'{}'::json"

    params = []
    geom_expr = f't."{geom_field.column}"'
    is_point = geom_field.geom_type in ('POINT', 'MULTIPOINT')
    if zoom is not None and zoom < GEOJSON_SIMPLIFY_BELOW_ZOOM and not is_point:
        lat = (bbox[1] + bbox[3]) / 2 if bbox else 52.0   # the Netherlands, when no viewport is given
        geom_expr = f"ST_SimplifyPreserveTopology({geom_expr}, %s)"
        params.append(_simplify_tolerance(zoom, lat, geom_field.geodetic(connection)))

    where = ""
    if bbox:
        where = (
            f'WHERE t."{geom_field.column}" && '
            f'ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 4326), {geom_field.srid})'
        )
        params.extend(bbox)

    sql = f"""
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(json_agg(f.feature), '[]'::json)
        )::text
        FROM (
            SELECT json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(ST_Transform({geom_expr}, 4326), {GEOJSON_PRECISION})::json,
                'properties', {props_expr}
            ) AS feature
            FROM "{table}" t
            {' '.join(joins)}
            {where}
        ) f
    """
    return sql, params


def model_geojson(request, app_label, model_name):
    """
    Generic GeoJSON endpoint for any registered vector model.
    URL: /api/layers/<app_label>/<model_name>/geojson/[?bbox=minLng,minLat,maxLng,maxLat][&zoom=z]

    Without `bbox` the whole layer is returned. The map requests large
    layers by viewport instead (Layers.js, VIEWPORT_LOAD_MIN_FEATURES).
    Responses are cached per (layer, bbox, whole zoom level) and invalidated
    whenever the layer's rows change (core/cache.py).
    """
    from core.cache import get_cache, layer_version

    key = f"{app_label}.{model_name}"
    if key not in VECTOR_REGISTRY:
        raise Http404(f"Model {key} not found in registry")
    model = VECTOR_REGISTRY[key]

    geom_field = next(
        (f for f in model._meta.get_fields() if isinstance(f, gis_models.GeometryField)), None
    )
    if geom_field is None:
        raise Http404(f"Model {key} has no geometry field")

    try:
        bbox = _parse_bbox(request.GET['bbox']) if request.GET.get('bbox') else None
        # Whole zoom levels only: the simplification tolerance and the cache
        # key then change once per level instead of on every wheel tick.
        zoom = int(float(request.GET['zoom'])) if request.GET.get('zoom') else None
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    cache = get_cache(GEOJSON_CACHE_ALIAS)
    bbox_key = ','.join(f'{v:.5f}' for v in bbox) if bbox else 'all'
    zoom_key = zoom if zoom is not None and zoom < GEOJSON_SIMPLIFY_BELOW_ZOOM else 'full'
    cache_key = f"geojson:{key}:{layer_version(model)}:{bbox_key}:{zoom_key}"

    body = cache.get(cache_key)
    cache_status = 'HIT'
    if body is None:
        cache_status = 'MISS'
        sql, params = _geojson_sql(model, geom_field, bbox, zoom)
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            body = cursor.fetchone()[0]
        if len(body) <= GEOJSON_CACHE_MAX_BYTES:
            cache.set(cache_key, body, GEOJSON_CACHE_TTL)

    # PostgreSQL already produced the JSON text; parsing it into Python and
    # re-serialising it (JsonResponse) would only cost time and memory.
    response = HttpResponse(body, content_type='application/json')
    response['X-Cache'] = cache_status
    return response


LAYER_STYLES = {
    # ── administrative hierarchy ────────────────────────────────────────────
    'administrative.Province': {
        'color': '#37474f',
        'layers': [
            {'type': 'fill',   'paint': {'fill-color': '#37474f', 'fill-opacity': 0.08}},
            {'type': 'line',   'paint': {'line-color': '#37474f', 'line-width': 2.5}},
        ],
    },
    'administrative.City': {
        'color': '#1565c0',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#1565c0', 'fill-opacity': 0.1}},
            {'type': 'line', 'paint': {'line-color': '#1565c0', 'line-width': 2}},
        ],
    },
    'administrative.District': {
        'color': '#1976d2',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#1976d2', 'fill-opacity': 0.12}},
            {'type': 'line', 'paint': {'line-color': '#1976d2', 'line-width': 1.5, 'line-dasharray': [4, 2]}},
        ],
    },
    'administrative.Neighborhood': {
        'color': '#42a5f5',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#42a5f5', 'fill-opacity': 0.15}},
            {'type': 'line', 'paint': {'line-color': '#42a5f5', 'line-width': 1, 'line-dasharray': [3, 2]}},
        ],
    },
    'physicalEnv.LandCoverVector': {
        'color': '#558b2f',
    },

    # ── watersupply ────────────────────────────────────────────────────────
    'watersupply.UsersLocation': {
        'color': '#0277bd',
        'layers': [
            {'type': 'circle', 'paint': {'circle-radius': 5, 'circle-color': '#0277bd', 'circle-stroke-width': 1, 'circle-stroke-color': '#ffffff'}},
        ],
    },
    'watersupply.Watershed': {
        'color': '#0097a7',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#0097a7', 'fill-opacity': 0.15}},
            {'type': 'line', 'paint': {'line-color': '#0097a7', 'line-width': 1.5}},
        ],
    },
    'watersupply.PipeNetwork': {
        'color': '#00acc1',
        'layers': [
            {'type': 'line', 'paint': {'line-color': '#00acc1', 'line-width': 2.5, 'line-dasharray': [4, 1]}},
        ],
    },
    'watersupply.CoverageWaterSupply': {
        'color': '#26c6da',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#26c6da', 'fill-opacity': 0.2}},
            {'type': 'line', 'paint': {'line-color': '#26c6da', 'line-width': 1}},
        ],
    },
    'watersupply.AreaAffectedDrought': {
        'color': '#f57f17',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#f57f17', 'fill-opacity': 0.3}},
            {'type': 'line', 'paint': {'line-color': '#e65100', 'line-width': 1.5}},
        ],
    },

    # ── builtup ────────────────────────────────────────────────────────────
    'builtup.ZoningArea': {
        'color': '#f57c00',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#f57c00', 'fill-opacity': 0.2}},
            {'type': 'line', 'paint': {'line-color': '#f57c00', 'line-width': 1}},
        ],
    },
    'builtup.Street': {
        'color': '#8d6e63',
        'layers': [
            {'type': 'line', 'paint': {'line-color': '#8d6e63', 'line-width': 2}},
        ],
    },
    'builtup.Park': {
        'color': '#66bb6a',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#66bb6a', 'fill-opacity': 0.4}},
            {'type': 'line', 'paint': {'line-color': '#388e3c', 'line-width': 1}},
        ],
    },
    'builtup.Facility': {
        'color': '#ab47bc',
        'layers': [
            {'type': 'circle', 'paint': {'circle-radius': 7, 'circle-color': '#ab47bc', 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff'}},
        ],
    },
    'builtup.Building': {
        'color': '#ffa726',
        'layers': [
            {'type': 'fill-extrusion', 'paint': {
                'fill-extrusion-color': '#ffa726',
                'fill-extrusion-height': ['coalesce', ['get', 'height'], 10],
                'fill-extrusion-base': 0,
                'fill-extrusion-opacity': 0.75,
            }},
        ],
    },
    'builtup.Property': {
        'color': '#ef5350',
        'layers': [
            {'type': 'circle', 'paint': {'circle-radius': 5, 'circle-color': '#ef5350', 'circle-stroke-width': 1, 'circle-stroke-color': '#ffffff'}},
        ],
    },

    # ── Energy ─────────────────────────────────────────────────────────────
    'Energy.BuildingEnergyLabel': {
        'color': '#66bb6a',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': [
                'match', ['get', 'energyLabel'],
                'A+++', '#00441b', 'A++', '#00622a', 'A+', '#037f39',
                'A', '#1a9850', 'B', '#66bd63', 'C', '#a6d96a',
                'D', '#fee08b', 'E', '#fdae61', 'F', '#f46d43', 'G', '#d73027',
                '#9e9e9e',
            ], 'fill-opacity': 0.65}},
            {'type': 'line', 'paint': {'line-color': '#37474f', 'line-width': 0.5}},
        ],
    },

    # ── housing ────────────────────────────────────────────────────────────
    'housing.HousingProject': {
        'color': '#ec407a',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#ec407a', 'fill-opacity': 0.25}},
            {'type': 'line', 'paint': {'line-color': '#ec407a', 'line-width': 1.5, 'line-dasharray': [3, 2]}},
        ],
    },

    # ── nature ─────────────────────────────────────────────────────────────
    'nature.ProtectedArea': {
        'color': '#2e7d32',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#2e7d32', 'fill-opacity': 0.2}},
            {'type': 'line', 'paint': {'line-color': '#1b5e20', 'line-width': 1.5}},
        ],
    },
    'nature.WaterWaysLN': {
        'color': '#1e88e5',
        'layers': [
            {'type': 'line', 'paint': {'line-color': '#1e88e5', 'line-width': 2}},
        ],
    },
    'nature.WaterWaysPG': {
        'color': '#039be5',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#039be5', 'fill-opacity': 0.35}},
            {'type': 'line', 'paint': {'line-color': '#0277bd', 'line-width': 1}},
        ],
    },
    
    'nature.WaterBodies': {
        'color': '#039be5',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#039be5', 'fill-opacity': 0.35}},
            {'type': 'line', 'paint': {'line-color': '#0277bd', 'line-width': 1}},
        ],
    },
    'nature.Forests': {
        'color': '#388e3c',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#388e3c', 'fill-opacity': 0.35}},
            {'type': 'line', 'paint': {'line-color': '#1b5e20', 'line-width': 1}},
        ],
    },
    'nature.GreenSpaces': {
        'color': '#81c784',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#81c784', 'fill-opacity': 0.4}},
            {'type': 'line', 'paint': {'line-color': '#388e3c', 'line-width': 1}},
        ],
    },

    # ── urban_heat ─────────────────────────────────────────────────────────
    'urban_heat.NatureBasedSolutionPolygon': {
        'color': '#43a047',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#43a047', 'fill-opacity': 0.4}},
            {'type': 'line', 'paint': {'line-color': '#2e7d32', 'line-width': 1.5}},
        ],
    },
    'urban_heat.NatureBasedSolutionPoint': {
        'color': '#66bb6a',
        'layers': [
            {'type': 'circle', 'paint': {'circle-radius': 6, 'circle-color': '#66bb6a', 'circle-stroke-width': 2, 'circle-stroke-color': '#2e7d32'}},
        ],
    },

    # ── weather ────────────────────────────────────────────────────────────
    'weather.WeatherStation': {
        'color': '#7e57c2',
        'layers': [
            {'type': 'circle', 'paint': {'circle-radius': 7, 'circle-color': '#7e57c2', 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff'}},
        ],
    },
}

_FALLBACK_COLORS = [
    '#3388ff', '#e74c3c', '#2ecc71', '#9b59b6', '#f39c12',
    '#1abc9c', '#e91e63', '#00bcd4', '#ff5722', '#607d8b',
    '#8bc34a', '#673ab7', '#ffeb3b', '#795548', '#009688',
]


def available_layers(request):
    """
    Returns a list of all available layers (models with geometry fields).
    URL: /api/layers/
    Optional ?app_labels=common,builtup restricts the response to those
    apps. Every entry costs at least one model.objects.count() (WMS/raster
    entries cost a full .objects.all() query too), so computing the whole
    registry on every call is the main reason map init used to be slow —
    the frontend now asks for just 'common' first and fetches the rest of
    the catalog in the background (see Layers.js:fetchAvailableLayers).
    """
    layers = []

    color_index = 0

    app_labels_param = request.GET.get('app_labels')
    allowed_app_labels = set(app_labels_param.split(',')) if app_labels_param else None

    for key, model in VECTOR_REGISTRY.items():
        if allowed_app_labels is not None and key.split('.')[0] not in allowed_app_labels:
            continue

        # Find geometry field
        geom_field = None
        geom_type = None

        for field in model._meta.get_fields():
            if isinstance(field, gis_models.GeometryField):
                geom_field = field.name
                # Determine geometry type
                field_type = type(field).__name__
                if 'Point' in field_type:
                    geom_type = 'point'
                elif 'Line' in field_type:
                    geom_type = 'line'
                else:
                    geom_type = 'polygon'
                break
        
        if geom_field:
            app_label, model_name = key.split('.')

            # Get record count
            try:
                count = model.objects.count()
            except Exception:
                count = 0

            style_layers = LAYER_STYLES.get(key, {}).get('layers')
            legend = None

            if key == 'physicalEnv.LandCoverVector':
                # Categorical color-per-class_name — computed per-request
                # (not baked into LAYER_STYLES) since LandCoverClasses rows
                # are get_or_create'd from source data and grow over time.
                try:
                    style_layers, legend = build_landcover_style_and_legend()
                except Exception:
                    legend = None

            layer_entry = {
                'key': key,
                'app_label': app_label,
                'model_name': model_name,
                'display_name': model._meta.verbose_name_plural.title(),
                'url': f'/api/layers/{app_label}/{model_name}/geojson/',
                'geometry_type': geom_type,
                'geometry_field': geom_field,
                'color': LAYER_STYLES.get(key, {}).get('color', _FALLBACK_COLORS[color_index % len(_FALLBACK_COLORS)]),
                'style_layers': style_layers,
                'fields': _field_metadata(model),
                'count': count,
            }
            if legend:
                layer_entry['legend'] = legend
            layers.append(layer_entry)

            color_index += 1
    
    for key, model in WMS_REGISTRY.items() if WMS_REGISTRY else []:
        wms_app_label = key.split('.')[0]
        if allowed_app_labels is not None and wms_app_label not in allowed_app_labels:
            continue

        wms_instances = model.objects.all()

        for wms in wms_instances:
            has_time_dimension = getattr(wms, 'has_time_dimension', False)
            # A WMS configured with an API key must be fetched server-side —
            # Mapbox's raster tile source can't attach an Authorization
            # header, and the key must never reach the browser — so route
            # tile requests through weather:wms_tile_proxy instead of the
            # real WMS URL. The proxy forwards whatever querystring the
            # frontend builds, so nothing else about the tile URL changes.
            requires_proxy = bool(getattr(wms, 'api_key_setting', None))
            wms_url = (
                reverse('weather:wms_tile_proxy', args=[wms.name])
                if requires_proxy else wms.url
            )

            # A stored legend_url is a static image and fine as-is for an
            # anonymous WMS, but an authenticated one needs the same
            # Authorization header as tiles — the browser can't attach it to
            # a plain <img src>, so route GetLegendGraphic through the same
            # proxy too. If no legend_url was configured at all, derive the
            # standard GetLegendGraphic request from layers_param — most WMS
            # servers support it without needing anything KNMI-specific.
            legend_qs = f'service=WMS&request=GetLegendGraphic&version=1.3.0&format=image/png&layer={wms.layers_param}'
            if requires_proxy:
                legend_url = f"{wms_url}?{legend_qs}"
            elif wms.legend_url:
                legend_url = wms.legend_url
            else:
                separator = '&' if '?' in wms.url else '?'
                legend_url = f'{wms.url}{separator}{legend_qs}'

            layer_entry = {
                'key': f'wms-{wms.name}',
                'display_name': wms.display_name,
                'app_label': wms_app_label,  # groups it under watersupply
                'geometry_type': 'raster',
                'color': wms.color,
                'count': 'WMS',
                'layer_type': 'wms',  # ← frontend uses this
                'wms_url': wms_url,
                'wms_layers': wms.layers_param,
                'legend_url': legend_url,
                'opacity': wms.opacity,
                'has_time_dimension': has_time_dimension,
                'is_active': wms.is_active,
            }
            if has_time_dimension:
                layer_entry['time_frame_count'] = wms.time_frame_count
                layer_entry['time_refresh_minutes'] = wms.time_refresh_minutes
                layer_entry['time_endpoint'] = reverse('weather:wms_time_steps', args=[wms.name])
            layers.append(layer_entry)
            
    # Raster Registry
    for key, model in RASTER_REGISTRY.items():
        app_label, model_name = key.split('.')
        if allowed_app_labels is not None and app_label not in allowed_app_labels:
            continue

        raster_instances = model.objects.all()
        
        for raster in raster_instances:
            if not raster.cog_path:
                continue
                
            fallback_name = getattr(raster, 'name', None) or f'{model._meta.verbose_name} {raster.id}'
            layers.append({
                'key': f'raster-{app_label}-{model_name}-{raster.id}',
                'display_name': raster_display_name(raster, key, fallback_name),
                'app_label': app_label,
                'model_name': model_name,
                'layer_type': 'raster',
                'raster_id': raster.id,
                'geometry_type': 'raster',
                'color': '#ff6b6b',
                'count': 1,
                # ✅ Point to your existing endpoint
                'tile_url_template': f'/api/raster/{app_label}/{model_name}/tiles/?id={raster.id}',
                'opacity': getattr(raster, 'opacity', 0.7),
                'colormap': getattr(raster, 'colormap', 'viridis'),
                'rescale': getattr(raster, 'rescale', '0,40'),
            })
            
    return JsonResponse({'layers': layers})


# Below this many rows (planner estimate) an exact ST_Extent scan is cheap
# enough, and unlike the estimate it is never stale.
ESTIMATED_EXTENT_MIN_ROWS = 100_000


def layer_bounds(request, app_label, model_name):
    """
    Returns the bounding box of a layer in WGS84, as [[west, south], [east, north]]
    (what Mapbox GL's fitBounds takes).
    URL: /api/layers/<app_label>/<model_name>/bounds/

    For large tables it uses ST_EstimatedExtent, which answers from the
    planner's statistics instead of scanning the table. Those statistics are
    only as fresh as the last ANALYZE, so smaller tables (where a scan is
    cheap anyway) and tables without statistics get the exact ST_Extent.
    """
    key = f"{app_label}.{model_name}"
    if key not in MODEL_REGISTRY:
        raise Http404(f"Model '{key}' not found in registry")
    model = MODEL_REGISTRY[key]

    geom_field = next(
        (f for f in model._meta.get_fields() if isinstance(f, gis_models.GeometryField)), None
    )
    if geom_field is None:
        raise Http404(f"Model '{key}' has no geometry field")

    table = model._meta.db_table
    to_wgs84 = (
        "SELECT ST_XMin(b), ST_YMin(b), ST_XMax(b), ST_YMax(b) "
        f"FROM (SELECT ST_Transform(ST_SetSRID(%s::box2d::geometry, {geom_field.srid}), 4326)::box2d AS b) s"
    )
    with connection.cursor() as cursor:
        extent = None
        cursor.execute("SELECT reltuples FROM pg_class WHERE oid = to_regclass(%s)", [f'"{table}"'])
        row = cursor.fetchone()
        if row and row[0] >= ESTIMATED_EXTENT_MIN_ROWS:
            try:
                with transaction.atomic():   # a failure here must not poison the fallback query
                    cursor.execute(
                        "SELECT ST_EstimatedExtent(current_schema()::text, %s, %s)::text",
                        [table, geom_field.column],
                    )
                    extent = cursor.fetchone()[0]
            except Exception:
                extent = None
        if extent is None:
            cursor.execute(f'SELECT ST_Extent("{geom_field.column}")::text FROM "{table}"')
            extent = cursor.fetchone()[0]
        if extent is None:
            return JsonResponse({'bounds': None})

        cursor.execute(to_wgs84, [extent])
        west, south, east, north = cursor.fetchone()

    return JsonResponse({'bounds': [[west, south], [east, north]]})
