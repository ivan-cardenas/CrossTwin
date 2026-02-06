from django.apps import apps

def build_model_registry():
    """Build MODEL_REGISTRY dynamically from specified apps."""
    allowed_apps = ['common', 'urbanHeat', 'watersupply', 'weather']
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