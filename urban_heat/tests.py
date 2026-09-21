from django.test import SimpleTestCase, TestCase

from .calculations import WBGT_BANDS, classify_wbgt, get_thermal_indices, wbgt_color
from .views import MOCK_DATA, _build_indicators


class ClassifyWbgtTests(SimpleTestCase):
    def test_none_has_no_category_or_color(self):
        self.assertIsNone(classify_wbgt(None))
        self.assertIsNone(wbgt_color(None))

    def test_band_edges_belong_to_the_hotter_band(self):
        # Upper bounds are exclusive: exactly 25 is already 'Moderate'.
        self.assertEqual(classify_wbgt(24.9), 'No Heat Stress')
        self.assertEqual(classify_wbgt(25), 'Moderate Heat Stress')
        self.assertEqual(classify_wbgt(28), 'Strong Heat Stress')
        self.assertEqual(classify_wbgt(30), 'Very Strong Heat Stress')
        self.assertEqual(classify_wbgt(33), 'Extreme Heat Stress')

    def test_extremes_are_covered(self):
        self.assertEqual(classify_wbgt(-10), 'No Heat Stress')
        self.assertEqual(classify_wbgt(60), 'Extreme Heat Stress')

    def test_color_follows_the_category(self):
        for upper, label, color in WBGT_BANDS:
            probe = upper - 0.01 if upper != float('inf') else 100
            self.assertEqual(classify_wbgt(probe), label)
            self.assertEqual(wbgt_color(probe), color)


class WbgtIndicatorTests(SimpleTestCase):
    def test_indicators_expose_wbgt_from_the_mock_data(self):
        indicators = _build_indicators(MOCK_DATA)
        self.assertEqual(indicators['wbgt_mean'], 23.4)
        self.assertEqual(indicators['wbgt_category'], 'No Heat Stress')
        self.assertEqual(indicators['wbgt_color'], '#22c55e')
        # 23.4 of a 35 degree gauge
        self.assertAlmostEqual(indicators['wbgt_pct'], 66.9, places=1)

    def test_gauge_is_capped_at_100_percent(self):
        data = {**MOCK_DATA, 'thermal': {**MOCK_DATA['thermal'], 'wbgt': {**MOCK_DATA['thermal']['wbgt'], 'mean': 50}}}
        self.assertEqual(_build_indicators(data)['wbgt_pct'], 100)

    def test_no_wbgt_raster_leaves_the_indicator_empty(self):
        data = {**MOCK_DATA, 'thermal': {k: v for k, v in MOCK_DATA['thermal'].items() if k != 'wbgt'}}
        indicators = _build_indicators(data)
        self.assertIsNone(indicators['wbgt_mean'])
        self.assertIsNone(indicators['wbgt_category'])
        self.assertEqual(indicators['wbgt_pct'], 0)


class WbgtRasterStatsTests(TestCase):
    """The stats query reads the newest WBGT raster inside the unit, like the other indices."""

    def test_thermal_indices_report_none_without_a_wbgt_raster(self):
        from watersupply.tests.factories import make_city
        indices = get_thermal_indices(make_city())
        self.assertIn('wbgt', indices)
        self.assertIsNone(indices['wbgt'])
