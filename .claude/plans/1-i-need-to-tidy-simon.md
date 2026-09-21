# CrossTwin – Plan: model automation, population scenario, dashboard toggle, KNMI WBGT

> Living document. Update **Decision log** and **Change log** as work proceeds.
> Status legend: ☐ todo · ◐ in progress · ☑ done · ✖ dropped
> Created: 2026-09-21 · Branch: `main` · Status of exploration: **done – A (audit), B (population), C (KNMI + dashboard) merged. Waiting on the user's answers to the open questions.**

## Context

Four requests from the user, in their own words:

1. Verify every model in every app has a proper `save()` for attributes that can be calculated automatically, and add **signals** so that a change in one model updates the models that depend on it.
2. Create a **population curve** from CBS table **85173NED** so the user can see predictions and "play" with them to see the effect on the indicators.
3. In `mainMap/templates/mainMap.html`, the **Dashboard** button (`#btn-dashboard`) should open and close the indicators panel.
4. Add an option to **import the latest heat measure (WBGT)** from the KNMI Data Platform: `https://api.dataplatform.knmi.nl/open-data/v1/datasets/wet_bulb_globe_temperature/versions/3.0/files`.

Related earlier work in this session (already done, not part of this plan): importer now stores every geometry/raster in `settings.COORDINATE_SYSTEM`; tests in `importer/tests.py`.

## Known starting facts (verified from code already read)

- `#btn-dashboard` and `#btn-scenarios` exist in `mainMap.html` (bottom-right `.mode-btn`s). The handler is in `core/static/js/Events.js:89` (`showDashboard`, mock KPIs, open-only) – see workstream 3.
- The side panel is `#side-panel`; it is shown by class **`visible`** (CSS `display:flex`); class `open` (added in the `htmx:afterSwap` handler) is decorative. It has its own `✕` (`#panel-close`).
- Indicator panels are driven by `ADMIN_PANEL_TOOLS` (`water`, `temperature`, `Housing`) + `window.ACTIVE_YEAR` / `ACTIVE_LEVEL` / `ACTIVE_LOCATION`, via `syncPanelBtns()` / `refreshActivePanel()`. Year buttons: 2025, 2026, 2027, 2030, 2050.
- Indicator pattern (CLAUDE.md): `calculations.py` → `views.py::_get_province_data/_build_indicators` (supports what-if overrides) → HTMX partials.
- CLAUDE.md already lists DAG gaps and two latent bugs relevant to workstream 1: `OPEX.save()` uses a non-existent `ExtractionWater.extraction_volume_m3`; `Province.save()` uses wrong-case `City.objects.filter(Province=...)`.
- Population cascades Neighborhood → District → City → Province in `administrative/signals.py` using `update()` (not `save()`) to avoid recursion.

## Workstreams

### 1. Model `save()` audit + cross-model signals  ☐
**Goal:** every derivable field is computed in `save()`; every cross-model dependency has a signal.

- ☐ Audit all models in: administrative, physicalEnv, urban_heat, watersupply, weather, builtup, Energy, housing, nature *(explorer A running)*
- ☐ Produce a table per app: field · derivable from · computed today? · action
- ☐ Map cross-model dependencies against `core/DAG.dot` (102 edges, only 28 implemented per CLAUDE.md)
- ☐ Check each `signals.py` is actually imported in its `apps.py::ready()`
- ☐ Fix latent bugs found (start with the two above)
- ☐ Implement missing `save()` logic + signals, following existing conventions (`update()` not `save()` inside signals; `DO_NOTHING` FKs)
- ☐ Tests per signal (factories in `watersupply/tests/factories.py` have a known SRID bug – decide whether to fix first)

**Findings (explorer A, done):**

*Wiring / conventions*
- Only `administrative/signals.py` (Neighborhood→District→City→Province cascade, via `update()`, with `dispatch_uid`) and `core/signals.py` (COG export) and `weather/signals.py` are actually connected. **`watersupply/signals.py` is dead code** (no `ready()` in `watersupply/apps.py`) and would raise `FieldError` if wired (`F("province__population")`).
- **`core/utils.py:6` lists `'urbanHeat'` but the app is `urban_heat`** – the `LookupError` is swallowed, so urban_heat models are missing from `MODEL_REGISTRY`/`RASTER_REGISTRY`, the layer catalog and COG auto-export. High-impact one-word fix.
- `weather/signals.py` covers 3 of 4 rasters (`WindSpeedRaster` missing) and builds SQL by string interpolation.
- Conventions to follow: cascades use `filter(pk=…).update(…)`; signals get `dispatch_uid`; `save()` computes from own fields + `aggregate()` on other models; importer uses `update_or_create` (fires signals); `queryset.update()`/`bulk_*` bypass them.
- Tests: only `watersupply/tests/` (factories + `test_metered_residential.py`) and `importer/tests.py`. **Factories build 4326 polygons for 28992 fields → areas/densities meaningless**; a metre-scale 28992 factory is needed before asserting derived values.

