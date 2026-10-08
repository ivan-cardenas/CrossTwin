from unittest import mock

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase

from administrative.models import City, District, Neighborhood, Province
from .models import LandCoverClasses, LandCoverVector


def _square(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))))


class UrbanAreaSourceComputationTests(TestCase):
    """physicalEnv.signals.landcover_changed: Neighborhood.urban_area is
    derived from the PostGIS intersection area between LandCoverVector
    polygons (matching URBAN_AREA_KEYWORDS) and the Neighborhood boundary,
    restricted to the most recent LandCoverVector.year per city."""

    def setUp(self):
        self.full_square = _square(0, 0, 1000, 1000)  # 1 km^2
        self.province = Province.objects.create(ProvinceName="P", geom=self.full_square)
        self.city = City.objects.create(cityName="C", province=self.province, geom=self.full_square)
        self.district = District.objects.create(
            id="D1", districtName="D", city=self.city, geom=self.full_square, currentPopulation=0
        )
        self.neighborhood = Neighborhood.objects.create(
            id="N1", neighborhoodName="N", district=self.district, geom=self.full_square, currentPopulation=0
        )
        self.urban_class = LandCoverClasses.objects.create(
            class_name="Urban fabric, continuous", description="test"
        )
        self.non_urban_class = LandCoverClasses.objects.create(
            class_name="Arable land", description="test"
        )

    def test_qualifying_landcover_sets_neighborhood_urban_area(self):
        half_square = _square(500, 0, 1000, 1000)  # 0.5 km^2, half the neighborhood
        LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.urban_class,
            land_use="Residential", geom=half_square, percentage=50.0,
        )

        self.neighborhood.refresh_from_db()
        self.district.refresh_from_db()
        self.city.refresh_from_db()
        self.province.refresh_from_db()

        self.assertAlmostEqual(self.neighborhood.urban_area, 0.5)
        self.assertAlmostEqual(self.district.urban_area, 0.5)
        self.assertAlmostEqual(self.city.urban_area, 0.5)
        self.assertAlmostEqual(self.province.urban_area, 0.5)

    def test_non_qualifying_category_is_ignored(self):
        LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.non_urban_class,
            land_use="Agriculture", geom=self.full_square, percentage=100.0,
        )

        self.neighborhood.refresh_from_db()
        self.assertEqual(self.neighborhood.urban_area, 0.0)

    def test_only_the_most_recent_year_is_summed(self):
        LandCoverVector.objects.create(
            city=self.city, year=2020, land_cover_type=self.urban_class,
            land_use="Residential", geom=self.full_square, percentage=100.0,
        )
        LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.urban_class,
            land_use="Residential", geom=_square(500, 0, 1000, 1000), percentage=50.0,
        )

        self.neighborhood.refresh_from_db()
        # Only 2024 (0.5 km^2) counts, not 2020 + 2024 (which would be 1.5).
        self.assertAlmostEqual(self.neighborhood.urban_area, 0.5)

    def test_deleting_the_last_row_resets_urban_area_to_zero(self):
        lcv = LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.urban_class,
            land_use="Residential", geom=self.full_square, percentage=100.0,
        )
        self.neighborhood.refresh_from_db()
        self.assertAlmostEqual(self.neighborhood.urban_area, 1.0)

        lcv.delete()

        self.neighborhood.refresh_from_db()
        self.district.refresh_from_db()
        self.city.refresh_from_db()
        self.province.refresh_from_db()
        self.assertEqual(self.neighborhood.urban_area, 0.0)
        self.assertEqual(self.district.urban_area, 0.0)
        self.assertEqual(self.city.urban_area, 0.0)
        self.assertEqual(self.province.urban_area, 0.0)


