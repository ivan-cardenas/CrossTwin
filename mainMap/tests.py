from django.conf import settings
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from administrative.admin_units import city_of
from watersupply.tests.factories import make_city, make_district, make_neighborhood, make_province

URL = 'map:dashboard_summary'


def _lonlat_of_rd(x, y):
    """WGS84 (lng, lat) of an EPSG:28992 point, as the map center is reported."""
    point = Point(x, y, srid=settings.COORDINATE_SYSTEM)
    point.transform(4326)
    return point.x, point.y


class DashboardSummaryTests(TestCase):
    def setUp(self):
        self.province = make_province()
        self.city = make_city(province=self.province, cityName="Testville")
        self.neighborhood = make_neighborhood(city=self.city, currentPopulation=1200)
        self.city.refresh_from_db()  # population cascade: neighborhood -> district -> city
        self.lng, self.lat = _lonlat_of_rd(257000.0, 470000.0)  # inside every factory polygon

    def get(self, **params):
        return self.client.get(reverse(URL), params)

    def test_selected_unit_population_is_shown(self):
        response = self.get(level='neighborhood', location='Test Neighborhood')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1,200')
        self.assertContains(response, 'Test Neighborhood')
        self.assertNotContains(response, 'no unit selected')

    def test_without_selection_the_city_at_the_map_center_is_shown(self):
        response = self.get(lng=self.lng, lat=self.lat)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Testville')
        self.assertContains(response, '1,200')  # city population = sum of its districts
        self.assertContains(response, 'no unit selected')

    def test_unknown_selection_falls_back_to_the_city(self):
        # The map starts with a placeholder selection ('province', 'Demo')
        response = self.get(level='province', location='Demo', lng=self.lng, lat=self.lat)
        self.assertContains(response, 'Testville')
        self.assertContains(response, 'no unit selected')

    def test_nothing_to_show_is_still_a_valid_partial(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select an administrative unit')

    def test_point_outside_every_unit(self):
        response = self.get(lng=0.0, lat=0.0)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select an administrative unit')


class CityOfTests(TestCase):
    def test_city_of_each_level(self):
        province = make_province()
        city = make_city(province=province)
        district = make_district(city=city)
        neighborhood = make_neighborhood(city=city, district=district)
        self.assertEqual(city_of(city), city)
        self.assertEqual(city_of(district), city)
        self.assertEqual(city_of(neighborhood), city)
        self.assertIsNone(city_of(province))  # a province spans many cities