*Missing/incorrect `save()` (by app; details in explorer output – summarised)*
- **watersupply (most broken):** `OPEX.save` (FieldError, wrong field names, no year filter), `TotalWaterProduction.save` (M2M misuse, 86400 vs 3600, wrong `ElectricityCost` query), `TotalWaterDemand.save` (units off by 1e9, unguarded `.get`), `ConsumptionCapita` (`total_consumption_m3_yr` never computed), `AvailableFreshWater.save` (shadowed `Province` → `UnboundLocalError` on every save), `ExtractionWater.save` (forced `source` override, class-attribute cost lookups, per-day cost in per-m³ field), `CoverageWaterSupply` (only recomputed on its own save), `NonRevenueWater` (stale sibling ILI, apparent losses ignored), `SupplySecurity`/`UsersLocation`/`AreaAffectedDrought`/`WaterTreatment`/`ImportedWater` (no `save()` though fields are derivable).
- **housing:** `Rentals.save` uses non-existent `property.price` → **always raises**; `Mortgage`, `HousePriceIndex`, `HousingSupplyDemand`, `HousingProject` have no `save()`; `HousingAffordability` never sets `affordabilityStressLevel` and doesn't pull from Rentals/Mortgage/Property.
- **administrative:** `Province.save` bugs (wrong kwarg, `None` division); `City.save` overwrites a directly imported `currentPopulation` with 0 when there are no District children (**conflicts with CBS import in workstream 2**); moving a child to another parent leaves the old parent stale (no `pre_save` capture).
- **physicalEnv:** `LandCoverVector.percentage` only computed by importer; `EnvironmentalCosts` field-name mismatch (`price_EUR_price_EUR_droughtDamage_m3` vs `price_EUR_droughtDamage_m3`).
- **builtup / nature:** `Park.area`, `Street.length`, `Facility.neighborhood` not derived; `Building.save`/`GreenSpaces.save`/`Property.save` overwrite an existing FK with `None` when the spatial lookup misses (`Property.building` is required → `IntegrityError`).
- **urban_heat:** `NatureBasedSolutionPolygon.area` not derived; `UTCI/PET.category` never set from `classify_*`.
- **weather / Energy:** `Meteorology.vapor_pressure_hPa` derivable (Magnus) but not computed; several `__str__` use wrong field names (`Province` vs `province`) and raise.

*Missing signals (DAG-mapped):* City/ConsumptionCapita → TotalWaterDemand → SupplySecurity; Extraction/Imported/Treatment/Pipe/Metered → OPEX; PipeNetwork → CoverageWaterSupply & NonRevenueWater; Property → Rentals/Mortgage/HousePriceIndex/HousingAffordability; City.area → LandCoverVector.percentage.

**Proposed order (each step = small commit + tests):**
1. Quick wins that unblock others: fix `core/utils.py` `urbanHeat` typo (B4), wire `watersupply` signals + fix receiver (B2), fix `Province.save` (B7), `Rentals.save`, `AvailableFreshWater.save`, `__str__` mismatches.
2. Metre-scale 28992 test factory (prerequisite for meaningful assertions).
3. Watersupply chain: `ConsumptionCapita` → `TotalWaterDemand` → `SupplySecurity`; `TotalWaterProduction`; `ExtractionWater`; `OPEX` + signals.
4. Housing chain: `Mortgage`, `Rentals`, `HousingAffordability` (needs the stress-threshold decision – existing TODO), `HousePriceIndex`.
5. Spatial derivations: `LandCoverVector.percentage`, `Park/Street/Facility/NBS` area/length/neighborhood (do **not** overwrite existing FKs with `None`).
6. Cascade hardening: capture old parent on move; make `City.save` not clobber imported population (decide with workstream 2).

### 2. Population curve from CBS 85173NED  ☐
**Goal:** projected population per year, visible as a curve, adjustable by the user, feeding the indicators.

- ☐ Confirm what 85173NED contains (dimensions, regions, years) via CBS OData `…/85173NED/DataProperties` – **not verifiable offline; check when implementing**
- ☐ Storage for projections (new model related to Province/City? or reuse existing fields?) *(explorer B)*
- ☐ Import path: new `CBSImporter` catalog entry + field mapping in `importer/external_catalog.py`
- ☐ A single shared helper that returns projected population for `(unit, year, scenario_params)` so water/housing/heat dashboards all use it
- ☐ Chart (reuse whatever the front end already uses – explorer B is checking) + a growth-rate slider using the existing HTMX `recalculate_indicators` pattern
- ☐ Wire into `_get_province_data` of each dashboard; tie the year selector (2025…2050) to the curve
- ☐ Address DAG gap: `Population_Growth -> Total_Population/Urbanization` (currently flat fields)

**Findings (explorer B, done):**

- **CBS importer exists, 85173NED is not referenced anywhere.** `CBSImporter` (`importer/external_data.py:1315-1543`) is driven by catalog entry + `FIELD_MAPPINGS`; the only CBS entry is `CBS_Housing` (`importer/external_catalog.py:281-296`, table 86098NED) — use it as the template. `get_metadata(table_id)` (1535) fetches `/DataProperties` for column discovery.
- **Importer assumptions that may not fit a prognose table:** `startswith(Perioden,'YYYY')` year filter (period codes like `2023JJ00`) and a bbox → `GM%04d` gemeente filter (`external_data.py:1364-1405`). Prognose tables are usually national/provincial with plain-year periods → likely needs a `region_prefix` param or a new branch. **Confirm against 85173NED metadata before coding.**
- **No projection store** in any `models.py`. Baseline is a single snapshot: `Province/City.currentPopulation`, `populationDate`; `City.popGrowthRate` / `urbanizationRate` exist but are **never read** (the DAG gap).
- **No shared population helper** – every dashboard reads `adminUnit.currentPopulation` directly (`watersupply/views.py:93`, `housing/views.py:36`). Only water demand actually uses it (`consumption/1000*population`, `watersupply/views.py:157`); housing returns it but never uses it; urban heat ignores it.
- **Year plumbing already exists** (buttons 2025/26/27/30/50 → `window.ACTIVE_YEAR` → `syncPanelBtns` → `refreshActivePanel`). Water and housing take `year`; **urban heat has no year** in URL/view.
- **What-if pattern:** one slider per panel, `hx-get` to `recalculate/`, swaps `#indicators-grid`. Each slider's `hx-include="this"` sends only its own value → a second control needs a shared `<form>`/`hx-include`.
- **No charting library** (gauges are hand-written SVG). Stack: Tailwind v4 CDN, HTMX 1.9.10, Mapbox GL 3.18; styles in `core/static/css/indicators.css` (`.card`, `.slider-*`).
- **Recommended shape:** new `administrative/population.py` → `get_population(unit, year, growth_override=None)`; a projection model keyed `(province|city, year)` with `last_updated`; new `CBS_PopulationForecast` catalog entry; extend each `_build_indicators` with a `population_override`; chart as inline SVG (matches existing gauges) unless a chart lib is preferred.

