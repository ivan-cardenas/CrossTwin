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
        self.assertContains(response, 'Population</strong> in the bottom bar')   # points to the dock
        self.assertNotContains(response, '<svg')                                 # the graph moved to the dock

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


class PopulationDockTests(TestCase):
    """The bottom dock: values, Curves-style graph with the 67% interval, what-if controls."""

    def setUp(self):
        from administrative.models import PopulationProjection
        self.city = make_city(cityName="Testville", currentPopulation=10000)
        for year, median in ((2025, 10500), (2030, 12000), (2035, 12500)):
            for scenario, factor in (('prognose', 1.0), ('low', 0.95), ('high', 1.05)):
                PopulationProjection.objects.create(
                    city=self.city, year=year, scenario=scenario, population=round(median * factor))

    def get(self, **params):
        params.setdefault('level', 'city')
        params.setdefault('location', 'Testville')
        return self.client.get(reverse('map:population_panel'), params)

    def test_values_today_projected_change_and_interval(self):
        response = self.get(year=2030)
        self.assertContains(response, 'id="pop-value-today">10,000<')
        self.assertContains(response, 'Projected 2030')
        self.assertContains(response, 'id="pop-value-projected">12,000<')
        self.assertContains(response, '+2,000')
        self.assertContains(response, '(+20.0%)')
        self.assertContains(response, '67% interval: 11,400 – 12,600')

    def test_graph_has_curve_band_interval_edges_handles_and_grid(self):
        response = self.get(year=2030)
        self.assertContains(response, '<svg class="pop-graph"')
        for css in ('class="pop-band"', 'class="pop-curve"', 'class="pop-baseline"',
                    'class="pop-marker-line"', 'class="pop-handle', 'class="pop-grid"'):
            self.assertContains(response, css)
        self.assertContains(response, 'today 10k')            # reference line for the current population
        self.assertContains(response, 'data-points="[{')      # per-year values for the hover read-out
        self.assertEqual(response.content.decode().count('class="pop-edge"'), 2)   # lower + upper bound

    def test_the_selected_year_handle_is_highlighted(self):
        self.assertContains(self.get(year=2030), 'pop-handle pop-handle-active')
        self.assertNotContains(self.get(year=2031), 'pop-handle pop-handle-active')

    def test_variant_changes_the_projected_value(self):
        self.assertContains(self.get(year=2030, pop_scenario='low'), 'id="pop-value-projected">11,400<')
        self.assertContains(self.get(year=2030, pop_scenario='high'), 'id="pop-value-projected">12,600<')
        self.assertContains(self.get(year=2030, pop_scenario='low'), 'Lower bound')

    def test_growth_adjustment_moves_the_value_but_not_the_interval(self):
        response = self.get(year=2030, pop_growth='2')
        factor = 1.02 ** 5
        self.assertContains(response, f'id="pop-value-projected">{round(12000 * factor):,}<')
        # The 67% interval reflects the original CBS prediction, unaffected by the what-if slider.
        self.assertContains(response, '67% interval: 11,400 – 12,600')

    def test_year_outside_the_data_says_so_instead_of_faking_a_projection(self):
        response = self.get(year=2040)
        self.assertContains(response, 'No projection for this year.')
        self.assertNotContains(response, 'id="pop-value-projected"')
        self.assertContains(response, '<svg class="pop-graph"')
        self.assertNotContains(response, 'pop-marker-line')

    def test_controls_are_in_the_dock_and_reflect_the_current_choice(self):
        response = self.get(pop_scenario='low', pop_growth='1.5')
        self.assertContains(response, 'class="pop-controls"')
        self.assertContains(response, '<option value="low" selected>')
        self.assertContains(response, 'value="1.5"')
        self.assertContains(response, 'resetPopulationControls')

    def test_no_projections_still_shows_todays_value_and_explains_the_import(self):
        from administrative.models import PopulationProjection
        PopulationProjection.objects.all().delete()
        response = self.get(year=2030)
        self.assertContains(response, 'id="pop-value-today">10,000<')
        self.assertContains(response, 'No projection for this area yet')
        self.assertNotContains(response, '<svg class="pop-graph"')

    def test_neighborhood_grows_by_the_citys_percentage_not_its_local_share(self):
        neighborhood = make_neighborhood(city=self.city, currentPopulation=2500, id="nb-1")
        self.city.refresh_from_db()   # cascade: 2500 is now the whole *locally imported* city
        response = self.get(level='neighborhood', location=neighborhood.neighborhoodName, year=2030)
        # The neighborhood's own 2500 scaled by CBS's real city growth (2025's
        # 10500 -> 2030's 12000, +14.3%), not the city's raw forecast number --
        # city.currentPopulation only reflects whichever units are imported so
        # far and must never be used as the growth baseline.
        self.assertContains(response, 'id="pop-value-projected">2,857<')

    def test_without_a_unit_the_dock_asks_for_a_selection(self):
        response = self.client.get(reverse('map:population_panel'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select an administrative unit')

    def test_city_at_the_map_center_is_used_when_nothing_is_selected(self):
        lng, lat = _lonlat_of_rd(257000.0, 470000.0)
        response = self.client.get(reverse('map:population_panel'), {'lng': lng, 'lat': lat, 'year': 2030})
        self.assertContains(response, 'Testville')
        self.assertContains(response, 'city at the map centre')
