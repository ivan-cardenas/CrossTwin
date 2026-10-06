"""
Batch-import helpers shared by the file-upload and external-data importers.

- SpatialParentIndex: resolves a feature's spatial parent (e.g. the City a
  land-cover polygon lies in) with prepared GEOS geometries and a bbox
  pre-check, instead of a linear scan of full point-in-polygon tests.
- deferred_cascades(): postpones the population and urban-area signal
  cascades until the end of an import, so they run once per affected parent
  instead of once per saved row.
- BulkWriter: writes rows with bulk_create (INSERT ... ON CONFLICT for
  upserts) for the models listed in BULK_IMPORT_MODELS.

See docs/PERFORMANCE.md §2 and §3.
"""
import logging
from contextlib import ExitStack, contextmanager

from django.db import models, transaction

from administrative.signals import deferred_population_cascade
from core.cache import bump_layer_version
from physicalEnv.signals import deferred_urban_area, schedule_urban_area_recompute

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Spatial parent lookup
# ---------------------------------------------------------------------------

class SpatialParentIndex:
    """
    Point-in-polygon lookup against a fixed set of parent rows.

    Each parent's geometry is prepared once (GEOS builds its internal index
    on first use), and a parent is only tested when the probe point falls
    inside its bounding box. The probe is the feature's point_on_surface,
    which, unlike its centroid, always lies on the feature itself, so a
    concave or ring-shaped feature is attributed to the parent it actually
    covers.
    """

    def __init__(self, parents):
        self._entries = []
        for parent in parents:
            geom = parent.geom
            if geom is None or geom.empty:
                continue
            self._entries.append((parent, geom.prepared, geom.extent))

    def __bool__(self):
        return bool(self._entries)

    def __len__(self):
        return len(self._entries)

    @classmethod
    def for_model(cls, ParentModel, extra_fields=()):
        """Load only what the lookup needs: pk, geom and any attributes read off the parent."""
        fields = ["pk", "geom", *(f for f in extra_fields if f)]
        return cls(ParentModel.objects.only(*fields))

    def find(self, geom):
        """The parent containing `geom`'s representative point, or None."""
        if geom is None or geom.empty:
            return None
        point = geom if geom.geom_type == "Point" else geom.point_on_surface
        x, y = point.x, point.y
        candidates = [
            (parent, prepared) for parent, prepared, (xmin, ymin, xmax, ymax) in self._entries
            if xmin <= x <= xmax and ymin <= y <= ymax
        ]
        for parent, prepared in candidates:
            if prepared.contains(point):
                return parent
        # A point exactly on a shared boundary is in neither interior; take
        # the first parent that touches it, as the old centroid lookup did.
        for parent, prepared in candidates:
            if prepared.intersects(point):
                return parent
        return None


# ---------------------------------------------------------------------------
# Deferred signal cascades
# ---------------------------------------------------------------------------

@contextmanager
def deferred_cascades():
    """
    Run the administrative population cascade and the land-cover urban-area
    recompute once per affected parent when the block ends, instead of once
    per row saved inside it. Enter this inside the import's transaction so
    the recompute commits (or rolls back) with the rows.
    """
    with ExitStack() as stack:
        # Exit order is the reverse: urban area first (it re-enters the
        # population cascade directly), then the deferred population cascade.
        stack.enter_context(deferred_population_cascade())
        stack.enter_context(deferred_urban_area())
        yield


# ---------------------------------------------------------------------------
# Bulk writes
# ---------------------------------------------------------------------------

def _finalize_landcover(rows):
    for city_id in {row.city_id for row in rows if row.city_id}:
        schedule_urban_area_recompute(city_id)


# Models the importer may write with bulk_create. bulk_create skips save()
# and post_save/post_delete, so a model belongs here only when it has no
# save() override (checked again at runtime) and when every post_save
# receiver it has is replayed by its finalizer below or is the layer-cache
# invalidation (BulkWriter bumps that itself). Adding a receiver to one of
# these models means adding it to the finalizer, or removing the model.
BULK_IMPORT_MODELS = {
    "physicalEnv.LandCoverVector": _finalize_landcover,   # replays physicalEnv/signals.py
    "builtup.Street": None,
    "builtup.Facility": None,
    "nature.ProtectedArea": None,
    "nature.WaterWaysLN": None,
    "nature.WaterWaysPG": None,
    "nature.WaterBodies": None,
    "nature.Forests": None,
    "nature.Tree": None,
}