**Bugs found by this explorer (candidates to fix, tracked in "Bugs found" below).**

### 3. Dashboard button toggles the indicators panel  ☐
**Goal:** `#btn-dashboard` opens/closes `#side-panel`.

- ☐ Confirm current handler state in `static/js/{panels,events,MapUI}.js` *(explorer C)*
- ☐ Toggle `open` on `#side-panel`; keep `.mode-btn.active`, the `✕` button and the `htmx:afterSwap` opener in sync
- ☐ When opened with no indicator tool active: decide which panel to load (see Open questions)
- ☐ Manual check in browser (open, close, switch tool while open, change year while open)

**Findings (explorer C, Part B – done). Correction to the starting assumption: the button is *not* a no-op.**

- `core/static/js/Events.js:89` binds `#btn-dashboard` → `showDashboard()` (`core/static/js/Panels.js:9-81`), which writes mock KPI cards into `#panel-body`, sets the title "CITY DASHBOARD", hides `#layers-panel` and **adds** class `visible` to `#side-panel`. It never removes it, so a second click does not close it.
- **The panel opens/closes via class `visible`** (`mainMap.css:628-646`: `display:none` → `.visible {display:flex}`), added by the toolbar click (`Events.js:45-50`, only if `TOOL_CONTENT[tool]` exists), removed by `✕` (`Events.js:54-56`) and by the layers/visible pills.
- Class `open` (added in the `htmx:afterSwap` handler, `mainMap.html:506-512`) has **no CSS rule → decorative**. That is why the Housing tool can show nothing: `Config.js` `TOOL_CONTENT` has no `Housing` entry (button uses capital-H `data-tool="Housing"`), so no `visible` is ever added.
- No `.mode-btn.active` style exists.
- `refreshActivePanel(fallbackTool)` (`mainMap.html:555`) already picks the active admin tool or a fallback and loads it via `htmx.ajax` **without** re-triggering the toolbar handler (layer visibility untouched).
- **Smallest change:** replace the direct `showDashboard` binding with a toggle: if `#side-panel.visible` → remove it, clear `.active` on the button; else add `visible`, set `.active`, call `refreshActivePanel(<default tool>)`, hide `#layers-panel`. Add `.mode-btn.active` CSS. Also switch the `htmx:afterSwap` handler from `open` to `visible` (fixes Housing).
- Edge cases: Scenarios/toolbar clicks while the dashboard is open should clear/keep the button state consistently; if `refreshActivePanel` finds no button the panel would open with stale content; the mock `showDashboard` content should be dropped or moved under another trigger (the guided tour text at `mainMap.html:397-400` describes Dashboard/Scenarios as scenario controls).
- Also noticed: template loads `events.js/panels.js/config.js` (lowercase) but the files are `Events.js/Panels.js/Config.js` – works on Windows, **404s on a case-sensitive host**.

### 4. KNMI WBGT import ("latest heat force")  ☑ (implemented in Phase 4; live-API check pending)
**Goal:** an option under "Retrieve Data from APIs" to fetch the latest WBGT file from the KNMI Data Platform.

- ☐ KNMI flow: list `/files` → pick latest → request temporary download URL → download. Needs an `Authorization` API key (env var name to be decided; never commit the value)
- ☐ Decide target: new raster model in `urban_heat` (+ `cog_path`, COG export via `core/signals.py`) vs. point/station values in `weather.Meteorology` *(depends on the file format – likely a gridded NetCDF/HDF5; unverified)*
- ☐ New catalog entry + handler in `importer/external_data.py`; reproject to `COORDINATE_SYSTEM` (reuse `load_raster_into_target_model`, and `to_storage_srid` for vectors)
- ☐ Check requirements for reading the format (netCDF4/xarray/h5py) *(explorer C)*
- ☐ Show latest WBGT (and its heat-stress class) in the urban-heat indicators

**Findings (explorer C, Part A – done):**

