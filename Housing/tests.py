from django.test import TestCase

from builtup.models import ZoningArea
from physicalEnv.models import HILUCSLandUse
from watersupply.tests.factories import make_neighborhood, make_polygon

from .calculations import calculate_zoning


class ZoningGroupsTests(TestCase):
    """calculate_zoning groups ZoningArea.zone_type HILUCS codes into the dashboard's four bars."""

    def test_codes_and_their_subcodes_fall_in_their_group(self):
        hood = make_neighborhood()
        for i, code in enumerate(["5", "5.1", "5.2", "3.1.1", "2.1", "6.3.2"]):
            ZoningArea.objects.create(
                neighborhood=hood, zone_type=HILUCSLandUse.objects.get(code=code),
                geom=make_polygon(257000.0 + i * 100, 470000.0, 10),   # 400 m² each
            )

        zoning = calculate_zoning(hood)

        counts = {group: data["count"] for group, data in zoning["by_type"].items()}
        # 5.2 is mixed only; 6.3.2 (water) is in no group but counts in the total
        self.assertEqual(counts, {"residential": 2, "commercial": 1, "industrial": 1, "mixed": 1})
        self.assertAlmostEqual(zoning["total_area_sqm"], 6 * 400)
        self.assertAlmostEqual(zoning["by_type"]["residential"]["area_pct"], 33.3)
