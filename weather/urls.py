from django.urls import path
from . import views

app_name = "weather"

urlpatterns = [
    path('wms/<str:wms_name>/times/', views.wms_time_steps, name='wms_time_steps'),
    path('wms/<str:wms_name>/tile/', views.wms_tile_proxy, name='wms_tile_proxy'),
]
