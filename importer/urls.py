from django.urls import path
from .views import upload_geodata, get_external_data

app_name = "importer"
urlpatterns = [
    path("", upload_geodata, name="upload_geodata"),
    path("getExternalData/", get_external_data, name="getExternalData"),
]