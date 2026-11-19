"""builtup/calculations/generative.py (neighbourhood generator), its metrics in chain.py and regulations.py."""
from django.test import SimpleTestCase

from builtup.calculations import chain, generative, regulations


def _site(x0=0, y0=0, x1=300, y1=200):
    from shapely.geometry import box
    return box(x0, y0, x1, y1)


def _irregular():
    from shapely.geometry import Polygon
    return Polygon([(0, 0), (320, -20), (360, 180), (150, 260), (-30, 170)])


def _wkts(layout):
    return [b["geom"].wkt for b in layout.buildings]


class GeneratorPinnedLayoutTests(SimpleTestCase):
    """A 300 m x 200 m site: pinned so a change in the geometry fails loudly (GENERATOR_VERSION 2)."""

    TYPOLOGIES = {
        # typology (style plain, variation 0 = the straight reference): (streets, blocks, buildings, dwellings, GFA m², street m²)
        "row": (5, 9, 252, 504, 40824.0, 14976.0),        # 3 floors: two flats per house (dwelling_mode auto)
        "semi": (5, 9, 144, 144, 17280.0, 14976.0),
        "detached": (5, 9, 108, 108, 17280.0, 14976.0),
        "perimeter": (5, 9, 54, 1278, 104832.0, 14976.0),
        "slab": (3, 4, 24, 1272, 101952.0, 11424.0),
    }
    STYLES = {
        # style (default variation 50 %, seed 1): (streets, blocks, buildings, dwellings, GFA m²)
        "plain": (5, 9, 251, 507, 44128.8),
        "vinex": (10, 9, 224, 451, 38596.6),
        "garden_city": (10, 13, 65, 65, 13897.5),
        "urban_block": (5, 9, 64, 1718, 139715.8),
        "modernist": (2, 4, 30, 1019, 82600.5),
    }

    def test_each_typology(self):
        for typology, expected in self.TYPOLOGIES.items():
            with self.subTest(typology):
                layout = generative.generate(_site(), {"typology": typology, "variation": 0})
                m = layout.metrics
                self.assertEqual((len(layout.streets), len(layout.blocks), m["buildings"], m["units"],
                                  m["gfa_m2"], m["street_m2"]), expected)

    def test_each_style(self):
        for style, expected in self.STYLES.items():
            with self.subTest(style):
                layout = generative.generate(_site(), {"style": style})
                m = layout.metrics
                self.assertEqual((len(layout.streets), len(layout.blocks), m["buildings"], m["units"], m["gfa_m2"]),
                                 expected)

    def test_every_style_and_pattern_builds_inside_the_outline(self):
        site = _irregular()
        for style in generative.STYLES:
            for pattern in generative.STREET_PATTERNS:
                with self.subTest(style=style, pattern=pattern):
                    layout = generative.generate(site, {"style": style, "street_pattern": pattern})
                    self.assertGreater(layout.metrics["buildings"], 0)
                    for building in layout.buildings:
                        self.assertTrue(site.buffer(0.01).contains(building["geom"]))

    def test_buildings_stay_off_the_streets(self):
        for style in generative.STYLES:
            layout = generative.generate(_irregular(), {"style": style})
            street_area = [s.buffer(layout.params["street_width"] / 2 - 0.05, cap_style="flat") for s in layout.streets]
            with self.subTest(style):
                for building in layout.buildings:
                    self.assertFalse(any(a.intersects(building["geom"]) for a in street_area))

    def test_same_seed_same_layout_new_seed_new_layout(self):
        a = generative.generate(_irregular(), {"style": "vinex", "seed": 7})
        b = generative.generate(_irregular(), {"style": "vinex", "seed": 7})
        c = generative.generate(_irregular(), {"style": "vinex", "seed": 8})
        self.assertEqual(_wkts(a), _wkts(b))
        self.assertNotEqual(_wkts(a), _wkts(c))

    def test_default_variation_is_half(self):
        self.assertEqual(generative.resolve_params({})["variation"], 0.5)
        for style in generative.STYLES:
            self.assertEqual(generative.resolve_params({"style": style})["variation"], 0.5)

    def test_no_variation_ignores_the_seed(self):
        a = generative.generate(_site(), {"style": "plain", "variation": 0, "seed": 1})
        b = generative.generate(_site(), {"style": "plain", "variation": 0, "seed": 99})
        self.assertEqual(_wkts(a), _wkts(b))

    def test_rotated_site_gives_the_same_layout(self):
        from shapely import affinity
        site = affinity.rotate(_site(), 30, origin="centroid")
        layout = generative.generate(site, {"typology": "row", "variation": 0})
        self.assertAlmostEqual(layout.params["angle_deg"], 30.0, places=4)
        self.assertEqual(layout.metrics["units"], self.TYPOLOGIES["row"][3])

    def test_buildable_area_is_respected(self):
        from shapely.geometry import box
        buildable = _site().difference(box(150, 0, 300, 200))      # the east half is protected
        layout = generative.generate(_site(), {"typology": "row"}, buildable=buildable)
        self.assertGreater(layout.metrics["buildings"], 0)
        for building in layout.buildings:
            self.assertTrue(buildable.buffer(0.01).contains(building["geom"]))
        self.assertEqual(layout.metrics["site_m2"], 30_000)
        self.assertEqual(layout.metrics["outline_m2"], 60_000)
        empty = generative.generate(_site(), {"typology": "row"}, buildable=box(0, 0, 0, 0))
        self.assertEqual(empty.metrics["buildings"], 0)

    def test_floors_follow_the_target(self):
        layout = generative.generate(_site(), {"typology": "perimeter", "target_units": 500, "variation": 0})
        self.assertEqual(layout.params["floors"], 2)
        self.assertGreaterEqual(layout.metrics["units"], 500)
        capped = generative.generate(_site(), {"typology": "perimeter", "target_units": 10**6})
        self.assertEqual(capped.params["floors"], generative.MAX_FLOORS)
        low_rise = generative.generate(_site(), {"typology": "row", "target_units": 10**6})
        self.assertEqual(low_rise.params["floors"], generative.LOW_RISE_MAX_FLOORS)

    def test_resolve_params(self):
        p = generative.resolve_params({"typology": "detached", "floors": "3", "street_width": "", "ring_street": "false"})
        self.assertEqual(p["floors"], 3)
        self.assertEqual(p["street_width"], generative.COMMON["street_width"])
        self.assertFalse(p["ring_street"])
        self.assertEqual(p["block_depth"], 2 * p["plot_depth"])
        self.assertEqual(p["generator_version"], generative.GENERATOR_VERSION)
        styled = generative.resolve_params({"style": "garden_city", "plot_width": 20})
        self.assertEqual((styled["typology"], styled["street_pattern"], styled["plot_width"]), ("detached", "curved", 20.0))
        for bad in ({"typology": "castle"}, {"style": "baroque"}, {"street_pattern": "maze"},
                    {"dwelling_mode": "tent"}, {"street_width": -1}):
            with self.subTest(bad), self.assertRaises(ValueError):
                generative.resolve_params(bad)

    def test_bbl_minimum_dwelling_size_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Bbl"):
            generative.resolve_params({"unit_gfa_m2": 30})


