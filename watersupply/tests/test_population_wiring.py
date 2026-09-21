from django.test import TestCase
from django.urls import reverse

from administrative.models import PopulationProjection

from .factories import make_city, make_consumption_capita

HX = {'HTTP_HX_REQUEST': 'true'}


class PopulationDrivesTheIndicatorsTests(TestCase):
    """Projected population (year, CBS variant, extra growth) reaches the dashboards."""

    def setUp(self):
        self.city = make_city(cityName="Testville", currentPopulation=10000)
        make_consumption_capita(city=self.city, year=2030, consumption_capita_L_d=100.0)
        for scenario, population in (('prognose', 12000), ('low', 11000), ('high', 13000)):
            PopulationProjection.objects.create(
                city=self.city, year=2030, scenario=scenario, population=population)

    def water(self, view='water_indicators', year=2030, **params):
        url = reverse(f'watersupply:{view}', args=['city', 'Testville', year])
        return self.client.get(url, params, **HX)

    # ---- water --------------------------------------------------------

    def test_water_panel_uses_the_projected_population(self):
        response = self.water()
        self.assertEqual(response.context['indicators']['population'], 12000)
        # demand [Mm3/yr] = 100 L/person/day / 1000 * population * 365 / 1e6
        self.assertEqual(response.context['indicators']['total_demand_Mm3'], round(0.1 * 12000 * 365 / 1e6, 2))

    def test_variant_and_growth_change_the_water_demand(self):
        low = self.water(pop_scenario='low').context['indicators']
        high = self.water(pop_scenario='high').context['indicators']
        self.assertEqual((low['population'], high['population']), (11000, 13000))
        self.assertLess(low['total_demand_Mm3'], high['total_demand_Mm3'])

        grown = self.water(pop_growth='2').context['indicators']['population']
        self.assertEqual(grown, round(12000 * 1.02 ** 5))

    def test_year_without_projection_falls_back_to_the_current_population(self):
        make_consumption_capita(city=self.city, year=2040, consumption_capita_L_d=100.0)
        self.assertEqual(self.water(year=2040).context['indicators']['population'], 10000)

    def test_recalculate_keeps_the_population_what_if(self):
        response = self.water('recalculate_indicators', consumption=100, pop_scenario='high')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['indicators']['population'], 13000)

    def test_panel_shows_the_population_and_carries_the_what_if_in_its_slider(self):
        response = self.water(pop_scenario='low', pop_growth='1.5')
        adjusted = round(11000 * 1.015 ** 5)   # lower bound, +1.5 %/yr from 2025 to 2030
        self.assertContains(response, f'{adjusted:,} inhabitants')
        self.assertContains(response, '"pop_scenario": "low"')
        self.assertContains(response, '"pop_growth": "1.5"')
        # the what-if controls live in the map's bottom dock, not in the indicator panel
        self.assertNotContains(response, 'class="pop-controls"')

    def test_invalid_population_params_are_ignored(self):
        response = self.water(pop_scenario='bogus', pop_growth='x')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['indicators']['population'], 12000)

    # ---- housing ------------------------------------------------------

    def housing(self, year=2030, view='housing_indicators', **params):
        url = reverse(f'housing:{view}', args=['city', 'Testville', year])
        return self.client.get(url, params, **HX)

    def test_housing_panel_uses_the_projected_population(self):
        response = self.housing(pop_scenario='low')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['indicators']['population'], 11000)
        self.assertContains(response, '11,000 inhabitants')
        self.assertContains(response, '"pop_scenario": "low"')

    def test_housing_recalculate_keeps_the_population_what_if(self):
        response = self.housing(view='recalculate_indicators', pop_scenario='high', interest_rate='4')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['indicators']['population'], 13000)
