"""
Extraction belongs to a watershed, not to the admin unit the well lies in: its
water is shared by the population of the watershed (calculate_total_extraction),
and stored SupplySecurity records follow that share (watersupply/signals.py).
"""
from unittest import mock

from django.conf import settings
from django.contrib.gis.geos import Point
from django.test import TestCase

from administrative.models import Neighborhood
from physicalEnv.models import EnvironmentalCosts
from watersupply import signals
from watersupply.calculations import calculate_total_extraction, watershed_share
from watersupply.models import AvailableFreshWater, ExtractionWater, SupplySecurity, TotalWaterDemand, Watershed

from .factories import make_city, make_consumption_capita, make_neighborhood, make_polygon
from .test_water_chain import make_source, make_well

RD = settings.COORDINATE_SYSTEM
FLOW_M3_S = 0.01  # 864 m3/day
DEMAND_M3_D = 1000
# pumping 24 h at FLOW_M3_S, no measured yearly extraction
WELL_VOLUME = dict(pumpflow_m3_s=FLOW_M3_S, OperationTime_h_day=24.0, current_extraction_Mm3_yr=None)


class WatershedTestCase(TestCase):
    """Cities A (3000 people) and B (1000 people) share a watershed; the well lies in neither."""

    def setUp(self):
        EnvironmentalCosts.objects.create(price_EUR_kg_CO2=0.05, price_EUR_droughtDamage_m3=0.02)
        self.watershed = Watershed.objects.create(
            name="Test watershed", geom=make_polygon(x=257500.0, half_size_m=2000.0))
        self.city_a = make_city(cityName="A", geom=make_polygon(x=257000.0))
        self.city_b = make_city(cityName="B", geom=make_polygon(x=258000.0))
        self.nbh_a = make_neighborhood(city=self.city_a, geom=make_polygon(x=257000.0), currentPopulation=3000)
        self.nbh_b = make_neighborhood(city=self.city_b, geom=make_polygon(x=258000.0), currentPopulation=1000)
        self.source = make_source(geom=self.watershed.geom, watershed=self.watershed)

    def add_well(self, x=259000.0, **kwargs):
        return make_well(geom=Point(x, 470000.0, srid=RD), source=self.source, **WELL_VOLUME, **kwargs)


class WatershedShareTests(WatershedTestCase):
    def test_well_outside_the_unit_is_shared_by_population(self):
        self.add_well()
        self.assertAlmostEqual(calculate_total_extraction(self.city_a), FLOW_M3_S * 86400 * 0.75)
        self.assertAlmostEqual(calculate_total_extraction(self.city_b), FLOW_M3_S * 86400 * 0.25)

    def test_shares_of_a_watershed_add_up_to_its_extraction(self):
        self.add_well()
        total = calculate_total_extraction(self.city_a) + calculate_total_extraction(self.city_b)
        self.assertAlmostEqual(total, FLOW_M3_S * 86400)

    def test_neighborhood_gets_its_own_share(self):
        self.add_well()
        self.assertAlmostEqual(calculate_total_extraction(self.nbh_b), FLOW_M3_S * 86400 * 0.25)

    def test_source_watershed_wins_over_well_location(self):
        # the well lies outside the watershed polygon, its source still points to it
        far_source = make_source(geom=make_polygon(x=300000.0), watershed=self.watershed)
        make_well(geom=Point(300000.0, 470000.0, srid=RD), source=far_source, **WELL_VOLUME)
        self.assertAlmostEqual(calculate_total_extraction(self.city_a), FLOW_M3_S * 86400 * 0.75)

    def test_well_without_source_watershed_uses_the_watershed_it_lies_in(self):
        self.source.watershed = None
        self.source.save()
        self.add_well()
        self.assertAlmostEqual(calculate_total_extraction(self.city_a), FLOW_M3_S * 86400 * 0.75)

    def test_well_without_any_watershed_counts_where_it_lies(self):
        # save() would take the watershed back from the location; detach it directly
        AvailableFreshWater.objects.filter(pk=self.source.pk).update(watershed=None)
        self.watershed.delete()
        self.add_well(x=257000.0)  # inside city A
        self.assertAlmostEqual(calculate_total_extraction(self.city_a), FLOW_M3_S * 86400)
        self.assertEqual(calculate_total_extraction(self.city_b), 0)

    def test_inactive_wells_are_excluded(self):
        self.add_well(is_active=False)
        self.assertEqual(calculate_total_extraction(self.city_a), 0)

    def test_area_share_without_neighborhood_population(self):
        Neighborhood.objects.update(currentPopulation=0)
        # city A covers 1 km2 of the 16 km2 watershed
        self.assertAlmostEqual(watershed_share(self.city_a, self.watershed), 1 / 16)


