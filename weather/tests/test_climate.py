"""
KNMI'23 climate scenarios (weather/calculations/climate.py) and where they
enter: the Scenarios panel, the heat panel's weather sliders and the water
panel's rain event and recharge. All what-ifs: nothing is written.
"""
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from weather.calculations import climate


class Knmi23TableTests(SimpleTestCase):
    """Pins a few cells of KNMI'23 Table 1 (KNMI Publication 23-03, pp. 3-4)."""

    def test_pinned_cells(self):
        self.assertEqual(climate.DELTAS["2050_Hd"]["summer"]["tx_c"], 2.2)
        self.assertEqual(climate.DELTAS["2100_Hd"]["summer"]["precip_pct"], -29)
        self.assertEqual(climate.DELTAS["2100_Hn"]["winter"]["precip_pct"], 24)
        self.assertEqual(climate.DELTAS["2100_Hn"]["summer"]["rain_1d_10y_pct"], 26)
        self.assertEqual(climate.DELTAS["2100_Hd"]["year"]["et_pct"], 17)
        self.assertEqual(climate.DELTAS["2050_Ld"]["year"]["kdown_wm2"], 5.8)

    def test_low_scenarios_stabilise_after_2050(self):
        for pathway in ("Ld", "Ln"):
            self.assertEqual(climate.DELTAS[f"2050_{pathway}"], climate.DELTAS[f"2100_{pathway}"])

    def test_every_season_has_the_weather_changes(self):
        for key in climate.SCENARIOS[1:]:
            for season in climate.SEASONS:
                for name in ("t_c", "tx_c", "tn_c", "precip_pct", "kdown_wm2", "rh_pp", "wind_ms"):
                    self.assertIn(name, climate.DELTAS[key][season], (key, season, name))

    def test_klimaateffectatlas_presets(self):
        self.assertEqual(climate.KEA_PRESETS, ("current", "2050_Hd", "2100_Hd"))

    def test_unknown_keys_are_the_current_climate(self):
        for key in (None, "", "2075_Hd", "<script>"):
            self.assertEqual(climate.normalize(key), climate.CURRENT)
        self.assertFalse(climate.describe("nonsense")["active"])


class DeltaChangeTests(SimpleTestCase):
    WEATHER = {"ta_c": 30.0, "rh_pct": 50.0, "wind_ms": 2.0, "kdown_wm2": 800.0, "source": "Open-Meteo"}

    def test_current_climate_changes_nothing(self):
        self.assertEqual(climate.apply_to_weather(self.WEATHER, "current", 7), self.WEATHER)

    def test_summer_day_in_2100_high_dry(self):
        out = climate.apply_to_weather(self.WEATHER, "2100_Hd", 7)
        self.assertEqual(out["ta_c"], 35.4)                       # + summer daily max 5.4
        self.assertEqual(out["rh_pct"], 46.0)                     # - 4 percentage points
        self.assertEqual(out["wind_ms"], 1.8)                     # - 0.2 m/s
        self.assertEqual(out["kdown_wm2"], round(800 * 230 / 206, 1))  # (206 + 24) / 206
        self.assertEqual(out["source"], "Open-Meteo")

    def test_night_uses_the_daily_minimum(self):
        night = {**self.WEATHER, "kdown_wm2": 0.0}
        self.assertEqual(climate.apply_to_weather(night, "2100_Hd", 1)["ta_c"], 34.0)  # winter Tn + 4.0

    def test_limits_and_missing_values(self):
        out = climate.apply_to_weather({"ta_c": None, "rh_pct": 99.5, "wind_ms": 0.0, "kdown_wm2": None},
                                       "2100_Hn", 12)
        self.assertIsNone(out["ta_c"])
        self.assertEqual(out["rh_pct"], 100.0)
        self.assertEqual(out["wind_ms"], 0.2)
        self.assertIsNone(climate.apply_to_weather(None, "2050_Hd"))

    def test_design_rain(self):
        self.assertEqual(climate.design_rain_mm(25, "current"), 25)
        self.assertEqual(climate.design_rain_mm(25, "2100_Hn"), 31.5)  # + 26 %

    def test_daily_rain_by_season(self):
        rain = climate.apply_to_daily_rain([10.0, 10.0, 0.0], [1, 7, 7], "2100_Hd")
        self.assertAlmostEqual(rain[0], 11.4)   # winter + 14 %
        self.assertAlmostEqual(rain[1], 7.1)    # summer - 29 %
        self.assertEqual(rain[2], 0.0)
        # without months: the yearly change (-3 %)
        self.assertAlmostEqual(climate.apply_to_daily_rain([10.0], None, "2100_Hd")[0], 9.7)

    def test_evaporation(self):
        self.assertAlmostEqual(climate.apply_to_et(600.0, "2100_Hd"), 702.0)
        self.assertEqual(climate.apply_to_et(600.0, "current"), 600.0)

    def test_panel_table(self):
        rows = climate.scenario_table("2050_Hd")
        self.assertEqual([r["label"] for r in rows][:2], ["Temperature", "Daily maximum"])
        self.assertEqual(rows[0]["cells"], ["+1.6", "+1.2", "+1.3", "+2.1", "+1.8"])
        self.assertEqual(rows[1]["cells"][0], "—")   # no yearly daily maximum in Table 1
        self.assertEqual(climate.scenario_table("current"), [])


