from django.urls import path
from . import views

app_name = "housing"

urlpatterns = [
    path('price-model/fit/', views.price_model_fit, name='price_model_fit'),
    path('price-model/refreeze/', views.price_model_refreeze, name='price_model_refreeze'),
    path('price-model/reprice/', views.price_model_reprice, name='price_model_reprice'),
    path('indicators/<str:level>/<str:location>/<int:year>/', views.housing_indicators, name='housing_indicators'),
    path('indicators/<str:level>/<str:location>/<int:year>/recalculate/',
         views.recalculate_indicators,
         name='recalculate_indicators'),
    path('indicators/<str:level>/<str:location>/<int:year>/json/',
         views.housing_indicators_json,
         name='housing_indicators_json'),
]
