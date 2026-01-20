from django.urls import path
from .views import upload_geodata

app_name = "importer"
urlpatterns = [
    path("upload/", upload_geodata, name="upload_geodata"),
]