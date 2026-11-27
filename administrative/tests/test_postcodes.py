"""
Postcode areas (PC4, PC6) as administrative units: the models, their lookup and containment helpers, and the
importer entries that fill them from the PDOK CBS postcode statistics.
"""
from django.conf import settings
from django.contrib.gis.geos import Point
from django.test import TestCase

from administrative import admin_units
from administrative.models import Postcode4, Postcode6
from importer.external_catalog import EXTERNAL_DATA_CATALOG, FIELD_MAPPINGS, KEA_NODATA
from importer.external_data import _prepare_features
from watersupply.tests.factories import make_city, make_district, make_neighborhood, make_polygon

SRID = settings.COORDINATE_SYSTEM


def _catalog(key):
    return next(entry for entry in EXTERNAL_DATA_CATALOG if entry["key"] == key)


class PostcodeModelTests(TestCase):
    def test_pc6_derives_its_pc4_and_normalises_the_code(self):
        area = Postcode6.objects.create(code="2611ag", geom=make_polygon(257000.0, 470000.0, 100), currentPopulation=40)
        self.assertEqual(area.code, "2611AG")
        self.assertEqual(area.postcode4, "2611")
        self.assertAlmostEqual(area.area_km2, 0.04)
        self.assertAlmostEqual(area.populationDensity, 1000.0)

    def test_pc4_keeps_its_figures_and_null_stays_null(self):
        area = Postcode4.objects.create(code=2611, geom=make_polygon(), dwellings=5000, meanWOZ_EUR=None)
        area.refresh_from_db()
        self.assertEqual((area.code, area.dwellings, area.meanWOZ_EUR), ("2611", 5000, None))
        self.assertEqual(area.populationDensity, 0.0)

    def test_postcode_models_are_in_the_registry(self):
        from core.utils import VECTOR_REGISTRY

        keys = {key.lower() for key in VECTOR_REGISTRY}
        self.assertIn("administrative.postcode4", keys)
        self.assertIn("administrative.postcode6", keys)


class PostcodeUnitTests(TestCase):
    def setUp(self):
        # a 1 km city with two neighborhoods side by side; a PC4 over the west one and half of the east one
        self.city = make_city(id=503, cityName="Delft", geom=make_polygon(257000.0, 470000.0, 1000))
        district = make_district(city=self.city, geom=make_polygon(257000.0, 470000.0, 1000))
        self.west = make_neighborhood(id="BU1", district=district, geom=make_polygon(256500.0, 470000.0, 500))
        self.east = make_neighborhood(id="BU2", district=district, geom=make_polygon(257500.0, 470000.0, 500))
        self.pc4 = Postcode4.objects.create(code="2611", geom=make_polygon(256500.0, 470000.0, 600))
        self.pc6 = Postcode6.objects.create(code="2611AG", geom=make_polygon(257500.0, 470000.0, 50))

    def test_lookup_by_code_at_both_levels(self):
        self.assertEqual(admin_units.resolve_admin_unit("postcode4", "2611"), self.pc4)
        self.assertEqual(admin_units.resolve_admin_unit("postcode6", "2611AG"), self.pc6)
        self.assertIsNone(admin_units.resolve_admin_unit("postcode6", "9999ZZ"))

    def test_a_map_point_still_resolves_through_the_hierarchy_only(self):
        point = Point(257500.0, 470000.0, srid=SRID)
        point.transform(4326)
        level, unit = admin_units.resolve_admin_unit_at_point(point.x, point.y)
        self.assertEqual((level, unit), ("neighborhood", self.east))
        found = admin_units.postcodes_at_point(point.x, point.y)
        self.assertEqual(found["postcode6"], self.pc6)
        self.assertIsNone(found["postcode4"])          # the PC4 covers the west only

    def test_neighborhoods_of_a_pc4_are_those_whose_middle_lies_in_it(self):
        self.assertEqual(list(admin_units.neighborhoods_within(self.pc4)), [self.west])

    def test_the_neighborhood_of_a_pc6_is_the_one_it_lies_in(self):
        self.assertEqual(list(admin_units.neighborhoods_within(self.pc6)), [self.east])

    def test_city_and_province_of_a_postcode_area(self):
        self.assertEqual(admin_units.city_of(self.pc4), self.city)
        self.assertEqual(admin_units.city_of(self.pc6), self.city)
        self.assertEqual(admin_units.province_of(self.pc6), self.city.province)
        self.assertEqual(list(admin_units.cities_within(self.pc4)), [self.city])

    def test_a_postcode_area_outside_every_city_has_no_city(self):
        far = Postcode6.objects.create(code="9999ZZ", geom=make_polygon(100000.0, 400000.0, 50))
        self.assertIsNone(admin_units.city_of(far))
        self.assertIsNone(admin_units.province_of(far))
        self.assertEqual(list(admin_units.neighborhoods_within(far)), [])


class PostcodeImportTests(TestCase):
    def test_catalog_entries_target_the_models_and_a_city_bbox(self):
        for key, model in (("pdok_postcode4", "administrative.Postcode4"), ("pdok_postcode6", "administrative.Postcode6")):
            entry = _catalog(key)
            self.assertEqual(entry["target_model"], model)
            self.assertEqual(entry["format"], "wfs")
            self.assertEqual(entry["bbox_from"], "administrative.City")
            self.assertIn(key.replace("pdok_", "") + "/", entry["url"])

    def test_every_mapped_field_exists_on_the_model(self):
        for key, model in (("pdok_postcode4", Postcode4), ("pdok_postcode6", Postcode6)):
            fields = {f.name for f in model._meta.get_fields()}
            mapping = FIELD_MAPPINGS[key]
            targets = [v for k, v in mapping.items() if not k.startswith("__")] + [mapping["__unique_field__"]]
            targets += list(mapping["__static__"])
            self.assertEqual([t for t in targets if t not in fields], [], key)

    def test_nodata_becomes_null_and_the_woz_value_is_scaled_to_euros(self):
        mapping = FIELD_MAPPINGS["pdok_postcode6"]
        feature = {"id": "f1", "properties": {"postcode6": "2611AG", "aantalWoningen": 20, "gemiddeldeWozWaardeWoning": 360,
                                              "percentageKoopwoningen": -99997}}
        prepared = _prepare_features([feature], mapping)[0]["properties"]
        self.assertEqual(prepared["gemiddeldeWozWaardeWoning"], 360_000)
        self.assertIsNone(prepared["percentageKoopwoningen"])
        self.assertEqual(prepared["aantalWoningen"], 20)
        self.assertEqual(mapping["__nodata__"], KEA_NODATA)