class HeatPanelClimateTests(SimpleTestCase):
    def test_sliders_start_at_the_scenario(self):
        from urban_heat.views import MOCK_DATA, _build_indicators
        weather = {"ta_c": 30.0, "rh_pct": 50, "wind_ms": 2.0, "kdown_wm2": 800.0,
                   "source": "Open-Meteo", "time": "2026-07-15T14:15"}
        data = {**MOCK_DATA, "weather": weather}
        current = _build_indicators(data)
        scenario = _build_indicators(data, climate_key="2050_Hd")
        self.assertEqual(current["air_temp_C"], 30.0)
        self.assertFalse(current["climate"]["active"])
        self.assertEqual(scenario["air_temp_C"], 32.2)
        self.assertEqual(scenario["weather_baseline"]["ta_c"], 32.2)   # Reset returns to the scenario
        self.assertFalse(scenario["weather_whatif"])
        self.assertEqual(scenario["climate_delta"]["ta_c"], 2.2)
        self.assertEqual(scenario["climate_season"], "summer")
        self.assertGreater(scenario["weather_stress"]["wbgt_estimate_c"],
                           current["weather_stress"]["wbgt_estimate_c"])
        # a moved slider still wins over the scenario
        self.assertEqual(_build_indicators(data, {"ta_c": 25.0}, "2050_Hd")["air_temp_C"], 25.0)


class WaterPanelClimateTests(SimpleTestCase):
    def test_rain_event_and_recharge(self):
        from watersupply.views import MOCK_DATA, _build_indicators
        current = _build_indicators(MOCK_DATA)
        dry = _build_indicators(MOCK_DATA, climate_key="2100_Hd")
        wet = _build_indicators(MOCK_DATA, climate_key="2100_Hn")
        self.assertEqual(current["rain_mm"], 25)
        self.assertEqual(dry["rain_mm"], 28.8)          # + 15 %
        self.assertEqual(wet["rain_mm"], 31.5)          # + 26 %
        self.assertLess(dry["recharge_mm_yr"], current["recharge_mm_yr"])
        self.assertGreater(wet["recharge_rain_mm_yr"], current["recharge_rain_mm_yr"])
        # the slider, once moved, is kept
        self.assertEqual(_build_indicators(MOCK_DATA, rain_mm=40, climate_key="2100_Hd")["rain_mm"], 40)


class ScenarioPanelViewTests(TestCase):
    def test_panel_lists_the_atlas_and_all_scenarios(self):
        response = self.client.get(reverse("weather:climate_panel"), HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-climate="current"')
        for label in ("Current", "2050 high", "2100 high", "High, dry", "Low, wet"):
            self.assertContains(response, label)

    def test_chosen_scenario_shows_its_changes(self):
        response = self.client.get(reverse("weather:climate_panel"), {"climate": "2100_Hd"})
        self.assertContains(response, 'data-climate="2100_Hd"')
        self.assertContains(response, "+4.4")       # yearly temperature
        self.assertContains(response, "+4.9 °C global warming")

    def test_heat_and_water_panels_take_the_scenario(self):
        heat = self.client.get(reverse("urban_heat:heat_indicators", args=["city", "Nowhere"]),
                               {"climate": "2050_Hd"}, HTTP_HX_REQUEST="true")
        self.assertContains(heat, 'name="climate" value="2050_Hd"')
        water = self.client.get(reverse("watersupply:recalculate_indicators", args=["city", "Nowhere", 2030]),
                                {"climate": "2100_Hn"})
        self.assertEqual(water.context["indicators"]["rain_mm"], 31.5)
