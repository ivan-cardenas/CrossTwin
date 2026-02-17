from django.apps import apps
from django.contrib.gis.db import models as gis_models

def build_model_registry():
    """Build MODEL_REGISTRY dynamically from specified apps."""
    allowed_apps = ['common', 'urbanHeat', 'watersupply', 'weather', 'builtup', 'Energy', 'Housing']
    registry = {}
    
    for app_label in allowed_apps:
        try:
            app_models = apps.get_app_config(app_label).get_models()
            for model in app_models:
                label = f"{app_label}.{model.__name__}"
                registry[label] = model
        except LookupError:
            continue
    
    
    return registry

MODEL_REGISTRY = build_model_registry()


VECTOR_REGISTRY = {
        key: value 
        for key, value in MODEL_REGISTRY.items() 
        if value._meta.get_fields() and any(isinstance(f, gis_models.GeometryField) for f in value._meta.get_fields()) and not any(isinstance(f, gis_models.RasterField) for f in value._meta.get_fields())
    }



    
WMS_REGISTRY = {key: value 
                    for key, value in MODEL_REGISTRY.items() 
                    if 'WMS' in key}

RASTER_REGISTRY = {
    key: value 
    for key, value in MODEL_REGISTRY.items() 
    if value._meta.get_fields() and any(isinstance(f, gis_models.RasterField) for f in value._meta.get_fields())
}    