- **A KNMI key already exists:** env var `KNMI_API_KEY` (in `.env` / `.env_template`, read at `DigitalTwin/settings.py:77`, described there as an authenticated-tier key). Used today only for the WMS proxy (`weather/views.py::_wms_auth_headers` sends the **raw key, no "Bearer"**; `_fetch_with_retry` reusable). ⚠ its value was echoed into the session transcript by an exploration grep – consider rotating.
- **Catalog pattern:** `importer/external_catalog.py` `EXTERNAL_DATA_CATALOG` entries (raster example `gee_temperature`) with keys `key, source, category, name, description, target_model, url, format, params, enabled, requires_bbox, requires_date_range, requires_auth, slow, resolution_m…`; `SOURCE_INFO` per source; dispatcher `import_dataset()` (`external_data.py:1943`) branches on `source`/`format` → add `elif source == "knmi": KNMIImporter.fetch_latest_wbgt(...)`.
- **Gotcha:** `views_external.py:33` hardcodes `source_order` and `with_source_info` (46) does `SOURCE_INFO[ds["source"]]` → a new `source:"knmi"` without a `SOURCE_INFO` entry raises `KeyError`. UI needs no bbox/credentials panel if the key is server-side (`requires_bbox: False`).
- **Handler outline:** `GET …/files?maxKeys=1&orderBy=created&sorting=desc` (Authorization = `settings.KNMI_API_KEY`) → `GET …/files/{filename}/url` → `temporaryDownloadUrl` (download **without** the auth header) → convert to GeoTIFF under `MEDIA_ROOT/imports/knmi/` → `load_raster_into_target_model(..., acquisition_date=<parsed from filename>)`. KNMI anonymous tier is 1 req/s/IP.
- **File format unknown offline** (likely NetCDF/HDF5 grid). `requirements.txt` has xarray, rasterio, rio-cogeo, gdal but **no netCDF4/h5netcdf/h5py/rioxarray** → simplest is GDAL's NetCDF/HDF5 driver via rasterio; verify with a real file.
- **No WBGT model/field exists.** Recommended target: new `WetBulbGlobeTemperature` raster model in `urban_heat/models.py` copying the `UTCI` pattern (`raster`, `date_time`, `source`, `measurement_method`, `resolution`, `cog_path`; +migration). It plugs into `load_raster_into_target_model` and the COG auto-export unchanged. `weather.*Raster` would fail `full_clean()` (needs `name`), `Meteorology` is per-station (not suitable). **Requires fixing B4 first** (urban_heat missing from `RASTER_REGISTRY` → no COG export).
- **Indicator:** add one line in `urban_heat/calculations.py::get_thermal_indices` (`_raster_stats_sql('urban_heat_wetbulbglobetemperature', …)`), a `classify_wbgt` (thresholds are a decision – typical bands ~25/28/30/33 °C), a gauge block in `partials/indicators_grid.html` copying the UTCI one (same `data-gauge-*` attributes) and `MAX_WBGT` in `_build_indicators`.
- `urban_heat/models.py:33` defines a `WMSLayer` duplicating `weather.WMSLayer` (worth cleaning later).

## Bugs found during exploration (not yet fixed)

| # | Where | Problem | Workstream | Status |
|---|-------|---------|-----------|--------|
| B1 | `importer/external_data.py:1447` | `get_model("common","City")` – app `common` no longer exists (City is in `administrative`); breaks CBS FK resolution incl. `CBS_Housing` | 2 | ☑ fixed (Phase 0). Also confirmed: importer maps `GM0363` → `City.pk=363` |
| B2 | `watersupply/signals.py:9-22` | Uses `F("province__population")` but `ConsumptionCapita` has no `province` field → signal is broken | 1 | ☑ fixed (Phase 1) |
| B3 | `mainMap.html:526-527` | `Housing` entry in `ADMIN_PANEL_TOOLS` omits `level` → URL matches nothing in `housing/urls.py` after year/location change | 2, 3 | ☑ fixed (Phase 3): Housing builder now `/housing/indicators/<level>/<location>/<year>/` |
| B4 | `core/utils.py:6` | `allowed_apps` has `urbanHeat`; installed app is `urban_heat` → **confirmed**: urban_heat models absent from registries, layer catalog and COG auto-export (`LookupError` swallowed at `utils.py:15`) | 1 | ☑ fixed (Phase 0): registry now has 10 urban_heat models / 6 rasters / 2 vector; `urban_heat.WMSLayer` also joins `WMS_REGISTRY` (harmless) |
| B5 | `watersupply/models.py:61-64` (`TotalWaterDemand.save`) | **Confirmed**: litres stored in a Mm³/day field (needs `/1e9`); unguarded `.get(city, year)` | 1 | ☑ fixed (Phase 1) |
| B9 | `housing/models.py:107-110` (`Rentals.save`) | `self.property.price` doesn't exist → every save raises `AttributeError` | 1 | ☑ fixed (Phase 1) |
| B10 | `watersupply/models.py:180-183` (`AvailableFreshWater.save`) | Local `Province` shadows the class → `UnboundLocalError` on every save | 1 | ☑ fixed (Phase 1) |
| B11 | `watersupply/models.py:640-682` (`TotalWaterProduction.save`) | M2M used as scalar; `*86400` should be `*3600` (24× error); wrong-case `Province=` kwarg | 1 | ☑ fixed (Phase 1) |
| B12 | `administrative/models.py:72-76` (`City.save`) | Overwrites directly-imported `currentPopulation` with District sum (0 if none) – conflicts with CBS import | 1, 2 | ☑ fixed (Phase 3): a city with no district population keeps its own value |
| B13 | `builtup/models.py` `Property.save`, `Building.save`, `nature` `GreenSpaces.save` | Overwrite an existing FK with `None` when the spatial lookup misses (`Property.building` required → `IntegrityError`) | 1 | ☐ |
| B14 | `physicalEnv/models.py:200` vs `watersupply/models.py:289` | Field name mismatch `price_EUR_price_EUR_droughtDamage_m3` vs `price_EUR_droughtDamage_m3` | 1 | ☑ fixed (Phase 1) |
| B15 | several `__str__` (LandCoverVector, EnvironmentalCosts, ElectricityCost, CentralBankPolicy, CreditSupplyConditions, SupplySecurity, MeteredResidential) | Reference non-existent attributes → raise in admin/shell | 1 | ☑ fixed (Phase 1) |
| B16 | `watersupply/tests/factories.py:11-17` | 4326 polygons stored in a 28992 field (SRID dropped by `MultiPolygon`) → meaningless areas | 1 | ☑ fixed (Phase 0): 1 km² RD square, SRID passed to `MultiPolygon` |
| B6 | `watersupply/models.py` `OPEX.save()` | Uses non-existent `ExtractionWater.extraction_volume_m3` (from CLAUDE.md) | 1 | ☑ fixed (Phase 1) |
| B7 | `administrative/models.py` `Province.save()` | `City.objects.filter(Province=...)` wrong-case kwarg (from CLAUDE.md) | 1 | ☑ fixed (Phase 1) |
| B8 | `importer/views.py:412` `_generic_import` | `field_by_name` only holds geometry/raster fields, so mapped attribute columns are likely never imported (unverified) | – | ☐ verify |

