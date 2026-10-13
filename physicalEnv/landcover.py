"""
Land-cover overlay edits driven by other layers.

urbanize_around() turns a buffer around a new building into "urban fabric":
the buffer is cut out of every land-cover polygon of the city's latest year
and inserted as one new polygon, so the layer keeps covering the city without
overlaps (Neighborhood.urban_area sums polygon areas; an overlapping ring
would be counted twice).

The raw UPDATE/DELETE fire no model signals, so two custom signals tell
listeners which rows change: `landcover_rewriting` before the write (pks of
the rows about to be clipped or deleted) and `landcover_created` after the
insert. mainMap/signals.py journals them so the map editor's backup restore
puts the original land cover back.
"""
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.db import connection, transaction
from django.db.models import Max
from django.dispatch import Signal
from django.utils import timezone

from core.cache import bump_layer_version
from .models import LandCoverClasses, LandCoverVector

BUILDING_BUFFER_M = 10
URBAN_FABRIC_CLASS = "urban fabric"

# Sent with pks=[...] before urbanize_around() clips or deletes those rows.
landcover_rewriting = Signal()
# Sent with pks=[...] after urbanize_around() inserted those rows.
landcover_created = Signal()


def _urban_fabric_class():
    """The 'urban fabric' class, matched case-insensitively like the PDOK BRT import's lookup."""
    existing = LandCoverClasses.objects.filter(class_name__iexact=URBAN_FABRIC_CLASS).order_by("pk").first()
    if existing:
        return existing
    return LandCoverClasses.objects.create(
        class_name=URBAN_FABRIC_CLASS,
        description="Auto-created for the urban-fabric buffer around buildings drawn in the map editor.",
    )


def _buffer_sql(expr):
    """ST_Buffer of BUILDING_BUFFER_M metres: planar in RD New, through geography for a geodetic CRS."""
    if LandCoverVector._meta.get_field("geom").geodetic(connection):
        return f"ST_Buffer(({expr})::geography, {BUILDING_BUFFER_M})::geometry"
    return f"ST_Buffer({expr}, {BUILDING_BUFFER_M})"


def urbanize_around(geom, city_id, land_use):
    """
    Make a BUILDING_BUFFER_M buffer around `geom` (clipped to the city)
    urban fabric in the city's latest land-cover year:

        B   = buffer(footprint, 10 m) ∩ city
        LC' = { P \\ B : P ∈ LC, P \\ B ≠ ∅ } ∪ { B as urban fabric }

    `percentage` of the clipped and new rows is recomputed from the city's
    area_km2. Returns the new LandCoverVector, or None when the city has no
    land cover (there is no layer to update) or the buffer misses the city.

    DAG edge: New_Units -> LandCover
    """
    from .signals import _area_sql

    year = LandCoverVector.objects.filter(city_id=city_id).aggregate(latest=Max("year"))["latest"]
    if year is None:
        return None

    from administrative.models import City
    city_table = City._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH b AS (
                SELECT ST_Multi(ST_CollectionExtract(
                           ST_Intersection({_buffer_sql("ST_GeomFromEWKT(%(geom)s)")}, c.geom), 3)) AS geom,
                       c.area_km2
                FROM "{city_table}" c WHERE c.id = %(city)s
            )
            SELECT ST_AsEWKT(b.geom), {_area_sql("b.geom")}, b.area_km2 FROM b
            """,
            {"geom": geom.ewkt, "city": city_id},
        )
        row = cursor.fetchone()
    if not row or not row[0]:
        return None
    buffer = GEOSGeometry(row[0])
    buffer_km2, city_km2 = (row[1] or 0) / 1e6, row[2]
    if buffer.empty:
        return None

    with transaction.atomic():
        affected = list(
            LandCoverVector.objects.filter(city_id=city_id, year=year, geom__intersects=buffer)
            .values_list("pk", flat=True)
        )
        if affected:
            landcover_rewriting.send(sender=LandCoverVector, pks=affected)
            table = LandCoverVector._meta.db_table
            clipped = "ST_Multi(ST_CollectionExtract(ST_Difference(geom, ST_GeomFromEWKT(%(buffer)s)), 3))"
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE "{table}"
                    SET geom = {clipped},
                        percentage = CASE WHEN %(city_km2)s > 0
                                          THEN {_area_sql(clipped)} / 1e6 / %(city_km2)s * 100
                                          ELSE percentage END,
                        last_updated = %(now)s
                    WHERE id = ANY(%(ids)s)
                    """,
                    {"buffer": buffer.ewkt, "city_km2": city_km2, "now": timezone.now(), "ids": affected},
                )
                cursor.execute(
                    f'DELETE FROM "{table}" WHERE id = ANY(%(ids)s) AND ST_IsEmpty(geom)',
                    {"ids": affected},
                )
            bump_layer_version(LandCoverVector)

        if not isinstance(buffer, MultiPolygon):
            buffer = MultiPolygon(buffer, srid=buffer.srid)
        # post_save of this row runs the neighborhood urban-area recompute
        # (signals.landcover_changed), which also covers the clipped rows.
        created = LandCoverVector.objects.create(
            city_id=city_id,
            year=year,
            land_cover_type=_urban_fabric_class(),
            land_use=land_use[:100],
            geom=buffer,
            percentage=(buffer_km2 / city_km2 * 100) if city_km2 else 0.0,
        )
        landcover_created.send(sender=LandCoverVector, pks=[created.pk])
    return created
