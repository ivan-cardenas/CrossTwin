from django.urls import path
from . import views

app_name = "urban_heat"

urlpatterns = [
    path('indicators/<str:level>/<str:location>/',
         views.heat_indicators,
         name='heat_indicators'),
    path('indicators/<str:level>/<str:location>/recalculate/',
         views.recalculate_indicators,
         name='recalculate_indicators'),
]
