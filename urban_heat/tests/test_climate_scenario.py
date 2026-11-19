"""
Stored climate scenario runs (weather.ClimateScenarioRun) in the heat module:
the WBGT equation, the one SOLWEIG run of a ScenarioHeat (current values from an
observed run of the same hour), and the guards that
keep scenario rasters and observed rasters apart (replace_covered, the
dashboard statistics). SOLWEIG itself is replaced by a stand-in.
"""
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, TestCase

from urban_heat.calculations.chain import globe_temperature_c, stull_wet_bulb_c, wbgt_outdoor_c


class WbgtEquationTests(SimpleTestCase):
    def test_stull_wet_bulb(self):
        # Stull (2011): 20 °C, 50 % -> 13.7 °C
        self.assertAlmostEqual(float(stull_wet_bulb_c(20, 50)), 13.7, places=1)

    def test_globe_equals_air_when_tmrt_does(self):
        import numpy as np

        self.assertAlmostEqual(float(globe_temperature_c(np.array([20.0]), 20.0, 2.0)[0]), 20.0, places=6)
        self.assertGreater(float(globe_temperature_c(np.array([50.0]), 20.0, 2.0)[0]), 20.0)

    def test_wbgt_pinned_values(self):
        import numpy as np

        wbgt = wbgt_outdoor_c(30.0, 50.0, 1.0, np.array([30.0, 50.0, 60.0]))
        np.testing.assert_allclose(wbgt, [24.608, 25.964, 26.731], atol=0.01)
        self.assertTrue(np.isnan(wbgt_outdoor_c(30.0, 50.0, 1.0, np.array([np.nan]))[0]))


def _fake_solweig(inputs, met, when_local):
    """Stand-in for SOLWEIG-GPU: Tmrt = Ta + 20, UTCI = Ta + 5 everywhere."""
    import numpy as np

    tmrt = np.full(inputs.shape, met.ta_c + 20.0, dtype="float32")
    return tmrt, np.full(inputs.shape, met.ta_c + 5.0, dtype="float32")


@mock.patch("core.rasterOperations.export_raster_to_cog")
@mock.patch("urban_heat.solweig.pipeline.run_solweig", side_effect=_fake_solweig)
@mock.patch("urban_heat.solweig.pipeline.device", return_value="cpu")
@mock.patch("urban_heat.solweig.pipeline.urban_pet",
            side_effect=lambda inputs, tmrt, met, when: (tmrt - 10.0, "test PET", tmrt * 0 + 1.0))
