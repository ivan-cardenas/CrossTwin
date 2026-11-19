"""physicalEnv.signals.street_landcover_saved/_deleted -> landcover.street_area (DAG edge Streets -> LandCover)."""
from django.contrib.gis.geos import LineString, MultiLineString

from physicalEnv.models import LandCoverVector, UrbanFabricCut
from physicalEnv.tests.test_physicalenv import _UrbanFabricTestCase


def _line(*points):
    return MultiLineString(LineString(points))


class StreetRoadLandCoverTests(_UrbanFabricTestCase):

    def _street(self, line=None, **kwargs):
        from builtup.models import Street
        from core.editing import editor_change
        kwargs.setdefault("classification", "residential")
        with editor_change():
            return Street.objects.create(name="New street", geom=line or _line((100, 300), (300, 300)), **kwargs)

    def _road(self):
        return LandCoverVector.objects.filter(source_street__isnull=False)

    def test_a_drawn_street_becomes_road_land_cover(self):
        street = self._street(width=10)
        road = self._road().get()
        self.assertEqual(road.source_street, street.pk)
        self.assertEqual(road.land_cover_type.class_name, "Road and rail networks and associated land")
        self.assertAlmostEqual(road.geom.area, 200 * 10, delta=0.01)     # flat ends: length x width
        self.pasture.refresh_from_db()
        self.assertAlmostEqual(self.pasture.geom.area + road.geom.area, 1e6, delta=0.01)

    def test_without_a_width_the_class_default_applies(self):
        from builtup.calculations.chain import DEFAULT_WIDTH_M
        self._street(classification="secondary")
        self.assertAlmostEqual(self._road().get().geom.area, 200 * DEFAULT_WIDTH_M["secondary"], delta=0.01)

    def test_moving_rewidening_and_deleting(self):
        from core.editing import editor_change
        street = self._street(width=8)
        with editor_change():
            street.geom = _line((100, 600), (300, 600))
            street.save()
        road = self._road().get()
        self.assertTrue(road.geom.intersects(_line((200, 599), (200, 601))))
        self.assertFalse(road.geom.intersects(_line((200, 299), (200, 301))))
        with editor_change():
            street.width = 12
            street.save()
        self.assertAlmostEqual(self._road().get().geom.area, 200 * 12, delta=0.01)
        with editor_change():
            street.delete()
        self.assertFalse(self._road().exists())
        self.assertFalse(UrbanFabricCut.objects.exists())
        self.pasture.refresh_from_db()
        self.assertAlmostEqual(self.pasture.geom.area, 1e6, delta=0.05)

    def test_a_rename_leaves_the_land_cover_alone(self):
        from core.editing import editor_change
        street = self._street(width=8)
        road_pk = self._road().get().pk
        with editor_change():
            street.name = "Renamed"
            street.save()
        self.assertEqual(self._road().get().pk, road_pk)

    def test_imported_streets_leave_the_land_cover_alone(self):
        from builtup.models import Street
        street = Street.objects.create(name="BGT street", classification="residential", geom=_line((100, 300), (300, 300)))
        street.delete()
        self.assertFalse(self._road().exists())

    def test_a_street_and_a_building_ring_released_in_either_order(self):
        from core.editing import editor_change
        for first in ("street", "building"):
            with self.subTest(first):
                street = self._street(_line((400, 500), (600, 500)), width=8)   # crosses the building ring
                building = self._building()
                for obj in ([street, building] if first == "street" else [building, street]):
                    with editor_change():
                        obj.delete()
                self.assertFalse(self._road().exists())
                self.assertFalse(self._urban_fabric().exists())
                self.assertFalse(UrbanFabricCut.objects.exists())
                self.pasture.refresh_from_db()
                self.assertAlmostEqual(self.pasture.geom.area, 1e6, delta=0.05)
