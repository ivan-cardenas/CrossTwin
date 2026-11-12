"""
Land-cover overlay edits driven by other layers.

Two owners rewrite land cover from the map editor, with the same cut /
give-back mechanics (convert_area / release_owner):
- a building: a 10 m buffer becomes "urban fabric" (urbanize_around,
  DAG edge Buildings -> LandCover);
- a green space (nature.GreenSpaces; a park is one of type 'park'): its
  outline becomes "green urban areas" (green_area, DAG edge
  New_Green_Area -> LandCover). The owner kind stays "park" (columns
  source_park / owner_park), the id is the GreenSpaces id;
- a street (builtup.Street): its line buffered by half its width becomes
  "Road and rail networks and associated land" (street_area, DAG edge
  Streets -> LandCover; columns source_street / owner_street);
- a generated neighbourhood (housing.HousingProject id): its outline becomes
  one urban-fabric polygon (project_area, DAG edge Buildings -> LandCover for
  all its buildings at once; columns source_project / owner_project); its
  streets then cut their road surface out of it.

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
from typing import NamedTuple

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.db import connection, transaction
from django.db.models import Max
from django.dispatch import Signal
from django.utils import timezone

from core.cache import bump_layer_version
from ..models import LandCoverClasses, LandCoverVector, UrbanFabricCut

BUILDING_BUFFER_M = 10
URBAN_FABRIC_CLASS = "urban fabric"
GREEN_AREA_CLASS = "Green urban areas"   # CORINE 1.4.1
ROAD_CLASS = "Road and rail networks and associated land"   # CORINE 1.2.2


# Every kind of editor object that owns converted land cover; each has a
# source_<kind> column (LandCoverVector, UrbanFabricCut) and owner_<kind> (UrbanFabricCut).
OWNER_KINDS = ("building", "park", "street", "project")


class Owner(NamedTuple):
    """The editor object a converted polygon belongs to."""
    kind: str   # one of OWNER_KINDS
    id: int

    @property
    def ring_field(self):
        """LandCoverVector / UrbanFabricCut column holding the owner of a converted polygon."""
        return f"source_{self.kind}"

    @property
    def cut_field(self):
        """UrbanFabricCut column holding the owner that took the piece."""
        return f"owner_{self.kind}"

    def label(self):
        return f"editor: {self.kind} {self.id}"

# Sent with sender=<model>, pks=[...] before those rows are changed or deleted.
landcover_rewriting = Signal()
# Sent with sender=<model>, pks=[...] after those rows were inserted.
landcover_created = Signal()

_POLYGONS = "ST_Multi(ST_CollectionExtract({}, 3))"
_SOURCE_FIELDS = tuple(f"source_{kind}" for kind in OWNER_KINDS)
_OWNER_FIELDS = tuple(f"owner_{kind}" for kind in OWNER_KINDS)
_SOURCE_COLUMNS = ", ".join(_SOURCE_FIELDS)


def _sources_of(row):
    """The source_<kind> values of a cut, to copy onto the polygon recreated or re-targeted from it."""
    return {name: getattr(row, name) for name in _SOURCE_FIELDS}


def _land_cover_class(name, description):
    """The class of that name, matched case-insensitively like the PDOK BRT import's lookup; created when missing."""
    existing = LandCoverClasses.objects.filter(class_name__iexact=name).order_by("pk").first()
    if existing:
        return existing
    return LandCoverClasses.objects.create(class_name=name, description=description)


def _urban_fabric_class():
    return _land_cover_class(
        URBAN_FABRIC_CLASS, "Auto-created for the urban-fabric buffer around buildings drawn in the map editor.")


def _green_area_class():
    return _land_cover_class(
        GREEN_AREA_CLASS, "Auto-created for green spaces (parks) drawn in the map editor (CORINE 1.4.1 Green urban areas).")


def _road_class():
    return _land_cover_class(
        ROAD_CLASS, "Auto-created for streets drawn or generated in the map editor (CORINE 1.2.2 Road and rail networks).")


