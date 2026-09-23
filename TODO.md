# TODO — Unimplemented DAG Edges

The DPSIR causal graph in [`core/DAG.dot`](core/DAG.dot) defines 102 edges. **Only 28 are backed by real derivation logic** — a `save()` method or a `calculations.py` function that actually reads the source field, not just a docstring claiming the edge. The rest are either flat stored fields with no computation, or `calculations.py` functions whose docstring claims an edge the code doesn't implement.

This file tracks the gaps, grouped by app. When one is closed, move it to the "Done" note at the bottom (or delete the line) and add the `# DAG edges:` comment to the implementing function per the convention in `CLAUDE.md`.

## Import bugs

- [ ] GEE importer needs to be verified against the actual configuration of each layer in the catalog see https://developers.google.com/earth-engine/datasets/catalog 

## administrative

- [x] `City.popGrowthRate` — now derived in `City.save()` from `population.annual_growth_rate()` (CBS compound annual growth rate over the city's imported projection years)
- [x] Population curve moves with change, it should be a static curve for bounds and the change can move, the bounds work as comparative 
- [ ] `urbanizationRate` — still a flat field, never consumed by the population projection in `administrative/population.py`
- [ ] Housing supply/demand does not depend on the projected population — `HousingSupplyDemand` demand still comes from stored rows, not `get_population()`
- [ ] Urban heat does not depend on the projected population
- [x] `urban_area` — now cascades Neighborhood → District → City → Province via `administrative/signals.py::_recompute_population()` (generalized to also sum `urban_area`), sourced at the Neighborhood level from `physicalEnv.LandCoverVector` spatial intersection area (`physicalEnv/signals.py`)
- [ ] No `Urbanization` model exists — `Urbanization -> CityArea/Buildings/Streets/LandCover` has nowhere to live (the new `urban_area` cascade computes a *result* consistent with what an `Urbanization` node would represent, but does not create the node or its DAG edges)



## physicalEnv

- [ ] `RS_Imagery -> LandCover/LST` — raster models are plain imports, no ingestion/derivation code
- [ ] `LandCover -> Infiltration` — `AvailableFreshWater.infiltrationRate_cm_h` is a flat field (see existing inline TODO)
- [ ] `New_Units -> LandCover` — `calculate_new_units()` never touches `LandCover`

## urban_heat

- [ ] `DSM -> SVF -> Tmrt/PET` chain — `SVF`/`Tmrt`/`PET` are `RasterField` containers with no `save()`
- [ ] `LST -> PET` — same, no derivation
- [ ] `Tmrt -> UTCI` — `UTCI` model has no `save()`
- [ ] `Canyon_Aspect -> DSM`, `Vegetation_Coverage -> DSM`, `Streets -> Canyon_Aspect` — unimplemented (expected to arrive pre-computed from SOLWEIG externally)
- [ ] `calculate_urban_morphology()` / `get_thermal_indices()` — only compute statistics *over* existing rasters, don't derive one raster from another
- [ ] `PET -> NBS` — `calculate_nbs_coverage()` counts NBS geometries but never reads PET values

## builtup / housing

- [ ] No `Accessibility` model exists — `Facilities/Streets/Green_Area -> Accessibility -> Property` unimplemented (`Building.connectivity` is the closest analog, itself an open TODO)
- [ ] `Zoning_Status -> Property` — `Property` has no `save()` logic
- [ ] `Property -> House_Price_Index/Mortgage` — `Mortgage`/`HousePriceIndex` `calculations.py` functions only average pre-existing stored values
- [ ] `Rent/Mortgage/Water_Tariff_Afford -> Income_Expenses -> Affordability_Stress` — `HousingAffordability.save()` computes `affordabilityIndex` only from its own stored fields, never pulls from `Mortgage`, `Rentals`, or watersupply tariffs
- [ ] `Credit_Supply -> Mortgage` — unimplemented
- [ ] No `NumberUsers` model — `NumberUsers -> Water_Tariff_Afford` unimplemented (`MeteredResidential.userAffordability_PCT` is a flat input)

## watersupply

- [ ] `Network -> Real_Losses` — `NonRevenueWater` records are entered directly, not linked to `PipeNetwork`
- [ ] `calculate_collection_ratio()` ignores `userAffordability_PCT` and acceptance rate despite its docstring
- [ ] `calculate_opex_recovery()` computes directly from stored totals rather than calling `calculate_collection_ratio()` or referencing NRW
- [ ] `Samples_WQ -> User_Acceptance_WS` — `calculate_water_quality()`'s `acceptance_rate` is `Avg('acceptanceRate')`, unrelated to computed compliance
- [ ] `WT_Efficiency -> WT_Cost` — `WaterTreatment` has no `save()`
- [ ] `Apparent_Losses -> ILI` — `NonRevenueWater` ILI is only defined for real losses
- [ ] `UsersLocation.usersTotal`/`populationServed` and non-latest-year `SupplySecurity` records aren't refreshed by signals — `OPEX`/`ExtractionWater`/`MeteredResidential`/`ImportedWater` carry no year field, so only the latest `OPEX`/`SupplySecurity` record is refreshed

---

## Other inline TODOs (non-DAG)

Collected from `#TODO` comments across the codebase:

**physicalEnv**
- Auto-calculate `LandCoverVector.percentage` from geom area vs. Province total area (`physicalEnv/models.py`)
- Add Vegetation Coverage and Builtup Coverage as additional fields on `LandCoverVector` (`physicalEnv/models.py`)

**builtup**
- Define connectivity index and calculation method for `Building.connectivity` (`builtup/models.py`)
- Define green visibility index and calculation method for `Property.greenVisibility` (`builtup/models.py`)

**watersupply**
- `UsersLocation.neighborhood` FK — decide whether this should be City-level or per-point (`watersupply/models.py`)
- `AvailableFreshWater.infiltrationRate_cm_h` — should be calculated from land cover and soil type (`watersupply/models.py`)
- `TotalWaterProduction.source` — handle imported or multiple sources (`watersupply/models.py`)

**housing**
- Validate affordability stress level thresholds against literature (`housing/models.py`)
- Connect `HousingAffordability.medianExpenditure` with water and electricity expenditure data (`housing/models.py`)
- Decide whether affordability index should use median disposable income instead of median income (`housing/models.py`)

**urban_heat**
- Add measurement method, source, and metadata fields to raster models: MRT, UTCI, SVF, LST (`urban_heat/models.py`)

---

## Product / feature backlog

Moved from `docs/Questions and bugs.md`'s "TODOS" section, with descriptions clarified. Two items marked `[x]` were already struck through there (treat as done, confirm before deleting); a few duplicate gaps already tracked above and are cross-referenced instead of repeated.

**Data sources & indices**
- [ ] Review current spectral indices (e.g. NDVI, NDWI) against recent remote-sensing research and evaluate whether better-performing alternatives exist for CrossTwin's Dutch/urban context.
- [ ] Evaluate Copernicus Destination Earth as a data source — note its native resolution is ~5km, coarse relative to CrossTwin's typical city/neighbourhood-scale Dutch datasets, so assess whether it's actually useful before integrating.
- [ ] Evaluate the Dutch Klimaateffectatlas (Climate Atlas) as a source: review what maps/layers it offers and whether/how to import or link to them.
- [x] Cloud-coverage filtering (max ~10%) for satellite imagery imports — already implemented, confirm still working as part of Sentinel-2/GEE import paths before deleting this line.

**Import / update workflow**
- [ ] Add an "update" action to the importer UI that re-checks an already-imported dataset against its source (PDOK/CBS/etc.) for upstream changes and re-imports only what changed, instead of only supporting one-off imports.
- [x] Overview panel listing currently active/visible map layers — already implemented, confirm still working before deleting this line.

**Alerts & reporting**
- [ ] Design an alerting/notification system: instant messages or alarms triggered when an indicator crosses a defined threshold (e.g. water supply security drops, extreme heat).
- [ ] Design pre-written/templated narrative summaries for indicator dashboards (auto-generated text describing what the computed values mean), rather than showing only raw numbers and gauges.

**External collaboration / methodology**
- [ ] Follow up with Carolina Pereira's climate-data app as a reference: it covers WBGT only as a quick proxy indicator; importing it would mean parsing a CSV feed per weather station, which looks tractable.
- [ ] Write the paper's Methodology section: document the development choices and steps taken across the project and the reasoning behind each.
- [ ] Coordinate with Mila to review how comparable projects approach this (e.g. Rakibun's example), to align methodology/approach.

**Domain data model / import design**
- [ ] `nature.Park` — no import path exists yet; decide the source dataset (e.g. PDOK) and confirm the storage model before building an importer for it.
- [ ] `builtup.Facility` — no import path exists yet; design how to source facilities from OpenStreetMap or Google Places/Maps.
- [ ] Confirm where zoning data should live and how additional sources should import into it — `builtup.ZoningArea` already receives INSPIRE spatial-plan data via the `pdok_landcover_kadaster` import, but zone *type* classification still has no source (see the existing `plu:ZoningElement` note in `importer/external_catalog.py`).
- [ ] Design how surface albedo could be derived for `LandCoverVector.material` from satellite band math (e.g. shortwave broadband albedo formulas over Sentinel-2/Landsat bands), instead of leaving `material` unset for WFS-sourced rows.
- [ ] Design how land-cover *changes between survey years* should propagate to dependent calculations — e.g. `AvailableFreshWater.infiltrationRate_cm_h` (see the inline TODO above) and surface reflection/albedo — rather than each being a flat, independently-set field.
- [ ] Link `builtup.Building`/`builtup.Property` to `housing` models via the BAG `woonfunctie` (residential-use) classification — no FK/relationship currently connects them.
- [ ] Decide whether the admin-hierarchy layer (Province/City/District/Neighborhood) should always stay available in `Config.js`'s `TOOL_CATEGORIES` for indicator grouping, given that makes map-click popup queries harder to disambiguate against other layers.
- [ ] Decide whether groundwater should stay as its own domain — currently little derivation logic actually uses it.
- [ ] Investigate whether underground-infrastructure navigation/visualization is feasible to add.
- [ ] Decide whether `nature.Park` and the other green-space model should be merged into one (currently green spaces and parks are tracked as two separate models).
- [ ] Investigate whether an infiltration-capacity table or map exists for the Netherlands that could back `AvailableFreshWater.infiltrationRate_cm_h` (see inline TODO above) instead of computing it from land cover alone.
- [ ] Decide how to define "degree of urbanisation" for CrossTwin — CBS defines it via address density per km² (5-band classification: <500 to 2,500+ addresses/km²), but the project's actual interest is urban-sprawl *growth over time*, which needs a different metric/approach.
- [ ] Decide which domain app should own the Population Density raster layer (e.g. `administrative` vs `physicalEnv`).

**HTMX indicator dashboards**
Existing three-layer pattern (`calculations.py` + `views.py` + templates, see CLAUDE.md) is only built for `watersupply`, `housing`, and `urban_heat` so far.
- [ ] Build the HTMX indicator dashboard for `builtup`.
- [ ] Build the HTMX indicator dashboard for `Energy`.
- [ ] Build the HTMX indicator dashboard for `nature`.
- [x] Housing indicator dashboard 

**Weather**
- [ ] Add a live/streaming weather data feed (current imports are static/batch): move the weather indicator higher in the map UI's layout, evaluate whether Mapbox's live rain-radar rendering can be enabled with it, and design a connection to physical weather stations.

**urban_heat (duplicate of gaps already tracked above)**
- The "create LST/PET/SVF/SUHII calculation functions, see SOLWEIG" item is the same gap as the `## urban_heat` section above (`DSM -> SVF -> Tmrt/PET`, `LST -> PET`, `Tmrt -> UTCI` chain) — not repeated here, see that section instead.