class DwellingsPerBuildingTests(SimpleTestCase):
    """dwelling_mode: auto = one home up to 2 floors for row/semi/detached, flats above; single; stacked."""

    def test_modes(self):
        p = generative.resolve_params({"typology": "row", "unit_gfa_m2": 80})
        self.assertEqual(generative.dwellings(54, 2, "row", p), 1)
        self.assertEqual(generative.dwellings(54, 3, "row", p), 2)            # 162 m² / 80 m²
        self.assertEqual(generative.dwellings(54, 3, "row", {**p, "dwelling_mode": "single"}), 1)
        self.assertEqual(generative.dwellings(54, 2, "row", {**p, "dwelling_mode": "stacked"}), 1)
        self.assertEqual(generative.dwellings(400, 6, "slab", p), 30)

    def test_layouts(self):
        two = generative.generate(_site(), {"typology": "row", "floors": 2, "variation": 0})
        self.assertEqual(two.metrics["units"], two.metrics["buildings"])
        four = generative.generate(_site(), {"typology": "row", "floors": 4, "variation": 0})
        self.assertEqual(four.metrics["max_dwellings_per_building"], 2)        # 216 m² / 80 m²
        self.assertEqual(four.metrics["single_family"], 0)


class RegulationTests(SimpleTestCase):
    def test_minimum_dwelling_size(self):
        self.assertAlmostEqual(regulations.min_unit_gfa_m2(), 18 / 0.55 / 0.8)

    def _building(self, x0, x1, height=9.0, typology="detached", units=1, floors=3):
        from shapely.geometry import box
        return {"geom": box(x0, 0, x1, 10), "floors": floors, "height_m": height, "units": units, "typology": typology}

    def test_fire_spread(self):
        apart = regulations.fire_spread([self._building(0, 10), self._building(15, 25)])
        close = regulations.fire_spread([self._building(0, 10), self._building(13, 23)])
        touching = regulations.fire_spread([self._building(0, 10), self._building(10, 20)])
        self.assertEqual((apart["severity"], close["severity"], touching["severity"]), ("ok", "warn", "ok"))

    def test_daylight_counts_facing_slabs_only(self):
        from shapely.geometry import box
        slab = lambda y: {"geom": box(0, y, 60, y + 12), "floors": 6, "height_m": 18.0, "units": 30, "typology": "slab"}
        self.assertEqual(regulations.daylight_spacing([slab(0), slab(30)])["severity"], "ok")      # 18 m gap
        self.assertEqual(regulations.daylight_spacing([slab(0), slab(25)])["severity"], "warn")    # 13 m gap
        end_to_end = [slab(0), {**slab(0), "geom": box(70, 0, 130, 12)}]                           # end walls 10 m apart
        self.assertEqual(regulations.daylight_spacing(end_to_end)["severity"], "ok")

    def test_too_small_flats_block(self):
        findings = regulations.check([self._building(0, 10, units=5, floors=2)], unit_gfa_m2=80)
        self.assertEqual(next(f for f in findings if f["code"] == "unit_size")["severity"], "block")   # 200 m² / 5


class LayoutMetricsTests(SimpleTestCase):
    def test_equations(self):
        m = chain.layout_metrics(site_m2=10_000, footprints_m2=[100, 200], floors=[2, 3], units=[1, 7],
                                 street_m2=2_000, street_length_m=250, target_units=10)
        self.assertEqual(m["gfa_m2"], 800.0)      # 100 x 2 + 200 x 3
        self.assertEqual(m["far"], 0.08)
        self.assertEqual(m["gsi"], 0.03)
        self.assertEqual(m["units"], 8)
        self.assertEqual(m["units_vs_target"], -2)
        self.assertEqual(m["density_units_ha"], 8.0)
        self.assertEqual(m["street_share"], 0.2)
        self.assertEqual((m["dwellings_per_building"], m["max_dwellings_per_building"]), (4.0, 7))
        self.assertEqual((m["single_family"], m["multi_family"]), (1, 1))

    def test_units_in(self):
        self.assertEqual(chain.units_in(799, 80), 9)
        self.assertEqual(chain.units_in(10, 80), 1)
