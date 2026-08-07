# Make map-panel selection work at any administrative level (Province/City/District/Neighborhood)

## Context

Clicking a province on the map is supposed to drive the Water Supply and Urban Heat side panels (`window.ACTIVE_PROVINCE` → `hx-get` URL → HTMX swap). While debugging why clicks did nothing, we found the click listener in `Map_init.js` was bound to a Mapbox layer ID (`common.Province-fill`) that never gets created — `common.Province` has a custom style in `LAYER_STYLES` (`mainMap/views.py`), so `Layers.js` actually creates `common.Province-custom-0`/`-1`, not `-fill`.

Rather than just patching the ID, the user wants clicking **any** administrative polygon — Province, City, District, or Neighborhood — to drive the panels, and each should show indicators computed **for that specific unit**, not rolled up to its parent province. That requires changes beyond the map: the `watersupply` and `urban_heat` dashboards are currently hard-wired to look up a `Province` by name and run province-scoped queries.

Investigation showed most of the underlying calculation logic is already geometry-based (`geom__intersects=province.geom`), which generalizes to any of the four models for free since `Province`, `City`, `District`, and `Neighborhood` (`common/models.py`) all carry a `geom` field. A handful of spots use FK-chain filtering (`City.objects.filter(province=province)`) or a hard Province FK (`AreaAffectedDrought.Province`, `LandCoverVector.Province`) that need to be made level-aware.

## Frontend changes

**`common/static/js/Layers.js`** (`addLayer`, ~line 129): right after `loadedLayers[key] = { layerIds, geojson, config: layerConfig };`, add an optional hook:
```js
if (typeof onAdminLayerLoaded === 'function') onAdminLayerLoaded(key, layerIds);
```
This fires once per layer exactly when its real Mapbox layer IDs become known — reusing the same dynamic-ID pattern the existing popup handler at Layers.js:132 already relies on, instead of hardcoding IDs like the current buggy code does.

