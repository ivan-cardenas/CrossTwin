# TODO — Unimplemented DAG Edges

The DPSIR causal graph in [`core/DAG.dot`](core/DAG.dot) defines 105 distinct edges (106 edge lines; `Total_Water_Prod -> OPEX` is listed twice). **Only 47 are backed by real derivation logic** (count as in `CLAUDE.md` › DAG Edge Coverage Gaps) — a `save()` method or a `calculations.py` function that actually reads the source field, not just a docstring claiming the edge. The rest are either flat stored fields with no computation, or `calculations.py` functions whose docstring claims an edge the code doesn't implement.

This file tracks the gaps, grouped by app. When one is closed, move it to the "Done" note at the bottom (or delete the line) and add the `# DAG edges:` comment to the implementing function per the convention in `CLAUDE.md`.

## Import bugs

- [X] `uv run` / `uv sync` fail on this machine: the `crosstwin[graphify]` extra asks for `graphify>=0.8.0`, which has no resolvable version, so only `uv run --no-sync` works. Fix the extra's pin in `pyproject.toml` (or drop it) and re-lock.
- [ ] GEE importer needs to be verified against the actual configuration of each layer in the catalog see https://developers.google.com/earth-engine/datasets/catalog 

## administrative

- [x] `City.popGrowthRate` — now derived in `City.save()` from `population.annual_growth_rate()` (CBS compound annual growth rate over the city's imported projection years)
- [x] Population curve moves with change, it should be a static curve for bounds and the change can move, the bounds work as comparative 
- [ ] `urbanizationRate` — still a flat field, never consumed by function. This should be calculated from historical remote sensing imagery. This would be time consuming and memory intensive, so it should be a `calculations.py` function that reads a raster and averages over a time period.
- [x] Housing demand depends on the projected population — `HousingSupplyDemand.demand_units` is derived in `save()` (baseline population ÷ CBS persons per home, `housing/chain.py`) and refreshed by `housing/signals.py` when the city population, the median `PopulationProjection` or the `HouseholdSize` changes (see builtup / housing)
- [ ] Urban heat does not depend on the projected population
- [x] `urban_area` — now cascades Neighborhood → District → City → Province via `administrative/signals.py::_recompute_population()` (generalized to also sum `urban_area`), sourced at the Neighborhood level from `physicalEnv.LandCoverVector` spatial intersection area (`physicalEnv/signals.py`)
- [ ] No `Urbanization` model exists — `Urbanization -> CityArea/Buildings/Streets/LandCover` has nowhere to live (the new `urban_area` cascade computes a *result* consistent with what an `Urbanization` node would represent, but does not create the node or its DAG edges)



## physicalEnv

- [X] `RS_Imagery -> LandCover/LST` — raster models are plain imports, no ingestion/derivation code
- [x] `LandCover/Soil_Type -> Infiltration -> Available_FW`, `Meteorology -> Available_FW` — the dashboard card computes event infiltration (SCS); `AvailableFreshWater.save()` now stores `infiltrationRate_cm_h` (soil group x unsealed share) and, with a year of daily KNMI rain + Makkink ET (catalog `knmi_daily_water_balance`), `infiltrationDepth_cm` and the yield; receivers on soil, land cover, groundwater and daily meteorology refresh it
- [ ] Recharge simplifications to revisit: crop factor 1 for every surface (Makkink reference ET, no land-cover crop factors), no soil-moisture store between days, roads/rail sealed share 0.6 is an estimate
- [ ] Run `knmi_daily_water_balance` end to end from the importer UI (tested with a mocked KNMI answer only)
- [x] `New_Units -> LandCover` — a building drawn in the map editor turns a 10 m buffer into urban fabric (`physicalEnv/landcover.py::urbanize_around`); moving or deleting it gives the land back (`release_ring`, cut pieces kept in `UrbanFabricCut`). The housing pipeline's land take (greenfield vs infill) is a dashboard statistic (`housing/calculations.py::calculate_pipeline_land_take`)

## urban_heat

- [x] `DSM -> SVF -> Tmrt/PET` chain — on demand, not in `save()`: `physicalEnv/svf.py::calculate_svf` (map SVF tool) writes `SkyViewFactor`; the Thermal Comfort tool (`urban_heat/solweig/pipeline.py::calculate`, a background `ThermalComfortRun`) runs SOLWEIG-GPU from the DSM (with the editor's building patches) + one hour of meteorology and stores one `MeanRadiantTemperature`, `UTCI` and `PET` row (PET with `pet-adjusted`, `urban_pet`). No receivers by design (heavy GPU/download work); building edits mark results stale instead (`stale_results`)
- [x] `Tmrt -> UTCI` — computed by solweig-gpu in the same run (`run_solweig`), stored as `UTCI`
- [x] `LST -> PET` — removed from `core/DAG.dot`: PET comes from `Tmrt -> PET` (SOLWEIG Tmrt + air temperature with the Koopmans urban heat island + 1.2 m wind), the Landsat LST (`urban_heat/lst/`) is a separate surface temperature and not a PET input
- [X] Thermal comfort meteorology is uniform over the view for Tmrt/UTCI, and PET's wind/UHI source areas are cut at the 50 m halo
- [ ] `Canyon_Aspect -> DSM`, `Vegetation_Coverage -> DSM`, `Streets -> Canyon_Aspect` — unimplemented (expected to arrive pre-computed from SOLWEIG externally)
- [ ] `calculate_urban_morphology()` / `get_thermal_indices()` — only compute statistics *over* existing rasters, don't derive one raster from another
- [ ] `PET -> NBS` — `calculate_nbs_coverage()` counts NBS geometries but never reads PET values

## builtup / housing

- [x] `Total_Population, Household_Size -> Housing_Demand` — `housing.HouseholdSize` (CBS households 86291NED, catalog `CBS_Households`; the population is the median `PopulationProjection` already imported by `CBS_PopulationForecast`, so there is a single population import; `average_size` derived in `save()` and re-derived by signal when the forecast arrives later); `HousingSupplyDemand.demand_units` = baseline population ÷ persons per home. The housing dashboard slider is now *Average persons per home* (default = the CBS value of the unit; a what-if via `chain.what_if_demand`, never written)
- [x] `Household_Size -> Property` — `builtup.Property.residents` of every dwelling (BAG *Residential function*) = the city's latest average, written by `housing/signals.py` (one `update()` per city; bulk imports deferred)
- [ ] Verify `CBS_Households` with a real import from the importer UI — the API columns and filters were checked by hand, but no import has run end to end yet
- [ ] Years before the population forecast (2014-2022) have households but no average size, because the forecast starts in 2023; if they are needed, import observed populations into `PopulationProjection` (or a historical table) rather than adding a second population import
- [ ] `HousingSupplyDemand` has no supply derivation — `supply_units` is still the CBS stock balance (`CBS_Housing`); decide whether supply should be the count of BAG dwellings (`ResidentialProperty`) plus `New_Units` completions instead
- [ ] `Property.residents` uses the city's *latest* household size, not the dashboard's year; and household size is carried forward into forecast years (CBS 85172NED, the household forecast, was unavailable when this was built — import it when it is back, as `HouseholdSize` rows for 2027+)
- [ ] Dashboard note when a city's population only covers the imported neighborhoods (the stored demand already uses the whole-gemeente CBS population, so it is right; the panel's *inhabitants* line is not)
- [ ] `Housing_Demand -> Zoning_Status` and `Housing_Demand -> House_Price_Index` — demand is now stored, but nothing reads it yet; households are not split by tenure (owner/rental) or size class
- [ ] No `Accessibility` model exists — `Facilities/Streets/Green_Area -> Accessibility -> Property` unimplemented (`Building.connectivity` is the closest analog, itself an open TODO)
- [ ] `Zoning_Status -> Property` — `Property` has no `save()` logic
- [ ] `Property -> House_Price_Index/Mortgage` — `Mortgage`/`HousePriceIndex` `calculations.py` functions only average pre-existing stored values
- [ ] `Rent/Mortgage/Water_Tariff_Afford -> Income_Expenses -> Affordability_Stress` — `HousingAffordability.save()` computes `affordabilityIndex` only from its own stored fields, never pulls from `Mortgage`, `Rentals`, or watersupply tariffs
- [ ] `Credit_Supply -> Mortgage` — unimplemented
- [ ] No `NumberUsers` model — `NumberUsers -> Water_Tariff_Afford` unimplemented (`MeteredResidential.userAffordability_PCT` is a flat input)
 - [ ] `Buildings` can get height value from DSM. This needs to be incorporated in the model save() function if  the DSM exists.

## watersupply

- [x] `Network -> Real_Losses` — `NonRevenueWater.pipe` FK links each real loss to the `PipeNetwork` where the leakage is presumed (required for real, forbidden for apparent losses in `clean()`); `calculate_nrw()` returns `real_losses_by_pipe` (m³/day and m³/km/day)
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
- `TotalWaterProduction.source` — handle imported or multiple sources (`watersupply/models.py`)

**housing**
- Validate affordability stress level thresholds against literature (`housing/models.py`)
- Connect `HousingAffordability.medianExpenditure` with water and electricity expenditure data (`housing/models.py`)
- Decide whether affordability index should use median disposable income instead of median income (`housing/models.py`)

**urban_heat**
- Add measurement method, source, and metadata fields to raster models: MRT, UTCI, SVF, LST (`urban_heat/models.py`)

---

## Product / feature backlog


**Data sources & indices**
- [ ] Review current spectral indices (e.g. NDVI, NDWI) against recent remote-sensing research and evaluate whether better-performing alternatives exist for CrossTwin's Dutch/urban context.
- [X] Evaluate Copernicus Destination Earth as a data source — note its native resolution is ~5km, coarse relative to CrossTwin's typical city/neighbourhood-scale Dutch datasets, so assess whether it's actually useful before integrating.
- [X] Evaluate the Dutch Klimaateffectatlas (Climate Atlas) as a source: review what maps/layers it offers and whether/how to import or link to them.
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
- [ ] Design how land-cover *changes between survey years* should propagate to dependent calculations — e.g. surface reflection/albedo — rather than each being a flat, independently-set field (`AvailableFreshWater` infiltration now follows the latest land-cover year by signal).
- [ ] Link `builtup.Building`/`builtup.Property` to `housing` models via the BAG `woonfunctie` (residential-use) classification — partly done: `housing.ResidentialProperty` (proxy on dwellings) and `Property.residents` (set from `HouseholdSize`) connect them by signal; there is still no FK from `HousingSupplyDemand`/`HousingProject` to buildings.
- [ ] Decide whether the admin-hierarchy layer (Province/City/District/Neighborhood) should always stay available in `Config.js`'s `TOOL_CATEGORIES` for indicator grouping, given that makes map-click popup queries harder to disambiguate against other layers.
- [ ] Decide whether groundwater should stay as its own domain — currently little derivation logic actually uses it.
- [ ] Investigate whether underground-infrastructure navigation/visualization is feasible to add.
- [ ] Decide whether `nature.Park` and the other green-space model should be merged into one (currently green spaces and parks are tracked as two separate models).
- [ ] Investigate whether an infiltration-capacity table or map exists for the Netherlands that could replace the SCS soil-group rate ranges behind `AvailableFreshWater.infiltrationRate_cm_h` (now derived from soil map x land cover).
- [ ] Decide how to define "degree of urbanisation" for CrossTwin — CBS defines it via address density per km² (5-band classification: <500 to 2,500+ addresses/km²), but the project's actual interest is urban-sprawl *growth over time*, which needs a different metric/approach.
- [ ] Decide which domain app should own the Population Density raster layer (e.g. `administrative` vs `physicalEnv`).
- [ ] From point data like amenities, a interpolated raster should be created using euclidean distance. Each raster should be a separate layer in the map, and the UI should show the map layer as a heat map.
- [ ]  The zoning plans that carry these land-use codes come as one 28.7 GB national file, so every import reads the whole file, however small the area you pick.
  >
  > Every zoning import reads all 28.7 GB
  > * PDOK publishes the Dutch planned land-use data (where the HILUCS land-use links come from) as a single 28.7 GB GML file (a large XML map file). There are no regional pieces.
  > * The current importer goes through that file from top to bottom and keeps only the plans inside your chosen area. Picking a small area does not cut the download.

- [ ] Add 3D models for trees and ammenities. threes can get height from DSM. 

**HTMX indicator dashboards**
Existing three-layer pattern (`calculations.py` + `views.py` + templates, see CLAUDE.md) is built for `watersupply`, `housing`, `urban_heat` and `builtup` so far.
- [x] Build the HTMX indicator dashboard for `builtup` (`/builtup/indicators/<level>/<location>/<year>/`; what-if: additional park area).
- [ ] Build the HTMX indicator dashboard for `Energy`.
- [ ] Build the HTMX indicator dashboard for `nature`.
- [x] Housing indicator dashboard 

**Weather**
- [x] Live weather feed in the map UI: a weather pill at the top centre of the map shows the current weather at the map centre (Open-Meteo nowcast, `weather/live.py`, `/weather/live/`, cached per ~2 km cell for 10 min; `core/static/js/WeatherPill.js`). A click opens the Urban Heat panel, whose weather sliders (air temp., humidity, wind, solar radiation) are a what-if: weather-only heat stress (Steadman apparent temperature in shade/sun, BoM approximate WBGT; `urban_heat/chain.py`), never stored, mirrored on the pill with a *What-if* badge
- [ ] Live data comes from a model (Open-Meteo), not a physical station: connect to real-time station data (KNMI Data Platform `10-minute-in-situ-meteorological-observations`, needs `KNMI_API_KEY` and a NetCDF4 reader) if station measurements are wanted
- [ ] The weather what-if does not recompute the stored PET/UTCI rasters (those need a SOLWEIG run); consider prefilling the Thermal Comfort tool's manual weather from the panel's what-if
- [x] Evaluate whether Mapbox's live rain-radar rendering can be combined with the pill (the KNMI radar forecast WMS layer already exists). Mapbox has no rain radar for the Netherlands: its precipitation tilesets (`raster-array`) cover Japan only, and `map.setRain`/`setSnow` (GL JS ≥ 3.9, experimental) are screen-wide particle effects that only take zoom/light expressions, so they cannot show where it rains. Done: the pill's live weather code switches the rain/snow effect on as ambience (zoom ≥ 11–13, off with `prefers-reduced-motion`), and while it rains a *Radar* button beside the pill toggles the KNMI radar WMS layer (`WeatherPill.js`)
- [ ] Drive the rain effect from the KNMI radar value under the map centre instead of Open-Meteo's model precipitation (needs a GetFeatureInfo call through the WMS proxy)

**urban_heat (duplicate of gaps already tracked above)**
- The "create LST/PET/SVF/SUHII calculation functions, see SOLWEIG" item: LST (`urban_heat/lst/`), SVF (`physicalEnv/svf.py`) and Tmrt/UTCI/PET (`urban_heat/solweig/`) now exist; SUHII has no calculation yet; `LST -> PET` was dropped from the DAG, PET comes from Tmrt (see the `## urban_heat` section).

## OTHERS

- [ ] Add "Various Forest Assets Pack" (https://skfb.ly/pCEzX) by Dari is licensed under Creative Commons Attribution (http://creativecommons.org/licenses/by/4.0/). to reference in the map for 3D model