import io, zipfile, tempfile
import geopandas as gpd
from django.conf import settings

def gpd_read_any(django_file):
    f = django_file.name.lower()
    data = django_file.read()
    
    if f.endswith('.shp'):
        return gpd.read_file(io.BytesIO(data))
    elif f.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.endswith('.shp'):
                    return gpd.read_file(io.BytesIO(z.read(name)))
    elif f.endswith('.geojson') or f.endswith('.json'):
        return gpd.read_file(io.BytesIO(data))
    
    raise ValueError("Unsupported file format.")