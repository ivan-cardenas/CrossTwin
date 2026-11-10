from django.urls import path
from . import views, views_degurba

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
]