| B17 | `core/static/js/Config.js` `TOOL_CONTENT` + `mainMap.html:506-512` | No `Housing` entry and the `open` class has no CSS → Housing panel doesn't show unless already visible | 3 | ☑ fixed (Phase 2): `visible` added in the htmx handler. Housing panel still needs a manual click-test |
| B18 | `mainMap.html:16-22` | Script names lowercase vs files `Events.js/Panels.js/Config.js` → 404 on case-sensitive hosts | 3 | ☑ fixed (Phase 0) |
| B19 | `importer/views_external.py:33,46` | New `source` without `SOURCE_INFO` entry → `KeyError`; `source_order` hardcoded | 4 | ☑ fixed (Phase 4): `knmi` added to both; a test renders the import page |
| B23 | `importer/external_data.py::load_raster_into_target_model` | Only stored a `date` field, so `date_time` rasters (all urban_heat models) always got the import time instead of the acquisition time; `finally` block cannot delete its temp `.tif` files on Windows (`field_values` still references the `GDALRaster`, so `del gdal_raster` doesn't close it → `WinError 32` warnings, temp files left behind) | 4 | ◐ date fixed (Phase 4); temp-file leak **not fixed** (pre-existing, affects every raster import) |
| B20 | `importer/external_data.py:397` region | `source_labels` has no `knmi` (falls back to raw string – acceptable) | 4 | ✖ ok |

| B21 | `watersupply/calculations.py::calculate_supply_security` | Summed `TotalWaterDemand` of **all years** and assumed m³/day while the model stores Mm³/day → now takes `year` and converts | 1 | ☑ fixed (Phase 1) |
| B22 | `administrative/signals.py` | Cascade updates `City` via `update()` → `post_save(City)` never fires for cascaded population changes → added `city_population_changed` custom signal | 1 | ☑ fixed (Phase 1) |

## Decision log

| # | Date | Decision | Why | Status |
|---|------|----------|-----|--------|
| D1 | 2026-09-21 | Track the plan in a markdown file | User request, to follow decisions/changes later | ☑ |
| D2 | 2026-09-21 | **Dashboard button** toggles `#side-panel` (`visible` class). When no admin-driven indicator tool is active it shows a **summary panel**: number of layers available + total population of the selected administrative unit (or the city if none selected). If an admin tool (water/heat/housing) is active it reloads that tool as today. | User answer (replaces the "load Water/Heat by default" idea and the mock KPIs) | ☐ |
| D3 | 2026-09-21 | **Population curve is computed at City level** from CBS 85173NED (table is per gemeente) and **exposed for City, District and Neighborhood**. District/Neighborhood values = city projection × the unit's share of the city baseline. **Province = sum of its cities** (result of the lower levels; reuses the existing cascade). | User answer | ☐ |
| D4 | 2026-09-21 | **WBGT** is stored in a **new `urban_heat` raster model** (`WetBulbGlobeTemperature`, UTCI pattern). Uses existing `KNMI_API_KEY`. | User answer (recommended option) | ☑ |
| D10 | 2026-09-21 | KNMI import details (Phase 4): (a) GeoTIFF is reprojected to `COORDINATE_SYSTEM` **inside `KNMIImporter.to_geotiff`**, not left to `load_raster_into_target_model`, because that loader only reprojects when the source has an EPSG code and KNMI grids may not; (b) if a file holds several time steps only the **first** is used (matches the valid time parsed from the file name) and the result message says so; (c) scale/offset and Kelvin are converted to °C; (d) the file's valid time is parsed from the file name (fallback: the API's `created`) and an already-imported valid time is **skipped without downloading**; (e) WBGT categories are **provisional** bands at 25/28/30/33 °C, kept in one table (`WBGT_BANDS`) and shown as such in the info tooltip; (f) WBGT is not a DAG node (observed input), so no DAG edge was documented. | The real file layout could not be inspected offline; each choice is the safest reading and is covered by tests on synthetic grids | ☑ / ☐ confirm bands + live file |
| D6 | 2026-09-21 | Water demand/production stored in **Mm³/day** (as documented); consumers convert. OPEX/SupplySecurity signals refresh only the **latest** record (inputs carry no year). `TotalWaterProduction` not added into OPEX (its energy cost is inside `opex_EUR_m3`). `UsersLocation`/`WaterTreatment`/`ImportedWater` derivations skipped (ambiguous formulas). | Consistency with the model docs; avoid double counting and overwriting historical snapshots | ☑ |
| D7 | 2026-09-21 | Dashboard: closed→open shows the **active tool's indicators** if one is active (water/heat/housing), else the **summary** (layers available/visible + population of the explicitly clicked unit, else the city at the map centre); open→close hides the panel. Button `.active` follows the panel via a MutationObserver. Explicit selection tracked separately (`window.SELECTED_UNIT`) from `ACTIVE_*` (which also follows panning). | Matches D2 without regressing indicator panels | ☑ |
| D8 | 2026-09-21 | Population "play" control = **variant selector (CBS Prognose / lower 67 % / upper 67 %) + an additional growth-adjustment slider** applied on top of the chosen variant. `PopulationProjection.scenario` stores `prognose|low|high`. | 85173NED provides these three variants natively | ☑ (proposed, confirm when UI is built) |
| D8b | 2026-09-21 | Implemented as decided: `PopulationProjection(city, year, scenario, population)`; `get_population()` in `administrative/population.py`; controls (variant + extra growth %/yr from 2025, clamped ±5) live in the dashboard summary **and** the water/housing panels so the effect is visible next to the indicators; state in `window.POP_SCENARIO/POP_GROWTH`, sent as `?pop_scenario=&pop_growth=`. **Housing demand is not yet driven by population** (needs a household-size assumption) – only shown. Urban heat unchanged (no year). | Housing demand comes from stored `HousingSupplyDemand`; inventing a household size would be a modelling decision | ☑ / ☐ housing link open |
| D9 | 2026-09-21 | **Population UI redesign (user request):** the what-if controls and the curve moved out of the dashboard/indicator panels into a **bottom Population dock** opened from the Population pill, independent of the side panel (slides left of it when both are open). It shows today / projected-for-year / change / 67 % interval, and a **Curves-style graph**: dark plot with grid, smooth monotone-cubic curve, square handles every 5 years + selected year, shaded low-high band, dashed 'today' line, hover read-out. Indicator panels keep only a header line with the projected population; the dashboard keeps only the value card. | Lets the indicators stay visible while playing with the population; a graph is easier to read | ☑ |
| D5 | 2026-09-21 | **Audit scope now: quick wins + watersupply chain.** Housing chain, spatial derivations and cascade hardening are a **second round** (kept in the plan, not implemented now). | User answer (recommended option) | ☐ |

