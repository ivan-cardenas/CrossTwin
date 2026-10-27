"""
Visual editing of layer objects on the map, plus one backup / restore point
for what-if tests (docs/MAP_EDITING.md).

Objects are edited through a ModelForm built per model: the geometry travels
as GeoJSON in a hidden field, which Django's GIS form field parses, checks
against the model's geometry type and reprojects to COORDINATE_SYSTEM. Saving
goes through obj.save(), so derived fields, cascade signals and the GeoJSON
cache invalidation (core/signals.py) all apply as for any other write.

Backups are a change journal (mainMap.models.EditBackup / EditBackupRow):
creating one copies nothing; each change made here first records the
object's original row, once per object, and Restore reverts only those rows.
Changes made through the importer, the admin, QGIS or psql are not recorded.

Which layers are editable is switched in the map's settings panel
(mainMap.models.EditableLayer, mainMap/settings_views.py). How their forms
look (fields left out or not required) is configured in
core/editable_layers.toml (FIELD_RULES, read once at startup), because it
follows from each model's save().
"""
import json
import threading
import tomllib
from pathlib import Path

from django import forms
from django.apps import apps
from django.contrib.gis.db import models as gis_models
from django.core import serializers
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, connection, transaction
from django.db.models import AutoField, Min, Model
from django.forms import modelform_factory
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from core.utils import VECTOR_REGISTRY
from mainMap.models import EditableLayer, EditBackup, EditBackupRow

EDITABLE_LAYERS_FILE = Path(__file__).with_name('editable_layers.toml')
_LAYER_SETTINGS = ('exclude', 'optional')


def load_editable_layers(path=EDITABLE_LAYERS_FILE):
    """
    Registry key -> {'exclude': [...], 'optional': [...]} from the TOML file:
    the form rules of each layer, not whether it is editable (EditableLayer).
    Only the file's shape is checked here; that every key is a vector layer
    and every field exists is checked by mainMap/test_editing.py.
    """
    try:
        with open(path, 'rb') as f:
            config = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ImproperlyConfigured(f'Cannot read editable layers from {path}: {e}') from e

    layers = {}
    for key, settings in config.items():
        if not isinstance(settings, dict):
            raise ImproperlyConfigured(f'{path}: [{key!r}] must be a table, e.g. ["{key}"]')
        unknown = set(settings) - set(_LAYER_SETTINGS)
        if unknown:
            raise ImproperlyConfigured(f'{path}: [{key!r}] has unknown setting(s) {sorted(unknown)}; '
                                       f'allowed: {list(_LAYER_SETTINGS)}')
        for name, value in settings.items():
            if not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
                raise ImproperlyConfigured(f'{path}: [{key!r}].{name} must be a list of field names')
        layers[key] = {name: list(settings.get(name, [])) for name in _LAYER_SETTINGS}
    return layers


FIELD_RULES = load_editable_layers()
NO_RULES = {'exclude': [], 'optional': []}

# Apps with receivers that skip raw=True saves, so restore_backup would leave
# their cascades stale (docs/MAP_EDITING.md). Their layers need field rules
# and a restore hook before they can be switched on.
RAW_SKIPPING_APPS = {'watersupply'}

FORM_TEMPLATE = 'mainMap/partials/feature_form.html'
BACKUP_TEMPLATE = 'mainMap/partials/backup_bar.html'


def geometry_field(model):
    return next((f for f in model._meta.get_fields() if isinstance(f, gis_models.GeometryField)), None)


def editable_keys():
    """Registry keys of the layers switched on in the settings panel (one query)."""
    return set(EditableLayer.objects.filter(key__in=VECTOR_REGISTRY).values_list('key', flat=True))


def is_editable(key, user, keys=None):
    """
    True when `user` may edit the layer `key`. The layer catalog passes
    `keys` (editable_keys()) so it asks the database once, not per layer.
    """
    if not getattr(user, 'is_staff', False):
        return False
    return key in (editable_keys() if keys is None else keys)


def enable_blocker(key):
    """
    Why the layer `key` may not be switched on, or None when it may. A model
    whose save() derives fields needs field rules in editable_layers.toml,
    otherwise the form shows fields whose typed values save() overwrites.
    """
    model = VECTOR_REGISTRY.get(key)
    if model is None:
        return 'Not a vector layer.'
    if key in FIELD_RULES:
        return None
    if model._meta.app_label in RAW_SKIPPING_APPS:
        return ('Its cascades skip raw saves, so Restore would leave them stale. '
                'Add it to core/editable_layers.toml with a restore hook first.')
    if model.save is not Model.save:
        return ('Its save() derives fields. Add it to core/editable_layers.toml with the '
                'fields save() sets as exclude, then restart the server.')
    return None


def _editable_model(app_label, model_name):
    key = f'{app_label}.{model_name}'
    if key not in VECTOR_REGISTRY or not EditableLayer.objects.filter(key=key).exists():
        raise Http404(f'Layer {key} is not editable')
    return key, VECTOR_REGISTRY[key]


