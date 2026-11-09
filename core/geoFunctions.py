from django.contrib.gis.measure import Area
from django.apps import apps
from django.contrib.gis.db import models

def get_area(self): 
        """ 
        Returns the area in square kilometers. 
        """
        area_sqkm = self.polygon.area.sq_km
      

        return area_sqkm


_MULTI_OF = {'Point': 'MultiPoint', 'LineString': 'MultiLineString', 'Polygon': 'MultiPolygon'}


def fit_geometry_type(geos, field):
    """
    Convert between single and multi geometries to match the target field:
    a Point into a MultiPointField is wrapped, a one-part MultiPoint into a
    PointField is unwrapped (shapefiles/GeoPackages often store single points
    as multi; the map editor draws a single line for a MultiLineStringField).
    Anything else is returned unchanged and rejected by the field.
    """
    from django.contrib.gis import geos as geos_mod

    target = field.geom_type.replace('_', '').upper()  # 'POINT', 'MULTIPOINT', 'GEOMETRY', ...
    current = geos.geom_type
    if target == current.upper() or target == 'GEOMETRY':
        return geos
    if target == _MULTI_OF.get(current, '').upper():
        return getattr(geos_mod, _MULTI_OF[current])([geos], srid=geos.srid)
    if current.startswith('Multi') and target == current[5:].upper() and len(geos) == 1:
        single = geos[0]
        single.srid = geos.srid
        return single
    return geos
