"""House price index base year + extrapolation, the historical mortgage rate and its slider, modelled property values."""
import math

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from watersupply.tests.factories import make_city, make_neighborhood

from housing import views
from housing.calculations import chain
from housing.calculations.indicators import (build_curve, calculate_mortgage_indicators, calculate_price_history, hpi_at_year,
                                              hpi_window, price_chart)
from housing.models import HousePriceIndex, MortgageRate
from importer import cbs_hpi, dnb_mortgage


class HpiCurveTests(SimpleTestCase):
    SERIES = [(2019, 3000.0), (2020, 3300.0), (2021, 3630.0), (2022, 3993.0)]   # +10 % a year

    def test_base_year_is_100(self):
        rebased = dict(chain.rebase_index(self.SERIES))
        self.assertEqual(rebased[2019], 100.0)
        self.assertAlmostEqual(rebased[2021], 121.0, places=1)

    def test_no_base_year_value_gives_no_curve(self):
        self.assertEqual(chain.rebase_index([(2020, 3300.0), (2021, 3630.0)]), [])
        self.assertIsNone(chain.hpi_curve([(2020, 3300.0), (2021, 3630.0)]))

    def test_trend_recovers_a_constant_growth_and_runs_to_2100(self):
        curve = chain.hpi_curve(self.SERIES)
        self.assertAlmostEqual(curve["growth_pct"], 10.0, places=1)
        self.assertEqual(curve["projected"][0][0], 2023)
        self.assertEqual(curve["projected"][-1][0], chain.HPI_END_YEAR)
        last_year, last_value = curve["observed"][-1]
        self.assertAlmostEqual(dict(curve["projected"])[2030], last_value * 1.1 ** (2030 - last_year), delta=0.5)

    def test_two_observed_years_are_too_few_for_a_trend(self):
        curve = chain.hpi_curve([(2019, 3000.0), (2020, 3300.0)])
        self.assertEqual(curve["projected"], [])
        self.assertIsNone(curve["growth_pct"])

    def test_the_trend_uses_only_the_last_observed_years(self):
        flat_then_rising = [(2000 + i, 100.0) for i in range(10)] + [(2010 + i, 100.0 * 1.05 ** (i + 1)) for i in range(10)]
        self.assertAlmostEqual(chain.hpi_curve(flat_then_rising, base_year=2000)["growth_pct"], 5.0, places=1)

    def test_hpi_at_marks_the_projected_years(self):
        curve = chain.hpi_curve(self.SERIES)
        self.assertEqual(chain.hpi_at(curve, 2021)[2], False)
        value, previous, projected = chain.hpi_at(curve, 2030)
        self.assertTrue(projected and previous and value > previous)
        self.assertEqual(chain.hpi_at(curve, 2101), (None, dict(curve["projected"])[2100], False))
        self.assertIsNone(hpi_at_year(curve, 2101))
        self.assertEqual(hpi_at_year(curve, 2020)["avg_index"], 110.0)


class MortgageEquationTests(SimpleTestCase):
    def test_annuity_payment_of_a_known_loan(self):
        # 200 000 EUR, 4 % a year, 30 years: 954.83 EUR a month
        self.assertAlmostEqual(chain.annuity_payment(200_000, 4.0, 30), 954.83, places=2)

    def test_zero_rate_repays_linearly_and_no_loan_has_no_payment(self):
        self.assertAlmostEqual(chain.annuity_payment(360_000, 0.0, 30), 1000.0)
        self.assertIsNone(chain.annuity_payment(None, 4.0, 30))
        self.assertIsNone(chain.annuity_payment(200_000, None, 30))

    def test_rate_of_the_year_else_the_latest_earlier_one(self):
        rates = {2019: 2.28, 2020: 1.88}
        self.assertEqual(chain.mortgage_rate_at(rates, 2020), (1.88, 2020))
        self.assertEqual(chain.mortgage_rate_at(rates, 2030), (1.88, 2020))
        self.assertEqual(chain.mortgage_rate_at(rates, 2018), (None, None))

    def test_dnb_export_keeps_only_the_housing_loans_and_cleans_the_labels(self):
        payload = {"data": [
            ["Assets ", "Loans for house purchasing - Total ", "New business ", "Total ", "Total * ", 1041379200000, 5.1],
            ["Assets ", "Consumer credit and other loans - Total ", "New business ", "Total ", "Total ", 1041379200000, 9.0],
            ["Assets ", "Loans for house purchasing - Total ", "Outstanding amounts ", "Total ", "Total ", 1044057600000, None]]}
        rows = dnb_mortgage.parse(payload)
        self.assertEqual(rows, [{"year": 2003, "month": 1, "instrument": "Loans for house purchasing - Total",
                                 "flowType": "New business", "maturity": "Total", "rateFixation": "Total", "ratePct": 5.1}])

    def test_cbs_rows_keep_the_annual_index_only(self):
        rows = [{"Periods": "2020JJ00", "PriceIndexSellingPrices_1": 100.0, "ChangesComparedToThePreviousYear_3": 7.9,
                 "SoldHomes_4": 235511, "AveragePurchasePrice_7": 334488},
                {"Periods": "2020MM01", "PriceIndexSellingPrices_1": 97.0},
                {"Periods": "2021JJ00", "PriceIndexSellingPrices_1": None}]
        self.assertEqual(list(cbs_hpi.parse_rows(rows)), [2020])

    def test_price_factor_is_the_index_of_the_year_over_that_of_the_fit_year(self):
        curve = chain.hpi_curve([(2019, 92.7), (2020, 100.0), (2021, 115.1), (2022, 130.4)])
        self.assertAlmostEqual(chain.hpi_price_factor(curve, 2022, 2020), 130.4 / 100.0, places=2)
        self.assertEqual(chain.hpi_price_factor(curve, 2020, 2020), 1.0)
        self.assertEqual(chain.hpi_price_factor(None, 2022, 2020), 1.0)
        self.assertEqual(chain.hpi_price_factor(curve, 2022, 1990), 1.0)      # no index for the fit year


