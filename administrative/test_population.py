from django.test import TestCase

from watersupply.tests.factories import make_city, make_district, make_neighborhood, make_province

from .models import PopulationProjection
from .population import (
    REFERENCE_YEAR, get_population, normalize_scenario, population_by_year, population_curve,
    projection_years,
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
