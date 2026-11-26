import os
import tempfile

import numpy as np
from django.test import SimpleTestCase

from core.calculations.raster_blocks import BlockGridError, block_mean, raster_blocks


class BlockMeanTests(SimpleTestCase):
    def test_mean_of_full_and_partial_containers(self):
        values = np.arange(25, dtype=float).reshape(5, 5)
        means, counts = block_mean(values, np.ones((5, 5), bool), 2)
        self.assertEqual(means.shape, (3, 3))
        self.assertEqual(means[0, 0], np.mean([0, 1, 5, 6]))
        self.assertEqual(counts[2, 2], 1)          # corner container: one cell
        self.assertEqual(means[2, 2], 24)

    def test_nodata_is_skipped_and_empty_container_is_nan(self):
        values = np.full((4, 4), 10.0)
        valid = np.ones((4, 4), bool)
        valid[0, 0] = False
        valid[2:, 2:] = False
        means, counts = block_mean(values, valid, 2)
        self.assertEqual(means[0, 0], 10.0)
        self.assertEqual(counts[0, 0], 3)
        self.assertTrue(np.isnan(means[1, 1]))


class RasterBlocksTests(SimpleTestCase):
    def _tif(self, data):
        import rasterio
        from rasterio.transform import from_origin

        path = os.path.join(tempfile.mkdtemp(), "t.tif")
        # 10 m cells in EPSG:28992 around Enschede
        with rasterio.open(
            path, "w", driver="GTiff", height=data.shape[0], width=data.shape[1], count=1,
            dtype="float32", crs="EPSG:28992", transform=from_origin(258000, 472000, 10, 10), nodata=-9999,
        ) as dst:
            dst.write(data.astype("float32"), 1)
        return path

    def test_grid_values_size_and_determinism(self):
        data = np.arange(64, dtype=float).reshape(8, 8)
        data[0, 0] = -9999
        path = self._tif(data)
        grid = raster_blocks(path, 4)
        self.assertEqual(len(grid["value"]), 4)
        self.assertAlmostEqual(grid["cell_size_m"], 40.0, places=3)   # 4 cells x 10 m
        self.assertAlmostEqual(grid["value"][0], np.mean([v for v in data[:4, :4].ravel() if v != -9999]), places=3)
        self.assertEqual(grid, raster_blocks(path, 4))

    def test_invalid_size_and_no_overlap(self):
        path = self._tif(np.ones((4, 4)))
        with self.assertRaises(BlockGridError):
            raster_blocks(path, 0)
        with self.assertRaises(BlockGridError):
            raster_blocks(path, 2, bbox_wgs84=(0.0, 0.0, 0.1, 0.1))
