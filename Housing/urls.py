from django.urls import path
from . import views

app_name = "housing"

urlpatterns = [
    path('indicators/<str:location>/<int:year>/', views.housing_indicators, name='housing_indicators'),
    path('indicators/<str:location>/<int:year>/recalculate/',
         views.recalculate_indicators,
         name='recalculate_indicators'),
    path('indicators/<str:location>/<int:year>/json/',
         views.housing_indicators_json,
         name='housing_indicators_json'),
]