class ScenarioHeatTests(TestCase):
    BBOX = [6.8930, 52.2200, 6.8940, 52.2206]
    WHEN = datetime(2025, 7, 15, 15, tzinfo=ZoneInfo("Europe/Amsterdam"))
    MET = dict(ta_c=25.0, rh_pct=50.0, wind_ms=2.0, wind_dir_deg=240.0, kdown_wm2=700.0,
               pressure_kpa=101.3, source="KNMI 290 Twenthe",
               tmax_c=27.0, tmin_c=14.0, kdown_day_wm2=300.0, wind_day_ms=3.0)

    def setUp(self):
        import numpy as np

        from django.contrib.gis.geos import MultiPolygon

        from physicalEnv.calculations.svf import _storage_box, wgs84_to_storage
        from physicalEnv.tests.test_physicalenv import _stored_dsm
        from watersupply.tests.factories import make_city

        view = wgs84_to_storage(self.BBOX)
        _stored_dsm(np.full((300, 300), 5.0, dtype="float32"),
                    origin=(float(np.floor(view[0])) - 100, float(np.ceil(view[3])) + 100))
        self.area = _storage_box(view)
        self.city = make_city(cityName="Heatville", geom=MultiPolygon(self.area.buffer(500), srid=self.area.srid))

    def make_run(self, scenario="2050_Hd", heat="summer", area=None):
        from weather.models import ClimateScenarioRun

        return ClimateScenarioRun.objects.create(
            scenario=scenario, heat_mode=heat, unit_level="city", unit_name="Heatville",
            area=area or self.area, bbox_wgs84=self.BBOX, analysis_datetime=self.WHEN,
            parameters={"run_heat": True, "met_observed": dict(self.MET), "resolution": 2.0})

    def _observed_run(self, ta_c=25.0, when=None, bbox=None):
        from physicalEnv.calculations.svf import _storage_box, wgs84_to_storage
        from urban_heat.models import ThermalComfortRun
        from urban_heat.solweig import pipeline

        bbox = bbox or self.BBOX
        run = ThermalComfortRun.objects.create(
            area=_storage_box(wgs84_to_storage(bbox)), bbox_wgs84=bbox, date_time=when or self.WHEN,
            met={**self.MET, "ta_c": ta_c}, resolution=2.0)
        return pipeline.execute(run.pk)

    def _queued_runs(self, start_run):
        """Run the SOLWEIG runs start_run was asked to start, in order."""
        from urban_heat.solweig import pipeline

        for call in start_run.call_args_list:
            pipeline.execute(call.args[0].pk)

    def test_scenario_met_is_the_observed_hour_moved_into_the_scenario(self, *_):
        from urban_heat.models import ScenarioHeat
        from weather.calculations import climate

        with mock.patch("urban_heat.solweig.pipeline.solweig_available", return_value=False):
            run = self.make_run()
        heat = ScenarioHeat.objects.get(run=run)
        # minus the change already in the observed hour's year (2025)
        delta = climate.deltas("2050_Hd", "summer", run.analysis_datetime.year)
        self.assertLess(delta["tx_c"], climate.DELTAS["2050_Hd"]["summer"]["tx_c"])
        self.assertAlmostEqual(heat.met_scenario["ta_c"], round(25.0 + delta["tx_c"], 1))
        self.assertAlmostEqual(heat.met_scenario["tmin_c"], round(14.0 + delta["tn_c"], 1))
        self.assertTrue(heat.met_scenario["source"].startswith("KNMI23 2050_Hd summer"))
        self.assertEqual(heat.status, "unavailable")      # SOLWEIG missing: said so, nothing queued

    def test_one_run_and_the_observed_run_of_the_hour_as_baseline(self, *_):
        from urban_heat.models import ScenarioHeat, ThermalComfortRun, WetBulbGlobeTemperature

        observed = self._observed_run()
        with mock.patch("urban_heat.solweig.pipeline.solweig_available", return_value=True),                 mock.patch("urban_heat.solweig.pipeline.start_run") as start_run:
            run = self.make_run(area=observed.area)       # the same covered view
            self.assertEqual(start_run.call_count, 1)        # only the scenario weather
            self._queued_runs(start_run)
        heat = ScenarioHeat.objects.get(run=run)
        self.assertEqual(heat.status, "done", heat.message)
        self.assertEqual(heat.thermal_baseline_id, observed.pk)
        self.assertEqual(heat.tmrt_now, 45.0)
        self.assertGreater(heat.tmrt_scenario, heat.tmrt_now)
        self.assertIsNotNone(heat.wbgt_now)                  # from the observed run's Tmrt
        self.assertGreater(heat.wbgt_scenario, heat.wbgt_now)
        self.assertEqual(WetBulbGlobeTemperature.objects.filter(climate_run=run).count(), 1)
        self.assertEqual(ThermalComfortRun.objects.filter(climate_run=run).count(), 1)

    def test_without_an_observed_run_the_current_column_stays_empty(self, *_):
        from urban_heat.models import ScenarioHeat

        with mock.patch("urban_heat.solweig.pipeline.solweig_available", return_value=True),                 mock.patch("urban_heat.solweig.pipeline.start_run") as start_run:
            run = self.make_run()
            self._queued_runs(start_run)
        heat = ScenarioHeat.objects.get(run=run)
        self.assertEqual(heat.status, "done")
        self.assertIsNone(heat.thermal_baseline)
        self.assertIsNone(heat.tmrt_now)
        self.assertIsNotNone(heat.tmrt_scenario)

    def test_scenario_and_observed_rasters_never_replace_each_other(self, *_):
        from urban_heat.models import UTCI

        observed = self._observed_run()
        with mock.patch("urban_heat.solweig.pipeline.solweig_available", return_value=True), \
                mock.patch("urban_heat.solweig.pipeline.start_run") as start_run:
            run = self.make_run()
            self._queued_runs(start_run)
        self.assertTrue(UTCI.objects.filter(pk=observed.utci_id).exists())
        self.assertEqual(UTCI.objects.filter(climate_run=run).count(), 1)
        again = self._observed_run(ta_c=26.0)               # a new observed run of the same hour
        self.assertEqual(again.stats["replaced"]["utci"], [observed.utci_id])
        self.assertEqual(UTCI.objects.filter(climate_run=run).count(), 1)

    def test_dashboard_reads_only_observed_rasters(self, *_):
        from urban_heat.calculations.indicators import get_thermal_indices

        self._observed_run()
        with mock.patch("urban_heat.solweig.pipeline.solweig_available", return_value=True), \
                mock.patch("urban_heat.solweig.pipeline.start_run") as start_run:
            self.make_run("2100_Hd", "warmest")
            self._queued_runs(start_run)
        self.assertEqual(get_thermal_indices(self.city)["utci"]["mean"], 30.0)   # observed Ta 25 + 5

    def test_card_reads_tmrt_pet_and_utci_from_one_run(self, *_):
        """Tmrt, PET and UTCI describe the same hour: the latest run of equal extent."""
        from datetime import timedelta

        from urban_heat.calculations.indicators import get_thermal_indices

        self._observed_run(ta_c=25.0)
        later = self._observed_run(ta_c=30.0, when=self.WHEN + timedelta(hours=1))
        indices = get_thermal_indices(self.city)
        self.assertEqual(indices["run"]["id"], later.pk)
        self.assertEqual(indices["tmrt"]["mean"], 50.0)   # Ta + 20
        self.assertEqual(indices["pet"]["mean"], 40.0)    # Tmrt - 10
        self.assertEqual(indices["utci"]["mean"], 35.0)   # Ta + 5

    def test_larger_coverage_beats_a_newer_hour(self, *_):
        from datetime import timedelta

        from urban_heat.calculations.indicators import get_thermal_indices
        from watersupply.tests.factories import make_city
        from django.contrib.gis.geos import MultiPolygon

        full = self._observed_run(ta_c=25.0)
        city = make_city(cityName="Tightville", geom=MultiPolygon(full.area, srid=full.area.srid))
        small = self._observed_run(ta_c=30.0, when=self.WHEN + timedelta(hours=1),
                                   bbox=[6.8930, 52.2200, 6.8935, 52.2203])
        self.assertLess(small.area.area, full.area.area)
        indices = get_thermal_indices(city)
        self.assertEqual(indices["run"]["id"], full.pk)
        self.assertEqual(indices["run"]["coverage_pct"], 100)
        self.assertEqual(indices["utci"]["mean"], 30.0)
        self.assertEqual(indices["utci"]["coverage_pct"], 100)

    def test_no_run_reports_no_run(self, *_):
        from urban_heat.calculations.indicators import get_thermal_indices

        indices = get_thermal_indices(self.city)
        self.assertIsNone(indices["run"])
        self.assertIsNone(indices["utci"])

    def test_deleting_the_run_removes_its_rasters(self, *_):
        from urban_heat.models import UTCI, ThermalComfortRun

        observed = self._observed_run()
        with mock.patch("urban_heat.solweig.pipeline.solweig_available", return_value=True), \
                mock.patch("urban_heat.solweig.pipeline.start_run") as start_run:
            run = self.make_run()
            self._queued_runs(start_run)
        run.delete()
        self.assertEqual(list(UTCI.objects.values_list("pk", flat=True)), [observed.utci_id])
        self.assertEqual(ThermalComfortRun.objects.filter(climate_run__isnull=False).count(), 0)

    def test_input_changes_after_the_heat_model_ask_for_a_rerun(self, *_):
        from mainMap.views_climate import heat_inputs_changed
        from urban_heat import signals
        from urban_heat.models import ScenarioHeat

        with mock.patch("urban_heat.solweig.pipeline.solweig_available", return_value=True), \
                mock.patch("urban_heat.solweig.pipeline.start_run") as start_run:
            run = self.make_run()
            self._queued_runs(start_run)
        heat = ScenarioHeat.objects.get(run=run)
        self.assertEqual(heat_inputs_changed(heat), [])
        signals._last_mark.clear()
        signals.mark_heat_input_changed("land cover")
        self.assertEqual(heat_inputs_changed(heat), ["land cover"])


class ScenarioRasterLabelTests(TestCase):
    """A scenario raster's label names the scenario, not only the observed hour it was shifted from."""

    def test_labels(self):
        from urban_heat.models import MeanRadiantTemperature
        from weather.models import ClimateScenarioRun

        when = datetime(2025, 7, 15, 14, tzinfo=ZoneInfo("Europe/Amsterdam"))
        run = ClimateScenarioRun.objects.create(scenario="2070_Hd", heat_mode="warmest",
                                                unit_level="city", unit_name="Nowhere")
        self.assertIn("interpolated:", run.knmi_source)
        observed = MeanRadiantTemperature(date_time=when)
        scenario = MeanRadiantTemperature(date_time=when, climate_run=run)
        self.assertTrue(str(observed).startswith("MRT Measurement at 2025-07-15"))
        self.assertIn("climate 2070 High, dry (Hd, interpolated), warmest day of the year", str(scenario))
        self.assertIn(f"run {run.pk} · observed hour 2025-07-15", str(scenario))
