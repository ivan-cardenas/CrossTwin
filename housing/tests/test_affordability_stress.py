"""
Affordability stress: the housing-cost burden scaled by the neighborhood's CBS
socio-economic status (housing/calculations/chain.py, HousingAffordability.save(),
receiver housing.signals.social_profile_changed).

DAG edges: Income_Expenses -> Affordability_Stress, Social_Profile -> Affordability_Stress
"""
from unittest import mock

from django.test import TestCase

from watersupply.tests.factories import make_neighborhood, make_polygon

from housing import signals
from housing.calculations import chain
from housing.calculations.indicators import calculate_affordability
from housing.models import HousingAffordability, NeighborhoodSocialProfile


class StressEquationTests(TestCase):
    """Pinned results of the pure equations (SimpleTestCase-style, no rows)."""

    def test_burden_is_twelve_months_of_cost_over_annual_income(self):
        self.assertAlmostEqual(chain.housing_cost_burden(1000, 40_000), 0.30)

    def test_burden_needs_cost_and_income(self):
        self.assertIsNone(chain.housing_cost_burden(None, 40_000))
        self.assertIsNone(chain.housing_cost_burden(1000, 0))

    def test_cost_is_weighted_by_the_rental_share(self):
        self.assertAlmostEqual(chain.monthly_housing_cost(1000, 2000, 25), 1750)
        self.assertAlmostEqual(chain.monthly_housing_cost(1000, 2000, None), 1500)

    def test_cost_uses_the_one_input_that_exists(self):
        self.assertEqual(chain.monthly_housing_cost(1000, 0, 25), 1000)
        self.assertEqual(chain.monthly_housing_cost(None, 2000, 25), 2000)
        self.assertIsNone(chain.monthly_housing_cost(0, None))

    def test_ses_modifier_is_ten_percent_per_sd_and_clamped(self):
        self.assertEqual(chain.ses_modifier(None), 1.0)
        self.assertAlmostEqual(chain.ses_modifier(-1), 1.1)
        self.assertAlmostEqual(chain.ses_modifier(1), 0.9)
        self.assertAlmostEqual(chain.ses_modifier(-5), 1.2)    # clamped at 2 SD
        self.assertAlmostEqual(chain.ses_modifier(5), 0.8)

    def test_levels_at_the_band_edges(self):
        self.assertEqual(chain.affordability_stress_level(0.2999), "low")
        self.assertEqual(chain.affordability_stress_level(0.30), "moderate")
        self.assertEqual(chain.affordability_stress_level(0.3999), "moderate")
        self.assertEqual(chain.affordability_stress_level(0.40), "high")
        self.assertIsNone(chain.affordability_stress_level(None))

    def test_a_low_status_pushes_the_same_burden_up_a_band(self):
        # 0.27 x 1.2 = 0.324 and 0.36 x 1.2 = 0.432 at -2 SD
        self.assertEqual(chain.affordability_stress_level(0.27, 0), "low")
        self.assertEqual(chain.affordability_stress_level(0.27, -2), "moderate")
        self.assertEqual(chain.affordability_stress_level(0.36, -1), "moderate")
        self.assertEqual(chain.affordability_stress_level(0.36, -2), "high")
        self.assertEqual(chain.affordability_stress_level(0.36, 2), "low")    # 0.288


