from django.urls import path
from . import views

app_name = "watersupply"

urlpatterns = [
    path("indicators/<int:region_id>/<int:year>/", views.water_indicators, name="indicators"),
    path("select_filter",views.water_indicators_main, name="select_filter"),
]