from django.test import TestCase

from watersupply.tests.factories import make_city, make_district, make_neighborhood, make_province

from .models import PopulationProjection
from .population import (
    REFERENCE_YEAR, extrapolate, get_population, normalize_scenario, population_by_year,
    population_curve, projection_years,
)


def project(city, year, population, scenario='prognose'):
    return PopulationProjection.objects.create(city=city, year=year, population=population, scenario=scenario)


class PopulationTestBase(TestCase):
    def setUp(self):
        self.province = make_province()
        # City A: two districts, 6000 + 4000 = 10000 (population cascade)
        self.city = make_city(province=self.province, cityName="A", currentPopulation=10000)
        self.d1 = make_district(city=self.city, currentPopulation=6000)
        self.d2 = make_district(city=self.city, currentPopulation=4000)
        self.city.refresh_from_db()
        project(self.city, 2030, 12000)
        project(self.city, 2030, 11000, 'low')
        project(self.city, 2030, 13000, 'high')


class CityPopulationTests(PopulationTestBase):
    def test_cascade_precondition(self):
        self.assertEqual(self.city.currentPopulation, 10000)

    def test_no_year_is_the_current_population(self):
        self.assertEqual(get_population(self.city), 10000)

    def test_projection_variants(self):
        self.assertEqual(get_population(self.city, 2030), 12000)
        self.assertEqual(get_population(self.city, 2030, 'low'), 11000)
        self.assertEqual(get_population(self.city, 2030, 'high'), 13000)

    def test_unknown_variant_falls_back_to_the_median(self):
        self.assertEqual(normalize_scenario('nonsense'), 'prognose')
        self.assertEqual(get_population(self.city, 2030, 'nonsense'), 12000)

    def test_year_without_projection_uses_the_current_population(self):
        self.assertEqual(get_population(self.city, 2040), 10000)

    def test_growth_adjustment_compounds_from_the_reference_year(self):
        expected = round(12000 * 1.02 ** (2030 - REFERENCE_YEAR))
        self.assertEqual(get_population(self.city, 2030, growth_adjust_pct=2), expected)
        # no adjustment up to and including the reference year
        project(self.city, REFERENCE_YEAR, 10500)
        self.assertEqual(get_population(self.city, REFERENCE_YEAR, growth_adjust_pct=5), 10500)

    def test_negative_growth_adjustment_lowers_the_population(self):
        self.assertLess(get_population(self.city, 2030, growth_adjust_pct=-1), 12000)

    def test_without_any_projection_data_nothing_changes(self):
        PopulationProjection.objects.all().delete()
        self.assertEqual(get_population(self.city, 2030), 10000)
        self.assertEqual(population_curve(self.city), [])


class LowerLevelTests(PopulationTestBase):
    def test_districts_share_the_city_projection(self):
        self.assertEqual(get_population(self.d1, 2030), round(0.6 * 12000))
        self.assertEqual(get_population(self.d2, 2030), round(0.4 * 12000))

    def test_districts_add_up_to_the_city(self):
        for scenario in ('prognose', 'low', 'high'):
            total = get_population(self.d1, 2030, scenario) + get_population(self.d2, 2030, scenario)
            self.assertEqual(total, get_population(self.city, 2030, scenario))

    def test_growth_adjustment_reaches_districts(self):
        self.assertEqual(
            get_population(self.d1, 2030, growth_adjust_pct=2),
            round(0.6 * get_population(self.city, 2030, growth_adjust_pct=2)),
        )

    def test_neighborhood_of_another_city(self):
        other = make_city(province=self.province, cityName="B", currentPopulation=1)
        neighborhood = make_neighborhood(city=other, currentPopulation=1200)  # cascade: city = 1200
        other.refresh_from_db()
        project(other, 2030, 1500)
        self.assertEqual(get_population(neighborhood, 2030), 1500)   # only unit -> whole city
        self.assertEqual(get_population(neighborhood), 1200)

    def test_unit_of_a_city_without_population_is_left_unscaled(self):
        empty_city = make_city(province=self.province, cityName="Empty", currentPopulation=0)
        district = make_district(city=empty_city, currentPopulation=None)
        self.assertEqual(get_population(district, 2030), 0)


class IncompleteCityDataTests(TestCase):
    """
    A district/neighborhood must scale by CBS's own growth rate, not by its
    share of `city.currentPopulation` -- because that field is only the sum
    of whichever districts happen to be imported locally, which can be far
    smaller than the real city CBS's numbers describe.
    """

    def setUp(self):
        self.province = make_province()
        # Only one district of a much larger real city has been imported, so
        # city.currentPopulation (5000, via the cascade) drastically
        # understates the real city population CBS's forecast is for.
        self.city = make_city(province=self.province, cityName="Undercounted", currentPopulation=1)
        self.district = make_district(city=self.city, currentPopulation=5000)
        self.city.refresh_from_db()
        self.assertEqual(self.city.currentPopulation, 5000)   # precondition: badly incomplete

        # CBS's real, whole-city numbers: +10% over five years.
        project(self.city, 2025, 100000)
        project(self.city, 2030, 110000)

    def test_district_grows_by_the_citys_percentage_not_its_inflated_share(self):
        # The old share-based formula would have computed share = 5000/5000 = 1.0
        # and returned the *entire* projected city population (110000) for a
        # district that only actually has 5000 people. The fix must instead
        # apply the city's real +10% growth to the district's own 5000.
        self.assertEqual(get_population(self.district, 2030), 5500)

    def test_growth_adjustment_still_compounds_on_top(self):
        expected = round(5000 * 1.1 * 1.02 ** (2030 - REFERENCE_YEAR))
        self.assertEqual(get_population(self.district, 2030, growth_adjust_pct=2), expected)

    def test_single_imported_year_falls_back_to_the_old_share_based_estimate(self):
        # With only one year of CBS data there's no rate to derive -- the
        # best remaining estimate is still the naive share, same as before.
        only_one_year_city = make_city(province=self.province, cityName="OneYear", currentPopulation=1)
        district = make_district(city=only_one_year_city, currentPopulation=3000)
        only_one_year_city.refresh_from_db()
        project(only_one_year_city, 2030, 12000)
        self.assertEqual(get_population(district, 2030), 12000)   # share = 3000/3000 = 1.0