class HpiAndMortgageDashboardTests(TestCase):
    def setUp(self):
        self.city = make_city(id=503, cityName="Testville")
        self.hood = make_neighborhood(city=self.city)
        for year, index in ((2019, 92.7), (2020, 100.0), (2021, 115.1), (2022, 130.4)):
            HousePriceIndex.objects.create(year=year, index_value=index)
        for year, rates in ((2021, (1.6, 1.8)), (2022, (2.2, 2.6))):
            for month, rate in enumerate(rates, 1):
                MortgageRate.objects.create(year=year, month=month, ratePct=rate, **chain.MORTGAGE_HEADLINE)
        # another series of the same month must not count
        MortgageRate.objects.create(year=2022, month=1, ratePct=9.9, **{**chain.MORTGAGE_HEADLINE, "flowType": "Outstanding amounts"})

    def test_history_has_the_base_year_curve(self):
        curve = calculate_price_history(self.city)["curve"]
        self.assertEqual(curve["observed"][0], (2019, 100.0))
        self.assertAlmostEqual(dict(curve["observed"])[2022], 130.4 / 92.7 * 100, places=1)
        self.assertEqual(curve["projected"][-1][0], 2100)

    def test_chart_shows_five_years_around_the_scenario_year(self):
        history = calculate_price_history(self.city)
        chart, unit = price_chart(history, 2022)
        self.assertEqual(unit, "index (2019 = 100) · 2020-2024")
        observed, projection = chart["series"]
        self.assertEqual([d["x"] for d in observed["dots"]], [2020, 2021, 2022])
        self.assertEqual([d["x"] for d in projection["dots"]], [2022, 2023, 2024])   # joined to the last observed year
        self.assertEqual([t["label"] for t in chart["x_ticks"]], ["2020", "2021", "2022", "2023", "2024"])

    def test_window_follows_the_scenario_year_and_stays_inside_the_curve(self):
        curve = calculate_price_history(self.city)["curve"]
        self.assertEqual(hpi_window(curve, 2060), (2058, 2062))
        self.assertEqual(hpi_window(curve, 2100), (2096, 2100))
        self.assertEqual(hpi_window(curve, 2019), (2019, 2023))
        self.assertEqual(price_chart(calculate_price_history(self.city), 2060)[1], "index (2019 = 100) · 2058-2062")

    def test_mortgage_slider_starts_at_the_historical_rate(self):
        self.assertEqual(calculate_mortgage_indicators(self.city, 2021)["mortgage_rate"], 1.7)       # mean of 1.6 and 1.8
        self.assertEqual(calculate_mortgage_indicators(self.city, 2030)["mortgage_rate"], 2.4)      # latest earlier year
        self.assertEqual(calculate_mortgage_indicators(self.city, 2030)["mortgage_rate_source"], "DNB 2022")

    def _indicators(self, **overrides):
        data = views._get_adminUnit_data("city", "Testville", 2021)
        data["mortgage"] = {**data["mortgage"], "avg_loan_amount": 200_000.0, "avg_monthly_payment": 800.0,
                            "avg_term_years": 30}
        return views._build_indicators(data, **overrides)

    def test_default_rate_keeps_the_stored_payment_and_the_slider_recomputes_it(self):
        stored = self._indicators()
        self.assertEqual((stored["mortgage_rate"], stored["avg_monthly_payment"], stored["mortgage_rate_whatif"]),
                         (1.7, 800.0, False))
        self.assertFalse(self._indicators(mortgage_rate_override=1.7)["mortgage_rate_whatif"])
        moved = self._indicators(mortgage_rate_override=4.0)
        self.assertTrue(moved["mortgage_rate_whatif"])
        self.assertAlmostEqual(moved["avg_monthly_payment"], 954.83, places=2)
        self.assertEqual(moved["mortgage_rate_stored"], 1.7)

    def test_panel_shows_the_slider_at_the_historical_rate_and_the_base_year_card(self):
        response = self.client.get(reverse("housing:housing_indicators", args=["city", "Testville", 2021]),
                                   HTTP_HX_REQUEST="true")
        self.assertContains(response, 'id="mortgage-rate-slider"')
        self.assertContains(response, 'value="1.7"')
        self.assertContains(response, "index (2019 = 100)")
        self.assertContains(response, 'id="hpi-year-slider"')
        self.assertContains(response, 'value="2021"')

    def test_a_projected_year_is_flagged(self):
        response = self.client.get(reverse("housing:housing_indicators", args=["city", "Testville", 2040]),
                                   HTTP_HX_REQUEST="true")
        self.assertContains(response, "trend extrapolation")

    def test_property_market_reads_the_stored_modelled_values(self):
        from housing.calculations.indicators import calculate_property_indicators

        calculate_property_indicators(self.city)
        data = views._get_adminUnit_data("city", "Testville", 2021)
        data["modelled_price"] = {**data["modelled_price"], "summary": {"stored_mean": 4000.0, "value_mean": 400_000.0, "priced": 12}}
        shown = views._build_indicators(data)
        self.assertEqual((shown["modelled_sqm"], shown["modelled_value"], shown["modelled_count"]), (4000, 400_000, 12))

    def test_modelled_prices_follow_the_index_of_the_scenario_year(self):
        from types import SimpleNamespace

        data = views._get_adminUnit_data("city", "Testville", 2022)
        fit = SimpleNamespace(wozYear=2020, pk=1, n=50, r2=0.5, form="linear", spatialModel="ols", moransP=0.5,
                              diagnosticPassed=True, formComparison={}, spec={}, screening={}, coefficients={})
        data["modelled_price"] = {"model": fit, "summary": {"stored_mean": 4000.0, "value_mean": 400_000.0,
                                                            "level_mean": 3800.0, "priced": 12}}
        in_fit_year = views._build_indicators(data, year=2020)
        later = views._build_indicators(data, year=2022)
        self.assertEqual((in_fit_year["modelled_sqm"], in_fit_year["mp_price"]), (4000, 4000))
        self.assertEqual((later["modelled_sqm"], later["modelled_value"], later["mp_price"]), (5216, 521_628, 5216))   # x 130.4 / 100 (the curve is rounded to 0.01)
        self.assertEqual(later["mp_level"], round(3800 * 1.304))
        self.assertTrue(later["mp_whatif"])

    def test_nothing_is_written(self):
        before = (MortgageRate.objects.count(), HousePriceIndex.objects.count())
        self.client.get(reverse("housing:recalculate_indicators", args=["city", "Testville", 2021]), {"mortgage_rate": "9"})
        self.assertEqual((MortgageRate.objects.count(), HousePriceIndex.objects.count()), before)
        self.assertEqual(MortgageRate.objects.filter(year=2021).count(), 2)


