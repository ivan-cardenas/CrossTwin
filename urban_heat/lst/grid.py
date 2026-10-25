"""The one raster grid every LST input is put on before the equations run."""
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Grid:
    """North-up grid: (x0, y0) is the top-left corner, cells are `resolution` m square."""

    srid: int
    x0: float
    y0: float
    resolution: float
    width: int
    height: int

    @classmethod
    def covering(cls, srid, xmin, ymin, xmax, ymax, resolution):
        """Smallest grid with corners on multiples of `resolution` that covers the extent."""
        x0 = math.floor(xmin / resolution) * resolution
        y0 = math.ceil(ymax / resolution) * resolution
        width = max(1, math.ceil((xmax - x0) / resolution))
        height = max(1, math.ceil((y0 - ymin) / resolution))
        return cls(srid, x0, y0, float(resolution), width, height)

    @property
    def gdal_transform(self):
        return (self.x0, self.resolution, 0.0, self.y0, 0.0, -self.resolution)

    @property
    def ee_crs_transform(self):
        """Affine in Earth Engine's order: [xScale, xShear, xOffset, yShear, yScale, yOffset]."""
        return [self.resolution, 0, self.x0, 0, -self.resolution, self.y0]

    @property
    def extent(self):
        return (self.x0, self.y0 - self.height * self.resolution, self.x0 + self.width * self.resolution, self.y0)

    def wgs84_bbox(self):
        """[west, south, east, north] in EPSG:4326, for filtering image collections."""
        from django.contrib.gis.geos import Polygon

        poly = Polygon.from_bbox(self.extent)
        poly.srid = self.srid
        poly.transform(4326)
        return list(poly.extent)
