from django.urls import path
from .views import upload_geodata
from .views_external import get_external_data, start_external_import, get_admin_areas_geojson

app_name = "importer"
urlpatterns = [
    path("", upload_geodata, name="upload_geodata"),
    path("external/", get_external_data, name="external_data"),
    path("external/import/", start_external_import, name="start_external_import"),
    path("external/areas/", get_admin_areas_geojson, name="admin_areas_geojson"),
]
