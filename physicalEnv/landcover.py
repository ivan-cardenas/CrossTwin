"""
Land-cover overlay edits driven by other layers.

urbanize_around() turns a buffer around a new building into "urban fabric":
the buffer is cut out of every land-cover polygon of the city's latest year
and inserted as one new polygon, so the layer keeps covering the city without
overlaps (Neighborhood.urban_area sums polygon areas; an overlapping ring
would be counted twice). The ring carries the building's id
(`source_building`) and every piece it cut is kept as an UrbanFabricCut, so
release_ring() can give the land back when the building is moved or deleted.

The raw UPDATE/DELETE fire no model signals, so two custom signals tell
listeners which rows change: `landcover_rewriting` before a write (pks of
the rows about to be changed or deleted) and `landcover_created` after an
insert. `sender` is the model (LandCoverVector or UrbanFabricCut).
mainMap/signals.py journals them so the map editor's backup restore puts the
original land cover back.
"""
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.db import connection, transaction
from django.db.models import Max
from django.dispatch import Signal
from django.utils import timezone

from core.cache import bump_layer_version
from .models import LandCoverClasses, LandCoverVector, UrbanFabricCut

BUILDING_BUFFER_M = 10
URBAN_FABRIC_CLASS = "urban fabric"

# Sent with sender=<model>, pks=[...] before those rows are changed or deleted.
landcover_rewriting = Signal()
# Sent with sender=<model>, pks=[...] after those rows were inserted.
landcover_created = Signal()

_POLYGONS = "ST_Multi(ST_CollectionExtract({}, 3))"


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


def _refresh_percentages(pks, city_id):
    """percentage = polygon area / city area_km2 * 100 for the given rows."""
    from administrative.models import City
    from .signals import _area_sql

    if not pks or not city_id:
        return
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE "{LandCoverVector._meta.db_table}" l
            SET percentage = {_area_sql("l.geom")} / 1e6 / c.area_km2 * 100
            FROM "{City._meta.db_table}" c
            WHERE c.id = %(city)s AND c.area_km2 > 0 AND l.id = ANY(%(ids)s)
            """,
            {"city": city_id, "ids": list(pks)},
        )


def urbanize_around(geom, city_id, land_use, building_id=None):
    """
    Make a BUILDING_BUFFER_M buffer around `geom` (clipped to the city)
    urban fabric in the city's latest land-cover year:

        B   = buffer(footprint, 10 m) ∩ city
        LC' = { P \\ B : P ∈ LC, P \\ B ≠ ∅ } ∪ { B as urban fabric }

    With `building_id`, the ring is tagged with it and each P ∩ B is stored as
    an UrbanFabricCut (with P's attributes), for release_ring().
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
                SELECT {_POLYGONS.format(f'ST_Intersection({_buffer_sql("ST_GeomFromEWKT(%(geom)s)")}, c.geom)')} AS geom,
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
        pieces = []
        if affected:
            landcover_rewriting.send(sender=LandCoverVector, pks=affected)
            table = LandCoverVector._meta.db_table
            clipped = _POLYGONS.format("ST_Difference(geom, ST_GeomFromEWKT(%(buffer)s))")
            params = {"buffer": buffer.ewkt, "city_km2": city_km2, "now": timezone.now(), "ids": affected}
            with connection.cursor() as cursor:
                if building_id is not None:
                    # What each polygon is about to lose, with what it takes to recreate it
                    cursor.execute(
                        f"""
                        SELECT id, land_cover_type_id, land_use, material_id, source_building,
                               ST_AsEWKT({_POLYGONS.format("ST_Intersection(geom, ST_GeomFromEWKT(%(buffer)s))")})
                        FROM "{table}" WHERE id = ANY(%(ids)s)
                        """,
                        params,
                    )
                    pieces = cursor.fetchall()
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
                    params,
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
            source_building=building_id,
        )
        landcover_created.send(sender=LandCoverVector, pks=[created.pk])

        cuts = []
        for target, class_id, target_use, material_id, target_source, piece in pieces:
            piece = GEOSGeometry(piece) if piece else None
            if piece is None or piece.empty:
                continue
            cuts.append(UrbanFabricCut.objects.create(
                owner_building=building_id, target=target, city_id=city_id, year=year,
                land_cover_type_id=class_id, land_use=target_use, material_id=material_id,
                source_building=target_source, geom=piece,
            ).pk)
        if cuts:
            landcover_created.send(sender=UrbanFabricCut, pks=cuts)
    return created


