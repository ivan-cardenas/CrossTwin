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


class _UrbanFabricTestCase(TestCase):
    """A 1 km x 1 km city covered by one pasture polygon (land-cover year 2024)."""

    def setUp(self):
        square = _square(0, 0, 1000, 1000)
        self.province = Province.objects.create(ProvinceName="P", geom=square)
        self.city = City.objects.create(cityName="C", province=self.province, geom=square)
        self.district = District.objects.create(
            id="D1", districtName="D", city=self.city, geom=square, currentPopulation=0)
        self.neighborhood = Neighborhood.objects.create(
            id="N1", neighborhoodName="N", district=self.district, geom=square, currentPopulation=0)
        self.pasture_class = LandCoverClasses.objects.create(class_name="pastures", description="test")
        self.pasture = LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.pasture_class,
            land_use="Agriculture", geom=square, percentage=100.0)

    def _building(self, pk=-1, x0=490, y0=490, x1=510, y1=510, **kwargs):
        from builtup.models import Building
        return Building.objects.create(id=pk, usageFunction="woonfunctie", geom=_square(x0, y0, x1, y1), **kwargs)

    def _urban_fabric(self):
        return LandCoverVector.objects.filter(land_cover_type__class_name__iexact="urban fabric")


class BuildingUrbanFabricBufferTests(_UrbanFabricTestCase):
    """physicalEnv.signals.building_created -> landcover.urbanize_around (DAG edge New_Units -> LandCover)."""

    def test_buffer_is_cut_out_and_inserted_as_urban_fabric(self):
        self._building()

        ring = self._urban_fabric().get()
        # 20 m x 20 m footprint + 10 m: 400 + 4*200 + pi*100 (rounded corners, segmented)
        self.assertAlmostEqual(ring.geom.area, 1514.2, delta=5)
        self.assertEqual(ring.year, 2024)
        self.assertEqual(ring.city_id, self.city.pk)
        self.assertEqual(ring.land_use, "Residential")
        self.assertAlmostEqual(ring.percentage, ring.geom.area / 1e6 * 100, places=6)

        self.pasture.refresh_from_db()
        self.assertAlmostEqual(self.pasture.geom.area + ring.geom.area, 1e6, delta=0.01)   # no overlap
        self.assertAlmostEqual(self.pasture.geom.intersection(ring.geom).area, 0, delta=0.01)
        self.assertAlmostEqual(self.pasture.percentage, self.pasture.geom.area / 1e6 * 100, places=6)

        self.neighborhood.refresh_from_db()
        self.city.refresh_from_db()
        self.assertAlmostEqual(self.neighborhood.urban_area, ring.geom.area / 1e6, places=6)
        self.assertAlmostEqual(self.city.urban_area, ring.geom.area / 1e6, places=6)

    def test_an_existing_urban_fabric_class_is_reused(self):
        existing = LandCoverClasses.objects.create(class_name="Urban fabric", description="BRT")
        self._building()
        self.assertEqual(self._urban_fabric().get().land_cover_type, existing)

    def test_a_polygon_inside_the_buffer_is_deleted(self):
        small = LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.pasture_class,
            land_use="Agriculture", geom=_square(495, 495, 505, 505), percentage=0.01)
        self._building()
        self.assertFalse(LandCoverVector.objects.filter(pk=small.pk).exists())

    def test_the_buffer_is_clipped_to_the_city(self):
        self._building(x0=0, y0=0, x1=20, y1=20)   # in the corner: the buffer sticks out on two sides
        ring = self._urban_fabric().get()
        self.assertTrue(self.city.geom.buffer(0.01).contains(ring.geom))
        # 30 m x 30 m with the outer corner rounded: 900 - (100 - pi*100/4)
        self.assertAlmostEqual(ring.geom.area, 878.5, delta=1)

    def test_older_years_are_left_alone(self):
        old = LandCoverVector.objects.create(
            city=self.city, year=2018, land_cover_type=self.pasture_class,
            land_use="Agriculture", geom=_square(0, 0, 1000, 1000), percentage=100.0)
        self._building()
        old.refresh_from_db()
        self.assertAlmostEqual(old.geom.area, 1e6)

    def test_imported_and_resaved_buildings_do_not_change_the_land_cover(self):
        imported = self._building(pk=1234)      # BAG id
        self.assertFalse(self._urban_fabric().exists())

        drawn = self._building(pk=-1, x0=100, y0=100, x1=120, y1=120)
        self.assertEqual(self._urban_fabric().count(), 1)
        drawn.geom = _square(700, 700, 720, 720)
        drawn.save()                            # a move does not add a second ring
        imported.save()
        self.assertEqual(self._urban_fabric().count(), 1)

    def test_raw_saves_are_ignored(self):
        from builtup.models import Building
        from physicalEnv import signals
        building = Building(id=-5, usageFunction=["Residential function"], buildingType="residential",
                            geom=_square(490, 490, 510, 510))
        signals.building_created(Building, building, created=True, raw=True)
        self.assertFalse(self._urban_fabric().exists())

    def test_a_city_without_land_cover_is_a_no_op(self):
        LandCoverVector.objects.all().delete()
        building = self._building()
        self.assertTrue(type(building).objects.filter(pk=-1).exists())
        self.assertFalse(LandCoverVector.objects.exists())

    def test_the_ring_and_its_cuts_record_the_building(self):
        from .models import UrbanFabricCut
        self._building()
        ring = self._urban_fabric().get()
        self.assertEqual(ring.source_building, -1)
        cut = UrbanFabricCut.objects.get()
        self.assertEqual((cut.owner_building, cut.target), (-1, self.pasture.pk))
        self.assertEqual(cut.land_cover_type, self.pasture_class)
        self.assertAlmostEqual(cut.geom.area, ring.geom.area, delta=0.01)


