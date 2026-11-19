from django.urls import path
from . import views, views_degurba, views_generator

app_name = "builtup"

urlpatterns = [
    path('indicators/<str:level>/<str:location>/<int:year>/', views.builtup_indicators, name='builtup_indicators'),
    path('indicators/<str:level>/<str:location>/<int:year>/recalculate/',
         views.recalculate_indicators,
         name='recalculate_indicators'),
    path('indicators/<str:level>/<str:location>/<int:year>/json/',
         views.builtup_indicators_json,
         name='builtup_indicators_json'),
    path('degurba/info/', views_degurba.degurba_info, name='degurba_info'),
    path('degurba/calculate/', views_degurba.degurba_calculate, name='degurba_calculate'),
    path('generator/projects/', views_generator.generator_projects, name='generator_projects'),
    path('generator/preview/', views_generator.generator_preview, name='generator_preview'),
    path('generator/commit/', views_generator.generator_commit, name='generator_commit'),
    path('generator/remove/', views_generator.generator_remove, name='generator_remove'),
]
