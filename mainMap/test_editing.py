"""Tests for editing layer objects on the map and the backup / restore point (mainMap/editing.py)."""
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from builtup.models import Building, Property
from core.cache import get_cache, layer_version
from watersupply.tests.factories import make_neighborhood, make_polygon

from .models import EditBackup, EditBackupRow


def _wgs84_geojson(geom):
    """The geometry as the browser sends it: WGS84 GeoJSON text."""
    return geom.transform(4326, clone=True).geojson


def _edit_url(pk):
    return reverse('map:feature_edit', args=['builtup', 'Building', pk])


NEW_URL = reverse('map:feature_new', args=['builtup', 'Building'])
BACKUP_URL = reverse('map:edit_backup')
RESTORE_URL = reverse('map:edit_backup_restore')
DISCARD_URL = reverse('map:edit_backup_discard')


class EditingTestCase(TestCase):
    def setUp(self):
        get_cache('geojson').clear()
        self.neighborhood = make_neighborhood()
        self.staff = get_user_model().objects.create_user('editor', password='x', is_staff=True)
        self.client.force_login(self.staff)
        self.building = Building.objects.create(
            id=1234, name='Original', usageFunction='woonfunctie', height_m=9.0,
            geom=make_polygon(half_size_m=10),
        )
        self.building.refresh_from_db()

    def post_building(self, url, **fields):
        data = {'name': 'Edited', 'usageFunction': 'Residential function',
                'geom': _wgs84_geojson(make_polygon(half_size_m=10))}
        data.update(fields)
        return self.client.post(url, data)


class FeatureAccessTests(EditingTestCase):
    def test_anonymous_and_non_staff_users_are_refused(self):
        self.client.logout()
        self.assertEqual(self.client.get(_edit_url(1234)).status_code, 403)
        self.assertEqual(self.client.post(BACKUP_URL).status_code, 403)

        user = get_user_model().objects.create_user('viewer', password='x')
        self.client.force_login(user)
        for url in (_edit_url(1234), NEW_URL, BACKUP_URL):
            self.assertEqual(self.client.get(url).status_code, 403)
        for url in (reverse('map:feature_delete', args=['builtup', 'Building', 1234]), RESTORE_URL, DISCARD_URL):
            self.assertEqual(self.client.post(url).status_code, 403)

    def test_a_layer_outside_the_allowlist_is_not_found(self):
        url = reverse('map:feature_new', args=['administrative', 'City'])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_catalog_marks_editable_layers_for_staff_only(self):
        def building_entry():
            layers = self.client.get(reverse('map:available_layers'), {'app_labels': 'builtup'}).json()['layers']
            return next(l for l in layers if l['key'] == 'builtup.Building')

        entry = building_entry()
        self.assertTrue(entry['editable'])
        self.assertEqual(entry['edit_geom_type'], 'MULTIPOLYGON')
        self.client.logout()
        self.assertNotIn('editable', building_entry())


