from django.shortcuts import render, redirect

import json
from django.http import JsonResponse, Http404
from django.core.serializers import serialize
from django.contrib.gis.db import models as gis_models
from django.db import connection
from django.apps import apps

from django.conf import settings


from importer.utils import build_model_registry 
MODEL_REGISTRY = build_model_registry()


def map_view(request):
    """Display the map page."""
    return render(request, 'mainMap.html')

def model_geojson(request, app_label, model_name):
    """
    Generic GeoJSON endpoint for any registered model.
    URL: /api/<app_label>/<model_name>/geojson/
    """
    # Find the model in registry
    key = f"{app_label}.{model_name}"
    
    if key not in MODEL_REGISTRY:
        raise Http404(f"Model {key} not found in registry")
    
    model = MODEL_REGISTRY[key]
    
    # Find the geometry field automatically
    geom_field = None
    for field in model._meta.get_fields():
        if isinstance(field, gis_models.GeometryField):
            geom_field = field.name
            break
    
    if not geom_field:
        raise Http404(f"Model {key} has no geometry field")
    
    # Get all non-geometry fields for properties (use db_column if available)
    property_fields = []
    for f in model._meta.get_fields():
        if hasattr(f, 'column') and not isinstance(f, gis_models.GeometryField):
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