def _forbidden():
    return HttpResponseForbidden('Editing requires a staff login.')


def _build_form(key, model, data=None, instance=None):
    cfg = FIELD_RULES.get(key, NO_RULES)
    geom = geometry_field(model)
    # The primary key is never editable (Building.id is a BAG id, not auto)
    exclude = [model._meta.pk.name, *cfg.get('exclude', [])]
    form_class = modelform_factory(model, exclude=exclude, widgets={geom.name: forms.HiddenInput})
    form = form_class(data=data, instance=instance)
    for name in cfg.get('optional', []):
        if name in form.fields:
            form.fields[name].required = False
    return form


def _next_negative_pk(model):
    """
    Next id for a model whose primary key is not generated by the database.
    User-created objects count down from -1, so they never collide with
    source ids (BAG ids are positive) and are recognisable as user-made.
    """
    lowest = model.objects.aggregate(lowest=Min('pk'))['lowest'] or 0
    return min(0, lowest) - 1


def _check_constraints():
    """
    Django creates FK constraints DEFERRABLE INITIALLY DEFERRED, so a broken
    reference only fails at COMMIT. Check them now, inside the atomic block,
    so the IntegrityError rolls back just this change and can be reported.
    """
    with connection.cursor() as cursor:
        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        cursor.execute('SET CONSTRAINTS ALL DEFERRED')


def _form_context(key, model, form, obj=None, **extra):
    app_label, model_name = key.split('.')
    geom = geometry_field(model)
    geojson = None
    if obj is not None and obj.pk is not None:
        stored = getattr(obj, geom.name)
        # Full resolution from the DB: the map's copy of a viewport-loaded
        # layer is simplified below zoom 14.
        geojson = json.loads(stored.transform(4326, clone=True).geojson) if stored else None
    pk = obj.pk if obj is not None else None
    context = {
        'form': form,
        'obj': obj,
        'layer_key': key,
        'verbose_name': model._meta.verbose_name,
        'geom_field': geom.name,
        'geom_type': geom.geom_type,
        'geom_errors': form.errors.get(geom.name),
        'geojson': geojson,
        'post_url': reverse('map:feature_edit', args=[app_label, model_name, pk]) if pk is not None
                    else reverse('map:feature_new', args=[app_label, model_name]),
        'delete_url': reverse('map:feature_delete', args=[app_label, model_name, pk]) if pk is not None else None,
        'backup': active_backup(),
    }
    context.update(extra)
    return context


@require_http_methods(['GET', 'POST'])
def feature_form(request, app_label, model_name, pk=None):
    """
    Attribute form + geometry for one object (pk) or a new one (no pk).
    GET renders it into the side panel; POST validates and saves, then
    re-renders it in a "saved" state with HX-Trigger: feature-saved.
    URL: /api/layers/<app>/<model>/features/new/ | /features/<pk>/
    """
    key, model = _editable_model(app_label, model_name)
    if not is_editable(key, request.user, keys={key}):
        return _forbidden()
    instance = get_object_or_404(model, pk=pk) if pk is not None else None

    if request.method == 'GET':
        form = _build_form(key, model, instance=instance)
        return render(request, FORM_TEMPLATE, _form_context(key, model, form, instance))

    form = _build_form(key, model, data=request.POST, instance=instance)
    if not form.is_valid():
        return render(request, FORM_TEMPLATE, _form_context(key, model, form, instance))

    creating = instance is None
    try:
        with transaction.atomic():
            if not creating:
                # Before the save: the journal reads the row as it is in the DB
                # (the form has already copied the new values onto `instance`).
                journal(key, model, instance.pk)
            obj = form.save(commit=False)
            if creating and not isinstance(model._meta.pk, AutoField):
                obj.pk = _next_negative_pk(model)
            # force_insert: two editors creating at once can get the same id, and a
            # plain save() would then UPDATE (overwrite) the other's new object.
            obj.save(force_insert=creating)
            form.save_m2m()
            if creating:
                journal(key, model, obj.pk, created=True)
    except IntegrityError as exc:
        if not creating:
            raise
        # Most likely the id race above: saving again picks a fresh id
        form.add_error(None, f"Could not save, please try again ({exc}).")
        return render(request, FORM_TEMPLATE, _form_context(key, model, form, instance))

    obj.refresh_from_db()
    form = _build_form(key, model, instance=obj)
    response = render(request, FORM_TEMPLATE, _form_context(key, model, form, obj, saved=True))
    response['HX-Trigger'] = json.dumps({'feature-saved': {'layer': key}})
    return response


