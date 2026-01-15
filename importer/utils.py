from django.conf import settings

import geopandas as gpd
import tempfile
import zipfile
import os

def gpd_read_any(django_file):
    name = django_file.name.lower()
    data = django_file.read()

    # --- GEOJSON ---
    if name.endswith((".geojson", ".json")):
        with tempfile.NamedTemporaryFile(suffix=".geojson") as f:
            f.write(data)
            f.flush()
            return gpd.read_file(f.name)

    # --- SHAPEFILE ZIP ---
    if name.endswith(".zip"):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "data.zip")
            with open(zip_path, "wb") as f:
                f.write(data)

            with zipfile.ZipFile(zip_path) as z:
                z.extractall(tmpdir)

            # find .shp
            for root, _, files in os.walk(tmpdir):
                for file in files:
                    if file.endswith(".shp"):
                        return gpd.read_file(os.path.join(root, file))

        raise ValueError("No .shp found inside ZIP.")

    # --- RAW SHP UPLOAD (rare, but handle it) ---
    if name.endswith(".shp"):
        raise ValueError("Shapefile must be uploaded as a ZIP.")

    raise ValueError("Unsupported file format.")
