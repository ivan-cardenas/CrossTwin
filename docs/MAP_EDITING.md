# Visual editing of layer objects on the map

Status: implemented 2026-10-05 (proposal written 2026-10-01). Code: `mainMap/editing.py`, `mainMap/models.py` (`EditBackup`, `EditBackupRow`), `core/static/js/Editing.js`; tests in `mainMap/test_editing.py`; equations in `docs/functions_and_equations.tex` §"Map editing and what-if backup".

## Context

Today the map is read-only: objects can only be created or changed through the importer or the Django admin. The goal is to edit objects visually on the main map — draw a new building, reshape one, change its attribute values, delete it — with as little new code as possible.

Decisions made:
- **Scope:** built-up layers only (Building, Street, Park, Facility, Zoning area), as an allowlist that is easy to extend.
- **Access:** staff login only (the existing Django admin login). Everyone else sees the map as today.
- **Delete:** included, with an inline confirm step.
- **Backup / restore:** one restore point for what-if tests, so edits can be tried out and rolled back to the state before the test. It is stored as a change journal (only the objects edited after the restore point, not a copy of whole tables) and covers edits made through the map editor only.

## Approach

**Drawing library: `@mapbox/mapbox-gl-draw` v1.5.0**, loaded from the Mapbox CDN (same host as the geocoder plugin already used; both files verified to exist). It works with Mapbox GL JS v3, handles points, lines, polygons and Multi* geometries, and needs no build step. Terra Draw was considered: more modes, but needs an adapter layer and is more than this needs.

**Server: let Django's ModelForm do the work.** One small generic view builds a form for any allowlisted model with `modelform_factory`. The geometry travels as GeoJSON in a hidden form field; Django's GIS form field parses it, checks the geometry type and reprojects WGS84 → `settings.COORDINATE_SYSTEM` by itself. Saving goes through `obj.save()`, so existing behaviour comes free: derived fields (`Building.save()`), cascade signals, and GeoJSON cache invalidation (`core/signals.py` → `bump_layer_version`).

**UI: reuse the side panel.** The form is an HTMX partial swapped into `#panel-body`, like the indicator panels. No new overlay.

### User flow
1. **Edit:** click an object → popup shows an "Edit" button (staff, editable layers only) → the side panel shows the attribute form and the shape becomes editable on the map (drag vertices).
2. **Create:** a "＋" button on each editable layer in the Layers panel → draw the shape on the map → fill the form.
3. **Save / Cancel / Delete** in the form. Delete asks "Are you sure?" inline. After save or delete the layer reloads.
4. **Backup / Restore:** a backup bar at the top of the Layers panel (staff, when any layer is editable):
   - no backup: "Create backup", with a note that changes are permanent;
   - backup active: "Backup since 14:32 · 3 objects changed · Restore · Discard".

   **Restore** (inline confirm) puts every changed object back as it was, deletes objects created since the backup, brings back deleted ones with their original id, and reloads the affected layers. **Discard** keeps the current data and drops the restore point.

## Server changes

**New `mainMap/editing.py`**
- `EDITABLE_LAYERS`: allowlist keyed by registry key, with per-model `exclude` (fields the model derives itself) and `optional` (fields the form must not require). Fill the lists by reading each model's `save()`. Known for Building: exclude `area_sqm`, `neighborhood`, `last_updated`, `connectivity`; `buildingType` optional (derived from `usageFunction`).
- `feature_form(request, app_label, model_name, pk=None)`:
  - 404 if the key is not in `EDITABLE_LAYERS`; 403 unless `request.user.is_staff`.
  - GET: render the partial with the form and the object's **full-resolution** geometry as WGS84 GeoJSON (`geom.transform(4326, clone=True).geojson`). Must not reuse the map's copy: viewport-loaded layers are simplified below zoom 14.
  - POST: validate and `form.save()`. On success return the partial in a "saved" state with an `HX-Trigger: feature-saved` header carrying the layer key. On error re-render with messages.
  - Primary key is never editable. `Building.id` is a non-auto BigInteger (BAG id): new buildings get the next **negative** id (`min(0, lowest id) - 1`), so they never collide with BAG and are recognisable as user-created.
