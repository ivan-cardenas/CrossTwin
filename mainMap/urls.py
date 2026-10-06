from django.urls import path, register_converter
from .views import model_geojson, map_view, available_layers, layer_bounds, admin_unit_at_point, dashboard_summary, population_panel
from . import editing
from core import views


class SignedIntConverter:
    """Like <int:>, but also matches negative ids (user-created Buildings, see editing.py)."""
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

    # API endpoints
    path('api/layers/', available_layers, name='available_layers'),
    path('api/layers/<str:app_label>/<str:model_name>/geojson/', model_geojson, name='model_geojson'),
    path('api/layers/<str:app_label>/<str:model_name>/bounds/', layer_bounds, name='layer_bounds'),
    path('api/admin-unit/', admin_unit_at_point, name='admin_unit_at_point'),
    path('api/dashboard/summary/', dashboard_summary, name='dashboard_summary'),
    path('api/population/panel/', population_panel, name='population_panel'),

    # Editing layer objects on the map (staff only, mainMap/editing.py)
    path('api/layers/<str:app_label>/<str:model_name>/features/new/', editing.feature_form, name='feature_new'),
    path('api/layers/<str:app_label>/<str:model_name>/features/<sint:pk>/', editing.feature_form, name='feature_edit'),
    path('api/layers/<str:app_label>/<str:model_name>/features/<sint:pk>/delete/', editing.feature_delete, name='feature_delete'),
    path('api/editing/backup/', editing.backup, name='edit_backup'),
    path('api/editing/backup/restore/', editing.backup_restore, name='edit_backup_restore'),
    path('api/editing/backup/discard/', editing.backup_discard, name='edit_backup_discard'),
]
