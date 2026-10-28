from django.urls import path
from . import views
from .lst import views as lst_views
from .solweig import views as solweig_views

app_name = "urban_heat"

urlpatterns = [
    path('lst/scenes/', lst_views.lst_scenes, name='lst_scenes'),
    path('lst/calculate/', lst_views.lst_calculate, name='lst_calculate'),
    path('solweig/info/', solweig_views.solweig_info, name='solweig_info'),
    path('solweig/met/', solweig_views.solweig_met, name='solweig_met'),
    path('solweig/calculate/', solweig_views.solweig_calculate, name='solweig_calculate'),
    path('solweig/runs/<int:run_id>/', solweig_views.solweig_run, name='solweig_run'),
    path('solweig/stale/', solweig_views.solweig_stale, name='solweig_stale'),
    path('indicators/<str:level>/<str:location>/',
         views.heat_indicators,
         name='heat_indicators'),
    path('indicators/<str:level>/<str:location>/recalculate/',
         views.recalculate_indicators,
         name='recalculate_indicators'),
]
