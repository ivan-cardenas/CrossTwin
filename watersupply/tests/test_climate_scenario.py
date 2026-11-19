"""
Stored climate scenario runs (weather.ClimateScenarioRun) in the water module:
Climate_Change -> Meteorology -> Available_FW (ScenarioFreshWater) and the
scenario population's demand and supply security (ScenarioWaterSecurity).
Observed rows are never changed.
"""
from django.test import TestCase

from administrative.models import PopulationProjection
from physicalEnv.models import LandCoverClasses, LandCoverVector, SoilArea, SoilType
from watersupply.calculations import chain
from watersupply.models import AvailableFreshWater, ConsumptionCapita, ScenarioFreshWater, ScenarioWaterSecurity
from weather.calculations import climate
from weather.calculations.water_balance import yearly_water_balance
from weather.knmi import store_daily
from weather.models import ClimateScenarioRun

from .factories import make_city, make_polygon
from .test_infiltration_recharge import BBOX, SAND, X0, Y0, _box, knmi_csv


class ScenarioWaterTests(TestCase):
    def setUp(self):
        self.city = make_city(cityName="Rainville", currentPopulation=10000)
        sand = SoilType.objects.create(code="Zn21", name=SAND)
        SoilArea.objects.create(mapAreaID="a", soil_type=sand, geom=_box(X0, Y0, X0 + 1000, Y0 + 1000))
        pastures = LandCoverClasses.objects.create(class_name="pastures", description="test")
        LandCoverVector.objects.create(city=self.city, year=2024, land_cover_type=pastures, land_use="x",
                                       geom=_box(X0, Y0, X0 + 1000, Y0 + 1000), percentage=100)
        store_daily(knmi_csv(2024), BBOX)
        self.source = AvailableFreshWater.objects.create(SourceName="Src", geom=make_polygon())
        for year, population in ((2025, 10000), (2050, 12000)):
            PopulationProjection.objects.create(city=self.city, year=year, population=population, scenario="prognose")
        ConsumptionCapita.objects.create(city=self.city, year=2024, consumption_capita_L_d=120)

    def make_run(self, scenario="2050_Hd", **kwargs):
        return ClimateScenarioRun.objects.create(
            scenario=scenario, unit_level="city", unit_name="Rainville", parameters={"run_heat": False}, **kwargs)

    def test_run_stores_the_scenario_recharge_of_each_source(self):
        observed_depth = self.source.infiltrationDepth_cm
        run = self.make_run()
        fresh = ScenarioFreshWater.objects.get(run=run, source=self.source)
        met = yearly_water_balance(self.source.geom.point_on_surface)
        expected = chain.scenario_water_balance(met, [("A", "pastures", 1e6)], "2050_Hd")
        self.assertAlmostEqual(fresh.recharge_mm, round(expected["recharge_mm"], 1), places=1)
        self.assertAlmostEqual(fresh.baseline_recharge_mm, observed_depth * 10, places=0)
        self.assertNotEqual(fresh.recharge_mm, fresh.baseline_recharge_mm)
        self.assertEqual(fresh.met_year, 2024)
        # the observed source is untouched
        self.source.refresh_from_db()
        self.assertEqual(self.source.infiltrationDepth_cm, observed_depth)

    def test_dashboard_and_stored_scenario_recharge_agree(self):
        """The dashboard's recharge card and the stored run call the same chain function."""
        from watersupply.views import _recharge_indicators

        run = self.make_run()
        fresh = ScenarioFreshWater.objects.get(run=run)
        met = yearly_water_balance(self.source.geom.point_on_surface)
        card = _recharge_indicators({"water_balance": met, "composition": [("A", "pastures", 1e6)]}, 1e6, "2050_Hd")
        self.assertEqual(card["recharge_mm_yr"], round(fresh.recharge_mm))

    def test_security_uses_the_scenario_population_year(self):
        run = self.make_run()
        security = ScenarioWaterSecurity.objects.get(run=run)
        self.assertEqual(security.year, 2050)
        self.assertEqual(security.population, 12000)
        self.assertEqual(security.baseline_population, 10000)
        self.assertAlmostEqual(security.demand_m3_d, chain.demand_m3_d(120, 12000))
        self.assertAlmostEqual(security.yield_Mm3_year, ScenarioFreshWater.objects.get(run=run).yield_Mm3_year, places=3)

    def test_2100_is_a_trend_extrapolation(self):
        run = self.make_run("2100_Hd")
        self.assertTrue(run.population_extrapolated)
        self.assertTrue(ScenarioWaterSecurity.objects.get(run=run).population_extrapolated)

    def test_raw_save_does_nothing(self):
        from watersupply import signals

        run = self.make_run()
        ScenarioFreshWater.objects.all().delete()
        signals.climate_run_freshwater(ClimateScenarioRun, instance=run, raw=True)
        self.assertFalse(ScenarioFreshWater.objects.filter(run=run).exists())

    def test_delete_cascades(self):
        run = self.make_run()
        run.delete()
        self.assertFalse(ScenarioFreshWater.objects.exists())
        self.assertFalse(ScenarioWaterSecurity.objects.exists())
        self.assertTrue(AvailableFreshWater.objects.filter(pk=self.source.pk).exists())

    def test_run_derives_its_station_and_year(self):
        run = self.make_run("2100_Ln")
        self.assertEqual(run.population_year, 2100)
        self.assertEqual(run.city, self.city)
        self.assertIn(run.station, climate.STATIONS)
        self.assertEqual(run.method_version, climate.SCENARIO_RUN_VERSION)
