"""
Stored climate scenario runs (weather.ClimateScenarioRun) in the housing
module: homes needed for the scenario population (ScenarioHousingNeed),
DAG edges Total_Population, Household_Size -> Housing_Demand.
"""
from django.test import SimpleTestCase, TestCase

from administrative.models import PopulationProjection
from housing.calculations import chain
from housing.models import HouseholdSize, HousingSupplyDemand, ScenarioHousingNeed
from watersupply.tests.factories import make_city
from weather.models import ClimateScenarioRun


class DwellingGapTests(SimpleTestCase):
    def test_gap(self):
        self.assertEqual(chain.dwelling_gap(1200, 1000), 200)
        self.assertEqual(chain.dwelling_gap(900, 1000), -100)
        self.assertIsNone(chain.dwelling_gap(None, 1000))


class ScenarioHousingTests(TestCase):
    def setUp(self):
        self.city = make_city(cityName="Homeville", currentPopulation=10000)
        for year, population in ((2025, 10000), (2050, 12000)):
            PopulationProjection.objects.create(city=self.city, year=year, population=population, scenario="prognose")
        HouseholdSize.objects.create(city=self.city, year=2025, households=5000)   # 2.0 persons per home
        HousingSupplyDemand.objects.create(city=self.city, year=2025, supply_units=4800)

    def make_run(self, scenario="2050_Hd"):
        return ClimateScenarioRun.objects.create(
            scenario=scenario, unit_level="city", unit_name="Homeville", parameters={"run_heat": False})

    def test_homes_needed_for_the_scenario_population(self):
        need = ScenarioHousingNeed.objects.get(run=self.make_run())
        self.assertEqual(need.year, 2050)
        self.assertEqual(need.population, 12000)
        self.assertEqual(need.household_size_year, 2025)
        self.assertEqual(need.dwellings_needed, 6000)
        self.assertEqual(need.baseline_dwellings_needed, 5000)
        self.assertEqual(need.stock_units, 4800)
        self.assertEqual(need.gap_units, 1200)

    def test_observed_demand_is_untouched(self):
        before = list(HousingSupplyDemand.objects.values_list("demand_units", flat=True))
        self.make_run()
        self.assertEqual(list(HousingSupplyDemand.objects.values_list("demand_units", flat=True)), before)

    def test_2100_holds_the_household_size_and_flags_the_trend(self):
        need = ScenarioHousingNeed.objects.get(run=self.make_run("2100_Hd"))
        self.assertTrue(need.population_extrapolated)
        self.assertEqual(need.household_size_year, 2025)
        self.assertGreater(need.population, 12000)

    def test_recalculate_follows_new_data(self):
        run = self.make_run()
        HousingSupplyDemand.objects.create(city=self.city, year=2024, supply_units=4900)
        HousingSupplyDemand.objects.filter(year=2025).update(supply_units=5500)
        run.save()
        self.assertEqual(ScenarioHousingNeed.objects.get(run=run).gap_units, 500)