def _buffer_sql(expr, metres=BUILDING_BUFFER_M):
    """ST_Buffer of `metres`: planar in RD New, through geography for a geodetic CRS; none for 0."""
    if not metres:
        return expr
    if LandCoverVector._meta.get_field("geom").geodetic(connection):
        return f"ST_Buffer(({expr})::geography, {metres})::geometry"
    return f"ST_Buffer({expr}, {metres})"


def refresh_percentages(city_id, pks=None):
    """
    percentage = polygon area / city area_km2 * 100, in one UPDATE: for the
    given rows of the city, or for all its rows when pks is None (bulk
    imports, a changed city boundary). Rows whose value is already right are
    not rewritten. Returns the number of rows changed; bumps the layer cache
    when there are any (an UPDATE fires no post_save).
    """
    from administrative.models import City
    from ..signals import _area_sql

    if not city_id or (pks is not None and not pks):
        return 0
    new = f'{_area_sql("l.geom")} / 1e6 / c.area_km2 * 100'
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE "{LandCoverVector._meta.db_table}" l
            SET percentage = {new}
            FROM "{City._meta.db_table}" c
            WHERE c.id = %(city)s AND c.area_km2 > 0 AND l.city_id = c.id
              AND (%(all)s OR l.id = ANY(%(ids)s))
              AND (l.percentage IS NULL OR abs(l.percentage - {new}) > 1e-9)
            """,
            {"city": city_id, "all": pks is None, "ids": list(pks or [])},
        )
        changed = cursor.rowcount
    if changed:
        bump_layer_version(LandCoverVector)
    return changed


def urbanize_around(geom, city_id, land_use, building_id=None, roof_material=None):
    """
    Make a BUILDING_BUFFER_M buffer around `geom` (clipped to the city)
    urban fabric in the city's latest land-cover year:

        B   = buffer(footprint, 10 m) ∩ city
        LC' = { P \\ B : P ∈ LC, P \\ B ≠ ∅ } ∪ { B as urban fabric }

    With `building_id`, the ring is tagged with it and each P ∩ B is stored as
    an UrbanFabricCut (with P's attributes), for release_ring(). The ring's
    albedo is estimated from the roof (footprint) and paving (rest),
    albedo.ring_albedo. Returns the new LandCoverVector, or None when the city
    has no land cover (there is no layer to update) or the buffer misses the city.

    DAG edge: Buildings -> LandCover
    """
    from .albedo import ring_albedo

    estimate = None
    if not geom.srs or not geom.srs.geographic:
        estimate = ring_albedo(geom.buffer(BUILDING_BUFFER_M).area, geom.area, roof_material)
    owner = Owner("building", building_id) if building_id is not None else None
    source = (owner.label() if owner else "editor: building") if estimate is not None else None
    return convert_area(geom, city_id, _urban_fabric_class(), land_use, owner=owner,
                        buffer_m=BUILDING_BUFFER_M, albedo=estimate, albedo_source=source)


def green_area(geom, city_id, park_id, name="Park", vegetation_type=None):
    """
    Make a green space's (park's) outline (clipped to the city) green urban area in the
    city's latest land-cover year, cutting it out of what lay there:

        G   = park ∩ city
        LC' = { P \\ G : P ∈ LC, P \\ G ≠ ∅ } ∪ { G as green urban areas }

    Material: trees when the vegetation type mentions them, else grass (its
    albedo is the polygon's default). Released by release_green_area().

    DAG edge: New_Green_Area -> LandCover
    """
    from .albedo import DECIDUOUS, GRASS, material

    trees = bool(vegetation_type) and any(w in vegetation_type.lower() for w in ("tree", "wood", "forest"))
    return convert_area(geom, city_id, _green_area_class(), name or "Park", owner=Owner("park", park_id),
                        buffer_m=0, material=material(DECIDUOUS if trees else GRASS))


def project_area(geom, city_id, project_id, footprint_m2=0.0, name="Generated neighbourhood"):
    """
    Make a generated neighbourhood's outline (clipped to the city) one
    urban-fabric polygon in the city's latest year; its buildings get no ring
    of their own (physicalEnv.signals.building_created skips them) and its
    streets cut their road surface out of it afterwards (street_area). The
    albedo is estimated like a building ring: roofs over the footprints,
    paving elsewhere (albedo.ring_albedo). Released by release_owner(Owner("project", id)).

        U   = outline ∩ city
        LC' = { P \ U : P ∈ LC, P \ U ≠ ∅ } ∪ { U as urban fabric }

    DAG edge: Buildings -> LandCover (all buildings of the project at once)
    """
    from .albedo import ring_albedo

    estimate = None
    if not geom.srs or not geom.srs.geographic:
        estimate = ring_albedo(geom.area, min(footprint_m2, geom.area), None)
    owner = Owner("project", project_id)
    return convert_area(geom, city_id, _urban_fabric_class(), (name or "Generated neighbourhood")[:100],
                        owner=owner, albedo=estimate, albedo_source=owner.label() if estimate is not None else None)


def street_area(geom, city_id, street_id, width_m, name="Street"):
    """
    Make a street's surface (its centre line buffered by half its width, flat
    ends, clipped to the city) road land cover in the city's latest year,
    cutting it out of what lay there:

        S   = buffer(street line, W / 2) ∩ city
        LC' = { P \\ S : P ∈ LC, P \\ S ≠ ∅ } ∪ { S as road and rail networks }

    W = Street.width, else the class default (builtup/calculations/chain.py::DEFAULT_WIDTH_M,
    passed in by the receiver). Released by release_street().

    DAG edge: Streets -> LandCover
    """
    if not width_m or width_m <= 0:
        return None
    # Flat ends (end_cap_style 2) and mitred joins (join_style 2), like the generator's street area.
    surface = geom.buffer_with_style(width_m / 2, end_cap_style=2, join_style=2)
    return convert_area(surface, city_id, _road_class(), (name or "Street")[:100], owner=Owner("street", street_id))


def release_street(street_id):
    """
    Undo street_area() for an editor street that moved or was deleted (release_owner).

    DAG edge: Streets -> LandCover (the inverse step)
    """
    return release_owner(Owner("street", street_id))


def convert_area(geom, city_id, land_cover_class, land_use, owner=None, buffer_m=0,
                 material=None, albedo=None, albedo_source=None):
    """
    Cut buffer(geom, buffer_m) ∩ city out of the city's latest land-cover
    year and insert it as one polygon of `land_cover_class`. With `owner`,
    the new polygon is tagged with it and each piece it cut is stored as an
    UrbanFabricCut (with the cut polygon's attributes), for release_owner().
    `percentage` of the clipped rows is recomputed from the city's area_km2
    (the new row's by its pre_save receiver); without `material` the
    class's default material applies. Returns the new LandCoverVector, or
    None when the city has no land cover (there is no layer to update) or
    the area misses the city.
    """
    from ..signals import _area_sql

    year = LandCoverVector.objects.filter(city_id=city_id).aggregate(latest=Max("year"))["latest"]
    if year is None:
        return None

    from administrative.models import City
    city_table = City._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH b AS (
                SELECT {_POLYGONS.format(f'ST_Intersection({_buffer_sql("ST_GeomFromEWKT(%(geom)s)", buffer_m)}, c.geom)')} AS geom,
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
                if owner is not None:
                    # What each polygon is about to lose, with what it takes to recreate it
                    cursor.execute(
                        f"""
                        SELECT id, land_cover_type_id, land_use, material_id, {_SOURCE_COLUMNS},
                               albedo, albedo_source, albedo_date,
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
        owner_fields = {owner.ring_field: owner.id} if owner is not None else {}
        created = LandCoverVector.objects.create(
            city_id=city_id,
            year=year,
            land_cover_type=land_cover_class,
            land_use=land_use[:100],
            geom=buffer,
            percentage=(buffer_km2 / city_km2 * 100) if city_km2 else 0.0,
            material=material,
            albedo=albedo,
            albedo_source=albedo_source,
            **owner_fields,
        )
        landcover_created.send(sender=LandCoverVector, pks=[created.pk])

        cuts = []
        n = len(OWNER_KINDS)
        for row in pieces:
            target, class_id, target_use, material_id = row[:4]
            sources = dict(zip(_SOURCE_FIELDS, row[4:4 + n]))
            target_albedo, target_albedo_source, target_albedo_date, piece = row[4 + n:]
            piece = GEOSGeometry(piece) if piece else None
            if piece is None or piece.empty:
                continue
            cuts.append(UrbanFabricCut.objects.create(
                **{owner.cut_field: owner.id}, target=target, city_id=city_id, year=year,
                land_cover_type_id=class_id, land_use=target_use, material_id=material_id,
                **sources,
                albedo=target_albedo, albedo_source=target_albedo_source, albedo_date=target_albedo_date,
                geom=piece,
            ).pk)
        if cuts:
            landcover_created.send(sender=UrbanFabricCut, pks=cuts)
    return created


def release_ring(building_id):
    """Undo urbanize_around() for an editor building that moved or was deleted (release_owner)."""
    return release_owner(Owner("building", building_id))


def release_green_area(park_id):
    """
    Undo green_area() for an editor green space that moved or was deleted (release_owner).

    DAG edge: New_Green_Area -> LandCover (the inverse step)
    """
    return release_owner(Owner("park", park_id))


def release_owner(owner):
    """
    Undo convert_area() for an editor object that moved or was deleted:
    every piece its ring R took goes back to the polygon it came from,

        T' = T ∪ (cut_T ∩ R)        (T recreated from the cut when it is gone)

    so only the area R still holds is returned; what a later ring took from
    R stays with that ring. Cuts that later rings took *from R* are
    re-targeted to R's own targets (cut ∩ cut_T -> T), so releasing those
    rings later returns their land to what lay under R. Then R and its cuts
    are deleted. Returns True when anything changed.

    DAG edge: Buildings -> LandCover (the inverse step)
    """
    from ..signals import deferred_urban_area

    ring = LandCoverVector.objects.filter(**{owner.ring_field: owner.id}).first()
    own = list(UrbanFabricCut.objects.filter(**{owner.cut_field: owner.id}))
    taken_from_ring = list(
        UrbanFabricCut.objects.filter(**{owner.ring_field: owner.id}).exclude(**{owner.cut_field: owner.id})
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
                    WHERE c.{owner.cut_field} = %(b)s
                    GROUP BY c.target
                    """,
                    {"ring": ring.pk, "b": owner.id},
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
                    material_id=cut.material_id, **_sources_of(cut), albedo=cut.albedo, albedo_source=cut.albedo_source,
                    albedo_date=cut.albedo_date, geom=piece, percentage=0.0,
                )
                recreated.append(target)
        if recreated:
            landcover_created.send(sender=LandCoverVector, pks=recreated)
        city_id = ring.city_id if ring is not None else next((c.city_id for c in own), None)
        refresh_percentages(city_id, [t for t, _ in returned])
        if returned:
            bump_layer_version(LandCoverVector)

        # 2. Re-target what later rings took from this ring onto its targets.
        new_cuts = []
        if taken_from_ring and own:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {", ".join("o." + f for f in _OWNER_FIELDS)}, c.id,
                           ST_AsEWKT({_POLYGONS.format("ST_Intersection(o.geom, c.geom)")})
                    FROM "{cut_table}" o
                    JOIN "{cut_table}" c ON c.{owner.cut_field} = %(b)s
                         AND o.geom && c.geom AND ST_Intersects(o.geom, c.geom)
                    WHERE o.id = ANY(%(others)s)
                    """,
                    {"b": owner.id, "others": [o.pk for o in taken_from_ring]},
                )
                overlaps = cursor.fetchall()
            by_pk = {c.pk: c for c in own}
            for row in overlaps:
                owners = dict(zip(_OWNER_FIELDS, row[:len(OWNER_KINDS)]))
                cut_pk, piece = row[len(OWNER_KINDS):]
                piece = GEOSGeometry(piece) if piece else None
                if piece is None or piece.empty:
                    continue
                c = by_pk[cut_pk]
                new_cuts.append(UrbanFabricCut(
                    **owners, target=c.target,
                    city_id=c.city_id, year=c.year,
                    land_cover_type_id=c.land_cover_type_id, land_use=c.land_use,
                    material_id=c.material_id, **_sources_of(c), albedo=c.albedo, albedo_source=c.albedo_source,
                    albedo_date=c.albedo_date, geom=piece,
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
            from ..signals import schedule_urban_area_recompute
            schedule_urban_area_recompute(city_id)
    return True