## Open questions

Resolved by the user on 2026-09-21 (see D2–D5). Still open, to settle **during implementation**:

1. ~~"Play" control~~ **Resolved by D8 below** (85173NED has median/low/high variants).
2. **WBGT heat-stress thresholds** for `classify_wbgt` – **implemented as provisional 25/28/30/33 °C bands** (`urban_heat/calculations.py::WBGT_BANDS`); still to be confirmed against the standard the project follows.
3. **WBGT file format / GDAL driver** – GDAL 3.11 in the venv has the NetCDF and HDF5 drivers, so no new dependency was added; `to_geotiff` handles multi-variable containers (prefers a subdataset named `*wbgt*`), packed values and Kelvin. **Still to verify with one real download** (variable name, time-step layout, CRS present?).
4. **`City.save` vs imported CBS population (B12):** with the city as the source of truth for the curve, decide whether `City.currentPopulation` stays the District sum or becomes the imported baseline.

## Final implementation plan (decisions D2–D5 applied)

Order chosen so each phase unblocks the next; each phase = its own commit(s) + tests. Run the suite with `--keepdb`.

### Phase 0 – Foundations (small, unblock everything)  ☑ done 2026-09-21
- B4 `core/utils.py:6` `'urbanHeat'` → `'urban_heat'` (registers urban_heat models; needed for WBGT COG export). Check nothing relied on the missing registration.
- B16 metre-scale **28992** polygon factory (fix `watersupply/tests/factories.py`) so derived areas/densities can be asserted; re-run existing tests.
- B1 `importer/external_data.py:1447` `("common","City")` → `("administrative","City")`.
- B17/B18 front-end: rename script includes to match `Events.js/Panels.js/Config.js`; add `Housing` handling (see Phase 2).

