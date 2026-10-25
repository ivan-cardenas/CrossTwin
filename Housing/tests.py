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


class PipelineLandTakeTests(TestCase):
    """calculate_pipeline_land_take: DAG edge New_Units -> LandCover, dashboard only."""

    def setUp(self):
        from physicalEnv.models import LandCoverClasses, LandCoverVector
        self.hood = make_neighborhood()   # 1 km x 1 km around (257000, 470000)
        city = self.hood.district.city
        pasture = LandCoverClasses.objects.create(class_name="pastures", description="test")
        urban = LandCoverClasses.objects.create(class_name="Urban fabric", description="test")
        # west half pasture, east half urban fabric; an older year that must be ignored
        for year in (2018, 2024):
            LandCoverVector.objects.create(city=city, year=year, land_cover_type=pasture, land_use="Agriculture",
                                           geom=make_polygon(256750.0, 470000.0, 250), percentage=50)
        LandCoverVector.objects.create(city=city, year=2024, land_cover_type=urban, land_use="Residential",
                                       geom=make_polygon(257250.0, 470000.0, 250), percentage=50)
        self.LandCoverVector = LandCoverVector

    def _project(self, x, completion, half=50):
        from .models import HousingProject
        return HousingProject.objects.create(
            neighborhood=self.hood, year=2024, year_expected_completion=completion,
            project_name="P", project_description="", project_area=(2 * half) ** 2,
            project_units=100, geom=make_polygon(x, 470000.0, half))

    def test_footprint_split_into_greenfield_and_infill(self):
        from .calculations import calculate_pipeline_land_take
        self._project(257000.0, 2030)          # straddles the boundary: 0.5 ha each side
        self._project(257000.0, 2030, half=25)  # overlaps the first: counted once
        self._project(256600.0, 2020)          # completed: not pipeline
        before = self.LandCoverVector.objects.count()

        take = calculate_pipeline_land_take(self.hood, 2025)

        self.assertAlmostEqual(take["footprint_ha"], 1.0, places=2)
        self.assertAlmostEqual(take["greenfield_ha"], 0.5, places=2)
        self.assertAlmostEqual(take["infill_ha"], 0.5, places=2)
        self.assertAlmostEqual(take["uncovered_ha"], 0.0, places=2)
        self.assertEqual({c["class_name"]: c["urban"] for c in take["by_class"]},
                         {"pastures": False, "Urban fabric": True})
        self.assertEqual(self.LandCoverVector.objects.count(), before)   # writes nothing

    def test_no_pipeline_is_zero(self):
        from .calculations import calculate_pipeline_land_take
        take = calculate_pipeline_land_take(self.hood, 2025)
        self.assertEqual((take["footprint_ha"], take["by_class"]), (0.0, []))