class SupplySecurityFollowsTheWatershedTests(WatershedTestCase):
    def setUp(self):
        super().setUp()
        # the city's stored population (10 000) x 100 L/day = 1000 m3/day
        make_consumption_capita(city=self.city_a, year=2024, consumption_capita_L_d=100.0)
        TotalWaterDemand.objects.create(city=self.city_a, year=2024, demandDay=0)
        self.security = SupplySecurity.objects.create(
            city=self.city_a, year=2024, supply_security_pct=0, security_goal_pct=90, service_time_hours=0)

    def test_new_well_outside_the_city_refreshes_its_supply_security(self):
        self.add_well()
        self.security.refresh_from_db()
        self.assertAlmostEqual(self.security.supply_security_pct, 864 * 0.75 / DEMAND_M3_D * 100)

    def test_population_of_a_neighbour_city_changes_the_share(self):
        self.add_well()
        self.nbh_b.currentPopulation = 3000
        self.nbh_b.save()  # cascades to city B -> city_population_changed
        self.security.refresh_from_db()
        self.assertAlmostEqual(self.security.supply_security_pct, 864 * 0.5 / DEMAND_M3_D * 100)

    def test_neighbour_refreshes_are_deferred_and_run_once(self):
        self.add_well()
        with mock.patch.object(signals, '_resave', wraps=signals._resave) as resave:
            with signals.deferred_water_refresh():
                for population in (2000, 2500, 3000):
                    signals.city_population_cascaded(sender=None, city_id=self.city_b.pk)
                    Neighborhood.objects.filter(pk=self.nbh_b.pk).update(currentPopulation=population)
                self.assertEqual(resave.call_count, 0)
            security_resaves = [c for c in resave.call_args_list
                                if getattr(c.args[0], 'model', None) is SupplySecurity]
        self.assertEqual(len(security_resaves), 1)  # city A, once
        self.security.refresh_from_db()
        self.assertAlmostEqual(self.security.supply_security_pct, 864 * 0.5 / DEMAND_M3_D * 100)


class WellVolumeTests(WatershedTestCase):
    """ExtractionWater.volume_m3_d: measured yearly volume, else flow x hours, else flow x 24 h."""

    def extraction(self, **fields):
        self.add_well()
        ExtractionWater.objects.update(**fields)
        return calculate_total_extraction(self.city_a) / 0.75  # whole watershed

    def test_measured_yearly_extraction_wins(self):
        self.assertAlmostEqual(self.extraction(current_extraction_Mm3_yr=3.65), 10_000)

    def test_flow_times_operation_hours(self):
        self.assertAlmostEqual(self.extraction(OperationTime_h_day=12.0), FLOW_M3_S * 12 * 3600)

    def test_flow_all_day_without_hours(self):
        self.assertAlmostEqual(self.extraction(OperationTime_h_day=None), FLOW_M3_S * 86400)

    def test_well_without_any_volume_adds_nothing(self):
        self.assertEqual(self.extraction(pumpflow_m3_s=None), 0)