**`common/static/js/Map_init.js`**: replace the single hardcoded Province click handler (current lines 63-77) with:
- `window.ACTIVE_LEVEL = 'province'` and `window.ACTIVE_LOCATION = 'Demo'` (renamed from `ACTIVE_PROVINCE` since it now holds any unit's name).
- An `ADMIN_LEVELS` map keyed by the four registry keys (`common.Province`, `common.City`, `common.District`, `common.Neighborhood`) to `{ level, nameField }` (`ProvinceName`, `cityName`, `districtName`, `neighborhoodName` — confirmed these are the exact `f.name` values `mainMap/views.py:model_geojson` serializes into GeoJSON `properties`).
- `function onAdminLayerLoaded(key, layerIds)` — looks up `ADMIN_LEVELS[key]`, and if found, binds `map.on('click', layerIds[0], ...)`, which sets `ACTIVE_LEVEL`/`ACTIVE_LOCATION` from the clicked feature's properties, then calls `syncWaterBtn()` / `syncHeatBtn()` (see below) and clicks the water button — preserving today's behavior of auto-opening the water panel on selection.

**`mainMap/templates/mainMap.html`**:
- Update `syncWaterBtn()`/`syncHeatBtn()` (~lines 509-525) to build URLs as `/watersupply/indicators/${level}/${location}/${year}/` and `/urban_heat/indicators/${level}/${location}/`, defaulting to `'province'`/`'Demo'`.
- Replace the duplicated inline URL-rebuilding logic in the year-button handler (~lines 353-359) with a call to `syncWaterBtn()`, eliminating that duplication.
- Update the two initial `hx-get="{% url ... %}"` button attributes (~lines 57, 70) to pass `level='province'` alongside the existing `location='Demo'`.

## Backend changes

**New `common/admin_units.py`** — small shared resolver so both apps use identical logic:
```python
ADMIN_LEVELS = {
    'province': (Province, 'ProvinceName'),
    'city': (City, 'cityName'),
    'district': (District, 'districtName'),
    'neighborhood': (Neighborhood, 'neighborhoodName'),
}

def resolve_admin_unit(level, name):
    ... # returns the model instance or None

def cities_within(unit):
    ... # dispatches on isinstance(unit, Province/City/District/Neighborhood)
        # Province -> City.objects.filter(province=unit)
        # City     -> City.objects.filter(pk=unit.pk)
        # District -> City.objects.filter(pk=unit.city_id)
        # Neighborhood -> City.objects.filter(pk=unit.district.city_id)

def neighborhoods_within(unit):
    ... # same dispatch pattern down to Neighborhood.objects.filter(pk=unit.pk)
```
Dispatching on `isinstance(unit, ...)` instead of threading a `level` string through every calculation function keeps the diff in `calculations.py` minimal — call sites basically just swap `City.objects.filter(province=province)` for `cities_within(unit)`.

**`watersupply/urls.py`**: add `<str:level>/` segment to both routes: `indicators/<str:level>/<str:location>/<int:year>/` (and the `/recalculate/` variant).

**`watersupply/views.py`**:
- `_get_province_data(level, location, year)`: resolve via `resolve_admin_unit(level, location)` instead of `PM.objects.get(ProvinceName=location)`. Keep the returned dict's `'province'` key (holds whichever unit was resolved) and other key names as-is to minimize downstream churn. Use `unit.currentPopulation or 0` since District/Neighborhood allow null population.
- `water_indicators`/`recalculate_indicators`: accept `level` from the URL, pass through, and add `'level': level, 'location': location` to the template context (the raw request strings — used for display and to build the recalculate URL, valid whether real data or `MOCK_DATA` was used).

**`watersupply/calculations.py`**: swap FK-chain filters for the new helpers:
- `_get_consumption_capita`, `calculate_supply_security`, `calculate_coverage` → `cities_within(unit)` instead of `City.objects.filter(province=province)`.
- `calculate_collection_ratio`, `calculate_opex_recovery` → `neighborhoods_within(unit)` instead of `Neighborhood.objects.filter(district__city__province=province)`.
- `calculate_drought_area` → switch `AreaAffectedDrought.objects.filter(Province=province, year=year)` to `AreaAffectedDrought.objects.filter(geom__intersects=unit.geom, year=year)` (the model already has its own `geom` field, so this is a straight generalization, not a schema change).
- Everything already using `geom__intersects=province.geom` (extraction, energy, CO2, available freshwater) needs no change beyond the incoming param now potentially being a City/District/Neighborhood instead of only Province.

**`urban_heat/urls.py`**: same `<str:level>/` addition to both routes (no `year` segment here).

**`urban_heat/views.py`**: same `_get_province_data(level, location)` resolver swap; same `level`/`location` context additions.

**`urban_heat/calculations.py`**: only `calculate_green_area` needs a change — its `LandCoverVector.objects.filter(green_filter, Province=province)` becomes `.filter(green_filter, geom__intersects=unit.geom)` (model has `geom`). Everything else already filters by `geom__intersects=province.geom` and generalizes for free.
  - **Known pre-existing limitation, not fixed here**: `LandCoverVector.percentage` is stored as "% of the *Province*'s total area" (see CLAUDE.md TODO). For a City/District/Neighborhood selection, `calculate_vegetation_coverage`'s percentage math will still be province-relative, not unit-relative, since fixing that requires the already-tracked `percentage` auto-calculation TODO. Worth a one-line comment noting this, not a rewrite.

**Templates** — both apps hardcode `{{ Province.ProvinceName }}` for the header and for building the recalculate slider's `hx-get` URL:
- `watersupply/templates/watersupply/water_indicators.html` (lines 17, 50) and `.../partials/indicators_panel.html` (lines 12, 42)
- `urban_heat/templates/urban_heat/heat_indicators.html` (lines 15, 46) and `.../partials/indicators_panel.html` (lines 12, 43)

Change `{{ Province.ProvinceName }}` → `{{ location }}` for display, and `{% url '...:recalculate_indicators' Province.ProvinceName year %}` → `{% url '...:recalculate_indicators' level location year %}` (drop `year` for urban_heat). This avoids depending on an attribute (`ProvinceName`) that only exists on the `Province` model.

## Out of scope

- `housing` app is not wired to `ACTIVE_PROVINCE`/map clicks at all — untouched.
- Not fixing the pre-existing `LandCoverVector.percentage` province-relative semantics (flagged above, already a tracked TODO).
- Not touching the OPEX average calc in `watersupply/views.py` (`avg_opex_m3`) — it was already global/unscoped before this change, unrelated to admin-level selection.

## Verification

1. `python manage.py runserver 8000` (and `uvicorn tiler:app --port 8001 --reload` if raster tiles are involved, not required for this feature).
2. In the browser: click a Province polygon → water panel opens showing that province's indicators; click a City inside it → panel refreshes with that city's own numbers (not the parent province's); repeat for a District and a Neighborhood. Toggle a year button after selecting a City and confirm the water panel URL keeps the City context. Switch to the heat panel (temperature tool) and confirm it also reflects the same selected unit.
3. Check the browser console for errors on each click (mistyped GeoJSON property names would show up as `undefined` in the URL rather than a JS error, so also inspect the `hx-get` attribute value via devtools to confirm `level`/`location` are populated correctly).
4. `python manage.py test watersupply urban_heat --settings=DigitalTwin.settings_test` to make sure existing tests (if any cover `_get_province_data`) still pass with the new signature.
