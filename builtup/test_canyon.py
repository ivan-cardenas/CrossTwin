"""Streets/Buildings -> Canyon_Aspect: builtup.StreetCanyon, builtup/chain.py, builtup/signals.py."""
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import LineString, MultiLineString, MultiPolygon, Polygon
from django.test import SimpleTestCase, TestCase

from builtup import chain, signals
from builtup.models import Building, Street, StreetCanyon

SRID = settings.COORDINATE_SYSTEM


def _rect(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))), srid=SRID)


def _line(*points):
    return MultiLineString(LineString(*points), srid=SRID)


class CanyonChainTests(SimpleTestCase):
    def test_height_is_the_mean_of_both_sides_open_side_zero(self):
        self.assertEqual(chain.canyon_height(12, 12), 12)
        self.assertEqual(chain.canyon_height(12, None), 6)
        self.assertEqual(chain.canyon_height(None, None), 0)

    def test_width_priority_street_then_facade_then_default(self):
        self.assertEqual(chain.canyon_width(10, 20, "residential"), (10.0, "street"))
        self.assertEqual(chain.canyon_width(None, 20, "residential"), (20.0, "facade"))
        self.assertEqual(chain.canyon_width(0, None, "primary"), (20.0, "default"))
        self.assertEqual(chain.canyon_width(None, None, "unknown"), (chain.FALLBACK_WIDTH_M, "default"))

    def test_aspect_ratio_needs_a_positive_width(self):
        self.assertAlmostEqual(chain.aspect_ratio(12, 20), 0.6)
        self.assertIsNone(chain.aspect_ratio(12, 0))


class StreetCanyonTests(TestCase):
    """A 200 m street along y = 0 between two 12 m blocks, 10 m from it on each side."""

    def setUp(self):
        Building.objects.create(id=1, height_m=12, geom=_rect(0, 10, 200, 20))    # left (north)
        Building.objects.create(id=2, height_m=12, geom=_rect(0, -20, 200, -10))  # right (south)
        self.street = Street.objects.create(name="Kanaalstraat", classification="residential",
                                            geom=_line((0, 0), (200, 0)))

    def canyon(self):
        return StreetCanyon.objects.get(street=self.street)

    def test_street_save_creates_canyon_from_facade_gap(self):
        c = self.canyon()
        self.assertAlmostEqual(c.h_left_m, 12)
        self.assertAlmostEqual(c.h_right_m, 12)
        self.assertAlmostEqual(c.w_facade_m, 20)
        self.assertEqual(c.width_source, "facade")
        self.assertAlmostEqual(c.aspect_ratio, 0.6)
        self.assertEqual((c.n_left, c.n_right), (1, 1))

    def test_typed_street_width_overrides_the_facade_gap(self):
        self.street.width = 10
        self.street.save()
        c = self.canyon()
        self.assertEqual(c.width_source, "street")
        self.assertAlmostEqual(c.aspect_ratio, 1.2)

    def test_deleting_a_building_opens_one_side(self):
        Building.objects.get(id=2).delete()
        c = self.canyon()
        self.assertAlmostEqual(c.height_m, 6)
        self.assertEqual(c.width_source, "default")       # residential: 8 m
        self.assertAlmostEqual(c.aspect_ratio, 6 / 8)

    def test_raising_a_building_refreshes_the_canyon(self):
        b = Building.objects.get(id=1)
        b.height_m = 24
        b.save()
        self.assertAlmostEqual(self.canyon().height_m, 18)

    def test_floors_stand_in_for_a_missing_height(self):
        b = Building.objects.get(id=1)
        b.height_m, b.numberFloors = None, 2
        b.save()
        self.assertAlmostEqual(self.canyon().h_left_m, 6)

    def test_attribute_only_edit_refreshes_nothing(self):
        b = Building.objects.get(id=1)
        b.name = "Renamed"
        with mock.patch.object(signals, "refresh_canyons", wraps=signals.refresh_canyons) as spy:
            b.save()
        spy.assert_not_called()

    def test_far_building_does_not_touch_the_canyon(self):
        with mock.patch.object(signals, "refresh_canyons", wraps=signals.refresh_canyons) as spy:
            Building.objects.create(id=3, height_m=30, geom=_rect(0, 500, 20, 520))
        spy.assert_called_once_with([])
        self.assertAlmostEqual(self.canyon().height_m, 12)

    def test_save_recomputes_like_the_bulk_path(self):
        c = self.canyon()
        c.aspect_ratio = None
        c.save()
        self.assertAlmostEqual(StreetCanyon.objects.get(pk=c.pk).aspect_ratio, 0.6)

    def test_deleting_the_street_deletes_its_canyon(self):
        self.street.delete()
        self.assertFalse(StreetCanyon.objects.exists())

    def test_dashboard_weights_stored_canyons_by_length(self):
        from urban_heat.calculations import calculate_canyon_aspect

        Street.objects.create(name="Open", classification="residential", width=10,
                              geom=_line((0, 1000), (600, 1000)))    # no buildings: H/W 0, 600 m
        unit = SimpleNamespace(geom=MultiPolygon(Polygon.from_bbox((-50, -100, 700, 1100)), srid=SRID))
        result = calculate_canyon_aspect(unit)
        self.assertEqual(result["canyon_streets"], 2)
        self.assertAlmostEqual(result["aspect_ratio"], round(0.6 * 200 / 800, 2))
        self.assertAlmostEqual(result["canyon_open_pct"], 75.0)


class CanyonDeferralTests(TestCase):
    def test_bulk_buildings_refresh_once(self):
        Street.objects.create(name="A", classification="residential", geom=_line((0, 0), (200, 0)))
        with mock.patch.object(signals, "refresh_canyons", wraps=signals.refresh_canyons) as spy:
            with signals.deferred_canyon_refresh():
                for i in range(5):
                    Building.objects.create(id=10 + i, height_m=9, geom=_rect(i * 40, 10, i * 40 + 30, 20))
        spy.assert_called_once()
        self.assertAlmostEqual(StreetCanyon.objects.get().h_left_m, 9)

    def test_bulk_street_finalizer_creates_canyons(self):
        from importer.batching import _refresh_canyons_over

        Building.objects.create(id=1, height_m=12, geom=_rect(0, 10, 200, 20))
        rows = Street.objects.bulk_create([
            Street(name="B", classification="residential", geom=_line((0, 0), (200, 0)))])
        self.assertFalse(StreetCanyon.objects.exists())
        _refresh_canyons_over(rows)
        self.assertAlmostEqual(StreetCanyon.objects.get().h_left_m, 12)