class FeatureFormTests(EditingTestCase):
    def test_form_carries_the_full_resolution_geometry_in_wgs84(self):
        response = self.client.get(_edit_url(1234))
        self.assertEqual(response.status_code, 200)
        geojson = response.context['geojson']
        self.assertEqual(geojson['type'], 'MultiPolygon')
        lng, lat = geojson['coordinates'][0][0][0]
        self.assertTrue(6 < lng < 7.5 and 52 < lat < 52.5)   # Enschede, not RD metres
        self.assertNotIn('area_sqm', response.context['form'].fields)
        self.assertNotIn('id', response.context['form'].fields)

    def test_create_stores_a_multipolygon_in_the_storage_crs_with_a_negative_id(self):
        response = self.post_building(NEW_URL, usageFunction='Shop function,Residential function')
        self.assertEqual(response.status_code, 200)
        self.assertIn('feature-saved', response['HX-Trigger'])

        created = Building.objects.get(name='Edited')
        self.assertEqual(created.pk, -1)
        self.assertEqual(created.geom.srid, settings.COORDINATE_SYSTEM)
        self.assertEqual(created.geom.geom_type, 'MultiPolygon')
        self.assertEqual(created.buildingType, 'mixed')          # derived by Building.save()
        self.assertAlmostEqual(created.area_sqm, 400, delta=1)   # 20 m x 20 m
        self.assertEqual(created.neighborhood_id, self.neighborhood.pk)

        self.post_building(NEW_URL, name='Second')
        self.assertTrue(Building.objects.filter(pk=-2, name='Second').exists())

    def test_edit_attributes_and_geometry(self):
        bigger = make_polygon(half_size_m=20)
        response = self.post_building(_edit_url(1234), name='Renamed', geom=_wgs84_geojson(bigger))
        self.assertEqual(response.status_code, 200)
        self.building.refresh_from_db()
        self.assertEqual(self.building.name, 'Renamed')
        self.assertAlmostEqual(self.building.area_sqm, 1600, delta=1)

    def test_unchanged_geometry_round_trips_without_reprojection(self):
        # The form's hidden input holds the stored EWKT; posting it back as-is
        # must not move the shape.
        form_value = self.client.get(_edit_url(1234)).context['form']['geom'].value()
        self.post_building(_edit_url(1234), geom=str(form_value))
        stored = Building.objects.get(pk=1234).geom
        self.assertTrue(stored.equals_exact(self.building.geom, tolerance=1e-6))

    def test_wrong_geometry_type_is_a_form_error(self):
        polygon = make_polygon(half_size_m=10)[0]
        polygon.srid = settings.COORDINATE_SYSTEM
        response = self.post_building(_edit_url(1234), geom=_wgs84_geojson(polygon))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['geom_errors'])
        self.assertNotIn('HX-Trigger', response)
        self.assertEqual(Building.objects.get(pk=1234).name, 'Original')

    def test_delete(self):
        response = self.client.post(reverse('map:feature_delete', args=['builtup', 'Building', 1234]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Building.objects.filter(pk=1234).exists())
        self.assertIn('feature-saved', response['HX-Trigger'])

    def test_delete_of_a_referenced_building_is_a_message_not_a_500(self):
        Property.objects.create(name='Flat', grossArea=80, geom=self._inside_building())
        response = self.client.post(reverse('map:feature_delete', args=['builtup', 'Building', 1234]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('cannot be deleted', response.context['message'])
        self.assertTrue(Building.objects.filter(pk=1234).exists())

    def test_saving_invalidates_the_cached_geojson(self):
        before = layer_version(Building)
        self.post_building(_edit_url(1234))
        self.assertNotEqual(layer_version(Building), before)

    def _inside_building(self):
        return Point(257000.0, 470000.0, srid=settings.COORDINATE_SYSTEM)


class OtherEditableLayersTests(EditingTestCase):
    """Every allowlisted layer gets a working form, not just Building."""

    def test_every_editable_layer_renders_a_new_object_form(self):
        from .editing import EDITABLE_LAYERS
        for key in EDITABLE_LAYERS:
            with self.subTest(key=key):
                response = self.client.get(reverse('map:feature_new', args=key.split('.')))
                self.assertEqual(response.status_code, 200)
                self.assertIn('feature-editor', response.content.decode())

    def test_create_a_facility_from_a_point(self):
        point = Point(257010.0, 470010.0, srid=settings.COORDINATE_SYSTEM)
        response = self.client.post(reverse('map:feature_new', args=['builtup', 'Facility']),
                                    {'name': 'School', 'type': 'school', 'geom': _wgs84_geojson(point)})
        self.assertIn('feature-saved', response['HX-Trigger'])
        from builtup.models import Facility
        stored = Facility.objects.get(name='School').geom
        self.assertEqual(stored.srid, settings.COORDINATE_SYSTEM)
        self.assertAlmostEqual(stored.x, 257010.0, delta=0.01)   # WGS84 round trip stays within a centimetre

    def test_create_a_street_from_a_line(self):
        from django.contrib.gis.geos import LineString
        line = LineString((257000.0, 470000.0), (257100.0, 470000.0), srid=settings.COORDINATE_SYSTEM)
        response = self.client.post(reverse('map:feature_new', args=['builtup', 'Street']),
                                    {'name': 'Teststraat', 'classification': 'residential', 'width': 6,
                                     'geom': _wgs84_geojson(line)})
        self.assertIn('feature-saved', response['HX-Trigger'])
        from builtup.models import Street
        self.assertAlmostEqual(Street.objects.get(name='Teststraat').geom.length, 100, delta=0.1)

    def test_zoning_area_derives_its_area(self):
        from physicalEnv.models import HILUCSLandUse
        residential = HILUCSLandUse.objects.get(code='5.1')   # loaded by migration
        response = self.client.post(reverse('map:feature_new', args=['builtup', 'ZoningArea']),
                                    {'neighborhood': self.neighborhood.pk, 'zone_type': residential.pk,
                                     'geom': _wgs84_geojson(make_polygon(half_size_m=50))})
        self.assertIn('feature-saved', response['HX-Trigger'])
        from builtup.models import ZoningArea
        zone = ZoningArea.objects.get()
        self.assertAlmostEqual(zone.area, 10000, delta=5)
        self.assertEqual(zone.zone_type, residential)


class BackupRestoreTests(EditingTestCase):
    def create_backup(self):
        response = self.client.post(BACKUP_URL)
        self.assertEqual(response.status_code, 200)
        return EditBackup.objects.get()

    def restore(self):
        return self.client.post(RESTORE_URL)

    def test_without_a_backup_edits_are_not_journalled(self):
        self.post_building(_edit_url(1234))
        self.assertFalse(EditBackupRow.objects.exists())

    def test_restore_returns_the_exact_original_row(self):
        original = Building.objects.get(pk=1234)
        self.create_backup()
        self.post_building(_edit_url(1234), name='Changed', usageFunction='Office function',
                           geom=_wgs84_geojson(make_polygon(x=257050, half_size_m=15)))
        self.assertEqual(Building.objects.get(pk=1234).buildingType, 'commercial')

        response = self.restore()
        self.assertIn('backup-restored', response['HX-Trigger'])
        self.assertEqual(json.loads(response['HX-Trigger'])['backup-restored']['layers'], ['builtup.Building'])

        restored = Building.objects.get(pk=1234)
        self.assertEqual(restored.name, 'Original')
        self.assertEqual(restored.buildingType, 'residential')
        self.assertEqual(restored.usageFunction, original.usageFunction)
        self.assertEqual(restored.area_sqm, original.area_sqm)
        self.assertEqual(restored.geom.srid, settings.COORDINATE_SYSTEM)
        self.assertTrue(restored.geom.equals_exact(original.geom, tolerance=1e-9))
        self.assertFalse(EditBackup.objects.exists())   # the restore point is used up

    def test_restore_deletes_objects_created_since_the_backup(self):
        self.create_backup()
        self.post_building(NEW_URL)
        self.assertTrue(Building.objects.filter(pk=-1).exists())
        self.restore()
        self.assertFalse(Building.objects.filter(pk=-1).exists())

    def test_restore_brings_back_a_deleted_object_with_its_id(self):
        self.create_backup()
        self.client.post(reverse('map:feature_delete', args=['builtup', 'Building', 1234]))
        self.assertFalse(Building.objects.filter(pk=1234).exists())
        self.restore()
        self.assertEqual(Building.objects.get(pk=1234).name, 'Original')

    def test_the_first_pre_image_wins(self):
        self.create_backup()
        self.post_building(_edit_url(1234), name='First edit')
        self.post_building(_edit_url(1234), name='Second edit')
        self.assertEqual(EditBackupRow.objects.count(), 1)
        self.restore()
        self.assertEqual(Building.objects.get(pk=1234).name, 'Original')

    def test_a_blocked_restore_changes_nothing(self):
        self.create_backup()
        self.post_building(NEW_URL, geom=_wgs84_geojson(make_polygon(x=258000, half_size_m=10)))
        self.post_building(_edit_url(1234), name='Changed')
        # Created outside the editor, pointing at the building made during the test
        Property.objects.create(name='Flat', grossArea=80, geom=Point(258000.0, 470000.0, srid=settings.COORDINATE_SYSTEM))

        response = self.restore()
        self.assertEqual(response.status_code, 200)
        self.assertIn('nothing was changed', response.context['message'])
        self.assertNotIn('HX-Trigger', response)
        self.assertTrue(Building.objects.filter(pk=-1).exists())
        self.assertEqual(Building.objects.get(pk=1234).name, 'Changed')   # step 1 rolled back too
        self.assertTrue(EditBackup.objects.exists())

    def test_restore_invalidates_the_cached_geojson(self):
        self.create_backup()
        self.post_building(_edit_url(1234))
        before = layer_version(Building)
        self.restore()
        self.assertNotEqual(layer_version(Building), before)

    def test_only_one_backup_at_a_time(self):
        self.create_backup()
        response = self.client.post(BACKUP_URL)
        self.assertIn('first', response.context['message'])
        self.assertEqual(EditBackup.objects.count(), 1)

    def test_discard_keeps_the_current_data(self):
        self.create_backup()
        self.post_building(_edit_url(1234), name='Kept')
        self.client.post(DISCARD_URL)
        self.assertFalse(EditBackup.objects.exists())
        self.assertFalse(EditBackupRow.objects.exists())
        self.assertEqual(Building.objects.get(pk=1234).name, 'Kept')

    def test_backup_bar_shows_the_number_of_changed_objects(self):
        self.create_backup()
        self.post_building(_edit_url(1234))
        self.post_building(NEW_URL)
        response = self.client.get(BACKUP_URL)
        self.assertContains(response, '2 objects changed')