class UrbanAreaSetBasedUpdateTests(TestCase):
    """The single-statement recompute (docs/PERFORMANCE.md §2): clipping, cascade count, deferral."""

    def setUp(self):
        wide = _square(0, 0, 2000, 1000)
        self.province = Province.objects.create(ProvinceName="P", geom=wide)
        self.city = City.objects.create(cityName="C", province=self.province, geom=wide)
        self.district = District.objects.create(
            id="D1", districtName="D", city=self.city, geom=wide, currentPopulation=0)
        self.west = Neighborhood.objects.create(
            id="W", neighborhoodName="W", district=self.district, geom=_square(0, 0, 1000, 1000), currentPopulation=0)
        self.east = Neighborhood.objects.create(
            id="E", neighborhoodName="E", district=self.district, geom=_square(1000, 0, 2000, 1000), currentPopulation=0)
        self.urban = LandCoverClasses.objects.create(class_name="Railway", description="test")  # 'rail'

    def _landcover(self, geom, year=2024):
        return LandCoverVector.objects.create(
            city=self.city, year=year, land_cover_type=self.urban, land_use="Rail", geom=geom, percentage=0)

    def test_polygon_crossing_a_boundary_is_split_between_neighborhoods(self):
        self._landcover(_square(500, 0, 1500, 1000))    # half in W, half in E
        self._landcover(_square(1600, 0, 1800, 1000))   # entirely inside E: counted unclipped

        self.west.refresh_from_db()
        self.east.refresh_from_db()
        self.district.refresh_from_db()
        self.assertAlmostEqual(self.west.urban_area, 0.5)
        self.assertAlmostEqual(self.east.urban_area, 0.7)
        self.assertAlmostEqual(self.district.urban_area, 1.2)

    def test_each_parent_is_recomputed_once(self):
        from physicalEnv import signals

        with mock.patch.object(signals, "_recompute_population", wraps=signals._recompute_population) as cascade:
            self._landcover(_square(0, 0, 100, 100))
        # one district + the city + the province, not the full chain per district
        self.assertEqual(cascade.call_count, 3)

    def test_deferred_block_recomputes_once_per_city(self):
        from physicalEnv import signals

        with mock.patch.object(signals, "_recompute_neighborhood_urban_area",
                               wraps=signals._recompute_neighborhood_urban_area) as recompute:
            with signals.deferred_urban_area():
                for x in (0, 200, 400, 1200, 1400):
                    self._landcover(_square(x, 0, x + 100, 1000))
                recompute.assert_not_called()
        recompute.assert_called_once_with(self.city.pk)

        self.west.refresh_from_db()
        self.east.refresh_from_db()
        self.assertAlmostEqual(self.west.urban_area, 0.3)
        self.assertAlmostEqual(self.east.urban_area, 0.2)


# -- Soil hydrology (physicalEnv/soil.py) --------------------------------------

from django.test import SimpleTestCase


class SoilGroupClassificationTests(SimpleTestCase):
    """Dutch soil map names -> SCS hydrologic soil group; the most restrictive layer wins."""

    CASES = {
        # A: sand, also loamy and "kleiig" (clayey) sand
        "Veldpodzolgronden; leemarm en zwak lemig fijn zand": "A",
        "Hoge zwarte enkeerdgronden; grof zand": "A",
        "Kalkhoudende vlakvaaggronden; zwak en sterk lemig, kleiig, uiterst fijn zand": "A",
        # B: zavel, loam (not leemarm/lemig, not keileem)
        "Kalkrijke poldervaaggronden; lichte zavel, profielverloop 2": "B",
        "Ooivaaggronden met roest beginnend dieper dan 0.8 m; zandige leem in situ": "B",
        "Radebrikgronden; siltige leem": "B",
        # C: light clay, knip clay
        "Kalkloze poldervaaggronden; zavel en lichte klei, profielverloop 2": "C",
        "Knippige poldervaaggronden; lichte zavel, profielverloop 5": "C",
        # D: clay, peat, peaty layers, tidal mud, boulder clay
        "Kalkrijke poldervaaggronden; zware klei, profielverloop 5": "D",
        "Gorsvaaggronden; zware zavel en klei; geen zand beginnend ondieper dan 0.8 m": "D",
        "Slikvaaggronden; zand beginnend ondieper dan 0.8 m": "D",
        "Koopveengronden op zand, beginnend ondieper dan 1.2 m": "D",
        "Moerige eerdgronden met een zanddek en een moerige tussenlaag op zand": "D",
        "Kalkloze drechtvaaggronden; profielverloop 1": "D",
        "Zeer ondiepe keileem, potklei, enz": "D",
        "Kleefaarde": "D",
        "Veenafbraakgebied": "D",
    }

    def test_soil_map_names(self):
        from .soil import classify_soil_group
        for name, group in self.CASES.items():
            with self.subTest(name):
                self.assertEqual(classify_soil_group(name), group)

    def test_name_without_texture(self):
        from .soil import classify_soil_group
        self.assertIsNone(classify_soil_group("Bebouwing"))
        self.assertIsNone(classify_soil_group(""))