class BuildingUrbanFabricReleaseTests(_UrbanFabricTestCase):
    """Moving or deleting an editor building gives its ring's land back (landcover.release_ring)."""

    def assertCovered(self, total=1e6):
        """The layer still tiles the city: areas add up and no two polygons overlap."""
        polygons = list(LandCoverVector.objects.filter(year=2024))
        self.assertAlmostEqual(sum(p.geom.area for p in polygons), total, delta=0.5)
        for i, a in enumerate(polygons):
            for b in polygons[i + 1:]:
                self.assertAlmostEqual(a.geom.intersection(b.geom).area, 0, delta=0.01, msg=(a.pk, b.pk))

    def _pasture_area(self):
        return sum(p.geom.area for p in LandCoverVector.objects.filter(land_cover_type=self.pasture_class))

    def test_deleting_the_building_gives_the_land_back(self):
        from .models import UrbanFabricCut
        self._building().delete()
        self.assertFalse(self._urban_fabric().exists())
        self.assertFalse(UrbanFabricCut.objects.exists())
        self.pasture.refresh_from_db()
        self.assertAlmostEqual(self.pasture.geom.area, 1e6, delta=0.5)
        self.assertAlmostEqual(self.pasture.percentage, 100.0, places=3)
        self.neighborhood.refresh_from_db()
        self.assertAlmostEqual(self.neighborhood.urban_area, 0.0, places=9)

    def test_moving_the_building_moves_the_ring(self):
        building = self._building()
        building.geom = _square(100, 100, 120, 120)
        building.save()

        ring = self._urban_fabric().get()
        self.assertTrue(ring.geom.contains(building.geom))
        self.assertFalse(ring.geom.intersects(_square(490, 490, 510, 510)))
        self.assertAlmostEqual(self._pasture_area() + ring.geom.area, 1e6, delta=0.5)
        self.assertCovered()

    def test_an_attribute_edit_keeps_the_ring(self):
        building = self._building()
        ring = self._urban_fabric().get()
        building.name = "Renamed"
        building.save()
        self.assertEqual(self._urban_fabric().get().pk, ring.pk)

    def test_a_swallowed_polygon_comes_back_with_its_id(self):
        small = LandCoverVector.objects.create(
            city=self.city, year=2024, land_cover_type=self.pasture_class,
            land_use="Agriculture", geom=_square(495, 495, 505, 505), percentage=0.01)
        self._building().delete()
        small_back = LandCoverVector.objects.get(pk=small.pk)
        self.assertAlmostEqual(small_back.geom.area, 100, delta=0.01)
        self.assertEqual(small_back.land_use, "Agriculture")
        self.assertAlmostEqual(self._pasture_area(), 1e6 + 100, delta=0.5)   # as before the building

    def test_overlapping_rings_released_in_either_order(self):
        for first, second in ((-1, -2), (-2, -1)):
            with self.subTest(first=first):
                a = self._building(pk=-1, x0=490, y0=490, x1=510, y1=510)
                b = self._building(pk=-2, x0=515, y0=490, x1=535, y1=510)   # rings overlap by ~15 m
                self.assertCovered()
                buildings = {-1: a, -2: b}

                buildings[first].delete()
                remaining = self._urban_fabric().get()
                self.assertEqual(remaining.source_building, second)
                # the survivor keeps its full buffer
                expected = buildings[second].geom.buffer(10)
                self.assertAlmostEqual(remaining.geom.area, expected.area, delta=5)
                self.assertCovered()

                buildings[second].delete()
                self.assertFalse(self._urban_fabric().exists())
                self.assertAlmostEqual(self._pasture_area(), 1e6, delta=0.5)
                self.assertCovered()

    def test_a_ring_swallowed_by_a_later_one(self):
        from .models import UrbanFabricCut
        small = self._building(pk=-1, x0=495, y0=495, x1=505, y1=505)
        big = self._building(pk=-2, x0=470, y0=470, x1=530, y1=530)   # its buffer covers small's ring
        self.assertEqual(self._urban_fabric().get().source_building, -2)

        small.delete()   # its ring is already gone: only the bookkeeping changes
        self.assertEqual(self._urban_fabric().get().source_building, -2)
        self.assertFalse(UrbanFabricCut.objects.filter(owner_building=-1).exists())
        self.assertFalse(UrbanFabricCut.objects.filter(source_building=-1).exists())

        big.delete()     # the land under both rings goes back to pasture
        self.assertFalse(self._urban_fabric().exists())
        self.assertAlmostEqual(self._pasture_area(), 1e6, delta=0.5)
        self.assertCovered()

    def test_imported_buildings_never_release_land(self):
        imported = self._building(pk=1234)
        drawn = self._building(pk=-1, x0=100, y0=100, x1=120, y1=120)
        imported.delete()
        self.assertEqual(self._urban_fabric().get().source_building, drawn.pk)

    def test_a_failing_release_does_not_block_the_delete(self):
        from builtup.models import Building
        from physicalEnv import signals
        building = self._building()
        with mock.patch.object(signals, "release_ring", side_effect=RuntimeError("boom")), \
                self.assertLogs("physicalEnv.signals", "ERROR"):
            building.delete()
        self.assertFalse(Building.objects.filter(pk=-1).exists())

    def test_a_failing_overlay_does_not_block_the_building(self):
        from physicalEnv import signals
        with mock.patch.object(signals, "urbanize_around", side_effect=RuntimeError("boom")), \
                self.assertLogs("physicalEnv.signals", "ERROR"):
            building = self._building()
        self.assertTrue(type(building).objects.filter(pk=-1).exists())


