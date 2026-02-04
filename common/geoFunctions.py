from django.contrib.gis.measure import Area
from django.apps import apps
from django.contrib.gis.db import models

def get_area(self): 
        """ 
        Returns the area in square kilometers. 
        """
        area_sqkm = self.polygon.area.sq_km
      

        return area_sqkm


def build_model_registry():
    """Build MODEL_REGISTRY dynamically from specified apps."""
    allowed_apps = ['common', 'watersupply']
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

TARGET_MODELS = build_model_registry()