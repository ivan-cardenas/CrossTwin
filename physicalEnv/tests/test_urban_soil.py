from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase

from physicalEnv.calculations.soil import (
    URBAN_SOIL_CODE, URBAN_SOIL_GROUP, soil_landcover_composition, summarize_infiltration,
)
from physicalEnv.calculations.urban_soil import fill_urban_soil_gaps
from physicalEnv.models import LandCoverClasses, LandCoverVector, SoilArea, SoilType
from watersupply.tests.factories import make_city

X0, Y0 = 256500.0, 469500.0


def _box(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))), srid=28992)


class UrbanSoilTests(TestCase):
    """Built-up land the soil map leaves blank is stored as 'Urban land' soil."""

    def setUp(self):
        self.city = make_city(cityName="Urbanville")
        self.region = _box(X0, Y0, X0 + 1000, Y0 + 1000)
        sand = SoilType.objects.create(code="Zn21", name="Vlakvaaggronden; leemarm en zwak lemig fijn zand")
        # the soil map covers the west half only
        SoilArea.objects.create(mapAreaID="a", soil_type=sand, geom=_box(X0, Y0, X0 + 500, Y0 + 1000))
        self.urban = LandCoverClasses.objects.create(class_name="Discontinuous urban fabric", description="t")
        pastures = LandCoverClasses.objects.create(class_name="pastures", description="t")
        LandCoverVector.objects.create(city=self.city, year=2024, land_cover_type=self.urban, land_use="x",
                                       geom=_box(X0 + 250, Y0, X0 + 1000, Y0 + 500), percentage=1)
        LandCoverVector.objects.create(city=self.city, year=2024, land_cover_type=pastures, land_use="x",
                                       geom=_box(X0 + 250, Y0 + 500, X0 + 1000, Y0 + 1000), percentage=1)

    def test_gap_under_urban_land_becomes_urban_soil(self):
        self.assertEqual(fill_urban_soil_gaps(self.region), 1)
        area = SoilArea.objects.get(soil_type__code=URBAN_SOIL_CODE)
        # urban polygon (750 x 500) minus the soil map (x < 500): 500 x 500 m
        self.assertAlmostEqual(area.geom.area, 250_000, places=0)
        self.assertEqual(area.soil_type.soilGroup, URBAN_SOIL_GROUP)
        self.assertTrue(area.mapAreaID.startswith("urban-"))

    def test_rerun_is_idempotent_and_never_overlaps_the_soil_map(self):
        fill_urban_soil_gaps(self.region)
        first = set(SoilArea.objects.values_list("mapAreaID", flat=True))
        fill_urban_soil_gaps(self.region)
        self.assertEqual(set(SoilArea.objects.values_list("mapAreaID", flat=True)), first)
        real = SoilArea.objects.exclude(soil_type__code=URBAN_SOIL_CODE).get()
        fill = SoilArea.objects.get(soil_type__code=URBAN_SOIL_CODE)
        self.assertEqual(real.geom.intersection(fill.geom).area, 0)

    def test_composition_gains_the_urban_piece(self):
        before = soil_landcover_composition(self.region[0])[0]
        self.assertFalse(any(c == "Discontinuous urban fabric" and g == URBAN_SOIL_GROUP for g, c, _ in before))
        fill_urban_soil_gaps(self.region)
        after = soil_landcover_composition(self.region[0])[0]
        urban = [a for g, c, a in after if c == "Discontinuous urban fabric" and g == URBAN_SOIL_GROUP]
        self.assertAlmostEqual(sum(urban), 250_000, places=0)
        # the urban piece infiltrates less than sand-based pasture: CN 90 (urban, C) > CN 39 (pasture, A)
        result = summarize_infiltration([(URBAN_SOIL_GROUP, "Discontinuous urban fabric", 1.0)], 50)
        self.assertEqual(result["curve_number"], 90.0)
        self.assertLess(result["infiltration_coefficient"], 0.6)

    def test_urban_soil_is_not_filled_into_non_urban_land(self):
        fill_urban_soil_gaps(self.region)
        pasture_piece = _box(X0 + 600, Y0 + 600, X0 + 700, Y0 + 700)
        self.assertFalse(SoilArea.objects.filter(soil_type__code=URBAN_SOIL_CODE, geom__intersects=pasture_piece).exists())
