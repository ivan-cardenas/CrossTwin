from django.urls import path

from . import views

app_name = 'physicalEnv'

urlpatterns = [
    path('svf/info/', views.svf_info, name='svf_info'),
    path('svf/calculate/', views.svf_calculate, name='svf_calculate'),
]
