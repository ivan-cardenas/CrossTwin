from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path('api/raster/<str:app_label>/<str:layer_name>/tiles/', views.get_raster_tiles, name='raster-tiles'),
    path('api/raster/<str:app_label>/<str:layer_name>/info/', views.get_raster_info),
]