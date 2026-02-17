from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path('api/rasters/<str:app_label>/<str:layer_name>/tiles/', views.get_raster_tiles, name='raster-tiles'),
]