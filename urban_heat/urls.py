from django.urls import path
from . import views
from .lst import views as lst_views

app_name = "urban_heat"

urlpatterns = [
    path('lst/scenes/', lst_views.lst_scenes, name='lst_scenes'),
    path('lst/calculate/', lst_views.lst_calculate, name='lst_calculate'),
    path('indicators/<str:level>/<str:location>/',
         views.heat_indicators,
         name='heat_indicators'),
    path('indicators/<str:level>/<str:location>/recalculate/',
         views.recalculate_indicators,
         name='recalculate_indicators'),
]
