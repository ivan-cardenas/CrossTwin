"""AvailableFreshWater.yield_Mm3_year = yearly infiltration depth x source area (chain.recharge_Mm3_yr)."""
from django.test import SimpleTestCase, TestCase

from watersupply.chain import recharge_Mm3_yr
from watersupply.models import AvailableFreshWater

from .factories import make_polygon


def make_source(**kwargs):
    defaults = dict(SourceName="Src", geom=make_polygon())  # 1 km2
    defaults.update(kwargs)
    return AvailableFreshWater.objects.create(**defaults)


class RechargeEquationTests(SimpleTestCase):
    def test_depth_times_area(self):
        # 30 cm/yr over 1 km2 = 0.3 m x 1e6 m2 = 3e5 m3 = 0.3 Mm3/yr
        self.assertAlmostEqual(recharge_Mm3_yr(30, 1e6), 0.3)


class AvailableFreshWaterYieldTests(TestCase):
    def test_yield_is_derived_from_depth_and_area(self):
        source = make_source(infiltrationDepth_cm=30.0, yield_Mm3_year=99.0)
        self.assertAlmostEqual(source.yield_Mm3_year, 0.3)

    def test_yield_scales_with_the_polygon(self):
        source = make_source(infiltrationDepth_cm=30.0, geom=make_polygon(half_size_m=1000.0))  # 4 km2
        self.assertAlmostEqual(source.yield_Mm3_year, 1.2)

    def test_yield_follows_an_edited_depth(self):
        source = make_source(infiltrationDepth_cm=30.0)
        source.infiltrationDepth_cm = 10.0
        source.save()
        self.assertAlmostEqual(source.yield_Mm3_year, 0.1)

    def test_supplied_yield_is_kept_without_a_depth(self):
        source = make_source(yield_Mm3_year=5.0)
        self.assertEqual(source.yield_Mm3_year, 5.0)

    def test_rate_alone_derives_nothing(self):
        source = make_source(infiltrationRate_cm_h=2.0)
        self.assertIsNone(source.yield_Mm3_year)