class SkyViewFactorTests(TestCase):
    """physicalEnv/svf.py: DSM -> SVF horizon search."""

    def test_flat_surface_sees_the_whole_sky(self):
        import numpy as np
        from .svf import sky_view_factor

        svf = sky_view_factor(np.full((20, 20), 30.0), cell_size=1.0, radius_pixels=5)
        np.testing.assert_allclose(svf, 1.0, atol=1e-6)

    def test_pit_sees_less_sky_and_is_scaled_by_cell_size(self):
        import numpy as np
        from .svf import sky_view_factor

        dsm = np.zeros((21, 21))
        dsm[:, :] = 10.0
        dsm[8:13, 8:13] = 0.0  # 5 x 5 cells, 10 m deep
        fine = sky_view_factor(dsm, cell_size=1.0, radius_pixels=8)[10, 10]
        coarse = sky_view_factor(dsm, cell_size=10.0, radius_pixels=8)[10, 10]
        self.assertLess(fine, 0.5)
        # Same heights over 10x wider cells: a much shallower pit.
        self.assertGreater(coarse, fine)
        # Wall 10 m high, 30 m away: horizon atan(1/3), SVF ~ 1 - sin(18.4 deg).
        self.assertAlmostEqual(float(coarse), 0.68, delta=0.05)

    def test_nodata_stays_nodata_and_is_not_a_horizon(self):
        import numpy as np
        from .svf import sky_view_factor

        dsm = np.full((15, 15), 5.0)
        dsm[7, 7] = -9999.0
        svf = sky_view_factor(dsm, cell_size=1.0, radius_pixels=4, no_data=-9999.0)
        self.assertTrue(np.isnan(svf[7, 7]))
        self.assertAlmostEqual(float(svf[7, 8]), 1.0, places=5)

    def test_blocks_match_a_single_pass(self):
        import numpy as np
        from .svf import sky_view_factor

        rng = np.random.default_rng(0)
        dsm = rng.uniform(0, 20, (40, 30))
        whole = sky_view_factor(dsm, cell_size=1.0, radius_pixels=6, block_rows=1000)
        blocked = sky_view_factor(dsm, cell_size=1.0, radius_pixels=6, block_rows=7)
        np.testing.assert_array_equal(whole, blocked)

    @mock.patch("core.rasterOperations.export_raster_to_cog")
    def test_calculate_svf_stores_a_sky_view_factor_raster(self, _cog):
        import numpy as np
        from django.conf import settings
        from django.contrib.gis.gdal import GDALRaster

        from urban_heat.models import SkyViewFactor
        from .models import DigitalSurfaceModel
        from .svf import NODATA, calculate_svf

        data = np.full((12, 10), 3.0, dtype="float32")
        data[0, 0] = -1.0
        dsm = DigitalSurfaceModel.objects.create(
            year=2024, source="AHN4", resolution=2.0,
            dsm_raster=GDALRaster({
                "srid": int(settings.COORDINATE_SYSTEM), "width": 10, "height": 12,
                "origin": (250000.0, 470000.0), "scale": (2.0, -2.0), "datatype": 6,
                "bands": [{"data": data, "nodata_value": -1.0}],
            }),
        )

        record = calculate_svf(dsm, radius_m=6).record

        self.assertEqual(SkyViewFactor.objects.count(), 1)
        self.assertEqual(record.resolution, 2.0)
        self.assertIn("r=6 m", record.measurement_method)
        stored = SkyViewFactor.objects.get(pk=record.pk).raster
        self.assertEqual((stored.width, stored.height), (10, 12))
        self.assertEqual(tuple(stored.origin), (250000.0, 470000.0))
        values = stored.bands[0].data()
        self.assertEqual(values[0, 0], NODATA)
        self.assertAlmostEqual(float(values[5, 5]), 1.0, places=5)

    def test_cog_path_divides_heights_by_the_source_cell_size(self):
        """A COG in degrees: the cell size comes from the file, not dsm.resolution."""
        import os
        import tempfile

        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        from .models import DigitalSurfaceModel
        from .svf import dsm_extent, load_dsm

        # ~1 m cells near Enschede: 1e-5 deg lat ~ 1.11 m, 1.5e-5 deg lng ~ 1.02 m.
        path = os.path.join(tempfile.mkdtemp(), "dsm_4326.tif")
        with rasterio.open(path, "w", driver="GTiff", width=200, height=200, count=1,
                           dtype="float32", crs="EPSG:4326", nodata=-9999.0,
                           transform=from_origin(6.89, 52.22, 1.5e-5, 1e-5)) as dst:
            dst.write(np.full((200, 200), 40.0, dtype="float32"), 1)
        dsm = DigitalSurfaceModel(pk=1, year=2024, resolution=0.5, cog_path=path)

        height, _, cell, _ = load_dsm(dsm, dsm_extent(dsm))
        self.assertAlmostEqual(cell, 1.06, delta=0.1)  # not the stated 0.5 m
        self.assertTrue(np.nanmax(height) == 40.0)
        _, _, forced, _ = load_dsm(dsm, dsm_extent(dsm), resolution=2.0)
        self.assertEqual(forced, 2.0)


