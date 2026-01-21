import uuid
from django.conf import settings
from django.apps import apps

import geopandas as gpd
import tempfile
import zipfile
import os

def gpd_read_any(uploaded_file):
    """
    Read an uploaded file (GeoJSON, Shapefile zip, etc.) into a GeoDataFrame.
    Handles Windows file locking issues.
    """
    import tempfile
    import os
    import uuid
    import zipfile
    import geopandas as gpd
    
    filename = uploaded_file.name.lower()
    
    # Create a unique temp directory
    temp_dir = os.path.join(tempfile.gettempdir(), f'geodata_{uuid.uuid4().hex}')
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        if filename.endswith('.zip'):
            # Handle shapefile zip
            zip_path = os.path.join(temp_dir, 'upload.zip')
            with open(zip_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            
            # Extract zip
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(temp_dir)
            
            # Find .shp file
            shp_file = None
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.shp'):
                        shp_file = os.path.join(root, file)
                        break
            
            if not shp_file:
                raise ValueError("No .shp file found in zip")
            
            gdf = gpd.read_file(shp_file)
        
        elif filename.endswith(('.geojson', '.json')):
            # Handle GeoJSON
            file_path = os.path.join(temp_dir, 'upload.geojson')
            with open(file_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            
            gdf = gpd.read_file(file_path)
        
        else:
            # Try reading directly (for other formats)
            file_path = os.path.join(temp_dir, uploaded_file.name)
            with open(file_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            
            gdf = gpd.read_file(file_path)
        
        return gdf
    
    finally:
        # Clean up temp directory
        import shutil
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


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