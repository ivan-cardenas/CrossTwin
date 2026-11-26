<!-- Moved verbatim from .claude/CLAUDE.md on 2026-11-23. CLAUDE.md points here. -->

# TODOs

Collected from inline `#TODO` comments across the codebase:


### physicalEnv
- Add Vegetation Coverage and Builtup Coverage as additional fields on `LandCoverVector` (`physicalEnv/models.py`)

### builtup
- Network accessibility follow-ups: a way deleted from OpenStreetMap is not removed on re-import (`importer/osm_network.py`); one-way streets and the bicycle one-way exemption are ignored; a single map edit recomputes inside the save (move to a background worker if it is slow on a dense city)
- Define green visibility index and calculation method for `Property.greenVisibility` (`builtup/models.py`)

### watersupply
- `UsersLocation.neighborhood` FK — decide whether this should be City-level or per-point (`watersupply/models.py`)
- `TotalWaterProduction.source` — handle imported or multiple sources (`watersupply/models.py`)

### housing
- Validate affordability stress level thresholds against literature (`housing/models.py`)
- Connect `HousingAffordability.medianExpenditure` with water and electricity expenditure data (`housing/models.py`)
- Decide whether affordability index should use median disposable income instead of median income (`housing/models.py`)

### urban_heat
- Add measurement method, source, and metadata fields to raster models: MRT, UTCI, SVF, LST (`urban_heat/models.py`)
