from django.shortcuts import render, redirect

import json
from django.http import JsonResponse, Http404
from django.core.serializers import serialize
from django.contrib.gis.db import models as gis_models

from django.conf import settings

# Import your registry or define which models are available
from importer.utils import build_model_registry  # or wherever yours is

MODEL_REGISTRY = build_model_registry()

def map_view(request):
    """Display the map page."""
    return render(request, 'map.html', {
        'mapbox_access_token': getattr(settings, 'MAPBOX_ACCESS_TOKEN', ''),
    })

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
    
    # Get all non-geometry fields for properties
    property_fields = [
        f.name for f in model._meta.get_fields()
        if hasattr(f, 'column') and not isinstance(f, gis_models.GeometryField)
    ]
    
    # Query and serialize
    queryset = model.objects.all()
    geojson = serialize('geojson', queryset, geometry_field=geom_field, fields=property_fields)
    
    return JsonResponse(json.loads(geojson))
