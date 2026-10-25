"""
The stored water chain and the dashboard's population what-if share one
implementation (watersupply/chain.py): stored records use the baseline
population of their year (CBS median forecast, no extra growth), a new or
corrected forecast propagates through the signals, and the dashboard runs the
same functions with the request's what-if without writing anything.
"""
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from administrative.models import PopulationProjection
from importer.batching import deferred_cascades
from watersupply import chain, signals
from watersupply.models import ConsumptionCapita, ImportedWater, SupplySecurity, TotalWaterDemand

from .factories import make_city, make_consumption_capita

HX = {'HTTP_HX_REQUEST': 'true'}


def forecast(city, year, population, scenario='prognose'):
    return PopulationProjection.objects.create(city=city, year=year, scenario=scenario, population=population)


class ChainFunctionTests(TestCase):
    def test_service_time(self):
        self.assertEqual(chain.service_time_hours(600, 1200), 12.0)
        self.assertEqual(chain.service_time_hours(1200, 1200), chain.SERVICE_HOURS_MAX)
        self.assertEqual(chain.service_time_hours(5, 0), chain.SERVICE_HOURS_MAX)
        self.assertEqual(chain.service_time_hours(0, 0), 0)

    def test_supply_security_without_demand_is_zero(self):
        self.assertEqual(chain.supply_security_pct(100, 0), 0)


class StoredChainUsesTheBaselineTests(TestCase):
    def setUp(self):
        self.city = make_city(cityName="Testville", currentPopulation=10000)

    def test_stored_demand_uses_the_median_forecast_of_its_year(self):
        forecast(self.city, 2030, 12000)
        cc = make_consumption_capita(city=self.city, year=2030, consumption_capita_L_d=100.0)
        demand = TotalWaterDemand.objects.create(city=self.city, year=2030, demandDay=0)
        self.assertAlmostEqual(cc.total_consumption_m3_yr, 0.1 * 12000 * 365)
        self.assertAlmostEqual(demand.demandDay, 12000 * 100 / 1e9)

    def test_saving_a_forecast_refreshes_the_stored_chain(self):
        cc = make_consumption_capita(city=self.city, year=2030, consumption_capita_L_d=100.0)
        demand = TotalWaterDemand.objects.create(city=self.city, year=2030, demandDay=0)
        ImportedWater.objects.create(sourceName="Imp", quantity_m3_d=1000, price_EUR_m3=1.0)
        security = SupplySecurity.objects.create(
            city=self.city, year=2030, supply_security_pct=0, security_goal_pct=90, service_time_hours=0)
        self.assertEqual(security.service_time_hours, 24)   # 1000 m3/d covers 10000 x 100 L

        forecast(self.city, 2030, 20000)                     # 2000 m3/d demand

        cc.refresh_from_db(); demand.refresh_from_db(); security.refresh_from_db()
        self.assertAlmostEqual(cc.total_consumption_m3_yr, 0.1 * 20000 * 365)
        self.assertAlmostEqual(demand.demandDay, 20000 * 100 / 1e9)
        self.assertAlmostEqual(security.supply_security_pct, 50.0)
        self.assertEqual(security.service_time_hours, 12.0)

    def test_deleting_the_forecast_falls_back_to_the_current_population(self):
        projection = forecast(self.city, 2030, 12000)
        make_consumption_capita(city=self.city, year=2030, consumption_capita_L_d=100.0)
        demand = TotalWaterDemand.objects.create(city=self.city, year=2030, demandDay=0)
        projection.delete()
        demand.refresh_from_db()
        self.assertAlmostEqual(demand.demandDay, 10000 * 100 / 1e9)

    def test_low_and_high_variants_do_not_touch_the_stored_chain(self):
        make_consumption_capita(city=self.city, year=2030, consumption_capita_L_d=100.0)
        demand = TotalWaterDemand.objects.create(city=self.city, year=2030, demandDay=0)
        forecast(self.city, 2030, 11000, 'low')
        forecast(self.city, 2030, 13000, 'high')
        demand.refresh_from_db()
        self.assertAlmostEqual(demand.demandDay, 10000 * 100 / 1e9)

    def test_bulk_forecast_import_refreshes_each_city_once(self):
        make_consumption_capita(city=self.city, year=2030, consumption_capita_L_d=100.0)
        demand = TotalWaterDemand.objects.create(city=self.city, year=2030, demandDay=0)
        with mock.patch.object(signals, '_resave', wraps=signals._resave) as resave:
            with deferred_cascades():
                for year in range(2025, 2036):
                    forecast(self.city, year, 10000 + 200 * (year - 2025))
                demand.refresh_from_db()
                self.assertAlmostEqual(demand.demandDay, 10000 * 100 / 1e9)  # still deferred
        consumption_refreshes = [
            c for c in resave.call_args_list
            if getattr(c.args[0], 'model', None) is ConsumptionCapita
        ]
        self.assertEqual(len(consumption_refreshes), 1)
        demand.refresh_from_db()
        self.assertAlmostEqual(demand.demandDay, 11000 * 100 / 1e9)


class DashboardIsADeviationFromTheBaselineTests(TestCase):
    """Without a what-if the dashboard shows the stored chain; with one it moves away from it."""

    def setUp(self):
        self.city = make_city(cityName="Testville", currentPopulation=10000)
        forecast(self.city, 2030, 12000)
        make_consumption_capita(city=self.city, year=2030, consumption_capita_L_d=100.0)
        self.demand = TotalWaterDemand.objects.create(city=self.city, year=2030, demandDay=0)

    def indicators(self, **params):
        url = reverse('watersupply:water_indicators', args=['city', 'Testville', 2030])
        return self.client.get(url, params, **HX).context['indicators']

    def test_default_dashboard_matches_the_stored_demand(self):
        stored_Mm3_yr = self.demand.demandYR
        self.assertEqual(self.indicators()['total_demand_Mm3'], round(stored_Mm3_yr, 2))

    def test_population_what_if_is_not_written(self):
        grown = self.indicators(pop_growth='5')
        self.assertGreater(grown['population'], 12000)
        self.assertGreater(grown['total_demand_Mm3'], round(self.demand.demandYR, 2))
        self.demand.refresh_from_db()
        self.assertAlmostEqual(self.demand.demandDay, 12000 * 100 / 1e9)
