"""Vegetation_Coverage -> DSM: tree and forest changes as a DSM overlay (physicalEnv/calculations/dsm_patches.py)."""
from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase

SRID = int(settings.COORDINATE_SYSTEM)
ORIGIN = (250000.0, 470000.0)    # upper-left; 1 m cells; 60 x 60 grid
GROUND = 5.0


def _rect(x0, y0, x1, y1):
    return MultiPolygon(Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))), srid=SRID)


def _cell_xy(row, col):
    return ORIGIN[0] + col + 0.5, ORIGIN[1] - row - 0.5


def _grid():
    """Flat ground at 5 m with a 10 m tall canopy on rows/cols 10..20 and a 20 m building on 40..50."""
    import numpy as np

    data = np.full((60, 60), GROUND, dtype="float32")
    data[10:20, 10:20] = GROUND + 10
    data[40:50, 40:50] = GROUND + 20
    return data


def _apply(data):
    import numpy as np

    from physicalEnv.calculations.dsm_patches import apply_patches

    ground = np.full(data.shape, GROUND, dtype="float32")
    return apply_patches(data, ORIGIN, 1.0, SRID, ground=ground)


class VegetationOverlayTests(TestCase):
    def setUp(self):
        from builtup.models import Building

        x, y = _cell_xy(50, 40)
        Building.objects.create(id=1, height_m=20, geom=_rect(x - 0.5, y + 0.5, x + 9.5, y + 10.5))

    def patch(self, **kw):
        from physicalEnv.models import DSMVegetationPatch

        return DSMVegetationPatch.objects.create(source_id=kw.pop("source_id", 1), **kw)

    def test_a_felled_tree_clears_only_tall_vegetation_outside_buildings(self):
        cx, cy = _cell_xy(15, 15)
        crown = MultiPolygon(Point(cx, cy, srid=SRID).buffer(8), srid=SRID)
        self.patch(source="nature.Tree", original_geom=crown, geom=None, canopy_m=None)
        out = _apply(_grid())
        self.assertEqual(float(out[15, 15]), GROUND)
        self.assertEqual(float(out[11, 11]), GROUND)

    def test_clearing_never_lowers_a_building(self):
        bx, by = _cell_xy(45, 45)
        self.patch(source="nature.Forests", original_geom=_rect(bx - 10, by - 10, bx + 10, by + 10), geom=None)
        out = _apply(_grid())
        self.assertEqual(float(out[45, 45]), GROUND + 20)

    def test_a_planted_tree_gets_a_paraboloid_crown(self):
        from physicalEnv.calculations.dsm_patches import CROWN_EDGE_FRACTION, crown_heights

        cx, cy = _cell_xy(30, 30)
        crown = MultiPolygon(Point(cx, cy, srid=SRID).buffer(4, quadsegs=16), srid=SRID)
        self.patch(source="nature.Tree", original_geom=None, geom=crown, canopy_m=12)
        out = _apply(_grid())
        self.assertAlmostEqual(float(out[30, 30]), GROUND + 12, delta=0.2)     # the top
        edge = float(out[30, 33])
        self.assertGreaterEqual(edge, GROUND + 12 * CROWN_EDGE_FRACTION - 1e-4)
        self.assertLess(edge, float(out[30, 30]))
        self.assertEqual(float(out[30, 38]), GROUND)                           # outside the crown
        import numpy as np
        heights = crown_heights(crown, 12, ORIGIN, 1.0, (60, 60))
        self.assertTrue(np.isnan(heights[0, 0]))

    def test_planting_never_lowers_a_taller_surface(self):
        cx, cy = _cell_xy(15, 15)
        crown = MultiPolygon(Point(cx, cy, srid=SRID).buffer(3), srid=SRID)
        self.patch(source="nature.Tree", original_geom=None, geom=crown, canopy_m=4)
        self.assertEqual(float(_apply(_grid())[15, 15]), GROUND + 10)

    def test_a_reshaped_forest_clears_what_it_lost_and_plants_what_it_gained(self):
        from physicalEnv.calculations.dsm_patches import DEFAULT_FOREST_CANOPY_M

        x0, y0 = ORIGIN[0] + 10, ORIGIN[1] - 20          # the canopy block, rows/cols 10..20
        old = _rect(x0, y0, x0 + 10, y0 + 10)
        new = _rect(x0 + 5, y0, x0 + 25, y0 + 10)         # gave up cols 10..15, gained cols 20..35
        self.patch(source="nature.Forests", original_geom=old, geom=new, canopy_m=DEFAULT_FOREST_CANOPY_M)
        out = _apply(_grid())
        self.assertEqual(float(out[15, 12]), GROUND)                            # lost: cleared
        self.assertEqual(float(out[15, 17]), GROUND + 10)                       # kept: measured canopy
        self.assertEqual(float(out[15, 30]), GROUND + DEFAULT_FOREST_CANOPY_M)  # gained: planted

    def test_a_new_roof_wins_over_a_crown(self):
        from physicalEnv.models import DSMBuildingPatch

        cx, cy = _cell_xy(30, 30)
        self.patch(source="nature.Tree", original_geom=None,
                   geom=MultiPolygon(Point(cx, cy, srid=SRID).buffer(5), srid=SRID), canopy_m=15)
        DSMBuildingPatch.objects.create(building_id=-1, original_footprint=None,
                                        footprint=_rect(cx - 2, cy - 2, cx + 2, cy + 2), height_m=6)
        out = _apply(_grid())
        self.assertEqual(float(out[30, 30]), GROUND + 6)
        self.assertGreater(float(out[30, 34]), GROUND + 6)    # crown still around the roof

    def test_a_tree_may_grow_where_a_building_was_demolished(self):
        from builtup.models import Building
        from physicalEnv.models import DSMBuildingPatch

        building = Building.objects.get(id=1)
        DSMBuildingPatch.objects.create(building_id=1, original_footprint=building.geom, footprint=None)
        building.delete()
        cx, cy = _cell_xy(45, 45)
        self.patch(source="nature.Tree", original_geom=None,
                   geom=MultiPolygon(Point(cx, cy, srid=SRID).buffer(3), srid=SRID), canopy_m=8)
        out = _apply(_grid())
        self.assertAlmostEqual(float(out[45, 45]), GROUND + 8, delta=0.5)
        self.assertEqual(float(out[41, 41]), GROUND)


