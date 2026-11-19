"""
Small businesses on household-type connections add to the residential demand:
total demand = residential demand x chain.SMALL_BUSINESS_DEMAND_FACTOR (1.2, Vitens).
"""
from django.test import SimpleTestCase, TestCase

from watersupply.calculations import chain
from watersupply.models import TotalWaterDemand
from watersupply.views import _build_indicators

from .factories import make_city, make_consumption_capita


class SmallBusinessFactorTests(SimpleTestCase):
    def test_factor_is_vitens_1_2(self):
        self.assertEqual(chain.SMALL_BUSINESS_DEMAND_FACTOR, 1.2)

    def test_total_demand_is_residential_times_the_factor(self):
        # 10 000 people x 120 L/day = 1200 m3/day residential, 1440 m3/day in total
        self.assertAlmostEqual(chain.residential_demand_m3_d(120, 10_000), 1200)
        self.assertAlmostEqual(chain.demand_m3_d(120, 10_000), 1440)
        self.assertAlmostEqual(chain.demand_m3_d(120, 10_000, small_business_factor=1.0), 1200)

    def test_yearly_consumption_stays_residential(self):
        self.assertAlmostEqual(chain.consumption_m3_yr(120, 10_000), 1200 * 365)


class StoredDemandIncludesSmallBusinessesTests(TestCase):
    def setUp(self):
        self.city = make_city()  # no projections: baseline = current population
        make_consumption_capita(city=self.city, year=2024, consumption_capita_L_d=120.0)

    def test_stored_demand_and_factor(self):
        demand = TotalWaterDemand.objects.create(city=self.city, year=2024, demandDay=0)
        expected = chain.demand_m3_d(120, self.city.currentPopulation)
        self.assertAlmostEqual(demand.demandDay * 1e6, expected)
        self.assertEqual(demand.small_business_factor, 1.2)

    def test_dashboard_shows_both_parts(self):
        data = {'population': 10_000, 'consumption_capita': 120, 'supply_m3_d': 2880, 'opex_total': 0,
                'network_length': 0}
        ind = _build_indicators(data)
        self.assertEqual(ind['demand_m3_d'], 1440)
        self.assertEqual(ind['residential_demand_m3_d'], 1200)
        self.assertEqual(ind['small_business_demand_m3_d'], 240)
        self.assertEqual(ind['supply_security'], 200)
