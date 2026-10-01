# Visual editing of layer objects on the map

Status: proposal, not implemented yet (written 2026-10-01).

## Context

Today the map is read-only: objects can only be created or changed through the importer or the Django admin. The goal is to edit objects visually on the main map — draw a new building, reshape one, change its attribute values, delete it — with as little new code as possible.

Decisions made:
- **Scope:** built-up layers only (Building, Street, Park, Facility, Zoning area), as an allowlist that is easy to extend.
- **Access:** staff login only (the existing Django admin login). Everyone else sees the map as today.
- **Delete:** included, with an inline confirm step.

## Approach

**Drawing library: `@mapbox/mapbox-gl-draw` v1.5.0**, loaded from the Mapbox CDN (same host as the geocoder plugin already used; both files verified to exist). It works with Mapbox GL JS v3, handles points, lines, polygons and Multi* geometries, and needs no build step. Terra Draw was considered: more modes, but needs an adapter layer and is more than this needs.

**Server: let Django's ModelForm do the work.** One small generic view builds a form for any allowlisted model with `modelform_factory`. The geometry travels as GeoJSON in a hidden form field; Django's GIS form field parses it, checks the geometry type and reprojects WGS84 → `settings.COORDINATE_SYSTEM` by itself. Saving goes through `obj.save()`, so existing behaviour comes free: derived fields (`Building.save()`), cascade signals, and GeoJSON cache invalidation (`core/signals.py` → `bump_layer_version`).

**UI: reuse the side panel.** The form is an HTMX partial swapped into `#panel-body`, like the indicator panels. No new overlay.

### User flow
1. **Edit:** click an object → popup shows an "Edit" button (staff, editable layers only) → the side panel shows the attribute form and the shape becomes editable on the map (drag vertices).
2. **Create:** a "＋" button on each editable layer in the Layers panel → draw the shape on the map → fill the form.
3. **Save / Cancel / Delete** in the form. Delete asks "Are you sure?" inline. After save or delete the layer reloads.

## Server changes

**New `mainMap/editing.py`** (~120 lines)
- `EDITABLE_LAYERS`: allowlist keyed by registry key, with per-model `exclude` (fields the model derives itself) and `optional` (fields the form must not require). Fill the lists by reading each model's `save()`. Known for Building: exclude `area_sqm`, `neighborhood`, `last_updated`, `connectivity`; `buildingType` optional (derived from `usageFunction`).
- `feature_form(request, app_label, model_name, pk=None)`:
  - 404 if the key is not in `EDITABLE_LAYERS`; 403 unless `request.user.is_staff`.
  - GET: render the partial with the form and the object's **full-resolution** geometry as WGS84 GeoJSON (`geom.transform(4326, clone=True).geojson`). Must not reuse the map's copy: viewport-loaded layers are simplified below zoom 14.
  - POST: validate and `form.save()`. On success return the partial in a "saved" state with an `HX-Trigger: feature-saved` header carrying the layer key. On error re-render with messages.
  - Primary key is never editable. `Building.id` is a non-auto BigInteger (BAG id): new buildings get the next **negative** id (`min(0, lowest id) - 1`), so they never collide with BAG and are recognisable as user-created.
- `feature_delete(...)`: POST, staff only. Catch `IntegrityError` (e.g. a Building still referenced by a Property — FKs are `DO_NOTHING`) and show it as a message instead of a 500.

**`mainMap/urls.py`** — three routes under the existing prefix:
`api/layers/<app>/<model>/features/new/`, `.../features/<pk>/`, `.../features/<pk>/delete/`.

**`mainMap/views.py::available_layers`** — add `editable: true` and the Multi*/single geometry type to a layer entry when it is in `EDITABLE_LAYERS` and the user is staff. This is what makes the buttons appear.

**New `mainMap/templates/mainMap/partials/feature_form.html`** — crispy-tailwind form (already installed), hidden geometry input, `{% csrf_token %}` (HTMX posts it with the form, no extra wiring), Save / Cancel / Delete-with-confirm.

## Frontend changes

**New `core/static/js/Editing.js`** (~150 lines; no inline scripts, per project convention)
- `startEdit(layerKey, pk)` / `startCreate(layerKey)`: load the form with `htmx.ajax` into `#panel-body`, add a `MapboxDraw` control, load the geometry (edit → `direct_select`; create → `draw_polygon` / `draw_line_string` / `draw_point` from the layer's geometry type).
- On `draw.create` / `draw.update`: write the geometry into the hidden input, wrapping Polygon → MultiPolygon etc. when the model field is a Multi* type.
- While editing: hide the original object with a layer filter on its `id` (otherwise the extruded building covers the edit handles), and ease the camera pitch to 0.
- `stopEdit()`: remove the draw control, restore the filter. Called on save, cancel, delete, panel close, a basemap switch, or when `#panel-body` gets swapped to something else.
- On `feature-saved`: reload the layer.

**Small hooks in existing files**
- `Layers.js`: "Edit" button in the popup head (`_popupHead`, using the layer key and `properties.id`); skip opening popups while editing (`initFeaturePopup`); a `reloadLayer(key)` beside the existing `reloadViewportLayer` for layers that load whole.
- `MapUI.js::renderLayerList`: "＋" button on editable layers.
- `mainMap.js::refreshActivePanel` and `Map_init.js::onAdminLayerLoaded`: do nothing while editing. Without this, panning the map or clicking a neighbourhood would replace the form in `#panel-body`.
- `Map_init.js::changeBasemap`: cancel the edit (a style change removes Draw's layers).
- `mainMap.html`: the two CDN tags and `Editing.js`. `mainMap.css`: a few rules for the buttons and form.
- `.claude/CLAUDE.md`: short section on editing and how to add a layer to the allowlist.

## Out of scope (first version)
- Snapping to neighbouring objects, undo history, editing several objects at once.
- Administrative, water, nature and other layers (add to `EDITABLE_LAYERS` later; several have many required or computed fields and will need their `exclude` lists tuned).
- A login link on the map page: staff log in at `/admin/` as today.

## Verification
1. **Tests** in `mainMap/tests.py` (`python manage.py test mainMap builtup --settings=DigitalTwin.settings_test --keepdb --noinput`):
   - anonymous and non-staff users get 403; a non-allowlisted layer gets 404; `editable` appears in the catalog only for staff;
   - create a Building from a WGS84 Polygon → stored as MultiPolygon in EPSG:28992, negative id, `buildingType`/`area_sqm` derived;
   - edit attributes and geometry of an existing building; invalid geometry type is rejected with a form error;
   - delete works; deleting a building referenced by a Property returns a message, not a 500;
   - a save invalidates the cached GeoJSON (same pattern as `ModelGeoJsonTests`).
2. **Browser check** against the running app (headless Chrome over DevTools, as used for the earlier map changes, logged in as a temporary staff user that is removed afterwards): edit a building's attribute and a vertex, create a building, delete it; confirm the layer reloads each time, the popup stays closed while drawing, panning does not replace the form, and there are no console errors.
3. Confirm a logged-out visitor sees no Edit or ＋ buttons.
