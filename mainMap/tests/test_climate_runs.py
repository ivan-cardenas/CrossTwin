"""
The Scenarios panel's stored climate scenario runs (mainMap/views_climate.py):
permissions, validation, the results partial and delete.
"""
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from administrative.models import PopulationProjection
from housing.models import HouseholdSize
from watersupply.tests.factories import make_city
from weather.models import ClimateScenarioRun


class ClimateRunViewTests(TestCase):
    def setUp(self):
        self.city = make_city(cityName="Runville", currentPopulation=10000)
        for year, population in ((2025, 10000), (2050, 12000)):
            PopulationProjection.objects.create(city=self.city, year=year, population=population, scenario="prognose")
        HouseholdSize.objects.create(city=self.city, year=2025, households=5000)
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.url = reverse("map:climate_runs")

    def post(self, **data):
        body = {"climate": "2050_Hd", "heat": "summer", "level": "city", "location": "Runville",
                "run_heat": "0", "datetime": "2025-07-15T14:00"}
        body.update(data)
        return self.client.post(self.url, body)

    def test_staff_only(self):
        self.assertEqual(self.post().status_code, 403)

    def test_validation(self):
        self.client.force_login(self.staff)
        self.assertContains(self.post(climate="current"), "future scenario", status_code=400)
        self.assertContains(self.post(location="Nowhere"), "Select a city", status_code=400)
        self.assertContains(self.post(heat="winter"), "winter", status_code=400)   # July is not winter
        self.assertContains(self.post(run_heat="1"), "map view", status_code=400)   # heat model needs the bbox
        self.assertFalse(ClimateScenarioRun.objects.exists())

    def test_create_stores_the_run_and_its_results(self):
        self.client.force_login(self.staff)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Trigger"], "climate-run-changed")
        run = ClimateScenarioRun.objects.get()
        self.assertEqual((run.scenario, run.heat_mode, run.population_year), ("2050_Hd", "summer", 2050))
        self.assertEqual(run.created_by, self.staff)
        self.assertContains(response, "Homes needed")
        self.assertContains(response, "LST")
        self.assertContains(response, "surface reflectance")
        self.assertEqual(run.heat.status, "skipped")

    def test_list_detail_recalculate_delete(self):
        self.client.force_login(self.staff)
        self.post()
        run = ClimateScenarioRun.objects.get()
        listing = self.client.get(self.url, {"level": "city", "location": "Runville"})
        self.assertContains(listing, f"Run {run.pk}")
        self.client.logout()
        self.assertEqual(self.client.get(reverse("map:climate_run_detail", args=[run.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse("map:climate_run_delete", args=[run.pk])).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse("map:climate_run_recalculate", args=[run.pk])).status_code, 200)
        run.refresh_from_db()
        self.assertIsNotNone(run.recalculated)
        response = self.client.post(reverse("map:climate_run_delete", args=[run.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("climate-run-deleted", response["HX-Trigger"])
        self.assertFalse(ClimateScenarioRun.objects.exists())

    def test_panel_shows_the_cta_to_staff_only(self):
        url = reverse("weather:climate_panel")
        params = {"climate": "2050_Hd", "level": "city", "location": "Runville"}
        self.assertNotContains(self.client.get(url, params), 'id="climate-run-btn"')
        self.assertContains(self.client.get(url, params), 'id="climate-effects-btn"')
        self.client.force_login(self.staff)
        response = self.client.get(url, params)
        self.assertContains(response, 'id="climate-run-btn"')
        self.assertContains(response, "location=Runville")


class RasterLabelTests(SimpleTestCase):
    def test_scenario_rasters_are_labelled(self):
        from types import SimpleNamespace

        from mainMap.styles.rasterStyles import climate_run_suffix

        self.assertEqual(climate_run_suffix(SimpleNamespace(climate_run_id=None)), "")
        self.assertEqual(climate_run_suffix(SimpleNamespace(climate_run_id=3, source="SOLWEIG DSM 1: KNMI23 2050_Hd")),
                         " · KNMI'23 run 3")
        self.assertEqual(climate_run_suffix(SimpleNamespace(climate_run_id=3, source="SOLWEIG DSM 1: KNMI 290")),
                         " · run 3 (current climate)")


class ThermalComfortToolScenarioTests(TestCase):
    """The Thermal Comfort tool follows the selected scenario (SolweigTool.js)."""

    BBOX = "6.8930,52.2200,6.8940,52.2206"

    def setUp(self):
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)

    def test_preview_moves_the_form_weather_into_the_scenario(self):
        from weather.calculations import climate

        response = self.client.get(reverse("urban_heat:solweig_scenario_met"), {
            "bbox": self.BBOX, "datetime": "2025-07-15T15:00", "climate": "2050_Hd", "heat": "summer",
            "ta_c": 25, "rh_pct": 50, "wind_ms": 2, "kdown_wm2": 700, "tmax_c": 27, "tmin_c": 14})
        data = response.json()
        delta = climate.DELTAS["2050_Hd"]["summer"]
        self.assertAlmostEqual(data["scenario"]["ta_c"], 25 + delta["tx_c"])
        self.assertAlmostEqual(data["delta"]["tmin_c"], delta["tn_c"])
        self.assertTrue(data["month_fits"])
        winter = self.client.get(reverse("urban_heat:solweig_scenario_met"), {
            "bbox": self.BBOX, "datetime": "2025-07-15T15:00", "climate": "2050_Hd", "heat": "winter",
            "ta_c": 25, "rh_pct": 50, "wind_ms": 2, "kdown_wm2": 700}).json()
        self.assertFalse(winter["month_fits"])

    def test_tool_stores_a_scenario_run_for_the_view_alone(self):
        from unittest import mock

        self.client.force_login(self.staff)
        with mock.patch("urban_heat.solweig.pipeline.solweig_available", return_value=False):
            response = self.client.post(reverse("map:climate_runs"), {
                "format": "json", "climate": "2100_Hd", "heat": "warmest", "bbox": self.BBOX,
                "datetime": "2025-07-15T15:00", "met_source": "manual", "met_label": "KNMI 290 Twenthe",
                "ta_c": 25, "rh_pct": 50, "wind_ms": 2, "wind_dir_deg": 240, "kdown_wm2": 700, "pressure_kpa": 101.3})
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data["heat_status"], "unavailable")
        self.assertIsNone(data["thermal_run"])
        run = ClimateScenarioRun.objects.get(pk=data["id"])
        self.assertEqual(run.unit_level, "")
        self.assertEqual(run.station, "Groningen")   # nearest key-figure station to the view (Enschede)
