from django.urls import path
from . import views

app_name = "watersupply"

urlpatterns = [
    path('indicators/<str:location>/<int:year>/', views.water_indicators, name='water_indicators'),
    path('indicators/<str:location>/<int:year>/recalculate/', 
         views.recalculate_indicators, 
         name='recalculate_indicators'),
]