- `feature_delete(...)`: POST, staff only. Catch `IntegrityError` (e.g. a Building still referenced by a Property — FKs are `DO_NOTHING`) and show it as a message instead of a 500.

**`mainMap/urls.py`** — three routes under the existing prefix:
`api/layers/<app>/<model>/features/new/`, `.../features/<pk>/`, `.../features/<pk>/delete/`.
Plus the backup routes (see [Backup and restore](#backup-and-restore)): `api/editing/backup/` (GET status, POST create), `.../backup/restore/`, `.../backup/discard/`.

**`mainMap/views.py::available_layers`** — add `editable: true` and the Multi*/single geometry type to a layer entry when it is in `EDITABLE_LAYERS` and the user is staff. This is what makes the buttons appear.

**New `mainMap/templates/mainMap/partials/feature_form.html`** — crispy-tailwind form (already installed), hidden geometry input, `{% csrf_token %}` (HTMX posts it with the form, no extra wiring), Save / Cancel / Delete-with-confirm.

## Backup and restore

A **change journal**, not a table copy: "Create backup" only sets a restore point (instant, even for 100k+ BAG buildings). After that, each edit, create or delete made through the editor first records the object's original row, once per object. Restore reverts only those rows. There is at most one backup at a time.

**Models in `mainMap/models.py`** (+ migration). mainMap is not in `core/utils.py` `allowed_apps`, so these stay out of the layer registries and the layer catalog.
- `EditBackup`: `created_at`, `created_by` (FK user). At most one row; creating a backup while one exists is refused with "restore or discard the current backup first".
- `EditBackupRow`: `backup` (FK, `CASCADE`, since this is bookkeeping, not spatial reference data), `layer_key`, `object_pk` (CharField, works for BAG BigInteger ids and auto ids), `original` (JSONField; `null` = the object did not exist when the backup was made). Unique on (`backup`, `layer_key`, `object_pk`).

**Recording, in `mainMap/editing.py`:** `journal(layer_key, model, pk)` runs inside the same `transaction.atomic()` as the change: *before* `form.save()` on edit and before the delete; *after* the save on create, with `original=None`. It writes only when the object has no row yet, so the first pre-image wins and editing an object twice still restores it to its state before the test. The row is serialized with `django.core.serializers.serialize("json", [obj])`, which handles GIS fields and keeps the geometry in its stored CRS (no WGS84 round trip, so no coordinate drift). Without an active backup nothing is recorded and edits are permanent, as before.

**Restore** (`POST api/editing/backup/restore/`, staff only): one transaction, wrapped in `importer/batching.py::deferred_cascades()`:
1. Rows with an `original`: `serializers.deserialize(...)` → `.save()`. This is a raw save. It writes the stored values back exactly, derived fields included (`Building.save()` does not re-derive them), keeps the original pk so deleted objects come back with their id, and still fires `post_save`, so `core/signals.py` bumps the GeoJSON cache version.
2. Rows with `original=None`: delete the object if it still exists. This runs after step 1, so FK targets are back first.
3. On `IntegrityError` (e.g. a Property now points at a building created during the test; FKs are `DO_NOTHING`), roll back the whole restore and show which object blocks it. Never a partial restore.
4. Delete the backup and return `HX-Trigger: backup-restored` with the affected layer keys.

**Create** (`POST api/editing/backup/`) and **Discard** (`POST .../backup/discard/`): staff only. **Status** (`GET api/editing/backup/`) renders `mainMap/templates/mainMap/partials/backup_bar.html`. The bar loads itself and refreshes on `feature-saved` (`hx-trigger="load, feature-saved from:body"`); Create, Restore and Discard re-render it with their own response.

**Limits to keep in mind**
- Changes made through the importer, the admin, QGIS or psql are not journalled. An object changed *only* that way is left alone by Restore. An object changed through **both** the editor and another route after the backup is set back to its pre-backup state, which also undoes the other change for that object.
- Raw saves: built-up models have no signal receivers that skip `raw=True`, but `watersupply/signals.py` does (`if raw: return`). When layers from such apps are added to `EDITABLE_LAYERS`, Restore must trigger their cascades itself (e.g. `physicalEnv.signals.schedule_urban_area_recompute`, the watersupply recomputes).

## Frontend changes

**New `core/static/js/Editing.js`** (no inline scripts, per project convention)
- `startEdit(layerKey, pk)` / `startCreate(layerKey)`: load the form with `htmx.ajax` into `#panel-body`, add a `MapboxDraw` control, load the geometry (edit → `direct_select`; create → `draw_polygon` / `draw_line_string` / `draw_point` from the layer's geometry type).
- On `draw.create` / `draw.update`: write the geometry into the hidden input, wrapping Polygon → MultiPolygon etc. when the model field is a Multi* type.
- While editing: hide the original object with a layer filter on its `id` (otherwise the extruded building covers the edit handles), and ease the camera pitch to 0.
- `stopEdit()`: remove the draw control, restore the filter. Called on cancel, delete, panel close, a basemap switch, or when `#panel-body` gets swapped to something else. After a save the form re-renders in its "saved" state and the drawing tools reload with the stored geometry, so editing can continue.
- On `feature-saved`: reload the layer; if it was not loaded yet (created with ＋ on an unchecked layer), switch it on so the new object appears.
- On `backup-restored`: `stopEdit()` if an edit is open, then `reloadLayer(key)` for each affected layer key.

**Small hooks in existing files**
- `Layers.js`: "Edit" button in the popup head (`_popupHead`, using the layer key and `properties.id`); skip opening popups while editing (`initFeaturePopup`); a `reloadLayer(key)` beside the existing `reloadViewportLayer` for layers that load whole.
- `MapUI.js::renderLayerList`: "＋" button on editable layers, and the backup bar container (`hx-get` to the status route) at the top of the Layers panel when any layer is `editable`.
- `mainMap.js::refreshActivePanel` and `Map_init.js::onAdminLayerLoaded`: do nothing while editing. Without this, panning the map or clicking a neighbourhood would replace the form in `#panel-body`.
- `Map_init.js::changeBasemap`: cancel the edit (a style change removes Draw's layers).
- `mainMap.html`: the two CDN tags and `Editing.js`. `mainMap.css`: a few rules for the buttons and form.
- `.claude/CLAUDE.md`: short section on editing, backup/restore, and how to add a layer to the allowlist.

## Out of scope (first version)
- Snapping to neighbouring objects, editing several objects at once.
- Per-step undo, multiple named backups, and backups of changes made outside the editor (importer, admin). The first version has one restore point.
- Administrative, water, nature and other layers (add to `EDITABLE_LAYERS` later; several have many required or computed fields and will need their `exclude` lists tuned).
- A login link on the map page: staff log in at `/admin/` as today.

## Verification
1. **Tests** in `mainMap/test_editing.py` (`python manage.py test mainMap builtup --settings=DigitalTwin.settings_test --keepdb --noinput`):
   - anonymous and non-staff users get 403; a non-allowlisted layer gets 404; `editable` appears in the catalog only for staff;
   - create a Building from a WGS84 Polygon → stored as MultiPolygon in EPSG:28992, negative id, `buildingType`/`area_sqm` derived;
   - edit attributes and geometry of an existing building; invalid geometry type is rejected with a form error;
   - delete works; deleting a building referenced by a Property returns a message, not a 500;
   - a save invalidates the cached GeoJSON (same pattern as `ModelGeoJsonTests`);
   - backup/restore: without a backup, edits write no journal rows; backup → edit attributes and geometry → restore returns the exact original row (geometry equal in EPSG:28992, derived fields unchanged); backup → create → restore deletes the new building; backup → delete → restore brings it back with the same BAG id; editing an object twice keeps the first pre-image; a restore blocked by a Property FK rolls back completely and returns a message; restore bumps the GeoJSON cache version; creating a second backup is refused; non-staff users get 403 on all backup routes.
2. **Browser check** against the running app (headless Chrome over DevTools, as used for the earlier map changes, logged in as a temporary staff user that is removed afterwards): edit a building's attribute and a vertex, create a building, delete it; confirm the layer reloads each time, the popup stays closed while drawing, panning does not replace the form, and there are no console errors. Then repeat with a backup: create backup → edit / create / delete → Restore, and confirm the map returns to its original state and the backup bar resets.
3. Confirm a logged-out visitor sees no Edit or ＋ buttons.
