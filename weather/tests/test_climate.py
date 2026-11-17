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


class HeatWaveDayTests(SimpleTestCase):
    """Warmest day of the year per station (KNMI'23 data portal key figures)."""

    WEATHER = {"ta_c": 30.0, "rh_pct": 50.0, "wind_ms": 2.0, "kdown_wm2": 800.0}

    def test_pinned_station_cells(self):
        self.assertEqual(climate.STATION_EXTREMES["De Bilt"]["warmest_day_c"]["reference"], 25.5)
        self.assertEqual(climate.STATION_EXTREMES["De Bilt"]["warmest_day_c"]["2100_Hd"], 6.9)
        self.assertEqual(climate.STATION_EXTREMES["Maastricht"]["warmest_day_c"]["2100_Hd"], 7.4)
        self.assertEqual(climate.STATION_EXTREMES["Den Helder"]["warmest_day_c"]["2050_Hd"], 1.8)
        self.assertEqual(climate.STATION_EXTREMES["Vlissingen"]["tropical_nights"]["2100_Hd"], 41)
        self.assertEqual(climate.STATION_EXTREMES["De Bilt"]["days_tx35"]["2100_Hn"], 4.1)

    def test_warmest_day_warms_more_than_the_average_summer_maximum(self):
        for key in climate.SCENARIOS[1:]:
            self.assertGreater(climate.warmest_day_change(key, "De Bilt"),
                               climate.DELTAS[key]["summer"]["tx_c"], key)

    def test_nearest_station(self):
        self.assertEqual(climate.nearest_station(52.22, 6.89), "Groningen")    # Enschede
        self.assertEqual(climate.nearest_station(52.09, 5.12), "De Bilt")      # Utrecht
        self.assertEqual(climate.nearest_station(50.85, 5.69), "Maastricht")
        self.assertEqual(climate.nearest_station(51.50, 3.61), "Vlissingen")
        self.assertEqual(climate.nearest_station(), "De Bilt")

    def test_heat_wave_day(self):
        out = climate.apply_to_weather(self.WEATHER, "2100_Hd", 1, climate.HEAT_WARMEST, "De Bilt")
        self.assertEqual(out["ta_c"], 36.9)       # + warmest day 6.9, whatever the month
        self.assertEqual(out["rh_pct"], 46.0)     # summer change
        night = climate.apply_to_weather({**self.WEATHER, "kdown_wm2": 0.0}, "2100_Hd", 7,
                                         climate.HEAT_WARMEST, "Maastricht")
        self.assertEqual(night["ta_c"], 37.4)     # same change at night
        self.assertEqual(climate.apply_to_weather(self.WEATHER, "current", 7, climate.HEAT_WARMEST),
                         self.WEATHER)

    def test_unknown_heat_mode_is_average(self):
        self.assertEqual(climate.normalize_heat("<x>"), climate.HEAT_AVERAGE)
        self.assertEqual(climate.apply_to_weather(self.WEATHER, "2100_Hd", 7, "<x>")["ta_c"], 35.4)

    def test_station_table(self):
        rows = climate.station_table("2050_Hd", "Maastricht")
        self.assertEqual(rows[0]["station"], "Maastricht")
        self.assertTrue(rows[0]["nearest"])
        self.assertEqual(rows[0]["cells"][0]["future"], 29.9)   # 26.9 + 3.0
        self.assertEqual(climate.station_table("current"), [])

    def test_heat_panel(self):
        from urban_heat.views import MOCK_DATA, _build_indicators
        weather = {"ta_c": 30.0, "rh_pct": 50, "wind_ms": 2.0, "kdown_wm2": 800.0,
                   "source": "Open-Meteo", "time": "2026-07-15T14:15"}
        data = {**MOCK_DATA, "weather": weather, "point": (50.85, 5.69)}
        average = _build_indicators(data, climate_key="2100_Hd")
        warmest = _build_indicators(data, climate_key="2100_Hd", climate_heat="warmest")
        self.assertEqual(average["air_temp_C"], 35.4)
        self.assertEqual(warmest["air_temp_C"], 37.4)
        self.assertEqual(warmest["climate_station"], "Maastricht")
        self.assertEqual(warmest["climate_heat"], "warmest")
        self.assertGreater(warmest["weather_stress"]["wbgt_estimate_c"],
                           average["weather_stress"]["wbgt_estimate_c"])


class HeatWavePanelViewTests(TestCase):
    def test_scenarios_panel_heat_modes_and_stations(self):
        response = self.client.get(reverse("weather:climate_panel"),
                                   {"climate": "2100_Hd", "heat": "warmest", "lat": "50.85", "lng": "5.69"})
        self.assertContains(response, 'data-climate-heat="warmest"')
        self.assertContains(response, "Warmest day of the year")
        self.assertContains(response, "+7.4 °C")
        self.assertContains(response, "heat=average&amp;lat=50.8500&amp;lng=5.6900")

    def test_heat_panel_takes_the_mode(self):
        heat = self.client.get(reverse("urban_heat:heat_indicators", args=["city", "Nowhere"]),
                               {"climate": "2050_Hd", "climate_heat": "warmest"}, HTTP_HX_REQUEST="true")
        self.assertContains(heat, 'name="climate_heat" value="warmest"')


