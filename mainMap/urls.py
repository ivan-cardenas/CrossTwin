from django.urls import path, register_converter
from .views import model_geojson, map_view, landing_view, available_layers, layer_bounds, building_mask, admin_unit_at_point, dashboard_summary, population_panel, climate_effects
from core import editing
from . import settings_views, views_climate
from core import views


class SignedIntConverter:
    """Like <int:>, but also matches negative ids (user-created Buildings, see core/editing.py)."""
    regex = '-?[0-9]+'

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return str(value)


register_converter(SignedIntConverter, 'sint')

app_name = "map"

urlpatterns = [
    # Map page
    path('', map_view, name='map'),
    path('welcome/', landing_view, name='landing'),

    # API endpoints
    path('api/layers/', available_layers, name='available_layers'),
    # Before the generic routes, which would read 'Building' as any model
    path('api/layers/builtup/Building/mask/', building_mask, name='building_mask'),
    path('api/layers/<str:app_label>/<str:model_name>/geojson/', model_geojson, name='model_geojson'),
    path('api/layers/<str:app_label>/<str:model_name>/bounds/', layer_bounds, name='layer_bounds'),
    path('api/admin-unit/', admin_unit_at_point, name='admin_unit_at_point'),
    path('api/dashboard/summary/', dashboard_summary, name='dashboard_summary'),
    path('api/population/panel/', population_panel, name='population_panel'),
    path('api/climate/effects/', climate_effects, name='climate_effects'),
    path('api/climate/runs/', views_climate.climate_runs, name='climate_runs'),
    path('api/climate/runs/<int:run_id>/', views_climate.climate_run_detail, name='climate_run_detail'),
    path('api/climate/runs/<int:run_id>/recalculate/', views_climate.climate_run_recalculate, name='climate_run_recalculate'),
    path('api/climate/runs/<int:run_id>/heat/', views_climate.climate_run_heat, name='climate_run_heat'),
    path('api/climate/runs/<int:run_id>/delete/', views_climate.climate_run_delete, name='climate_run_delete'),

    # Editing layer objects on the map (staff only, core/editing.py)
    path('api/layers/<str:app_label>/<str:model_name>/features/new/', editing.feature_form, name='feature_new'),
    path('api/layers/<str:app_label>/<str:model_name>/features/<sint:pk>/', editing.feature_form, name='feature_edit'),
    path('api/layers/<str:app_label>/<str:model_name>/features/<sint:pk>/delete/', editing.feature_delete, name='feature_delete'),
    path('api/editing/backup/', editing.backup, name='edit_backup'),
    path('api/editing/backup/restore/', editing.backup_restore, name='edit_backup_restore'),
    path('api/editing/backup/discard/', editing.backup_discard, name='edit_backup_discard'),

    # Map settings panel: editable layers and styles (staff only, mainMap/settings_views.py)
    path('api/settings/', settings_views.map_settings, name='map_settings'),
    path('api/settings/editable/', settings_views.settings_editable, name='settings_editable'),
    path('api/settings/style/', settings_views.settings_style, name='settings_style'),
]
