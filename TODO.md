# TODO — Unimplemented DAG Edges

The DPSIR causal graph in [`core/DAG.dot`](core/DAG.dot) defines 102 edges. **Only 28 are backed by real derivation logic** — a `save()` method or a `calculations.py` function that actually reads the source field, not just a docstring claiming the edge. The rest are either flat stored fields with no computation, or `calculations.py` functions whose docstring claims an edge the code doesn't implement.

This file tracks the gaps, grouped by app. When one is closed, move it to the "Done" note at the bottom (or delete the line) and add the `# DAG edges:` comment to the implementing function per the convention in `CLAUDE.md`.

## Import bugs

- [ ] GEE importer needs to be verified against the actual configuration of each layer in the catalog see https://developers.google.com/earth-engine/datasets/catalog 

## administrative

- [x] `City.popGrowthRate` — now derived in `City.save()` from `population.annual_growth_rate()` (CBS compound annual growth rate over the city's imported projection years)
- [ ] Population curve moves with change, it should be a static curve for bounds and the change can move, the bounds work as comparative 
- [ ] `urbanizationRate` — still a flat field, never consumed by the population projection in `administrative/population.py`
- [ ] Housing supply/demand does not depend on the projected population — `HousingSupplyDemand` demand still comes from stored rows, not `get_population()`
- [ ] Urban heat does not depend on the projected population
- [ ] No `Urbanization` model exists — `Urbanization -> CityArea/Buildings/Streets/LandCover` has nowhere to live



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
