from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase

from builtup.models import Building


def _square(x, y, size=10):
    """A square MultiPolygon in the storage CRS (metres)."""
    polygon = Polygon(((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y)))
    return MultiPolygon(polygon, srid=settings.COORDINATE_SYSTEM)


class BuildingDerivedFieldsTests(TestCase):
    """Fields Building.save() derives must be stored on every save path."""

    def test_create_derives_building_type(self):
        Building.objects.update_or_create(
            id=1, defaults={"usageFunction": "woonfunctie", "geom": _square(0, 0)})

        building = Building.objects.get(id=1)
        self.assertEqual(building.buildingType, "residential")
        self.assertEqual(building.usageFunction, ["Residential function"])
        self.assertEqual(building.area_sqm, 100)

    def test_update_or_create_on_existing_building_stores_derived_fields(self):
        # The importer's path for a re-imported building: update_or_create saves
        # with update_fields = the keys of `defaults`, which holds none of the
        # derived fields.
        Building.objects.update_or_create(
            id=1, defaults={"usageFunction": "woonfunctie", "geom": _square(0, 0)})

        _, created = Building.objects.update_or_create(
            id=1, defaults={"usageFunction": "winkelfunctie,woonfunctie", "geom": _square(0, 0, size=20)})

        self.assertFalse(created)
        building = Building.objects.get(id=1)
        self.assertEqual(building.buildingType, "mixed")
        self.assertEqual(building.usageFunction, ["Shop function", "Residential function"])
        self.assertEqual(building.area_sqm, 400)

    def test_resaving_stored_labels_keeps_building_type(self):
        # A stored building holds labels, not raw BAG codes; a plain re-save
        # (what a backfill does) must derive the same type from them.
        Building.objects.create(id=1, usageFunction="industriefunctie", geom=_square(0, 0))
        Building.objects.filter(id=1).update(buildingType="")

        building = Building.objects.get(id=1)
        building.save(update_fields=["buildingType"])

        self.assertEqual(Building.objects.get(id=1).buildingType, "industrial")

    def test_undefined_usage_has_no_building_type(self):
        # BAG reports some Pand records with an empty gebruiksdoel
        Building.objects.create(id=1, usageFunction="", geom=_square(0, 0))

        building = Building.objects.get(id=1)
        self.assertEqual(building.usageFunction, ["Undefined"])
        self.assertEqual(building.buildingType, "")


# -- Indicator dashboard ------------------------------------------------------

from django.contrib.gis.geos import LineString, Point
from django.urls import reverse

from builtup.models import Facility, Park, Property, Street
from builtup.views import MOCK_DATA, _build_indicators
from mainMap.styles.layerStyles import BUILDING_TYPE_COLORS, LAYER_STYLES
from watersupply.tests.factories import make_neighborhood, make_polygon

HX = {'HTTP_HX_REQUEST': 'true'}
X0, Y0 = 257000.0, 470000.0   # centre of make_polygon()'s 1 km² square