class HpiFadeTests(SimpleTestCase):
    """The extrapolation starts at the recent trend and fades to the long-run average of the observed series."""

    # 1995-2004 at 2 % a year, then 2005-2014 at 10 %: recent trend 10 %, whole-series average about 5.9 %
    SERIES = ([(1995 + i, 100.0 * 1.02 ** i) for i in range(10)]
              + [(2005 + i, 100.0 * 1.02 ** 9 * 1.10 ** (i + 1)) for i in range(10)])

    def curve(self, **kwargs):
        return chain.hpi_curve(self.SERIES, base_year=1995, **kwargs)

    def test_long_run_is_the_average_growth_of_the_whole_series(self):
        points = chain.rebase_index(self.SERIES, 1995)
        expected = ((points[-1][1] / points[0][1]) ** (1 / 19) - 1) * 100
        self.assertAlmostEqual(chain.long_run_growth(points), expected, places=6)
        curve = self.curve()
        self.assertAlmostEqual(curve["recent_pct"], 10.0, places=1)
        self.assertAlmostEqual(curve["long_run_pct"], expected, places=1)

    def test_growth_halves_the_gap_every_half_life_and_ends_at_the_long_run_rate(self):
        self.assertAlmostEqual(chain.faded_growth(10.0, 4.0, 0), 10.0)
        self.assertAlmostEqual(chain.faded_growth(10.0, 4.0, chain.HPI_FADE_HALF_LIFE_YEARS), 7.0)
        self.assertAlmostEqual(chain.faded_growth(10.0, 4.0, 200), 4.0, places=6)

    def test_first_projected_year_grows_by_the_faded_rate_and_the_slider_changes_the_far_end(self):
        curve = self.curve(long_run_pct=3.0)
        last_year, last = curve["observed"][-1]
        first = dict(curve["projected"])[last_year + 1]
        self.assertAlmostEqual(first, last * (1 + chain.faded_growth(curve["recent_pct"], 3.0, 1) / 100), places=1)
        self.assertEqual(curve["long_run_pct"], 3.0)
        self.assertLess(dict(curve["projected"])[2100], dict(self.curve(long_run_pct=6.0)["projected"])[2100])
        self.assertAlmostEqual(dict(curve["projected"])[2100] / dict(curve["projected"])[2099], 1.03, places=3)

    def test_the_fade_is_far_below_the_unfaded_recent_trend(self):
        faded = dict(self.curve()["projected"])[2100]
        unfaded = self.curve()["observed"][-1][1] * 1.10 ** (2100 - 2014)
        self.assertLess(faded, unfaded / 10)

    def test_a_series_too_short_for_a_trend_has_no_projection(self):
        self.assertEqual(chain.hpi_curve([(2019, 100.0), (2020, 110.0)])["projected"], [])