### Phase 1 – Workstream 1, round 1: quick wins + watersupply chain  ☑ done 2026-09-21 (41 tests OK)
Quick wins: B2 (add `ready()` to `watersupply/apps.py`; rewrite receiver to use `city__currentPopulation`), B7 `Province.save`, B9 `Rentals.save`, B10 `AvailableFreshWater.save`, B14 field-name mismatch, B15 `__str__` fixes.
Watersupply chain (follow existing conventions: `update()` in signals, `dispatch_uid`, guard against recursion):
- `ConsumptionCapita.save` computes `total_consumption_m3_yr`; `TotalWaterDemand.save` fixes units (B5, `/1e9`) and guards missing rows; `SupplySecurity.save` (`supply_security_pct`, `service_time_hours`).
- `TotalWaterProduction.save` (B11: M2M, `3600`, `ElectricityCost` query, imported water); `ExtractionWater.save` (don't override explicit `source`, instance-based cost lookups).
- `OPEX.save` (B6: real field names, year filter, `totalOPEX_EUR`, zero guards).
- Signals: City → ConsumptionCapita/TotalWaterDemand; ConsumptionCapita → TotalWaterDemand → SupplySecurity; Extraction/Imported/Treatment/Metered → OPEX. Update the DAG-edge docstrings + the "DAG Edge Coverage Gaps" section of `CLAUDE.md`.
- Tests: one per model `save()` and per signal (change source → dependent updated, no recursion).
**Deferred to round 2 (kept in the audit above):** housing chain (Mortgage/Rentals/HousingAffordability/HousePriceIndex – needs the stress-threshold decision), spatial derivations (`LandCoverVector.percentage`, Park/Street/Facility/NBS), cascade hardening (old-parent capture, B12), B13, weather signals.

### Phase 2 – Workstream 3: Dashboard toggle + summary panel  ☑ done 2026-09-21 (code + server tests; **manual browser click-test still pending – Chrome extension was not connected**)
- `core/static/js/Events.js:89`: replace the `showDashboard` binding by a toggle. If `#side-panel.visible` → close + clear `.active`. Else open (`visible`, `.active`, hide `#layers-panel`): if an admin tool is active (`findActiveAdminTool()`), `refreshActivePanel()`; otherwise render the **summary panel** (D2).
- Summary panel content: **number of layers available** (from `availableLayers` in `Config.js`/`Layers.js`) and **total population of the selected administrative unit, or the city if none selected**. Population comes from a small new endpoint in `mainMap/views.py` (+ `mainMap/urls.py`, small partial template) reusing `administrative/admin_units.py::resolve_admin_unit` and `window.ACTIVE_LEVEL/ACTIVE_LOCATION`; it will later also host the population curve (Phase 3).
- Replace the mock KPI cards in `Panels.js::showDashboard`; keep `showScenarios` untouched.
- `mainMap.css`: add `.mode-btn.active`. `mainMap.html:506-512`: `open` → `visible` (fixes Housing panel, B17). Keep the ✕ button, layer pills and toolbar clicks consistent (clear the button's `.active` state when the panel closes any other way).
- Manual browser check (see Verification).

### Phase 3 – Workstream 2: population curve (CBS 85173NED)  ☑ done 2026-09-21 (87 tests OK; **UI click-test pending**, and import not yet run against the live CBS API)

**Verified facts about 85173NED** (fetched from the public CBS OData API on 2026-09-21 – no longer an assumption):
- Title: *Regionale prognose 2023-2050; bevolking, intervallen, regio-indeling 2021* (one-off table; age breakdowns were removed by CBS in July 2023, only totals remain).
- Dimensions: `RegioIndeling2021` (geo: gemeente `GM####`, also provincie/COROP), `PrognoseInterval`, `Leeftijd`, `Perioden` (`2023JJ00` … `2050JJ00`). Single measure `TotaleBevolking_1`, **unit ×1 000** (Enschede `GM0153`: 164.8 → 164 800 in 2025).
- `PrognoseInterval` = **`MW00000` Prognose (median)**, **`MOG0067` lower bound of the 67 % interval**, **`MBG0067` upper bound** → CBS itself provides low/median/high variants. `Leeftijd` total = `10000`.
- Codes come without trailing spaces here (the importer already `.strip()`s).
- **Importer gaps to close:** (a) region column is `RegioIndeling2021`, not the hard-coded `RegioS` used in the bbox filter (`external_data.py` ~1385-1405) → add a `region_field` param; (b) value must be ×1000 → add a `__value_scale__` mapping key; (c) rows must be filtered/kept per `PrognoseInterval` (store as `scenario`) and `Leeftijd eq '10000'` (via `params.filter`); (d) the `startswith(Perioden,'YYYY')` year filter already fits.

- **Model** `PopulationProjection` in `administrative/models.py` (+ `0002` migration): `city` FK, `year`, `population`, `scenario`/`variant`, `source`, `last_updated`; unique `(city, year, scenario)`. City-level only (D3).
- **Import:** new catalog entry `CBS_PopulationForecast` in `importer/external_catalog.py` (copy `CBS_Housing`: `source:"CBS"`, `format:"odata"`, `target_model:"administrative.PopulationProjection"`) + `FIELD_MAPPINGS` (gemeente code `GM####` → City FK via `__city_source__`, year from `Perioden`, population measure from `get_metadata("85173NED")`). Confirm the gemeente code ↔ `City.pk` assumption (`external_data.py:1385-1405`) with real data.
- **Helper** `administrative/population.py::get_population(unit, year, growth_override=None)`: City = projection for `year` (or baseline × compound growth override); **District/Neighborhood = city value × unit's share of the city baseline**; **Province = sum of its cities** (D3). Decide B12 here.
- **Wire into indicators:** `watersupply/views.py` (`_get_province_data` ~93, `_build_indicators` ~154: population/override, demand = `consumption/1000*population`); `housing/views.py` (demand from population; fix Housing URL builder B3 in `ADMIN_PANEL_TOOLS`); urban heat only if a real dependency is defined (it has no `year` today – out of scope unless requested).
- **UI:** population-curve card in the dashboard summary panel: inline SVG line chart (matches existing hand-written gauges; no new library) + growth slider (HTMX, shared `<form>`/`hx-include` so it can send to several panels) styled with `indicators.css` tokens. Slider value stored in `window` state and passed as `?growth=` to the `recalculate` endpoints; year buttons keep working via `syncPanelBtns/refreshActivePanel`.
- Document DAG edges `Population_Growth -> Total_Population` / `Total_Population -> Total_Water_Demand` in the docstrings.
- Tests: share downscaling (districts/neighborhoods sum to city), province = Σ cities, override changes water demand.

### Phase 4 – Workstream 4: KNMI WBGT import  ☑ done 2026-09-21 (144 tests OK; **never run against the live KNMI API** – the real file format/variable name is still unverified, see open question 3)
- **Model** `WetBulbGlobeTemperature` in `urban_heat/models.py` (UTCI pattern: `raster`, `date_time`, `source`, `measurement_method`, `resolution`, `cog_path`) + migration.
- **Catalog:** entry `knmi_wbgt` (`source:"knmi"`, `requires_bbox:False`, `requires_auth:False` – key is server-side) + `SOURCE_INFO["knmi"]` + add to `source_order` in `importer/views_external.py` (B19).
- **Handler:** `KNMIImporter.fetch_latest_wbgt` in `importer/external_data.py` + branch in `import_dataset()`: list latest file (`maxKeys=1&orderBy=created&sorting=desc`, `Authorization: settings.KNMI_API_KEY`, raw key, reuse `_fetch_with_retry` style) → `/files/{name}/url` → download **without** auth header → convert to GeoTIFF via GDAL/rasterio (verify driver; add `netCDF4`/`h5netcdf` only if needed) → `load_raster_into_target_model(..., acquisition_date=<from filename>)` (reprojects to `COORDINATE_SYSTEM`).
- **Indicator:** `get_thermal_indices` line for the new table, `classify_wbgt`, `MAX_WBGT`, gauge block in `urban_heat/templates/.../partials/indicators_grid.html` (copy the UTCI block's `data-gauge-*`).
- Tests: mock `requests` for the two KNMI calls + a small synthetic GeoTIFF; verify the raster is stored in 28992 and the COG is exported.
- Never log/commit the API key.

**Implemented as planned, with these deviations:** the indicator colour comes from a band table (`wbgt_color`) instead of the UTCI block's `'Heat' in category` test, which would have painted "No Heat Stress" red; `load_raster_into_target_model` gained `date_time` + `measurement_method` support (B23); no `netCDF4`/`h5netcdf` dependency was needed. Files: `urban_heat/{models,calculations,views,tests}.py` + `migrations/0004_wetbulbglobetemperature.py`, `urban_heat/templates/urban_heat/partials/indicators_grid.html`, `importer/{external_catalog,external_data,views_external,tests}.py`.

### After every phase
- Run the full suite (`python manage.py test --settings=DigitalTwin.settings_test --keepdb`), update the **Change log** below, then `graphify update .` (CLAUDE.md).

## Verification (end to end)

- `python manage.py test --settings=DigitalTwin.settings_test --keepdb` (note: a stale `test_digitaltwin` DB exists, hence `--keepdb`)
- New signal tests: change a source model → assert the dependent model's field updated, and no recursion.
- Population: import 85173NED → curve renders → moving the slider changes water/housing/heat indicators.
- Dashboard: manual browser check of open/close/switch-tool/year-change.
- KNMI: import runs from the UI; WBGT layer/indicator visible; COG appears under `cogs/urban_heat/` if raster.
- After code changes run `graphify update .` (per CLAUDE.md).

## Change log (fill in during implementation)

| Date | Area | Files | Summary | Commit |
|------|------|-------|---------|--------|
| 2026-09-21 | Importer CRS (before this plan) | `importer/{utils,views,forms,external_data,tests}.py`, `RasterMapping.html`, `watersupply/models.py` | All geometries/rasters stored in `COORDINATE_SYSTEM`; `to_storage_srid()` helper; `MultiPolygon` SRID-drop fixes; 11 importer tests | uncommitted |
| 2026-09-21 | Phase 0 | `core/utils.py`, `importer/external_data.py`, `watersupply/tests/factories.py`, `mainMap/templates/mainMap.html` | B4 registry typo, B1 `common`→`administrative`, B16 28992 factory, B18 script-name case. Suite 15/15 OK, `manage.py check` clean | uncommitted |
| 2026-09-21 | Phase 1 | `watersupply/{models,signals,apps,calculations,views}.py`, `administrative/{models,signals}.py`, `physicalEnv/{models,migrations/0002}.py`, `housing/models.py`, `Energy/models.py`, `core/tests.py`, `watersupply/tests/test_water_chain.py`, `CLAUDE.md` | B2/B5/B6/B7/B9/B10/B11/B14/B15/B21/B22 fixed; water chain `save()`+signals (consumption→demand→supply security; extraction/imported→production/OPEX; NRW ILI; pipe/users→coverage); `EnvironmentalCosts` field rename migration; CLAUDE.md DAG-gap/TODO notes updated. 41 tests OK, `makemigrations --check` clean | uncommitted |
| 2026-09-21 | Phase 2 | `core/static/js/{Panels,Events,Map_init,Config}.js`, `core/static/css/mainMap.css`, `mainMap/{views,urls,tests}.py`, `mainMap/templates/mainMap.html`, `mainMap/templates/mainMap/partials/dashboard_summary.html`, `administrative/admin_units.py` | Dashboard toggle + summary panel; new `/api/dashboard/summary/` partial; `city_of()` helper; `open`→`visible` (Housing panel fix, B17); `Config.js` tool categories `urbanHeat`/`'urban_heat,'` → `urban_heat` (needed after B4 so heat layers match the tool filters). 6 new tests, JS syntax-checked, static assets verified served | uncommitted |
| 2026-09-21 | Phase 3 | `administrative/{models,population,test_population}.py` + `migrations/0002_population_projection.py`, `importer/{external_data,external_catalog,tests}.py`, `watersupply/{views}.py` + `tests/test_population_wiring.py`, `housing/views.py`, water/housing `indicators_panel.html`, `Templates/partials/_population_controls.html`, `mainMap/{views,tests}.py` + `partials/dashboard_summary.html`, `mainMap.html`, `Panels.js`, `indicators.css`, `CLAUDE.md` | New `PopulationProjection` + CBS 85173NED import (region column param, x1000 scale, variant map); `get_population()`/`population_curve()`; water & housing use projected population; population what-if controls + SVG curve in dashboard; B1/B3/B12 fixed. 87 tests OK, `makemigrations --check` clean | uncommitted |
| 2026-09-21 | Phase 3 redesign | `mainMap/{charts,views,urls}.py`, `mainMap/test_charts.py`, `mainMap/templates/mainMap/partials/{population_panel,dashboard_summary}.html`, `mainMap.html`, `Templates/partials/_population_controls.html`, water/housing `indicators_panel.html`, `core/static/js/{Panels,Events,Map_init}.js`, `core/static/css/{mainMap,indicators}.css`, tests | Bottom Population dock (own endpoint `/api/population/panel/`), Curves-style SVG graph with the 67 % band, values panel, hover read-out, reset; controls removed from indicator panels. 109 tests OK; layout checked in headless Edge screenshots and Panels.js behaviour (hover, toggle, what-if state, reset) checked in headless Edge | uncommitted |
| 2026-09-21 | Importer admin bbox (side request) | `importer/{external_catalog,external_data,views_external,urls,tests}.py`, `importer/templates/importer/external_data.html` | Import-map area of interest picked from cities for districts and from districts for neighborhoods (`bbox_from` in the catalog, `/importer/external/areas/?level=`); picker layers created up front (fixes a load race). 23 importer tests OK | uncommitted |
| 2026-09-21 | Phase 4 | `urban_heat/{models,calculations,views,tests}.py` + `migrations/0004_wetbulbglobetemperature.py`, `urban_heat/templates/urban_heat/partials/indicators_grid.html`, `importer/{external_catalog,external_data,views_external,tests}.py`, `CLAUDE.md` | New `WetBulbGlobeTemperature` raster; `knmi_wbgt` catalog entry + `KNMIImporter` (latest file → temp URL → GeoTIFF in 28992 → model → COG signal), `SOURCE_INFO["knmi"]`; WBGT gauge with provisional heat-stress bands; B19 fixed, B23 partly. 144 tests OK, `makemigrations --check` and `manage.py check` clean. **Not run against the live KNMI API** | uncommitted |