def _stored_dsm(data, origin=(250000.0, 470000.0), cell=1.0, year=2024):
    """A DigitalSurfaceModel with its raster stored in Postgres."""
    import numpy as np
    from django.conf import settings
    from django.contrib.gis.gdal import GDALRaster

    from .models import DigitalSurfaceModel

    data = np.ascontiguousarray(data, dtype="float32")
    return DigitalSurfaceModel.objects.create(
        year=year, source="AHN4", resolution=cell,
        dsm_raster=GDALRaster({
            "srid": int(settings.COORDINATE_SYSTEM), "width": data.shape[1],
            "height": data.shape[0], "origin": origin, "scale": (cell, -cell),
            "datatype": 6, "bands": [{"data": data, "nodata_value": -9999.0}],
        }),
    )


def _city_blocks(rows=80, cols=80):
    """Flat ground at 0 m with 20 m high blocks every 10 cells."""
    import numpy as np

    data = np.zeros((rows, cols), dtype="float32")
    for r in range(2, rows, 10):
        for c in range(2, cols, 10):
            data[r:r + 5, c:c + 5] = 20.0
    return data


@mock.patch("core.rasterOperations.export_raster_to_cog")
class SkyViewFactorViewWindowTests(TestCase):
    """calculate_svf reads only the view + a halo, and replaces on recalculation."""

    def test_reads_only_the_view_plus_one_radius(self, _cog):
        from . import svf

        dsm = _stored_dsm(_city_blocks())
        view = (250020.0, 469940.0, 250040.0, 469960.0)  # 20 x 20 cells inside
        with mock.patch.object(svf, "load_dsm", wraps=svf.load_dsm) as load:
            result = svf.calculate_svf(bbox=view, radius_m=5)
        window = load.call_args.args[1]
        self.assertEqual(window, (250015.0, 469935.0, 250045.0, 469965.0))
        self.assertEqual((result.width, result.height), (20, 20))
        self.assertEqual(result.dsm, dsm)
        self.assertEqual(tuple(result.record.raster.extent), view)

    def test_view_result_equals_the_full_dsm_result_inside_the_view(self, _cog):
        import numpy as np

        from .svf import calculate_svf, sky_view_factor

        data = _city_blocks()
        dsm = _stored_dsm(data)
        full = sky_view_factor(data, 1.0, radius_pixels=8)
        result = calculate_svf(dsm, bbox=(250020.0, 469940.0, 250040.0, 469960.0), radius_m=8)
        view = result.record.raster.bands[0].data()
        # rows 40..60 from the top (y 469960 -> 469940), columns 20..40
        np.testing.assert_allclose(view, full[40:60, 20:40], atol=1e-6)

    def test_recalculating_replaces_the_rows_inside_the_new_view(self, _cog):
        from urban_heat.models import SkyViewFactor

        from .svf import calculate_svf

        dsm = _stored_dsm(_city_blocks())
        small = calculate_svf(dsm, bbox=(250020.0, 469940.0, 250030.0, 469950.0), radius_m=5).record
        elsewhere = calculate_svf(dsm, bbox=(250060.0, 469930.0, 250070.0, 469940.0), radius_m=5).record
        other_dsm = _stored_dsm(_city_blocks(), year=2020)
        foreign = calculate_svf(other_dsm, bbox=(250020.0, 469940.0, 250030.0, 469950.0), radius_m=5).record

        again = calculate_svf(dsm, bbox=(250010.0, 469930.0, 250040.0, 469960.0), radius_m=5)

        self.assertEqual(again.replaced, [small.pk])
        self.assertSetEqual(set(SkyViewFactor.objects.values_list("pk", flat=True)),
                            {elsewhere.pk, foreign.pk, again.record.pk})

    def test_picks_the_dsm_covering_most_of_the_view(self, _cog):
        from .svf import dsm_for_view

        _stored_dsm(_city_blocks(20, 20), year=2025)  # newer, covers a corner only
        big = _stored_dsm(_city_blocks(), year=2020)
        dsm, covered = dsm_for_view((250010.0, 469930.0, 250050.0, 469970.0))
        self.assertEqual(dsm, big)
        self.assertEqual(covered, (250010.0, 469930.0, 250050.0, 469970.0))

    def test_refuses_a_view_above_the_cell_limit(self, _cog):
        from . import svf

        dsm = _stored_dsm(_city_blocks())
        with mock.patch.object(svf, "MAX_CELLS", 100):
            with self.assertRaisesMessage(svf.SVFError, "zoom in"):
                svf.calculate_svf(dsm, bbox=(250020.0, 469940.0, 250040.0, 469960.0), radius_m=5)

    def test_no_dsm_for_the_view(self, _cog):
        from .svf import SVFError, calculate_svf

        _stored_dsm(_city_blocks())
        with self.assertRaisesMessage(SVFError, "No Digital Surface Model"):
            calculate_svf(bbox=(100000.0, 400000.0, 100100.0, 400100.0))


