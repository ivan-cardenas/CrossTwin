"""Tests for the header login and the map settings panel: editable layers and style overrides."""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import EditableLayer, LayerStyleOverride
from .styles.overrides import OTHER, apply_vector_override

SETTINGS_URL = reverse('map:map_settings')
EDITABLE_URL = reverse('map:settings_editable')
STYLE_URL = reverse('map:settings_style')


def catalog_entry(client, key):
    layers = client.get(reverse('map:available_layers'), {'app_labels': key.split('.')[0]}).json()['layers']
    return next(l for l in layers if l['key'] == key)


class SettingsTestCase(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user('editor', password='x', is_staff=True)
        self.client.force_login(self.staff)


class LoginTests(TestCase):
    def test_header_shows_log_in_anonymously_and_settings_for_staff_only(self):
        page = self.client.get(reverse('map:map')).content.decode()
        self.assertIn(reverse('login'), page)
        self.assertNotIn('map-settings-btn', page)

        user = get_user_model().objects.create_user('viewer', password='x')
        self.client.force_login(user)
        page = self.client.get(reverse('map:map')).content.decode()
        self.assertIn('Log out', page)
        self.assertNotIn('map-settings-btn', page)

        user.is_staff = True
        user.save()
        page = self.client.get(reverse('map:map')).content.decode()
        self.assertIn('map-settings-btn', page)
        self.assertIn('settings-card', page)

    def test_login_page_logs_in_and_redirects(self):
        get_user_model().objects.create_user('editor', password='secret-pass-1', is_staff=True)
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)
        response = self.client.post(reverse('login'), {'username': 'editor', 'password': 'secret-pass-1', 'next': '/'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)


class SettingsAccessTests(TestCase):
    def test_non_staff_are_refused(self):
        for user in (None, get_user_model().objects.create_user('viewer', password='x')):
            if user:
                self.client.force_login(user)
            with self.subTest(user=user):
                self.assertEqual(self.client.get(SETTINGS_URL).status_code, 403)
                self.assertEqual(self.client.post(EDITABLE_URL, {'key': 'builtup.Street'}).status_code, 403)
                self.assertEqual(self.client.get(STYLE_URL, {'target': 'vector:builtup.Park'}).status_code, 403)


class EditableLayerSettingsTests(SettingsTestCase):
    def test_migration_seeds_the_layers_the_toml_listed(self):
        self.assertTrue(EditableLayer.objects.filter(key='builtup.Building').exists())

    def test_switching_a_layer_off_and_on_takes_effect_without_restart(self):
        new_street = reverse('map:feature_new', args=['builtup', 'Street'])
        self.assertTrue(catalog_entry(self.client, 'builtup.Street').get('editable'))

        response = self.client.post(EDITABLE_URL, {'key': 'builtup.Street'})   # unchecked = off
        self.assertEqual(json.loads(response['HX-Trigger'])['editable-changed'],
                         {'key': 'builtup.Street', 'enabled': False})
        self.assertNotIn('editable', catalog_entry(self.client, 'builtup.Street'))
        self.assertEqual(self.client.get(new_street).status_code, 404)

        self.client.post(EDITABLE_URL, {'key': 'builtup.Street', 'enabled': 'on'})
        self.assertTrue(catalog_entry(self.client, 'builtup.Street').get('editable'))
        self.assertEqual(self.client.get(new_street).status_code, 200)

    def test_a_layer_whose_save_derives_fields_needs_field_rules(self):
        # administrative.City overrides save() and has no rules in editable_layers.toml
        response = self.client.post(EDITABLE_URL, {'key': 'administrative.City', 'enabled': 'on'})
        self.assertNotIn('HX-Trigger', response)
        self.assertIn('editable_layers.toml', response.content.decode())
        self.assertFalse(EditableLayer.objects.filter(key='administrative.City').exists())

    def test_watersupply_layers_are_locked(self):
        from core.editing import enable_blocker
        from core.utils import VECTOR_REGISTRY
        key = next(k for k in VECTOR_REGISTRY if k.startswith('watersupply.'))
        self.assertIn('Restore', enable_blocker(key))

    def test_panel_lists_every_vector_layer(self):
        from core.utils import VECTOR_REGISTRY
        page = self.client.get(SETTINGS_URL).content.decode()
        for key in VECTOR_REGISTRY:
            self.assertIn(f'value="{key}"', page)


class VectorStyleTests(SettingsTestCase):
    def test_saving_stores_only_the_difference_and_reaches_the_catalog(self):
        default = catalog_entry(self.client, 'builtup.Park')
        response = self.client.post(STYLE_URL, {
            'target': 'vector:builtup.Park', 'color': '#123456',
            'paint:0:fill-opacity': '0.9',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response['HX-Trigger'])['style-changed'],
                         {'kind': 'vector', 'key': 'builtup.Park'})
        data = LayerStyleOverride.objects.get(kind='vector', key='builtup.Park').data
        self.assertEqual(data, {'color': '#123456', 'paint': {'0': {'fill-opacity': 0.9}}})

        entry = catalog_entry(self.client, 'builtup.Park')
        self.assertEqual(entry['color'], '#123456')
        self.assertEqual(entry['style_layers'][0]['paint']['fill-opacity'], 0.9)
        # untouched properties keep following the code default
        self.assertEqual(entry['style_layers'][1:], default['style_layers'][1:])

        self.client.post(STYLE_URL, {'target': 'vector:builtup.Park', 'action': 'reset'})
        self.assertFalse(LayerStyleOverride.objects.exists())
        self.assertEqual(catalog_entry(self.client, 'builtup.Park'), default)

    def test_invalid_values_are_rejected(self):
        for field, value in (('color', 'red'), ('paint:0:fill-opacity', '2')):
            with self.subTest(field=field):
                response = self.client.post(STYLE_URL, {'target': 'vector:builtup.Park', field: value})
                self.assertNotIn('HX-Trigger', response)
                self.assertIn('settings-error', response.content.decode())
        self.assertFalse(LayerStyleOverride.objects.exists())

    def test_building_type_categories_recolour_the_match_and_the_legend(self):
        form = self.client.get(STYLE_URL, {'target': 'vector:builtup.Building'}).content.decode()
        self.assertIn('name="cat:residential"', form)
        self.client.post(STYLE_URL, {'target': 'vector:builtup.Building',
                                     'cat:residential': '#000001', f'cat:{OTHER}': '#000002'})
        entry = catalog_entry(self.client, 'builtup.Building')
        match = entry['style_layers'][0]['paint']['fill-extrusion-color']
        self.assertEqual(match[match.index('residential') + 1], '#000001')
        self.assertEqual(match[-1], '#000002')
        legend = {item['value']: item['color'] for item in entry['legend']}
        self.assertEqual(legend['residential'], '#000001')
        self.assertEqual(legend[OTHER], '#000002')

    def test_apply_ignores_style_layers_the_default_no_longer_has(self):
        layers = [{'type': 'fill', 'paint': {'fill-color': '#111111'}}]
        _, out, _ = apply_vector_override('#111111', layers, None, {'paint': {'5': {'fill-color': '#222222'}}})
        self.assertEqual(out, layers)


class RasterStyleTests(SettingsTestCase):
    def test_override_changes_the_resolved_colormap_and_range(self):
        from .styles.rasterStyles import resolve_raster_style
        raster = mock.Mock(index='NDVI', cog_path='')
        self.assertEqual(resolve_raster_style(raster, 'physicalEnv.LandCoverRaster')['colormap'], 'rdylgn')

        response = self.client.post(STYLE_URL, {'target': 'raster:NDVI', 'colormap': 'viridis',
                                                'min': '-1', 'max': '1'})
        self.assertIn('style-changed', response['HX-Trigger'])
        style = resolve_raster_style(raster, 'physicalEnv.LandCoverRaster')
        self.assertEqual((style['colormap'], style['rescale']), ('viridis', (-1.0, 1.0)))

        self.client.post(STYLE_URL, {'target': 'raster:NDVI', 'action': 'reset'})
        self.assertEqual(resolve_raster_style(raster, 'physicalEnv.LandCoverRaster')['rescale'], (-0.8, 0.8))

    def test_min_must_be_below_max_and_colormap_must_exist(self):
        for post in ({'min': '1', 'max': '0'}, {'colormap': 'no-such-map', 'min': '', 'max': ''}):
            with self.subTest(post=post):
                response = self.client.post(STYLE_URL, {'target': 'raster:NDVI', **post})
                self.assertNotIn('HX-Trigger', response)
        self.assertFalse(LayerStyleOverride.objects.exists())
