"""ConsumptionCapita.for_year: a year without its own record uses the latest earlier one."""
from django.test import TestCase

from watersupply.calculations import _get_consumption_capita, consumption_data_years
from watersupply.models import ConsumptionCapita, TotalWaterDemand
from watersupply.views import _build_indicators, _get_adminUnit_data

from .factories import make_city, make_consumption_capita


class ConsumptionForYearTests(TestCase):
    def setUp(self):
        self.city = make_city(currentPopulation=10000)

    def test_own_year_wins(self):
        make_consumption_capita(city=self.city, year=2015, consumption_capita_L_d=135.0)
        make_consumption_capita(city=self.city, year=2026, consumption_capita_L_d=120.0)
        self.assertEqual(ConsumptionCapita.for_year(self.city, 2026).consumption_capita_L_d, 120.0)

    def test_latest_earlier_year_is_used(self):
        make_consumption_capita(city=self.city, year=2010, consumption_capita_L_d=140.0)
        make_consumption_capita(city=self.city, year=2015, consumption_capita_L_d=135.0)
        self.assertEqual(ConsumptionCapita.for_year(self.city, 2026).year, 2015)

    def test_earliest_later_year_when_nothing_earlier(self):
        make_consumption_capita(city=self.city, year=2015, consumption_capita_L_d=135.0)
        make_consumption_capita(city=self.city, year=2020, consumption_capita_L_d=130.0)
        self.assertEqual(ConsumptionCapita.for_year(self.city, 2010).year, 2015)

    def test_none_without_records(self):
        self.assertIsNone(ConsumptionCapita.for_year(self.city, 2026))

    def test_dashboard_value_and_data_year(self):
        make_consumption_capita(city=self.city, year=2015, consumption_capita_L_d=135.0)
        self.assertEqual(_get_consumption_capita(self.city, 2026), 135.0)
        self.assertEqual(consumption_data_years(self.city, 2026), [2015])

    def test_indicators_show_the_data_year_until_the_slider_moves(self):
        make_consumption_capita(city=self.city, year=2015, consumption_capita_L_d=135.0)
        data = _get_adminUnit_data('city', self.city.cityName, 2026)
        self.assertEqual(data['consumption_years'], [2015])
        self.assertEqual(_build_indicators(data)['consumption_years'], [2015])
        self.assertEqual(_build_indicators(data, consumption_override=150)['consumption_years'], [])
        self.assertGreater(_build_indicators(data)['total_demand_Mm3'], 0)


class StoredDemandUsesTheClosestYearTests(TestCase):
    def setUp(self):
        self.city = make_city(currentPopulation=10000)
        self.old = make_consumption_capita(city=self.city, year=2015, consumption_capita_L_d=100.0)

    def test_demand_of_a_later_year_uses_the_earlier_consumption(self):
        demand = TotalWaterDemand.objects.create(city=self.city, year=2026, demandDay=0)
        self.assertAlmostEqual(demand.demandDay * 1e6, 1000.0)  # 10 000 x 100 L

    def test_new_record_refreshes_the_years_it_now_covers(self):
        demand = TotalWaterDemand.objects.create(city=self.city, year=2026, demandDay=0)
        make_consumption_capita(city=self.city, year=2024, consumption_capita_L_d=150.0)
        demand.refresh_from_db()
        self.assertAlmostEqual(demand.demandDay * 1e6, 1500.0)

    def test_deleting_a_record_falls_back_again(self):
        newer = make_consumption_capita(city=self.city, year=2024, consumption_capita_L_d=150.0)
        demand = TotalWaterDemand.objects.create(city=self.city, year=2026, demandDay=0)
        newer.delete()
        demand.refresh_from_db()
        self.assertAlmostEqual(demand.demandDay * 1e6, 1000.0)


class SupplyDemandBalanceTests(TestCase):
    """The Supply vs Demand card: both bars on the scale of the larger, plus the yearly balance."""

    def indicators(self, supply_m3_d, demand_people):
        city = make_city(currentPopulation=demand_people)
        make_consumption_capita(city=city, year=2026, consumption_capita_L_d=100.0)
        data = _get_adminUnit_data('city', city.cityName, 2026)
        data['supply_m3_d'] = supply_m3_d
        return _build_indicators(data)

    def test_surplus(self):
        ind = self.indicators(supply_m3_d=2000, demand_people=10000)  # demand 1000 m3/d
        self.assertEqual(ind['supply_bar_pct'], 100.0)
        self.assertEqual(ind['demand_bar_pct'], 50.0)
        self.assertAlmostEqual(ind['balance_Mm3'], round(1000 * 365 / 1e6, 2))

    def test_shortfall(self):
        ind = self.indicators(supply_m3_d=500, demand_people=10000)
        self.assertEqual(ind['demand_bar_pct'], 100.0)
        self.assertEqual(ind['supply_bar_pct'], 50.0)
        self.assertLess(ind['balance_Mm3'], 0)
        self.assertEqual(ind['balance_abs_Mm3'], -ind['balance_Mm3'])

    def test_nothing_known(self):
        ind = self.indicators(supply_m3_d=0, demand_people=0)
        self.assertEqual((ind['supply_bar_pct'], ind['demand_bar_pct'], ind['balance_Mm3']), (0, 0, 0))
