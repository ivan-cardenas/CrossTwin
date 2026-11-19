"""
Live weather (weather/live.py, the map's weather pill) and the heat panel's
weather what-if (urban_heat/calculations/chain.py, urban_heat/views.py).
"""
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from urban_heat.calculations import chain
from urban_heat.views import MOCK_DATA, _build_indicators, weather_overrides
from weather import live

OPEN_METEO = {
    "latitude": 52.22, "longitude": 6.9, "timezone": "Europe/Amsterdam",
    "current": {
        "time": "2026-07-15T14:15", "temperature_2m": 30.0, "relative_humidity_2m": 50,
        "wind_speed_10m": 2.0, "wind_direction_10m": 220, "shortwave_radiation": 800.0,
        "precipitation": 0.0, "weather_code": 1, "is_day": 1,
    },
}
LIVE = live.parse_current(OPEN_METEO)


class HeatStressEquationTests(SimpleTestCase):
    def test_vapour_pressure(self):
        self.assertAlmostEqual(chain.vapour_pressure_hpa(30, 50), 21.14, places=1)

    def test_bom_wbgt(self):
        # 0.567 x 30 + 0.393 x 21.14 + 3.94
        self.assertAlmostEqual(chain.wbgt_estimate_c(30, 50), 29.26, places=1)

    def test_apparent_temperature_shade_and_sun(self):
        stress = chain.weather_heat_stress(30, 50, 0, 800)
        self.assertAlmostEqual(stress["apparent_shade_c"], 33.1, places=1)
        # sun: + 0.7 x (0.7 x 0.25 x 800) / 10
        self.assertAlmostEqual(stress["apparent_sun_c"], round(33.11 + 0.7 * 140 / 10, 1), places=1)

    def test_wind_cools_and_missing_humidity_gives_none(self):
        calm = chain.apparent_temperature_c(30, 50, 0)
        windy = chain.apparent_temperature_c(30, 50, 5)
        self.assertLess(windy, calm)
        self.assertIsNone(chain.weather_heat_stress(30, None, 2, 0))


class WeatherWhatIfTests(SimpleTestCase):
    def data(self, weather=LIVE):
        return {**MOCK_DATA, "weather": weather}

    def test_default_controls_equal_the_baseline(self):
        indicators = _build_indicators(self.data())
        self.assertFalse(indicators["weather_whatif"])
        self.assertEqual(indicators["air_temp_C"], 30.0)
        self.assertEqual(indicators["weather_source"], "Open-Meteo")
        self.assertEqual(indicators["weather_stress"], chain.weather_heat_stress(30.0, 50, 2.0, 800.0))

    def test_override_is_a_what_if(self):
        indicators = _build_indicators(self.data(), {"ta_c": 35.0})
        self.assertTrue(indicators["weather_whatif"])
        self.assertEqual(indicators["air_temp_C"], 35.0)
        self.assertEqual(indicators["weather_baseline"]["ta_c"], 30.0)
        self.assertGreater(indicators["weather_stress"]["wbgt_estimate_c"],
                           _build_indicators(self.data())["weather_stress"]["wbgt_estimate_c"])

    def test_override_equal_to_the_baseline_is_not_a_what_if(self):
        self.assertFalse(_build_indicators(self.data(), {"ta_c": 30.0})["weather_whatif"])

    def test_without_live_weather_the_station_reading_is_used(self):
        indicators = _build_indicators(self.data(weather=None))
        self.assertEqual(indicators["weather_source"], "Weather station")
        self.assertEqual(indicators["air_temp_C"], MOCK_DATA["meteorology"]["temperature_C"])

    def test_overrides_are_clamped_and_bad_values_ignored(self):
        self.assertEqual(weather_overrides({"ta_c": "99", "rh_pct": "abc", "wind_ms": "", "kdown_wm2": "-5"}),
                         {"ta_c": 45.0, "kdown_wm2": 0.0})


class LiveWeatherParseTests(SimpleTestCase):
    def test_parse(self):
        self.assertEqual(LIVE["ta_c"], 30.0)
        self.assertEqual(LIVE["kdown_wm2"], 800.0)
        self.assertEqual(LIVE["description"], "Mainly clear")
        self.assertEqual(LIVE["icon"], "🌤️")

    def test_night_icon_and_unknown_code(self):
        self.assertEqual(live.describe(0, is_day=False), ("Clear sky", "🌙"))
        self.assertEqual(live.describe(1234)[0], "Unknown")

    def test_answer_without_current_values_is_an_error(self):
        with self.assertRaises(live.LiveWeatherError):
            live.parse_current({"current": {}})