class BulkWriter:
    """
    Collects rows and writes them `batch_size` at a time.

    With a unique field, rows are upserted with INSERT ... ON CONFLICT DO
    UPDATE and counted as created/updated from one lookup of the existing
    keys per batch. Rows with different sets of mapped fields are written in
    separate statements, so a row that lacks a source property never
    overwrites the stored value with the field default (the same behaviour
    as update_or_create's `defaults`). If a batch fails as a whole, it is
    retried row by row so a single bad feature only costs itself.
    """

    def __init__(self, Model, unique_field=None, batch_size=500):
        self.Model = Model
        self.unique_field = unique_field
        self.batch_size = batch_size
        self.finalizer = BULK_IMPORT_MODELS.get(Model._meta.label)
        self.created = 0
        self.updated = 0
        self.errors = []
        self._pending = []
        self._written = []

    @classmethod
    def for_model(cls, Model, unique_field=None, **kwargs):
        """A writer when `Model` can safely be bulk-written, otherwise None (use the row path)."""
        if Model._meta.label not in BULK_IMPORT_MODELS:
            return None
        if Model.save is not models.Model.save:
            logger.warning("%s overrides save(); importing it row by row", Model._meta.label)
            return None
        if unique_field and not Model._meta.get_field(unique_field).unique:
            # ON CONFLICT needs a unique index on the column
            return None
        return cls(Model, unique_field, **kwargs)

    def add(self, field_values):
        self._pending.append(field_values)
        if len(self._pending) >= self.batch_size:
            self.flush()

    def flush(self):
        rows, self._pending = self._pending, []
        if not rows:
            return
        try:
            with transaction.atomic():
                self._write(rows)
        except Exception as exc:
            logger.warning("Bulk write of %d %s rows failed (%s); retrying row by row",
                           len(rows), self.Model._meta.label, exc)
            for field_values in rows:
                try:
                    with transaction.atomic():
                        self._write([field_values])
                except Exception as row_exc:
                    self.errors.append(str(row_exc))

    def finish(self):
        """Write what is left, replay the skipped signals and invalidate the layer cache."""
        self.flush()
        if self._written:
            if self.finalizer:
                self.finalizer(self._written)
            bump_layer_version(self.Model)
        return self.created, self.updated, self.errors

    def _write(self, rows):
        unique = self.unique_field
        groups = {}
        for field_values in rows:
            keyed = bool(unique) and field_values.get(unique) is not None
            groups.setdefault((keyed, frozenset(field_values)), []).append(field_values)

        for (keyed, fields), group in groups.items():
            if not keyed:
                objs = [self.Model(**fv) for fv in group]
                self.Model.objects.bulk_create(objs)
                self.created += len(objs)
                self._written.extend(objs)
                continue

            # One statement can't upsert the same key twice; the last row wins.
            # Keys are normalised to the field's Python type (a WFS code can
            # arrive as an int for a CharField pk) so they compare with the DB's.
            to_python = self.Model._meta.get_field(unique).to_python
            by_key = {to_python(fv[unique]): fv for fv in group}
            existing = set(
                self.Model.objects.filter(**{f"{unique}__in": list(by_key)})
                .values_list(unique, flat=True)
            )
            objs = [self.Model(**fv) for fv in by_key.values()]
            update_fields = [f for f in fields if f != unique]
            if update_fields:
                self.Model.objects.bulk_create(
                    objs, update_conflicts=True,
                    unique_fields=[unique], update_fields=update_fields,
                )
            else:
                self.Model.objects.bulk_create(objs, ignore_conflicts=True)
            self.updated += sum(1 for key in by_key if key in existing)
            self.created += sum(1 for key in by_key if key not in existing)
            self._written.extend(objs)