class ProvinceTests(PopulationTestBase):
    def test_province_is_the_sum_of_its_cities(self):
        other = make_city(province=self.province, cityName="B", currentPopulation=1)
        make_neighborhood(city=other, currentPopulation=1200)
        other.refresh_from_db()
        project(other, 2030, 1500)

        self.assertEqual(get_population(self.province, 2030), 12000 + 1500)
        self.province.refresh_from_db()  # the cascade writes with update(), bypassing this instance
        self.assertEqual(get_population(self.province), 10000 + 1200)
        # a year only one city has data for: the other contributes its current population
        project(self.city, 2035, 12500)
        self.assertEqual(get_population(self.province, 2035), 12500 + 1200)

    def test_curve_and_years(self):
        project(self.city, 2035, 12500)
        self.assertEqual(projection_years(self.province), [2030, 2035])
        self.assertEqual(projection_years(self.d1), [2030, 2035])
        curve = population_curve(self.province, 'high')
        self.assertEqual([p['year'] for p in curve], [2030, 2035])
        self.assertEqual(curve[0]['population'], 13000)
        self.assertEqual(population_by_year(self.province, [2030])[2030], 12000)


class CitySaveKeepsImportedPopulationTests(TestCase):
    """A city without district population keeps its own value when re-saved (was reset to 0)."""

    def test_city_without_districts_keeps_its_population(self):
        city = make_city(currentPopulation=164800)
        city.cityName = "Renamed"
        city.save()
        city.refresh_from_db()
        self.assertEqual(city.currentPopulation, 164800)

    def test_districts_still_win_when_they_have_a_population(self):
        city = make_city(currentPopulation=999)
        make_district(city=city, currentPopulation=6000)
        make_district(city=city, currentPopulation=4000)
        city.refresh_from_db()
        city.save()
        self.assertEqual(city.currentPopulation, 10000)


class ExtrapolationTests(TestCase):
    def test_none_with_fewer_than_two_years(self):
        self.assertIsNone(extrapolate({}, 2060))
        self.assertIsNone(extrapolate({2030: 12000}, 2060))

    def test_none_when_the_starting_value_is_not_positive(self):
        self.assertIsNone(extrapolate({2025: 0, 2050: 12000}, 2060))

    def test_extrapolates_forward_at_the_implied_growth_rate(self):
        # 10 000 -> 12 000 over 25 years: 25-year CAGR carried 10 more years.
        series = {2025: 10000, 2050: 12000}
        growth = (12000 / 10000) ** (1 / 25) - 1
        self.assertAlmostEqual(extrapolate(series, 2060), 12000 * (1 + growth) ** 10)

    def test_extrapolates_backward_at_the_same_rate(self):
        series = {2025: 10000, 2050: 12000}
        growth = (12000 / 10000) ** (1 / 25) - 1
        self.assertAlmostEqual(extrapolate(series, 2020), 10000 * (1 + growth) ** -5)

    def test_year_inside_the_range_is_not_extrapolated_here(self):
        # extrapolate() always projects from the endpoints; callers only use it
        # for years missing from the series, so an in-range year is just an
        # example of the same formula, not a special case.
        series = {2025: 10000, 2050: 12000}
        self.assertGreater(extrapolate(series, 2040), 10000)
        self.assertLess(extrapolate(series, 2040), 12000)


class ProjectionExtrapolationIntegrationTests(PopulationTestBase):
    """get_population() falls through to extrapolate() beyond the imported horizon."""

    def setUp(self):
        super().setUp()
        project(self.city, 2050, 15000)   # now two imported years: 2030 and 2050

    def test_year_past_the_last_import_is_extrapolated_not_flat(self):
        value = get_population(self.city, 2060)
        self.assertNotEqual(value, self.city.currentPopulation)
        self.assertGreater(value, 15000)   # still growing past the last imported point

    def test_year_before_the_first_import_is_extrapolated_too(self):
        value = get_population(self.city, 2020)
        self.assertLess(value, 12000)


class PopulationParamsTests(TestCase):
    def test_defaults(self):
        from .population import population_params
        self.assertEqual(population_params({}), ('prognose', 0.0))

    def test_valid_values(self):
        from .population import population_params
        self.assertEqual(population_params({'pop_scenario': 'low', 'pop_growth': '1.5'}), ('low', 1.5))

    def test_invalid_values_fall_back_and_growth_is_clamped(self):
        from .population import MAX_GROWTH_ADJUST_PCT, population_params
        self.assertEqual(population_params({'pop_scenario': 'x', 'pop_growth': 'abc'}), ('prognose', 0.0))
        self.assertEqual(population_params({'pop_growth': '99'})[1], MAX_GROWTH_ADJUST_PCT)
        self.assertEqual(population_params({'pop_growth': '-99'})[1], -MAX_GROWTH_ADJUST_PCT)
        self.assertEqual(population_params({'pop_growth': 'nan'})[1], 0.0)