class SCSCurveNumberTests(SimpleTestCase):
    def test_runoff_against_a_hand_calculation(self):
        from .soil import infiltration_coefficient, scs_runoff_mm
        # CN 80: S = 25400/80 - 254 = 63.5 mm, Ia = 12.7 mm
        # P = 50 mm: Q = 37.3^2 / (37.3 + 63.5) = 13.80 mm
        self.assertAlmostEqual(scs_runoff_mm(50, 80), 37.3 ** 2 / 100.8, places=6)
        self.assertAlmostEqual(infiltration_coefficient(50, 80), 1 - 37.3 ** 2 / 100.8 / 50, places=6)

    def test_limits(self):
        from .soil import infiltration_coefficient, scs_runoff_mm
        self.assertEqual(scs_runoff_mm(10, 80), 0.0)        # P below Ia: no runoff
        self.assertEqual(infiltration_coefficient(10, 80), 1.0)
        self.assertEqual(scs_runoff_mm(30, 100), 30.0)      # open water
        self.assertIsNone(infiltration_coefficient(0, 80))

    def test_curve_numbers_by_land_cover_and_soil_group(self):
        from .soil import curve_number
        self.assertEqual(curve_number("pastures", "A"), 39)
        self.assertEqual(curve_number("pastures", "D"), 80)
        self.assertEqual(curve_number("discontinuous urban fabric", "B"), 85)
        self.assertEqual(curve_number("continuous urban fabric", "B"), 92)
        self.assertEqual(curve_number("green urban areas", "B"), 61)   # not urban fabric
        self.assertEqual(curve_number("road and rail networks and associated land", "C"), 92)
        self.assertEqual(curve_number("broad-leaved forest", "A"), 30)
        self.assertIsNone(curve_number("glaciers", "A"))
        self.assertIsNone(curve_number("pastures", None))

    def test_summary_weights_runoff_per_piece_not_the_curve_number(self):
        from .soil import scs_runoff_mm, summarize_infiltration
        pieces = [("A", "broad-leaved forest", 1000.0), ("D", "urban fabric", 1000.0), (None, "pastures", 500.0)]
        result = summarize_infiltration(pieces, 40)

        q_forest, q_urban = scs_runoff_mm(40, 30), scs_runoff_mm(40, 92)
        expected = 1 - (q_forest + q_urban) / 2 / 40
        self.assertAlmostEqual(result["infiltration_coefficient"], expected)
        self.assertNotAlmostEqual(expected, 1 - scs_runoff_mm(40, 61) / 40)   # mean CN would differ
        self.assertEqual(result["curve_number"], 61.0)
        self.assertEqual((result["classified_m2"], result["unclassified_m2"]), (2000.0, 500.0))
        self.assertAlmostEqual(result["infiltrated_m3"] + result["runoff_m3"], 0.040 * 2000)


class SoilTypeTests(TestCase):
    def test_save_derives_group_and_infiltration_rate(self):
        from .models import SoilType
        sand = SoilType.objects.create(code="Hn21", name="Veldpodzolgronden; leemarm en zwak lemig fijn zand")
        peat = SoilType.objects.create(code="hVs", name="Koopveengronden op veenmosveen")
        self.assertEqual((sand.soilGroup, sand.infiltrationMin_mm_h, sand.infiltrationMax_mm_h), ("A", 7.6, None))
        self.assertEqual((peat.soilGroup, peat.infiltrationMin_mm_h, peat.infiltrationMax_mm_h), ("D", 0.0, 1.3))


