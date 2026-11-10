from django.urls import path

from . import views

app_name = 'physicalEnv'

urlpatterns = [
    path('svf/info/', views.svf_info, name='svf_info'),
    path('svf/calculate/', views.svf_calculate, name='svf_calculate'),
    path('dsm/edited/status/', views.dsm_edited_status, name='dsm_edited_status'),
]
