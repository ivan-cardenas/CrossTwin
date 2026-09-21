import json

from django.test import SimpleTestCase, TestCase

from administrative.models import PopulationProjection
from watersupply.tests.factories import make_city

from .charts import (
    band_d, build_population_chart, build_population_stats, monotone_segments, nice_step,
    path_d, short_number,
)


class HelperTests(SimpleTestCase):
    def test_short_number(self):
        self.assertEqual(short_number(164800), '164.8k')
        self.assertEqual(short_number(160000), '160k')
        self.assertEqual(short_number(2_100_000), '2.1M')
        self.assertEqual(short_number(950), '950')

    def test_nice_step_gives_round_grid_values(self):
        self.assertEqual(nice_step(7500), 10000)
        self.assertEqual(nice_step(23456), 25000)
        self.assertEqual(nice_step(1200), 2000)
        self.assertEqual(nice_step(0), 1)


class SplineTests(SimpleTestCase):
    def test_curve_passes_through_every_point(self):
        points = [(0, 100), (10, 80), (20, 50), (30, 45), (40, 44)]
        ends = [seg[3] for seg in monotone_segments(points)]
        self.assertEqual(ends, points[1:])
        self.assertEqual(monotone_segments(points)[0][0], points[0])

    def test_monotone_data_gives_a_curve_that_never_overshoots(self):
        # a steep step followed by a plateau is where an ordinary cubic spline overshoots
        points = [(0, 100), (10, 20), (20, 19), (30, 19)]
        for p0, c1, c2, p3 in monotone_segments(points):
            lo, hi = min(p0[1], p3[1]), max(p0[1], p3[1])
            self.assertTrue(lo <= c1[1] <= hi and lo <= c2[1] <= hi, (p0, c1, c2, p3))

    def test_flat_segments_stay_flat(self):
        for p0, c1, c2, p3 in monotone_segments([(0, 5), (10, 5), (20, 5)]):
            self.assertEqual((c1[1], c2[1]), (5, 5))

    def test_path_data_and_degenerate_input(self):
        self.assertTrue(path_d([(0, 0), (10, 10)]).startswith('M0.0,0.0 C'))
        self.assertEqual(path_d([(3, 4)]), 'M3.0,4.0')
        self.assertEqual(path_d([]), '')

    def test_band_is_a_closed_shape_between_the_two_curves(self):
        d = band_d([(0, 0), (10, -5)], [(0, 10), (10, 8)])
        self.assertTrue(d.startswith('M0.0,0.0') and d.endswith('Z'))
        self.assertIn('L10.0,8.0', d)            # jumps from the end of the upper curve to the lower one
        self.assertTrue(d.rstrip(' Z').endswith('0.0,10.0'))   # and returns along it to the start


class ChartTests(TestCase):
    def setUp(self):
        self.city = make_city(cityName="Testville", currentPopulation=164800)
        for year in range(2023, 2051):
            median = 160000 + (year - 2023) * 900
            for scenario, factor in (('prognose', 1.0), ('low', 0.97), ('high', 1.03)):
                PopulationProjection.objects.create(
                    city=self.city, year=year, scenario=scenario, population=round(median * factor))

    def chart(self, scenario='prognose', growth=0, year=2030):
        return build_population_chart(self.city, scenario, growth, year, self.city.currentPopulation)

    def test_no_projection_data_gives_no_chart(self):
        PopulationProjection.objects.all().delete()
        self.assertIsNone(self.chart())

    def test_grid_ticks_are_round_and_inside_the_plot(self):
        chart = self.chart()
        for g in chart['grid_h']:
            self.assertTrue(chart['y0'] - 1 <= g['y'] <= chart['y1'] + 1)
        self.assertGreaterEqual(len(chart['grid_h']), 4)
        self.assertEqual([g['label'] for g in chart['grid_v']], ['2025', '2030', '2035', '2040', '2045', '2050'])

    def test_every_variant_and_the_current_value_fit_in_the_plot(self):
        chart = self.chart()
        for p in json.loads(chart['points_json']):
            for key in ('y_low', 'y_median', 'y_high'):
                self.assertTrue(chart['y0'] <= p[key] <= chart['y1'], (p['year'], key, p[key]))
        self.assertTrue(chart['y0'] <= chart['baseline']['y'] <= chart['y1'])

    def test_the_band_lies_between_the_low_and_high_lines(self):
        for p in json.loads(self.chart()['points_json']):
            self.assertLessEqual(p['y_high'], p['y_median'])   # SVG y grows downwards
            self.assertLessEqual(p['y_median'], p['y_low'])
            self.assertLess(p['low'], p['median'])
            self.assertLess(p['median'], p['high'])

    def test_points_cover_every_year_left_to_right(self):
        points = json.loads(self.chart()['points_json'])
        self.assertEqual([p['year'] for p in points], list(range(2023, 2051)))
        xs = [p['x'] for p in points]
        self.assertEqual(xs, sorted(xs))

    def test_handles_every_five_years_plus_ends_and_the_selected_year(self):
        handles = self.chart(year=2033)['handles']
        self.assertEqual([h['year'] for h in handles], [2023, 2028, 2033, 2038, 2043, 2048, 2050])
        self.assertEqual([h['year'] for h in handles if h['active']], [2033])

    def test_marker_only_for_a_year_in_the_data(self):
        self.assertEqual(self.chart(year=2030)['marker']['year'], 2030)
        self.assertIsNone(self.chart(year=2060)['marker'])
        self.assertIsNone(self.chart(year=None)['marker'])

    def test_growth_adjustment_moves_the_band_with_the_curve(self):
        base = {p['year']: p for p in json.loads(self.chart()['points_json'])}
        grown = {p['year']: p for p in json.loads(self.chart(growth=2)['points_json'])}
        self.assertEqual(grown[2025]['median'], base[2025]['median'])          # nothing up to 2025
        self.assertGreater(grown[2040]['median'], base[2040]['median'])
        self.assertGreater(grown[2040]['high'], base[2040]['high'])
        self.assertGreater(grown[2040]['low'], base[2040]['low'])

    def test_selected_variant_is_labelled(self):
        self.assertEqual(self.chart('low')['variant_label'], 'Lower bound')
        self.assertEqual(self.chart('nonsense')['variant_label'], 'Median forecast')


class StatsTests(TestCase):
    def setUp(self):
        self.city = make_city(cityName="Testville", currentPopulation=10000)
        for scenario, population in (('prognose', 12000), ('low', 11000), ('high', 13000)):
            PopulationProjection.objects.create(city=self.city, year=2030, scenario=scenario, population=population)

    def test_values_delta_and_interval(self):
        stats = build_population_stats(self.city, 'prognose', 0, 2030, 10000)
        self.assertEqual((stats['current'], stats['projected'], stats['low'], stats['high']), (10000, 12000, 11000, 13000))
        self.assertEqual((stats['delta'], stats['delta_pct']), (2000, 20.0))
        self.assertTrue(stats['has_projection'])

    def test_a_year_without_data_is_not_presented_as_a_projection(self):
        stats = build_population_stats(self.city, 'prognose', 0, 2040, 10000)
        self.assertFalse(stats['has_projection'])
        self.assertNotIn('projected', stats)

    def test_no_year(self):
        self.assertFalse(build_population_stats(self.city, 'prognose', 0, None, 10000)['has_projection'])