def _response(payload, status=200):
    response = mock.Mock(status_code=status)
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@override_settings(LIVE_WEATHER=True)
class LiveWeatherEndpointTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_endpoint_returns_current_weather_and_caches_per_cell(self):
        with mock.patch("requests.get", return_value=_response(OPEN_METEO)) as get:
            first = self.client.get(reverse("weather:live_weather"), {"lat": "52.2201", "lng": "6.8952"})
            second = self.client.get(reverse("weather:live_weather"), {"lat": "52.2210", "lng": "6.8960"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["ta_c"], 30.0)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(get.call_count, 1)    # same ~2 km cell
        self.assertEqual(get.call_args.kwargs["params"]["wind_speed_unit"], "ms")

    def test_bad_parameters(self):
        self.assertEqual(self.client.get(reverse("weather:live_weather"), {"lat": "x"}).status_code, 400)
        self.assertEqual(self.client.get(reverse("weather:live_weather"),
                                         {"lat": "95", "lng": "6"}).status_code, 400)

    def test_upstream_failure_is_a_502(self):
        import requests
        with mock.patch("requests.get", side_effect=requests.ConnectionError("down")):
            response = self.client.get(reverse("weather:live_weather"), {"lat": "52.2", "lng": "6.9"})
        self.assertEqual(response.status_code, 502)

    @override_settings(LIVE_WEATHER=False)
    def test_turned_off(self):
        with mock.patch("requests.get") as get:
            response = self.client.get(reverse("weather:live_weather"), {"lat": "52.2", "lng": "6.9"})
        self.assertEqual(response.status_code, 503)
        get.assert_not_called()


class HeatPanelWeatherTests(TestCase):
    """The heat panel and its recalculation with the weather sliders (mock unit: no DB data)."""

    def test_panel_renders_the_weather_sliders(self):
        response = self.client.get(reverse("urban_heat:heat_indicators", args=["city", "Nowhere"]),
                                   HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="ta_c"')
        self.assertContains(response, 'id="heat-weather-state"')
        self.assertContains(response, "Current Weather")

    def test_recalculation_applies_the_what_if(self):
        response = self.client.get(reverse("urban_heat:recalculate_indicators", args=["city", "Nowhere"]),
                                   {"ta_c": "38", "rh_pct": "40"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weather what-if")
        self.assertContains(response, 'data-whatif="1"')
        self.assertContains(response, 'data-ta_c="38.0"')


class StationFallbackSkipsDailyRowsTests(TestCase):
    """
    The heat panel's station fallback reads hourly readings only: a KNMI daily
    row (24 h means, stamped at noon UTC) must not pass for a noon reading.
    """

    def setUp(self):
        from datetime import datetime, timezone

        from django.contrib.gis.geos import Point
        from watersupply.tests.factories import make_city
        from weather.models import Meteorology, WeatherStation

        self.city = make_city(cityName="Heatville")
        station = WeatherStation.objects.create(
            name="Inside", geom=Point(257000, 470000, srid=28992), elevation_m=30)
        Meteorology.objects.create(          # hourly reading, a day older
            station=station, date=datetime(2024, 7, 14, 13, tzinfo=timezone.utc),
            temperature_C=31.0, solar_radiation_W_m2=820.0, humidity_percent=40, wind_speed_m_s=2.0)
        Meteorology.objects.create(          # the daily row of the next day (newer)
            station=station, date=datetime(2024, 7, 15, 12, tzinfo=timezone.utc),
            period=Meteorology.PERIOD_DAY,
            temperature_C=22.0, solar_radiation_W_m2=290.0, humidity_percent=65, wind_speed_m_s=3.0)

    def test_latest_meteorology_is_the_hourly_reading(self):
        from urban_heat.calculations.indicators import get_latest_meteorology

        meteo = get_latest_meteorology(self.city)
        self.assertEqual((meteo['temperature_C'], meteo['solar_radiation_W_m2']), (31.0, 820.0))

    def test_only_daily_rows_give_no_station_baseline(self):
        from urban_heat.calculations.indicators import get_latest_meteorology
        from weather.models import Meteorology

        Meteorology.objects.filter(period=Meteorology.PERIOD_HOUR).delete()
        self.assertIsNone(get_latest_meteorology(self.city))
