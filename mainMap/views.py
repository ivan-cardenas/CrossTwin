from django.shortcuts import render, redirect

import re
import json
from django.http import JsonResponse, Http404
from django.core.serializers import serialize
from django.contrib.gis.db import models as gis_models
from django.db import connection
from django.apps import apps

from django.conf import settings

from core.utils import VECTOR_REGISTRY, WMS_REGISTRY, RASTER_REGISTRY, MODEL_REGISTRY


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

def model_geojson(request, app_label, model_name):
    """
    Generic GeoJSON endpoint for any registered model.
    URL: /api/<app_label>/<model_name>/geojson/
    """
    # Find the model in registry
    key = f"{app_label}.{model_name}"
    
    if key not in VECTOR_REGISTRY:
        raise Http404(f"Model {key} not found in registry")
    
    model = VECTOR_REGISTRY[key]
    
    # Find the geometry field automatically
    geom_field = None
    for field in model._meta.get_fields():
        if isinstance(field, gis_models.GeometryField):
            geom_field = field.name
            break
    
    if not geom_field:
        raise Http404(f"Model {key} has no geometry field")
    
    # Get all non-geometry fields for properties (use db_column if available)
    # EXCLUDE ManyToMany and reverse relations
    table_name = model._meta.db_table
    property_fields = []
    for f in model._meta.get_fields():
        # Skip if it's a geometry field
        if isinstance(f, gis_models.GeometryField):
            continue

        # Skip ManyToMany fields and reverse relations
        if f.many_to_many or f.one_to_many:
            continue

        # Only include fields that have actual database columns
        if not hasattr(f, 'column'):
            continue

        if f.is_relation and f.many_to_one:
            # FK fields: show the related object's name instead of its raw id
            related_model = f.related_model
            related_field = _display_field(related_model)
            related_table = related_model._meta.db_table
            expr = (
                f'(SELECT "{related_field.column}" FROM "{related_table}" '
                f'WHERE "{related_table}"."{related_model._meta.pk.column}" = '
                f'"{table_name}"."{f.column}")'
            )
            property_fields.append({'name': f.name, 'expr': expr})
        else:
            property_fields.append({
                'name': f.name,
                'column': f.column  # Actual database column name
            })

    # Build properties JSON object with quoted column names
    if property_fields:
        parts = [
            f"'{pf['name']}', {pf['expr']}" if 'expr' in pf
            else f"'{pf['name']}', \"{pf['column']}\""
            for pf in property_fields
        ]
        props_sql = ", ".join(parts)
        props_expr = f"json_build_object({props_sql})"
    else:
        props_expr = "'{}'::json"
    
    # Quote the geometry field name too
    sql = f"""
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(json_agg(
                json_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(ST_Transform("{geom_field}", 4326))::json,
                    'properties', {props_expr}
                )
            ), '[]'::json)
        )
        FROM "{table_name}"
    """
    
    with connection.cursor() as cursor:
        cursor.execute(sql)
        result = cursor.fetchone()[0]
    
    return JsonResponse(result, safe=False)


LAYER_STYLES = {
    # ── common — administrative hierarchy ──────────────────────────────────
    'common.Province': {
        'color': '#37474f',
        'layers': [
            {'type': 'fill',   'paint': {'fill-color': '#37474f', 'fill-opacity': 0.08}},
            {'type': 'line',   'paint': {'line-color': '#37474f', 'line-width': 2.5}},
        ],
    },
    'common.City': {
        'color': '#1565c0',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#1565c0', 'fill-opacity': 0.1}},
            {'type': 'line', 'paint': {'line-color': '#1565c0', 'line-width': 2}},
        ],
    },
    'common.District': {
        'color': '#1976d2',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#1976d2', 'fill-opacity': 0.12}},
            {'type': 'line', 'paint': {'line-color': '#1976d2', 'line-width': 1.5, 'line-dasharray': [4, 2]}},
        ],
    },
    'common.Neighborhood': {
        'color': '#42a5f5',
        'layers': [
            {'type': 'fill', 'paint': {'fill-color': '#42a5f5', 'fill-opacity': 0.15}},
            {'type': 'line', 'paint': {'line-color': '#42a5f5', 'line-width': 1, 'line-dasharray': [3, 2]}},
        ],
    },
    'common.LandCoverVector': {
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
    'nature.WaterWays': {
        'color': '#1e88e5',
        'layers': [
            {'type': 'line', 'paint': {'line-color': '#1e88e5', 'line-width': 2}},
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
    """
    layers = []

    color_index = 0
        
    for key, model in VECTOR_REGISTRY.items():
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
            
            layers.append({
                'key': key,
                'app_label': app_label,
                'model_name': model_name,
                'display_name': model._meta.verbose_name_plural.title(),
                'url': f'/api/layers/{app_label}/{model_name}/geojson/',
                'geometry_type': geom_type,
                'geometry_field': geom_field,
                'color': LAYER_STYLES.get(key, {}).get('color', _FALLBACK_COLORS[color_index % len(_FALLBACK_COLORS)]),
                'style_layers': LAYER_STYLES.get(key, {}).get('layers'),
                'fields': _field_metadata(model),
                'count': count,
            })
            
            color_index += 1
    
    for key, model in WMS_REGISTRY.items() if WMS_REGISTRY else []:
        wms_instances = model.objects.all()
        
        for wms in wms_instances:
            layers.append({
                'key': f'wms-{wms.name}',
                'display_name': wms.display_name,
                'app_label': wms.app_label,  # groups it under watersupply
                'geometry_type': 'raster',
                'color': wms.color,
                'count': 'WMS',
                'layer_type': 'wms',  # ← frontend uses this
                'wms_url': wms.url,
                'wms_layers': wms.layers_param,
                'legend_url': wms.legend_url or '',
                'opacity': wms.opacity,
            })
            
    # Raster Registry
    for key, model in RASTER_REGISTRY.items():
        app_label, model_name = key.split('.')
        raster_instances = model.objects.all()
        
        for raster in raster_instances:
            if not raster.cog_path:
                continue
                
            layers.append({
                'key': f'raster-{app_label}-{model_name}-{raster.id}',
                'display_name': getattr(raster, 'name', None) or f'{model._meta.verbose_name} {raster.id}',
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


def layer_bounds(request, app_label, model_name):
    """
    Returns the bounding box extent of a layer.
    URL: /api/<app_label>/<model_name>/bounds/
    """
    key = f"{app_label}.{model_name}"
    
    if key not in MODEL_REGISTRY:
        raise Http404(f"Model '{key}' not found in registry")
    
    model = MODEL_REGISTRY[key]
    
    # Find the geometry field
    geom_field = None
    for field in model._meta.get_fields():
        if isinstance(field, gis_models.GeometryField):
            geom_field = field.name
            break
    
    if not geom_field:
        raise Http404(f"Model '{key}' has no geometry field")
    
    # Get extent
    from django.contrib.gis.db.models import Extent
    extent = model.objects.aggregate(extent=Extent(geom_field))['extent']
    
    if extent:
        return JsonResponse({
            'bounds': [[extent[0], extent[1]], [extent[2], extent[3]]]
        })
    else:
        return JsonResponse({'bounds': None})
