<!-- Moved verbatim from .claude/CLAUDE.md on 2026-11-23. CLAUDE.md points here. -->

# API routes

| Path | Purpose |
|---|---|
| `/` | Main map view |
| `/welcome/` | Landing page (static, no queries) |
| `/api/layers/` | Layer catalog JSON |
| `/api/layers/<app>/<model>/geojson/` | GeoJSON for vector model (`?bbox=` WGS84, `?zoom=`; cached) |
| `/api/layers/<app>/<model>/bounds/` | Bounding box extent in WGS84 |
| `/api/layers/builtup/Building/mask/` | 50 m cells holding stored buildings (WGS84 GeoJSON; the map's clip mask; cached) |
| `/api/layers/<app>/<model>/features/new/`, `.../features/<pk>/`, `.../features/<pk>/delete/` | Map editing form / delete (staff, layers switched on in Map settings only) |
| `/api/settings/`, `/api/settings/editable/`, `/api/settings/style/` | Map settings panel: editable layers on/off, style form (`?target=vector:<key>|raster:<style key>`; POST saves, `action=reset` deletes) (staff) |
| `/accounts/login/`, `/accounts/logout/` | Header login / logout (POST) |
| `/api/editing/backup/` (+ `restore/`, `discard/`) | What-if backup bar: status, create, restore, discard (staff) |
| `/api/raster/<app>/<model>/tiles/` | TiTiler tile URL for raster |
| `/api/raster/<app>/<model>/info/` | Raster metadata |
| `/importer/` | File upload import |
| `/watersupply/` | Water supply indicators dashboard |
| `/urban_heat/` | Urban heat views |
| `/urban_heat/lst/scenes/`, `/urban_heat/lst/calculate/` | Map LST tool: Landsat scenes over `?bbox=` (ranked by clear share of the view); compute + store LST for the view (POST, staff) |
| `/urban_heat/solweig/info/`, `.../met/`, `.../calculate/`, `.../runs/<id>/`, `.../stale/` | Map Thermal Comfort tool: inputs + sun for `?bbox=&datetime=`; KNMI/ERA5 met prefill; start a background SOLWEIG run (POST, staff); run status + layers; results made stale by building edits |
| `/physicalEnv/dsm/edited/status/` | Whether map edits are still being written into the edited DSM COG (`{"busy": bool}`) |
| `/physicalEnv/svf/info/`, `/physicalEnv/svf/calculate/` | Map SVF tool: DSM, grid and existing SVF for `?bbox=`; compute + store SVF for the view (POST, staff) |
| `/api/climate/runs/` (GET list, POST create), `.../<id>/`, `.../<id>/recalculate/`, `.../<id>/heat/`, `.../<id>/delete/` | Stored climate scenario runs (POST staff) |
| `/api/climate/effects/` | Scenarios panel: water + heat indicators, current (2025) vs the scenario (`?climate=&heat=&level=&location=&pop_scenario=&pop_growth=`) |
| `/weather/live/` | Map weather pill: current weather at `?lat=&lng=` (Open-Meteo, cached per ~2 km cell) |
| `/watersupply/unserved/` | Homes no pipe reaches, as WGS84 GeoJSON points (`?bbox=`) |
| `/housing/` | Housing indicators dashboard |
| `/builtup/` | Built-up fabric indicators dashboard |
| `/builtup/degurba/info/`, `/builtup/degurba/calculate/` | Map Degree of Urbanisation card: stored grid status; rebuild for the current population year (POST, staff) |
| `/builtup/accessibility/info/`, `/builtup/accessibility/calculate/` | Map Network Accessibility card: stored network and scores per mode; recompute every building (POST, staff; 409 without a stored network) |
| `/builtup/generator/projects/`, `.../preview/`, `.../commit/`, `.../remove/` | Map Neighbourhood generator: housing projects; layout of an outline as GeoJSON + metrics (POST, what-if, writes nothing); store on a project as completed / set back to planned (POST, staff) |