class AffordabilityStressTests(TestCase):
    def setUp(self):
        self.hood = make_neighborhood()

    def _record(self, rent=900, income=40_000, mortgage=0, year=2024, **kwargs):
        return HousingAffordability.objects.create(
            neighborhood=self.hood, year=year, medianIncome=income, medianExpenditure=20_000,
            medianRent=rent, medianMortgage=mortgage, medianHousePrice=300_000, **kwargs)

    def _profile(self, **kwargs):
        return NeighborhoodSocialProfile.objects.create(
            neighborhood=self.hood, geom=make_polygon(), **kwargs)

    def test_level_and_inputs_are_stored_without_a_profile(self):
        rec = self._record(rent=1000)
        self.assertEqual(rec.affordabilityStressLevel, "moderate")
        self.assertAlmostEqual(rec.housingCostBurden_pct, 30.0)
        self.assertIsNone(rec.sesUsed)
        self.assertEqual(rec.sesModifier, 1.0)
        self.assertEqual(rec.stressMethod, chain.STRESS_METHOD)

    def test_the_profile_scales_the_burden(self):
        self._profile(socioEconomicStatus=-2.0)
        rec = self._record(rent=900)
        self.assertEqual(rec.affordabilityStressLevel, "moderate")   # 0.27 x 1.2
        self.assertEqual(rec.sesUsed, -2.0)
        self.assertAlmostEqual(rec.sesModifier, 1.2)

    def test_the_rental_share_weights_rent_against_mortgage(self):
        self._profile(rentalHousing_pct=25.0)
        rec = self._record(rent=1000, mortgage=2000)   # cost 1750 -> 52.5 %
        self.assertAlmostEqual(rec.housingCostBurden_pct, 52.5)
        self.assertEqual(rec.affordabilityStressLevel, "high")

    def test_missing_income_keeps_the_stored_level(self):
        rec = self._record(income=0, affordabilityStressLevel="high")
        self.assertEqual(rec.affordabilityStressLevel, "high")
        self.assertIsNone(rec.housingCostBurden_pct)

    def test_saving_the_profile_rederives_every_year(self):
        old, new = self._record(year=2023), self._record(year=2024)
        self.assertEqual({old.affordabilityStressLevel, new.affordabilityStressLevel}, {"low"})

        profile = self._profile(socioEconomicStatus=-2.0)
        for rec in (old, new):
            rec.refresh_from_db()
            self.assertEqual(rec.affordabilityStressLevel, "moderate")

        profile.socioEconomicStatus = 1.0
        profile.save()
        new.refresh_from_db()
        self.assertEqual(new.affordabilityStressLevel, "low")
        self.assertEqual(new.sesUsed, 1.0)

    def test_deleting_the_profile_drops_the_modifier(self):
        profile = self._profile(socioEconomicStatus=-2.0)
        rec = self._record(rent=900)
        self.assertEqual(rec.affordabilityStressLevel, "moderate")

        profile.delete()
        rec.refresh_from_db()
        self.assertEqual(rec.affordabilityStressLevel, "low")
        self.assertIsNone(rec.sesUsed)

    def test_another_neighborhood_is_not_touched(self):
        other = make_neighborhood()
        rec = HousingAffordability.objects.create(
            neighborhood=other, year=2024, medianIncome=40_000, medianExpenditure=20_000,
            medianRent=900, medianMortgage=0, medianHousePrice=300_000)
        self._profile(socioEconomicStatus=-2.0)
        rec.refresh_from_db()
        self.assertEqual(rec.affordabilityStressLevel, "low")

    def test_raw_saves_do_not_cascade(self):
        with mock.patch.object(signals, "_resave") as resave:
            signals.social_profile_changed(NeighborhoodSocialProfile, mock.Mock(neighborhood_id="x"), raw=True)
        resave.assert_not_called()

    def test_a_bulk_import_refreshes_each_neighborhood_once(self):
        self._record()
        with mock.patch.object(signals, "_resave", wraps=signals._resave) as resave:
            with signals.deferred_housing_refresh():
                profile = self._profile(socioEconomicStatus=-1.0)
                for field in ("rentalHousing_pct", "frailHealth_pct", "severeLoneliness_pct"):
                    setattr(profile, field, 10.0)
                    profile.save()
            self.assertEqual(resave.call_count, 1)

    def test_dashboard_distribution_equals_the_stored_levels(self):
        self._profile(socioEconomicStatus=-2.0)
        self._record(rent=900)    # moderate
        stress = calculate_affordability(self.hood, 2024)["stress_distribution"]
        self.assertEqual(stress, {"low": 0, "moderate": 1, "high": 0})