class SoilLandcoverCompositionTests(TestCase):
    """soil_landcover_composition clips soil x land cover to the unit and uses the latest land-cover year."""

    def setUp(self):
        from .models import SoilArea, SoilType
        square = _square(0, 0, 1000, 1000)
        province = Province.objects.create(ProvinceName="P", geom=square)
        self.city = City.objects.create(cityName="C", province=province, geom=square)

        sand = SoilType.objects.create(code="Zn21", name="Vlakvaaggronden; leemarm en zwak lemig fijn zand")
        peat = SoilType.objects.create(code="Vb", name="Vlierveengronden op zeggeveen")
        # sand west, peat east; the peat polygon reaches 500 m outside the city
        SoilArea.objects.create(mapAreaID="a", soil_type=sand, geom=_square(0, 0, 500, 1000))
        SoilArea.objects.create(mapAreaID="d", soil_type=peat, geom=_square(500, 0, 1500, 1000))

        pastures = LandCoverClasses.objects.create(class_name="pastures", description="test")
        urban = LandCoverClasses.objects.create(class_name="urban fabric", description="test")
        for year, cls, geom in [
            (2024, pastures, _square(0, 0, 1500, 500)),     # south
            (2024, urban, _square(0, 500, 1500, 1000)),     # north
            (2020, urban, _square(0, 0, 1500, 1000)),       # older year: ignored
        ]:
            LandCoverVector.objects.create(city=self.city, year=year, land_cover_type=cls,
                                           land_use="x", geom=geom, percentage=0)

    def _pieces(self, statistic="GHG"):
        from .soil import soil_landcover_composition
        self.city.refresh_from_db()
        composition, by_group, shallow_m2, drained_m2 = soil_landcover_composition(self.city.geom, statistic)
        pieces = {}
        for g, c, a in composition:
            pieces[(g, c)] = pieces.get((g, c), 0) + round(a)
        return pieces, {g: round(a) for g, a in by_group.items()}, round(shallow_m2), round(drained_m2)

    def test_pieces_and_soil_groups_inside_the_unit(self):
        pieces, by_group, shallow, drained = self._pieces()
        self.assertEqual(pieces, {
            ("A", "pastures"): 250_000, ("A", "urban fabric"): 250_000,
            ("D", "pastures"): 250_000, ("D", "urban fabric"): 250_000,
        })
        self.assertEqual(by_group, {"A": 500_000, "D": 500_000})
        self.assertEqual((shallow, drained), (0, 0))   # no groundwater raster imported

    def _groundwater(self, west_cm, east_cm, statistic="GHG"):
        """Groundwater raster over the city: 50 m cells, `west_cm` for x < 500, `east_cm` east of it."""
        from django.contrib.gis.gdal import GDALRaster
        from .models import GroundwaterDepth
        row = [west_cm] * 10 + [east_cm] * 10
        raster = GDALRaster({
            "srid": 28992, "width": 20, "height": 20, "origin": (0, 1000), "scale": (50, -50),
            "datatype": 1, "bands": [{"data": row * 20, "nodata_value": 255}],
        })
        with mock.patch("core.rasterOperations.export_raster_to_cog"):
            GroundwaterDepth.objects.create(year=2025, statistic=statistic, depth_raster=raster)

    def test_shallow_groundwater_turns_undrained_soil_into_group_d(self):
        self._groundwater(west_cm=30, east_cm=120)   # the sand (west) has GHG 30 cm
        pieces, by_group, shallow, drained = self._pieces()
        self.assertEqual(pieces, {
            ("D", "pastures"): 500_000,      # sand pasture moved to D, plus the peat
            ("A", "urban fabric"): 250_000,  # drained: keeps its texture group
            ("D", "urban fabric"): 250_000,  # peat by texture
        })
        self.assertEqual((shallow, drained), (250_000, 250_000))
        self.assertEqual(by_group, {"A": 500_000, "D": 500_000})   # texture shares unchanged

    def test_deep_groundwater_and_nodata_leave_the_texture_group(self):
        self._groundwater(west_cm=254, east_cm=255)   # 254 = 254 cm or deeper, 255 = nodata
        pieces, _by_group, shallow, drained = self._pieces()
        self.assertEqual((shallow, drained), (0, 0))
        self.assertEqual({g for g, _c in pieces}, {"A", "D"})

    def test_the_season_picks_its_groundwater_statistic(self):
        self._groundwater(west_cm=30, east_cm=120, statistic="GHG")    # wet: shallow sand
        self._groundwater(west_cm=150, east_cm=200, statistic="GLG")   # dry: deep everywhere
        self.assertEqual(self._pieces("GHG")[2], 250_000)
        self.assertEqual(self._pieces("GLG")[2], 0)


class DrainedLandCoverTests(SimpleTestCase):
    def test_built_up_and_paved_classes_are_drained(self):
        from .soil import is_drained
        for name in ("urban fabric", "discontinuous urban fabric", "industrial or commercial units",
                     "road and rail networks and associated land", "port areas", "airports"):
            with self.subTest(name):
                self.assertTrue(is_drained(name))
        for name in ("pastures", "broad-leaved forest", "green urban areas", "water bodies", None):
            with self.subTest(name):
                self.assertFalse(is_drained(name))
