"""Price history chart of the House Price Index card: geometry, data and the rendered panel."""
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from watersupply.tests.factories import make_city, make_neighborhood

from housing.calculations import charts
from housing.calculations.indicators import calculate_price_history, price_chart
from housing.models import HousePriceIndex, WOZValue


class ChartGeometryTests(SimpleTestCase):
    def test_nice_step_is_one_two_or_five_times_a_power_of_ten(self):
        self.assertEqual(charts.nice_step(1000), 500)
        self.assertEqual(charts.nice_step(120), 50)
        self.assertEqual(charts.nice_step(8), 2)

    def test_no_points_gives_no_chart(self):
        self.assertIsNone(charts.line_chart([]))
        self.assertIsNone(charts.line_chart([{"key": "a", "label": "A", "points": []}]))

    def test_points_land_inside_the_plot_and_rise_with_the_value(self):
        chart = charts.line_chart([{"key": "a", "label": "A", "points": [(2021, 4000.0), (2022, 4400.0), (2024, 5000.0)]}])
        dots = chart["series"][0]["dots"]
        self.assertEqual([d["x"] for d in dots], [2021, 2022, 2024])
        self.assertEqual(dots[0]["cx"], chart["left"])
        self.assertEqual(dots[-1]["cx"], chart["right"])
        cys = [d["cy"] for d in dots]
        self.assertEqual(cys, sorted(cys, reverse=True))                   # SVG y grows downwards
        self.assertTrue(all(chart["top"] <= cy <= chart["bottom"] for cy in cys))
        self.assertTrue(chart["series"][0]["path"].startswith("M"))
        self.assertEqual(dots[1]["y"], "4,400")

    def test_axis_covers_the_data_with_round_values(self):
        chart = charts.line_chart([{"key": "a", "label": "A", "points": [(2021, 4130.0), (2022, 4870.0)]}])
        labels = [int(t["label"].replace(",", "")) for t in chart["y_ticks"]]
        self.assertLessEqual(labels[0], 4130)
        self.assertGreaterEqual(labels[-1], 4870)
        self.assertEqual(len({b - a for a, b in zip(labels, labels[1:])}), 1)   # even steps

    def test_a_single_point_is_centred_and_has_no_line(self):
        chart = charts.line_chart([{"key": "a", "label": "A", "points": [(2024, 4000.0)]}])
        self.assertEqual(chart["series"][0]["path"], "")
        self.assertEqual(chart["series"][0]["dots"][0]["cx"], (chart["left"] + chart["right"]) / 2)

    def test_series_share_one_scale(self):
        chart = charts.line_chart([{"key": "a", "label": "A", "points": [(2022, 3000.0), (2023, 3200.0)]},
                                   {"key": "b", "label": "B", "points": [(2022, 5000.0), (2023, 5200.0)]}])
        a, b = chart["series"]
        self.assertGreater(a["dots"][0]["cy"], b["dots"][0]["cy"])           # B is higher up


class PriceHistoryTests(TestCase):
    def setUp(self):
        self.city = make_city(id=503, cityName="Testville")
        self.hood = make_neighborhood(city=self.city)
        self.other = make_neighborhood(district=self.hood.district)

    def test_series_are_yearly_means_over_the_unit(self):
        for hood, year, index, price in ((self.hood, 2023, 100.0, 4000.0), (self.other, 2023, 100.0, 4200.0),
                                         (self.hood, 2024, 110.0, 4400.0), (self.other, 2024, 110.0, 4600.0)):
            HousePriceIndex.objects.create(neighborhood=hood, year=year, index_value=index, pricePerSqm_EUR=price)
        history = calculate_price_history(self.city)
        self.assertEqual(history["nvm"], [(2023, 4100.0), (2024, 4500.0)])
        self.assertEqual(history["index"], [(2023, 100.0), (2024, 110.0)])

    def test_woz_is_weighted_by_dwellings_and_dated_at_its_valuation_year(self):
        WOZValue.objects.create(neighborhood=self.hood, year=2024, avgWOZ_EUR=400_000.0, meanArea_sqm=100.0, dwellings=300)   # 4000/m2
        WOZValue.objects.create(neighborhood=self.other, year=2024, avgWOZ_EUR=500_000.0, meanArea_sqm=100.0, dwellings=100)  # 5000/m2
        self.assertEqual(calculate_price_history(self.city)["woz"], [(2023, 4250.0)])

    def test_a_manual_index_without_prices_is_charted_as_the_index(self):
        HousePriceIndex.objects.create(neighborhood=self.hood, year=2020, index_value=87.5)
        HousePriceIndex.objects.create(neighborhood=self.hood, year=2021, index_value=92.0)
        chart, unit = price_chart(calculate_price_history(self.city))
        self.assertEqual(unit, "index (base year = 100)")
        self.assertEqual([s["key"] for s in chart["series"]], ["index"])

    def test_prices_win_over_the_index_and_nothing_gives_no_chart(self):
        self.assertEqual(price_chart(calculate_price_history(self.city)), (None, "index (base year = 100)"))
        HousePriceIndex.objects.create(neighborhood=self.hood, year=2023, index_value=100.0, pricePerSqm_EUR=4000.0)
        chart, unit = price_chart(calculate_price_history(self.city))
        self.assertEqual((unit, [s["key"] for s in chart["series"]]), ("EUR per m²", ["nvm"]))

    def test_nothing_is_written(self):
        HousePriceIndex.objects.create(neighborhood=self.hood, year=2023, index_value=100.0, pricePerSqm_EUR=4000.0)
        before = HousePriceIndex.objects.count()
        calculate_price_history(self.city)
        self.assertEqual(HousePriceIndex.objects.count(), before)


class PriceChartPanelTests(TestCase):
    def setUp(self):
        self.city = make_city(id=503, cityName="Testville")
        self.hood = make_neighborhood(city=self.city)

    def panel(self):
        url = reverse("housing:housing_indicators", args=["city", "Testville", 2024])
        return self.client.get(url, HTTP_HX_REQUEST="true")

    def test_panel_draws_the_chart_when_there_is_history(self):
        for year, price in ((2023, 4000.0), (2024, 4400.0)):
            HousePriceIndex.objects.create(neighborhood=self.hood, year=year, index_value=100.0, pricePerSqm_EUR=price)
        response = self.panel()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="price-chart"')
        self.assertContains(response, "NVM transaction price 2024: 4,400")
        self.assertContains(response, "EUR per m²")

    def test_panel_has_no_chart_without_history(self):
        response = self.panel()
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="price-chart"')
