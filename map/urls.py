from django.urls import path
from .views import model_geojson

app_name = "map"
urlpatterns = [
    path('api/<str:app_label>/<str:model_name>/geojson/', model_geojson, name='model_geojson')
]