class BuildingTreeClearanceTests(TestCase):
    """A new or moved building clears tall vegetation within TREE_CLEARANCE_M (10 m) of its footprint."""

    def setUp(self):
        from builtup.models import Building

        x, y = _cell_xy(50, 40)
        Building.objects.create(id=1, height_m=20, geom=_rect(x - 0.5, y + 0.5, x + 9.5, y + 10.5))

    def building_patch(self, footprint, original=None, height_m=6, building_id=-1):
        from physicalEnv.models import DSMBuildingPatch

        return DSMBuildingPatch.objects.create(building_id=building_id, original_footprint=original,
                                               footprint=footprint, height_m=height_m)

    @staticmethod
    def _footprint_below_canopy():
        """Cells rows 22..25, cols 12..15: the canopy's lower edge (row 19) is 2.5 m away, row 11 is 10.5 m."""
        return _rect(ORIGIN[0] + 12, ORIGIN[1] - 26, ORIGIN[0] + 16, ORIGIN[1] - 22)

    def test_a_new_building_clears_the_canopy_within_10_m(self):
        self.building_patch(self._footprint_below_canopy())
        out = _apply(_grid())
        self.assertEqual(float(out[19, 14]), GROUND)          # 2.5 m from the footprint
        self.assertEqual(float(out[12, 14]), GROUND)          # 9.5 m
        self.assertEqual(float(out[11, 14]), GROUND + 10)     # 10.5 m: kept
        self.assertEqual(float(out[24, 14]), GROUND + 6)      # the new roof

    def test_a_height_only_change_keeps_the_trees(self):
        footprint = self._footprint_below_canopy()
        self.building_patch(footprint, original=footprint, height_m=9)
        out = _apply(_grid())
        self.assertEqual(float(out[19, 14]), GROUND + 10)

    def test_a_moved_building_clears_around_its_new_footprint(self):
        old = _rect(ORIGIN[0] + 30, ORIGIN[1] - 26, ORIGIN[0] + 34, ORIGIN[1] - 22)
        self.building_patch(self._footprint_below_canopy(), original=old)
        out = _apply(_grid())
        self.assertEqual(float(out[19, 14]), GROUND)

    def test_the_clearance_never_lowers_a_stored_building(self):
        # 5 m above the stored 20 m building on rows/cols 40..49
        self.building_patch(_rect(ORIGIN[0] + 40, ORIGIN[1] - 35, ORIGIN[0] + 45, ORIGIN[1] - 30))
        out = _apply(_grid())
        self.assertEqual(float(out[42, 42]), GROUND + 20)

    def test_a_tree_planted_next_to_the_new_building_is_kept(self):
        from physicalEnv.models import DSMVegetationPatch

        self.building_patch(self._footprint_below_canopy())
        cx, cy = _cell_xy(17, 14)
        DSMVegetationPatch.objects.create(source="nature.Tree", source_id=1, original_geom=None,
                                          geom=MultiPolygon(Point(cx, cy, srid=SRID).buffer(2), srid=SRID),
                                          canopy_m=8)
        out = _apply(_grid())
        self.assertAlmostEqual(float(out[17, 14]), GROUND + 8, delta=0.5)
        self.assertEqual(float(out[13, 14]), GROUND)          # the measured canopy around it is cleared

    def test_a_footprint_just_outside_the_window_still_clears_inside_it(self):
        # a footprint 5 m west of a 3-column window: no part of it lies inside the window
        import numpy as np

        from physicalEnv.calculations.dsm_patches import apply_patches

        self.building_patch(_rect(ORIGIN[0] - 9, ORIGIN[1] - 20, ORIGIN[0] - 5, ORIGIN[1] - 10))
        data = np.full((60, 3), GROUND + 10, dtype="float32")
        out = apply_patches(data, ORIGIN, 1.0, SRID, ground=np.full(data.shape, GROUND, dtype="float32"))
        self.assertEqual(float(out[15, 0]), GROUND)           # 5.5 m from the footprint
        self.assertEqual(float(out[15, 2]), GROUND)           # 7.5 m
        self.assertEqual(float(out[0, 0]), GROUND + 10)       # ~11 m (corner): kept

    def test_the_logged_edit_area_covers_the_clearance(self):
        from physicalEnv.models import DSMEdit

        footprint = self._footprint_below_canopy()
        self.building_patch(footprint)
        x0, y0, x1, y1 = DSMEdit.objects.latest("pk").area.extent
        fx0, fy0, fx1, fy1 = footprint.extent
        self.assertEqual((x0, y0, x1, y1), (fx0 - 10, fy0 - 10, fx1 + 10, fy1 + 10))