class HpiAreaCurveTests(TestCase):
    """The unit's own WOZ value per m2 is the curve; beyond its last year it moves with the national index."""

    NATIONAL = [(2019, 92.7), (2020, 100.0), (2021, 115.1), (2022, 130.4), (2023, 126.6), (2024, 137.7), (2025, 149.5)]

    def setUp(self):
        from housing.models import WOZValue

        self.city = make_city(id=503, cityName="Testville")
        self.hood = make_neighborhood(city=self.city)
        for year, index in self.NATIONAL:
            HousePriceIndex.objects.create(year=year, index_value=index)
        # the area rises faster than the country: 4000 EUR/m2 in 2019, 6000 in 2022
        for year, woz in ((2019, 400_000.0), (2020, 450_000.0), (2021, 520_000.0), (2022, 600_000.0)):
            WOZValue.objects.create(neighborhood=self.hood, year=year, avgWOZ_EUR=woz, meanArea_sqm=100.0, dwellings=100)

    def test_observed_years_are_the_areas_own_values_rebased(self):
        curve = calculate_price_history(self.city)["curve"]
        self.assertEqual(curve["source"], "area")
        self.assertEqual(curve["observed"], [(2019, 100.0), (2020, 112.5), (2021, 130.0), (2022, 150.0)])

    def test_later_years_follow_the_national_index(self):
        curve = calculate_price_history(self.city)["curve"]
        projected = dict(curve["projected"])
        self.assertAlmostEqual(projected[2023], 150.0 * 126.6 / 130.4, places=1)     # the national change of 2023 (observed)
        self.assertAlmostEqual(projected[2025], 150.0 * 149.5 / 130.4, places=1)
        national = chain.hpi_curve([(y, v) for y, v in self.NATIONAL])
        nat = {**dict(national["observed"]), **dict(national["projected"])}
        self.assertAlmostEqual(projected[2100] / projected[2050], nat[2100] / nat[2050], places=2)
        self.assertEqual(curve["recent_pct"], national["recent_pct"])                  # the growth shown is the national one

    def test_the_long_run_slider_moves_the_national_growth_the_area_follows(self):
        history = calculate_price_history(self.city)
        low, high = build_curve(history, 2.0), build_curve(history, 6.0)
        self.assertLess(dict(low["projected"])[2100], dict(high["projected"])[2100])
        self.assertEqual(low["observed"], high["observed"])

    def test_without_wozvalues_the_national_index_is_the_curve_and_without_the_index_the_area_trend(self):
        from housing.models import WOZValue

        other = make_neighborhood(district=self.hood.district)
        self.assertEqual(calculate_price_history(self.city)["curve"]["source"], "area")
        WOZValue.objects.all().delete()
        self.assertEqual(calculate_price_history(self.city)["curve"]["source"], "series")
        self.assertEqual(calculate_price_history(self.city)["curve"]["observed"][0], (2019, 100.0))
        self.assertIsNotNone(other)

    def test_panel_says_whose_values_it_shows(self):
        response = self.client.get(reverse("housing:housing_indicators", args=["city", "Testville", 2022]),
                                   HTTP_HX_REQUEST="true")
        self.assertContains(response, "of this area, carried on with the national index")
