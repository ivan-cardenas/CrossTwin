from django.urls import path
from .views import model_geojson, map_view, available_layers, layer_bounds
from core import views

app_name = "map"

urlpatterns = [
    # Map page
    path('', map_view, name='map'),
    
    # API endpoints
    path('api/layers/', available_layers, name='available_layers'),
    path('api/<str:app_label>/<str:model_name>/geojson/', model_geojson, name='model_geojson'),
    path('api/<str:app_label>/<str:model_name>/bounds/', layer_bounds, name='layer_bounds'),
    
    path('api/tiles/<str:layer_name>/<int:z>/<int:x>/<int:y>.png', views.serve_raster_tile, name='raster_tile'),
]