class VegetationReceiverTests(TestCase):
    """Editor changes of trees and forests record a DSMVegetationPatch; imports do not."""

    def setUp(self):
        from nature.models import Tree

        self.tree = Tree.objects.create(height_m=12, crownDiameter_m=8, geom=Point(250030, 469970, srid=SRID))

    def patch(self, source="nature.Tree", pk=None):
        from physicalEnv.models import DSMVegetationPatch
        return DSMVegetationPatch.objects.filter(source=source, source_id=pk or self.tree.pk).first()

    def test_imports_and_plain_saves_record_nothing(self):
        self.tree.height_m = 20
        self.tree.save()
        self.assertIsNone(self.patch())

    def test_moving_a_tree_records_old_and_new_crown_and_an_edit(self):
        from core.editing import editor_change
        from physicalEnv.models import DSMEdit

        self.tree.geom = Point(250040, 469970, srid=SRID)
        with editor_change():
            self.tree.save()
        patch = self.patch()
        self.assertAlmostEqual(patch.original_geom.centroid.x, 250030, places=3)
        self.assertAlmostEqual(patch.geom.centroid.x, 250040, places=3)
        self.assertAlmostEqual(patch.canopy_m, 12)
        self.assertAlmostEqual(patch.geom.area, 3.14159 * 16, delta=2)      # 8 m crown
        self.assertTrue(DSMEdit.objects.exists())

    def test_an_attribute_only_edit_records_nothing(self):
        from core.editing import editor_change

        self.tree.species = "Tilia x europaea"
        with editor_change():
            self.tree.save()
        self.assertIsNone(self.patch())

    def test_a_drawn_then_deleted_tree_leaves_no_patch(self):
        from core.editing import editor_change
        from nature.models import Tree
        from physicalEnv.models import DSMVegetationPatch

        with editor_change():
            tree = Tree.objects.create(geom=Point(250010, 469990, srid=SRID))
        pk = tree.pk
        patch = self.patch(pk=pk)
        self.assertIsNone(patch.original_geom)
        self.assertEqual(patch.canopy_m, 10.0)                       # DEFAULT_TREE_HEIGHT_M
        with editor_change():
            tree.delete()                                            # (clears tree.pk)
        self.assertFalse(DSMVegetationPatch.objects.filter(source_id=pk).exists())

    def test_a_deleted_forest_clears_its_polygon(self):
        from core.editing import editor_change
        from nature.models import Forests

        forest = Forests.objects.create(name="Bos", geom=_rect(250000, 469900, 250050, 469950))
        pk = forest.pk
        with editor_change():
            forest.delete()
        patch = self.patch("nature.Forests", pk)
        self.assertIsNone(patch.geom)
        self.assertIsNotNone(patch.original_geom)

    def test_a_drawn_forest_plants_the_default_canopy(self):
        from core.editing import editor_change
        from nature.models import Forests
        from physicalEnv.calculations.dsm_patches import DEFAULT_FOREST_CANOPY_M

        with editor_change():
            forest = Forests.objects.create(name="Nieuw bos", geom=_rect(250000, 469900, 250050, 469950))
        self.assertEqual(self.patch("nature.Forests", forest.pk).canopy_m, DEFAULT_FOREST_CANOPY_M)

    def test_parks_never_patch_the_dsm(self):
        from core.editing import editor_change
        from nature.models import GreenSpaces
        from physicalEnv.models import DSMVegetationPatch

        with editor_change():
            park = GreenSpaces.objects.create(name="Park", type="park", geom=_rect(250000, 469900, 250050, 469950))
            park.delete()
        self.assertFalse(DSMVegetationPatch.objects.exists())
