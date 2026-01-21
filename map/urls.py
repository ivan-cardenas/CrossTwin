from django.urls import path
from .views import model_geojson, map_view

app_name = "map"

urlpatterns = [
    # Map page
    path('', map_view, name='map'),
    
    # API endpoints
    # path('api/layers/', views.available_layers, name='available_layers'),
    path('api/<str:app_label>/<str:model_name>/geojson/', model_geojson, name='model_geojson'),
    # path('api/<str:app_label>/<str:model_name>/bounds/', views.layer_bounds, name='layer_bounds'),
]
