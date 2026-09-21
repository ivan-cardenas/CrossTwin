import uuid
from django.conf import settings
from django.apps import apps

import geopandas as gpd
import tempfile
import zipfile
import os


def to_storage_srid(geom, source_srid=None):
    """
    Return `geom` expressed in settings.COORDINATE_SYSTEM, the only CRS
    geometries are stored in.

    `source_srid` is the CRS the coordinates are *actually* in and overrides
    whatever SRID the geometry carries: GEOSGeometry parses GeoJSON as 4326 by
    convention regardless of the real coordinates. Refuses to guess when neither
    is known, since a wrong guess silently stores misplaced geometries.

    Note: wrapping in MultiPolygon/MultiLineString/MultiPoint drops the SRID, so
    convert to the Multi* type after calling this and pass srid=geom.srid.
    """
    if geom is None or geom.empty:
        return geom

    srid = source_srid or geom.srid
    if not srid:
        raise ValueError("Geometry has no CRS and no source CRS was given; refusing to guess.")

    geom.srid = srid
    if srid != settings.COORDINATE_SYSTEM:
        geom.transform(settings.COORDINATE_SYSTEM)
    return geom


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