class ScenarioPopulationYearTests(TestCase):
    """A scenario sets the population year: current 2025, else its horizon."""

    def test_population_year_per_scenario(self):
        self.assertEqual(climate.population_year("current"), 2025)
        self.assertEqual(climate.population_year("2050_Hd"), 2050)
        self.assertEqual(climate.population_year("2100_Ln"), 2100)
        self.assertEqual(climate.population_year("bogus"), 2025)

    def test_current_year_matches_the_year_selector_baseline(self):
        from administrative.calculations.population import REFERENCE_YEAR
        self.assertEqual(climate.CURRENT_POPULATION_YEAR, REFERENCE_YEAR)

    def test_panel_carries_the_year_and_the_effects_button(self):
        response = self.client.get(reverse("weather:climate_panel"), {"climate": "2100_Hd"})
        self.assertContains(response, 'data-climate-year="2100"')
        self.assertContains(response, 'id="climate-effects-btn"')
        self.assertNotContains(response, "Applied in the panels")


class ClimateEffectsTests(TestCase):
    """mainMap/views.py::climate_effects: current (2025) vs scenario (horizon year)."""

    def test_rows_are_the_change_future_minus_now(self):
        from mainMap.views import climate_effect_rows
        rows = climate_effect_rows({"ta_c": 20.0, "population": 1000}, {"ta_c": 22.34, "population": 1100})
        by_label = {r["label"]: r for r in rows}
        self.assertEqual(by_label["Air temperature"]["change"], 2.3)
        self.assertEqual(by_label["Population"]["change"], 100)
        self.assertNotIn("WBGT (estimate)", by_label)   # missing on both sides

    def test_view_renders_heat_and_water(self):
        response = self.client.get(reverse("map:climate_effects"),
                                   {"climate": "2050_Hd", "level": "city", "location": "Nowhere"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Urban heat")
        self.assertContains(response, "Water supply")
        self.assertEqual(response.context["future_year"], 2050)
        rain = next(r for r in response.context["rows"] if r["label"] == "Design rain event")
        self.assertGreater(rain["future"], rain["now"])


class SeasonModeTests(TestCase):
    """Heat modes: the observed season, a chosen season, or the heat-wave day."""

    def test_season_for(self):
        self.assertEqual(climate.season_for("average", 7), "summer")
        self.assertEqual(climate.season_for("average", 1), "winter")
        self.assertEqual(climate.season_for("winter", 7), "winter")
        self.assertEqual(climate.season_for("warmest", 1), "summer")
        self.assertEqual(climate.season_for("bogus", 4), "spring")

    def test_chosen_season_overrides_the_observation_month(self):
        july_day = {"ta_c": 20.0, "rh_pct": 70.0, "wind_ms": 3.0, "kdown_wm2": 500.0}
        out = climate.apply_to_weather(july_day, "2050_Hd", 7, "winter")
        self.assertAlmostEqual(out["ta_c"], 20.0 + climate.DELTAS["2050_Hd"]["winter"]["tx_c"])

    def test_day_values_shift_like_the_hour(self):
        day = {"tmax_c": 25.0, "tmin_c": 12.0, "kdown_day_wm2": 300.0, "wind_day_ms": 3.0, "other": 1}
        out = climate.apply_to_day_values(day, "2050_Hd", "summer")
        d = climate.DELTAS["2050_Hd"]["summer"]
        self.assertAlmostEqual(out["tmax_c"], round(25.0 + d["tx_c"], 1))
        self.assertAlmostEqual(out["tmin_c"], round(12.0 + d["tn_c"], 1))
        self.assertEqual(out["other"], 1)
        hot = climate.apply_to_day_values(day, "2100_Hd", "warmest", station="De Bilt")
        self.assertAlmostEqual(hot["tmax_c"], 25.0 + 6.9)
        self.assertEqual(climate.apply_to_day_values(day, "current"), day)

    def test_panel_shows_six_modes_and_the_season(self):
        response = self.client.get(reverse("weather:climate_panel"), {"climate": "2050_Hd", "heat": "autumn"})
        for label in climate.HEAT_MODES.values():
            self.assertContains(response, label)
        self.assertContains(response, 'data-climate-heat="autumn"')
        self.assertContains(response, "Autumn change")


class ChangeToneTests(TestCase):
    """Colours of the Scenarios panel: Table 1 tones and the effects' worse/better."""

    def test_table_tone_follows_sign_and_size(self):
        self.assertEqual(climate.change_tone("tx_c", 0.4), "heat-1")
        self.assertEqual(climate.change_tone("tx_c", 5.0), "heat-3")
        self.assertEqual(climate.change_tone("precip_pct", -20), "dry-3")
        self.assertEqual(climate.change_tone("et_pct", 4), "dry-1")    # more evaporation dries
        self.assertEqual(climate.change_tone("wind_ms", 0.3), "")      # no tone
        self.assertEqual(climate.change_tone("t_c", None), "")
        row = climate.scenario_table("2100_Hd")[0]
        self.assertEqual(len(row["tones"]), len(row["cells"]))

    def test_effects_tone_is_the_consequence(self):
        from mainMap.views import change_tone
        self.assertEqual(change_tone("Air temperature", 20.0, 1.0), "worse")
        self.assertEqual(change_tone("Air temperature", 20.0, 3.0), "worse strong")
        self.assertEqual(change_tone("Supply security", 110.0, -2.0), "worse")
        self.assertEqual(change_tone("Groundwater recharge", 200.0, 30.0), "better strong")
        self.assertEqual(change_tone("Population", 1000, 100), "")
        self.assertEqual(change_tone("Air temperature", 20.0, 0), "")