@mock.patch("core.rasterOperations.export_raster_to_cog")
class SkyViewFactorToolViewTests(TestCase):
    """physicalEnv/views.py: the map's SVF tool endpoints."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.contrib.gis.geos import Polygon

        self.dsm = _stored_dsm(_city_blocks())
        # The middle 20 x 20 m of the DSM, as the map sends it (WGS84).
        box = Polygon.from_bbox((250020.0, 469940.0, 250040.0, 469960.0))
        from django.conf import settings
        box.srid = int(settings.COORDINATE_SYSTEM)
        box.transform(4326)
        w, s, e, n = box.extent
        # Shrink a little so the reprojected box stays inside the DSM.
        dx, dy = (e - w) * 0.05, (n - s) * 0.05
        self.bbox = f"{w + dx:.7f},{s + dy:.7f},{e - dx:.7f},{n - dy:.7f}"
        self.staff = get_user_model().objects.create_user("svf_staff", password="x", is_staff=True)

    def test_info_reports_the_dsm_and_existing_svf(self, _cog):
        url = "/physicalEnv/svf/info/"
        data = self.client.get(url, {"bbox": self.bbox, "radius": 5}).json()
        self.assertEqual(data["dsm"]["id"], self.dsm.pk)
        self.assertEqual(data["existing"], [])
        self.assertFalse(data["can_calculate"])

        self.client.force_login(self.staff)
        self.client.post("/physicalEnv/svf/calculate/", {"bbox": self.bbox, "radius": 5})
        data = self.client.get(url, {"bbox": self.bbox, "radius": 5}).json()
        self.assertEqual(len(data["existing"]), 1)
        self.assertTrue(data["can_calculate"])

    def test_calculate_is_staff_only(self, _cog):
        from urban_heat.models import SkyViewFactor

        response = self.client.post("/physicalEnv/svf/calculate/", {"bbox": self.bbox})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SkyViewFactor.objects.exists())

    def test_calculate_and_recalculate(self, _cog):
        self.client.force_login(self.staff)
        first = self.client.post("/physicalEnv/svf/calculate/", {"bbox": self.bbox, "radius": 5})
        self.assertEqual(first.status_code, 200, first.content)
        second = self.client.post("/physicalEnv/svf/calculate/", {"bbox": self.bbox, "radius": 10}).json()
        self.assertEqual(second["replaced"], [first.json()["id"]])
        self.assertEqual(second["dsm"]["id"], self.dsm.pk)
        self.assertGreater(second["valid_fraction"], 0.99)

    def test_bad_parameters_are_400(self, _cog):
        self.client.force_login(self.staff)
        for params in ({"bbox": "1,2,3"}, {"bbox": self.bbox, "radius": "1000"},
                       {"bbox": "0,0,0.001,0.001"}):
            response = self.client.post("/physicalEnv/svf/calculate/", params)
            self.assertEqual(response.status_code, 400, params)
            self.assertIn("error", response.json())


class DsmBuildingPatchOverlayTests(TestCase):
    """dsm_patches.apply_patches: DAG edge Buildings -> DSM, applied when the DSM is read."""

    def _square(self, x, y, half):
        from django.conf import settings
        return MultiPolygon(Polygon(((x - half, y - half), (x + half, y - half), (x + half, y + half),
                                     (x - half, y + half), (x - half, y - half))), srid=settings.COORDINATE_SYSTEM)

    def test_load_dsm_clears_the_old_footprint_and_raises_the_new_one(self):
        import numpy as np

        from . import svf
        from .models import DSMBuildingPatch

        data = np.full((80, 80), 5.0, dtype="float32")
        data[10:20, 10:20] = 25.0                                  # building at x 250010..20, y 469980..90
        dsm = _stored_dsm(data)
        DSMBuildingPatch.objects.create(
            building_id=1, original_footprint=self._square(250015, 469985, 5),
            footprint=self._square(250055, 469945, 5), height_m=12.0)

        height, origin, cell, _ = svf.load_dsm(dsm, (250000.0, 469920.0, 250080.0, 470000.0))
        self.assertEqual(origin, (250000.0, 470000.0))
        np.testing.assert_allclose(height[10:20, 10:20], 5.0)      # cleared to the (estimated) ground
        np.testing.assert_allclose(height[50:60, 50:60], 17.0)     # ground 5 + 12 m
        raw, *_ = svf.load_dsm(dsm, (250000.0, 469920.0, 250080.0, 470000.0), patches=False)
        self.assertEqual(float(raw[15, 15]), 25.0)

    def test_without_patches_the_grid_is_unchanged(self):
        import numpy as np

        from .dsm_patches import apply_patches

        grid = np.ones((4, 4), dtype="float32")
        self.assertIs(apply_patches(grid, (0.0, 4.0), 1.0, 28992), grid)
