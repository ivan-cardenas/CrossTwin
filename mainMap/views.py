from django.shortcuts import render, redirect

import json
from django.http import JsonResponse, Http404
from django.core.serializers import serialize
from django.contrib.gis.db import models as gis_models
from django.db import connection
from django.apps import apps

from django.conf import settings

from core.utils import VECTOR_REGISTRY, WMS_REGISTRY, RASTER_REGISTRY, MODEL_REGISTRY



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
    property_fields = []
    for f in model._meta.get_fields():
        # Skip if it's a geometry field
        if isinstance(f, gis_models.GeometryField):
            continue
        
        # Skip ManyToMany fields and reverse relations
        if f.many_to_many or f.one_to_many:
            continue
        
        # Only include fields that have actual database columns
        if hasattr(f, 'column'):
            property_fields.append({
                'name': f.name,
                'column': f.column  # Actual database column name
            })
    
    # Build the SQL query using PostGIS
    table_name = model._meta.db_table
    
    # Build properties JSON object with quoted column names
    if property_fields:
        props_sql = ", ".join([f"'{f['name']}', \"{f['column']}\"" for f in property_fields])
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
        FROM {table_name}
    """
    
    with connection.cursor() as cursor:
        cursor.execute(sql)
        result = cursor.fetchone()[0]
    
    return JsonResponse(result, safe=False)


def available_layers(request):
    """
    Returns a list of all available layers (models with geometry fields).
    URL: /api/layers/
    """
    layers = []
    
    # Color palette for automatic assignment
    colors = [
        '#3388ff', '#e74c3c', '#2ecc71', '#9b59b6', '#f39c12',
        '#1abc9c', '#e91e63', '#00bcd4', '#ff5722', '#607d8b',
        '#8bc34a', '#673ab7', '#ffeb3b', '#795548', '#009688',
    ]
    
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
                'url': f'/map/api/{app_label}/{model_name}/geojson/',
                'geometry_type': geom_type,
                'geometry_field': geom_field,
                'color': colors[color_index % len(colors)],
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