def release_ring(building_id):
    """
    Undo urbanize_around() for an editor building that moved or was deleted:
    every piece its ring R took goes back to the polygon it came from,

        T' = T ∪ (cut_T ∩ R)        (T recreated from the cut when it is gone)

    so only the area R still holds is returned; what a later ring took from
    R stays with that ring. Cuts that later rings took *from R* are
    re-targeted to R's own targets (cut ∩ cut_T -> T), so releasing those
    rings later returns their land to what lay under R. Then R and its cuts
    are deleted. Returns True when anything changed.

    DAG edge: New_Units -> LandCover (the inverse step)
    """
    from .signals import deferred_urban_area

    ring = LandCoverVector.objects.filter(source_building=building_id).first()
    own = list(UrbanFabricCut.objects.filter(owner_building=building_id))
    taken_from_ring = list(
        UrbanFabricCut.objects.filter(source_building=building_id).exclude(owner_building=building_id)
    )
    if ring is None and not own and not taken_from_ring:
        return False

    lcv_table = LandCoverVector._meta.db_table
    cut_table = UrbanFabricCut._meta.db_table
    template = {cut.target: cut for cut in own}

    with transaction.atomic(), deferred_urban_area():
        # 1. Give back what the ring still holds, per target.
        returned = []
        if ring is not None and own:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT c.target,
                           ST_AsEWKT({_POLYGONS.format("ST_Union(ST_Intersection(c.geom, r.geom))")})
                    FROM "{cut_table}" c JOIN "{lcv_table}" r ON r.id = %(ring)s
                    WHERE c.owner_building = %(b)s
                    GROUP BY c.target
                    """,
                    {"ring": ring.pk, "b": building_id},
                )
                returned = [(t, GEOSGeometry(g)) for t, g in cursor.fetchall() if g]
            returned = [(t, g) for t, g in returned if not g.empty]

        existing = set(
            LandCoverVector.objects.filter(pk__in=[t for t, _ in returned]).values_list("pk", flat=True)
        )
        rewritten = sorted(existing | ({ring.pk} if ring is not None else set()))
        if rewritten:
            landcover_rewriting.send(sender=LandCoverVector, pks=rewritten)

        recreated = []
        with connection.cursor() as cursor:
            for target, piece in returned:
                if target in existing:
                    cursor.execute(
                        f"""
                        UPDATE "{lcv_table}"
                        SET geom = {_POLYGONS.format("ST_Union(geom, ST_GeomFromEWKT(%(piece)s))")},
                            last_updated = %(now)s
                        WHERE id = %(id)s
                        """,
                        {"piece": piece.ewkt, "now": timezone.now(), "id": target},
                    )
                    continue
                cut = template[target]
                if not isinstance(piece, MultiPolygon):
                    piece = MultiPolygon(piece, srid=piece.srid)
                LandCoverVector.objects.create(
                    id=target, city_id=cut.city_id, year=cut.year,
                    land_cover_type_id=cut.land_cover_type_id, land_use=cut.land_use,
                    material_id=cut.material_id, source_building=cut.source_building,
                    geom=piece, percentage=0.0,
                )
                recreated.append(target)
        if recreated:
            landcover_created.send(sender=LandCoverVector, pks=recreated)
        city_id = ring.city_id if ring is not None else next((c.city_id for c in own), None)
        _refresh_percentages([t for t, _ in returned], city_id)
        if returned:
            bump_layer_version(LandCoverVector)

        # 2. Re-target what later rings took from this ring onto its targets.
        new_cuts = []
        if taken_from_ring and own:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT o.owner_building, c.id,
                           ST_AsEWKT({_POLYGONS.format("ST_Intersection(o.geom, c.geom)")})
                    FROM "{cut_table}" o
                    JOIN "{cut_table}" c ON c.owner_building = %(b)s
                         AND o.geom && c.geom AND ST_Intersects(o.geom, c.geom)
                    WHERE o.id = ANY(%(others)s)
                    """,
                    {"b": building_id, "others": [o.pk for o in taken_from_ring]},
                )
                overlaps = cursor.fetchall()
            by_pk = {c.pk: c for c in own}
            for owner, cut_pk, piece in overlaps:
                piece = GEOSGeometry(piece) if piece else None
                if piece is None or piece.empty:
                    continue
                c = by_pk[cut_pk]
                new_cuts.append(UrbanFabricCut(
                    owner_building=owner, target=c.target, city_id=c.city_id, year=c.year,
                    land_cover_type_id=c.land_cover_type_id, land_use=c.land_use,
                    material_id=c.material_id, source_building=c.source_building, geom=piece,
                ))

        # 3. Drop the ring and every cut that referred to it.
        dropped = [c.pk for c in own] + [o.pk for o in taken_from_ring]
        if dropped:
            landcover_rewriting.send(sender=UrbanFabricCut, pks=dropped)
            UrbanFabricCut.objects.filter(pk__in=dropped).delete()
        created_cuts = []
        for cut in new_cuts:
            cut.save()
            created_cuts.append(cut.pk)
        if created_cuts:
            landcover_created.send(sender=UrbanFabricCut, pks=created_cuts)
        if ring is not None:
            ring.delete()   # post_delete schedules the urban-area recompute
        elif city_id:
            from .signals import schedule_urban_area_recompute
            schedule_urban_area_recompute(city_id)
    return True