class BuiltupDashboardTests(TestCase):
    """The builtup panel aggregates the fabric of one admin unit (a 1 km² neighborhood here)."""

    def setUp(self):
        self.hood = make_neighborhood(neighborhoodName="Testbuurt", currentPopulation=1000)
        # 100 m² residential with 3 floors; 400 m² shop, 7 m tall (≈ 2 storeys) and vacant
        Building.objects.create(id=1, usageFunction="woonfunctie", numberFloors=3,
                                numberUnits=4, constructionYear=1930, geom=_square(X0, Y0))
        Building.objects.create(id=2, usageFunction="winkelfunctie", height_m=7.0, vacant=True,
                                constructionYear=1980, geom=_square(X0 + 100, Y0, size=20))
        # 1 km of street, 600 m of it inside the unit (its east edge is at X0 + 500)
        Street.objects.create(name="Hoofdweg", classification="primary", width=8,
                              geom=LineString((X0 - 100, Y0), (X0 + 900, Y0), srid=settings.COORDINATE_SYSTEM))
        # Park.save() derives area from geom: a 5 000 m² square
        Park.objects.create(name="Park", vegetationType="grass",
                            neighborhood=self.hood, geom=make_polygon(X0, Y0, 5000 ** 0.5 / 2))
        Facility.objects.create(name="School", type="school", neighborhood=self.hood,
                                geom=Point(X0, Y0, srid=settings.COORDINATE_SYSTEM))

    def get(self, view='builtup_indicators', **params):
        url = reverse(f'builtup:{view}', args=['neighborhood', 'Testbuurt', 2025])
        return self.client.get(url, params, **HX)

    def test_panel_aggregates_the_building_stock(self):
        response = self.get()
        self.assertTemplateUsed(response, 'builtup/partials/indicators_panel.html')
        ind = response.context['indicators']
        self.assertEqual(ind['total_buildings'], 2)
        self.assertEqual(ind['total_units'], 4)
        self.assertEqual(ind['total_floor_area_m2'], 100 * 3 + 400 * 2)
        self.assertEqual(ind['built_coverage_pct'], round(500 / 1e6 * 100, 1))
        self.assertEqual(ind['floor_area_ratio'], round(1100 / 1e6, 2))
        self.assertEqual(ind['vacant_pct'], 50.0)
        mix = {seg['key']: seg for seg in ind['mix_segments']}
        self.assertEqual((mix['residential']['pct'], mix['commercial']['pct'], mix['unknown']['pct']), (50.0, 50.0, 0))
        # same colours as the Buildings layer on the map
        self.assertEqual(mix['industrial']['color'], BUILDING_TYPE_COLORS['industrial'])
        self.assertEqual(ind['layer_colors']['street'], LAYER_STYLES['builtup.Street']['color'])
        self.assertContains(self.get(), f'stroke="{LAYER_STYLES["builtup.Park"]["color"]}"')
        periods = {p['key']: p['count'] for p in ind['age_periods']}
        self.assertEqual((periods['pre_1945'], periods['1975_1991']), (1, 1))

    def test_streets_count_only_their_length_inside_the_unit(self):
        ind = self.get().context['indicators']
        self.assertAlmostEqual(ind['street_length_km'], 0.6)
        self.assertAlmostEqual(ind['street_density'], 0.6)
        self.assertEqual(ind['street_primary_pct'], 100.0)

    def test_green_space_and_facilities_are_per_inhabitant(self):
        ind = self.get().context['indicators']
        population = ind['population']
        self.assertTrue(population)
        self.assertEqual(ind['green_per_capita_m2'], round(5000 / population, 1))
        self.assertEqual(ind['facilities_per_10k'], round(1 / population * 10_000, 1))

    def test_recalculate_adds_the_what_if_park_area(self):
        response = self.get('recalculate_indicators', green_added_ha='2')
        self.assertTemplateUsed(response, 'builtup/partials/indicators_grid.html')
        ind = response.context['indicators']
        self.assertEqual(ind['park_area_ha'], 2.5)
        self.assertEqual(ind['green_per_capita_m2'], round(25_000 / ind['population'], 1))

    def test_invalid_what_if_is_ignored(self):
        ind = self.get('recalculate_indicators', green_added_ha='lots').context['indicators']
        self.assertEqual(ind['park_area_ha'], 0.5)

    def test_unknown_unit_falls_back_to_mock_data(self):
        url = reverse('builtup:builtup_indicators', args=['city', 'Nowhere', 2025])
        response = self.client.get(url)
        self.assertTemplateUsed(response, 'builtup/builtup_indicators.html')
        self.assertEqual(response.context['indicators']['total_buildings'],
                         MOCK_DATA['stock']['total_buildings'])

    def test_json_endpoint(self):
        data = self.get('builtup_indicators_json').json()
        self.assertEqual(data['adminUnit'], 'Testbuurt')
        self.assertEqual(data['indicators']['total_buildings'], 2)


class BuildIndicatorsTests(TestCase):
    """_build_indicators is pure: green status bands follow the WHO thresholds."""

    def status(self, per_capita):
        data = {**MOCK_DATA, 'green': {**MOCK_DATA['green'], 'park_area_per_capita_m2': per_capita}}
        return _build_indicators(data)['green_status']

    def test_green_status_bands(self):
        self.assertEqual(self.status(5), 'bad')
        self.assertEqual(self.status(20), 'warn')
        self.assertEqual(self.status(60), 'ok')
        self.assertIsNone(self.status(None))


class PropertyBagIdTests(TestCase):
    """pdok_properties stores the 16-digit BAG verblijfsobject id as Property.id."""

    BAG_ID = 153010000123456   # 0153010000123456, beyond a 32-bit integer

    def test_property_and_its_rentals_take_a_bag_id(self):
        from housing.models import Rentals

        Building.objects.create(id=1, usageFunction="woonfunctie", geom=_square(0, 0))
        prop = Property.objects.create(id=self.BAG_ID, name="Flat", grossArea=80,
                                       salePrice_EUR=240000.0,
                                       geom=Point(5, 5, srid=settings.COORDINATE_SYSTEM))
        Rentals.objects.create(property=prop, monthlyRent=1000.0)

        self.assertEqual(Property.objects.get(pk=self.BAG_ID).building_id, 1)
        self.assertEqual(Rentals.objects.get().property_id, self.BAG_ID)

    def test_properties_without_an_id_are_still_numbered(self):
        Building.objects.create(id=1, usageFunction="woonfunctie", geom=_square(0, 0))
        prop = Property.objects.create(name="Flat", grossArea=80,
                                       geom=Point(5, 5, srid=settings.COORDINATE_SYSTEM))
        self.assertIsNotNone(prop.pk)