@require_POST
def feature_delete(request, app_label, model_name, pk):
    """
    Delete one object. A delete that would break a reference (e.g. a
    Building still referenced by a Property: FKs are DO_NOTHING) is rolled
    back and shown as a message, not a 500.
    URL: /api/layers/<app>/<model>/features/<pk>/delete/
    """
    key, model = _editable_model(app_label, model_name)
    if not is_editable(key, request.user, keys={key}):
        return _forbidden()
    obj = get_object_or_404(model, pk=pk)
    label = f'{model._meta.verbose_name} {obj.pk}'

    try:
        with transaction.atomic():
            journal(key, model, obj.pk)
            obj.delete()
            _check_constraints()
    except IntegrityError as exc:
        obj = get_object_or_404(model, pk=pk)
        form = _build_form(key, model, instance=obj)
        message = f'{label} cannot be deleted: other records still refer to it. ({_first_line(exc)})'
        return render(request, FORM_TEMPLATE, _form_context(key, model, form, obj, message=message))

    response = render(request, FORM_TEMPLATE, {'deleted': label, 'layer_key': key})
    response['HX-Trigger'] = json.dumps({'feature-saved': {'layer': key, 'deleted': True}})
    return response


def _first_line(exc):
    detail = str(exc).strip().splitlines()
    return ' '.join(detail[:2]) if detail else exc.__class__.__name__


# ── Backup / restore ─────────────────────────────────────────────────────────

def active_backup():
    return EditBackup.objects.order_by('-created_at').first()


def journal(key, model, pk, created=False):
    """
    Record the original state of one object in the active backup, unless it
    is already recorded: the first record wins, so an object edited twice
    still goes back to its state before the test. `created=True` records
    "did not exist" (restore deletes it). No-op without an active backup.
    """
    backup = active_backup()
    if backup is None:
        return
    if EditBackupRow.objects.filter(backup=backup, layer_key=key, object_pk=str(pk)).exists():
        return
    original = None
    if not created:
        original = json.loads(serializers.serialize('json', model.objects.filter(pk=pk)))
    EditBackupRow.objects.create(backup=backup, layer_key=key, object_pk=str(pk), original=original)


def _backup_bar(request, message=None, status=200):
    backup = active_backup()
    context = {
        'backup': backup,
        'changed': backup.rows.count() if backup else 0,
        'message': message,
    }
    return render(request, BACKUP_TEMPLATE, context, status=status)


@require_http_methods(['GET', 'POST'])
def backup(request):
    """
    GET: the backup bar shown above the Layers panel's layer list.
    POST: create the restore point (refused while one exists).
    URL: /api/editing/backup/
    """
    if not request.user.is_staff:
        return _forbidden()
    if request.method == 'POST':
        if active_backup() is not None:
            return _backup_bar(request, 'Restore or discard the current backup first.')
        EditBackup.objects.create(created_by=request.user)
    return _backup_bar(request)


@require_POST
def backup_discard(request):
    """Keep the current data and drop the restore point. URL: /api/editing/backup/discard/"""
    if not request.user.is_staff:
        return _forbidden()
    EditBackup.objects.all().delete()
    return _backup_bar(request)


_restoring = threading.local()


def is_restoring():
    """
    True while restore_backup() runs. Receivers that undo an edit's side
    effects on delete (e.g. physicalEnv's release of a building's land-cover
    ring) check it: the restore puts those rows back itself, as with raw saves.
    """
    return getattr(_restoring, 'active', False)


def restore_backup(backup):
    """
    Put every object recorded in `backup` back as it was, in one transaction,
    then delete the backup. Returns the affected map layer keys (journalled
    bookkeeping tables such as physicalEnv.UrbanFabricCut are restored but not
    listed). Raises IntegrityError (with everything rolled back) when a
    reference blocks it.
    """
    rows = list(backup.rows.all())
    _restoring.active = True
    try:
        with transaction.atomic():
            _restore_rows(rows)
            backup.delete()
    finally:
        _restoring.active = False
    return sorted({row.layer_key for row in rows if row.layer_key in VECTOR_REGISTRY})


def _restore_rows(rows):
    from importer.batching import deferred_cascades

    with transaction.atomic():
        with deferred_cascades():
            # 1. Changed and deleted objects. A raw save writes the stored
            #    values back exactly (derived fields included, no save()
            #    re-derivation), keeps the original pk, and still fires
            #    post_save, so the GeoJSON cache version is bumped.
            for row in rows:
                if row.original is not None:
                    for restored in serializers.deserialize('json', json.dumps(row.original)):
                        restored.save()
            # 2. Objects created since the backup, after step 1 so any
            #    reference targets are back first.
            for row in rows:
                if row.original is None:
                    apps.get_model(row.layer_key).objects.filter(pk=row.object_pk).delete()
            _check_constraints()


@require_POST
def backup_restore(request):
    """Revert every journalled change. URL: /api/editing/backup/restore/"""
    if not request.user.is_staff:
        return _forbidden()
    backup = active_backup()
    if backup is None:
        return _backup_bar(request, 'There is no backup to restore.')
    try:
        layers = restore_backup(backup)
    except IntegrityError as exc:
        return _backup_bar(request, f'Restore cancelled, nothing was changed: {_first_line(exc)}')
    response = _backup_bar(request, f'Restored {len(layers)} layer(s) to the backup.' if layers else 'Nothing to restore.')
    response['HX-Trigger'] = json.dumps({'backup-restored': {'layers': layers}})
    return response
