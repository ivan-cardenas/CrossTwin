# Drought damage from groundwater abstraction in CrossTwin

## Context
`docs/groundwater_drought_damage.md` describes this chain: pumping → aquifer drawdown → phreatic drawdown → capillary rise → root-zone stress → crop yield loss and nature damage → €. It recommends Tier 2 (an analytic drawdown plus a daily 1-D bucket over ≥30 years, damage = run *with* − run *without*).

CrossTwin should show what a change in extraction does to crops and nature, and what it costs. The DAG already has `Total_Extraction -> Area_Drought`, but it is a gap: `watersupply/calculations/indicators.py:503 calculate_drought_area` only sums stored `AreaAffectedDrought` polygons. The only cost today is a flat price, `ExtractionWater.drought_damage_EUR_m3` = `EnvironmentalCosts.price_EUR_droughtDamage_m3`.

## Evaluation: what CrossTwin has for each link

| Link | Needed | Already in CrossTwin | Gap → fill |
|---|---|---|---|
| Pumping Q | Rate per well | `ExtractionWater.volume_m3_d()`, `geom`, `depth_m`, `is_active` | none |
| 1. Drawdown | kD (T), S, aquitard c | **nothing** | New `AquiferProperties` per `Watershed` (kD, S, c, w, `source`), with cited defaults by region type. REGIS II import later. |
| 2. Phreatic drawdown | Drainage resistance w | **nothing** | Same model. A default w per land-cover class, scaled by ditch density from `nature.WaterWaysLN` length per km². |
| Baseline water table | GHG, GLG (GVG for nature) | `GroundwaterDepth` GHG/GLG, 50 m (BIS) | Add a catalog entry `bodemdata_gvg`; it is the same WCS. |
| 3. Capillary rise | Gardner α, Ks, TAW, root depth per soil | `SoilType.soilGroup` A–D and texture words (`soil.py::classify_soil_group`) | Constant table per soil group (Staring series values: α, Ks, TAW), cited. BOFEK2020 later. |
| 4. Weather | ≥30 years of daily P and ET₀ | `Meteorology` daily `RH`/`EV24` (`weather/knmi.py`); only yearly sums are exposed | New `daily_series(point, start, end)` in `weather/calculations/water_balance.py`. The KNMI import already takes a date range; import 1991–2020. |
| 5a. Crops | Crop per field, Ky, potential yield, €/t | Only the land-cover class (arable, pasture, fruit) | New catalog entry `pdok_brp_gewaspercelen` (BRP crop parcels, PDOK WFS) → new `builtup`/`physicalEnv` `CropParcel`. Crop table `CROPS` (Ky, Kc, root depth, potential yield t/ha, price €/t; FAO-33/66, WUR KWIN). Without BRP, fall back to the land-cover class. |
| 5b. Nature | Vegetation goal, Waternood break-points | `nature.ProtectedArea` (N2K/NNN), `AreaAffectedDrought` from `kea_droogtegevoelige_natuur` (sensitivity 2–4) | Waternood trapezoid on GVG with break-points per sensitivity class (wet, moist, dry nature; STOWA/Runhaar). Report ΔGR × ha; no € by default. |
| € | Prices | Flat €/m³ | € per year = Σ ΔL × potential yield × price × area. Derive €/m³ = €/yr ÷ extracted volume. |

The repo already has numerical support: scipy (`exp1`, `k0`), numpy and the raster stack. No timflow, pastas or pyswap is needed for Tier 2. They come later, for calibration and validation only.

## Approach (Tier 2, on-demand, reproducible)

### 1. Pure equations: `watersupply/calculations/drought.py`
Numpy only, with named and cited constants:
- `theis`, `de_glee`, `phreatic_fraction(c, w)`; drawdown is superposed over all active wells (linear in Q).
- `gardner_qmax(Ks, alpha, z)`.
- `water_table_series(ghg, glg, doy)`: a sinusoid with GHG around 1 March and GLG around 1 September. This is a documented approximation.
- `simulate_bucket(P, ET0, gw_depth, soil, crop)`: vectorised over cells × days, FAO-56 Ks, Kc·ET₀.
- `yield_loss(ETa, ETp, Ky)`.
- `waternood_gr(x, A1, A2, B2, B1)`.
- `damage_summary(per_year)`: mean, P90 and the dry years.

The demo in §5 of the doc becomes a pinned test.

### 2. Inputs and storage
- **New models:**
  - `watersupply.AquiferProperties`: Watershed FK, kD, S, c, w, `source`.
  - `physicalEnv.CropParcel`: geom, crop code/name, year; registered for bulk import.
- **Catalog:** `bodemdata_gvg` and `pdok_brp_gewaspercelen` in `importer/external_catalog.py`.
- **Constants:** a `CROPS` table and a `SOIL_HYDRAULICS` table in `drought.py`, with citations.
- **Run model:** `watersupply.DroughtDamageRun` stores every input for reproducibility: wells and their Q, aquifer parameters, weather station and years, GHG/GLG ids, crop year, constant-table version and Q multipliers. Results are stored as raster rows (registered so they export to COG):
  - `PhreaticDrawdown`;
  - `CropDamage` (Δ yield loss %-pt, € per ha per year);
  - `NatureDamage` (ΔGR).

### 3. Pipeline: `watersupply/drought/pipeline.py`
Follows `urban_heat/solweig/`, with a background run.
1. **Grid:** the GHG/GLG 50 m grid, clipped to the area where s_p > 1 cm (about 3λ around the wells) and to the view.
2. **Rasterise inputs** per cell: soil group (`SoilArea`), crop (`CropParcel`, else the land-cover class), nature class (`AreaAffectedDrought`/`ProtectedArea`).
3. **Drawdown** of all active wells. Multipliers Q × {0, 0.5, 1, 1.5, 2} give a damage-vs-extraction curve per cell; 0 is the "without" run.
4. **Bucket** over 30 years × 5 scenarios, only for agricultural and nature cells. Roughly 10⁴ cells × 11 000 days × 5 scenarios, vectorised, takes seconds to minutes.
5. **Store** the rasters, the summary (ha affected, € per year, €/m³) and the per-scenario totals.

### 4. Showing the result
- **Map tool:** a "Drought Damage" card in Actions menu → *Calculate for this view*.
  - Copy the SVF pattern: `physicalEnv/views.py:97/120` `_run`, `core/static/js/SvfTool.js`, and the `.lst-card` in `mainMap.html:270`.
  - Endpoints: `/watersupply/drought/info/`, `calculate/` (POST, staff) and `runs/<id>/`. Code goes in `core/static/js/DroughtTool.js`.
  - Layers: phreatic drawdown, crop € per ha, nature ΔGR.
  - Staleness: mark the result stale when an `ExtractionWater` changes, like the SOLWEIG staleness check.
- **Water dashboard what-if:** a slider "Extraction change (%)" in `watersupply/partials/indicators_panel.html`.
  - `_build_indicators(..., extraction_pct)` interpolates the stored Q-multiplier curve of the latest run (`drought.interpolate_damage`). It never writes.
  - It shows the drought-damage card: ha of crops affected, € per year, €/m³, nature ha with ΔGR < 0.
  - The card also gets a `?` help entry in `core/indicator_help.py`.
- **OPEX / cost link (stored):** `ExtractionWater.save()` takes `drought_damage_EUR_m3` from the latest covering run when one exists, else the flat price. This keeps the existing OPEX chain intact.

### 5. DAG and docs
- **Edge:** `Total_Extraction -> Area_Drought` becomes *implemented (on demand)*. `calculate_drought_area` reads the run's results when present.
- **New edges:** consider `Area_Drought -> OPEX` (the damage cost) and whether `Area_Drought` needs crop and nature children. Argue them in `docs/DAG_REVISIONS.md` and update `core/tests/test_dag.py`.
- **Docs:**
  - `docs/functions_and_equations.tex`: equations and summary-table rows.
  - The coverage count in CLAUDE.md.
  - A new `docs/DROUGHT_DAMAGE.md` with assumptions and limits: the sinusoid water table, the bucket instead of Richards' equation, default c and w, no oxygen stress yet.

## Critical files
- New:
  - `watersupply/calculations/drought.py`
  - `watersupply/drought/{pipeline,inputs,views}.py`
  - `core/static/js/DroughtTool.js`
  - `docs/DROUGHT_DAMAGE.md`
- Edit:
  - `watersupply/models.py` (AquiferProperties, DroughtDamageRun, result rasters, `ExtractionWater.save`)
  - `physicalEnv/models.py` (CropParcel)
  - `weather/calculations/water_balance.py` (`daily_series`)
  - `importer/external_catalog.py`, `importer/batching.py`
  - `watersupply/views.py`, `watersupply/calculations/indicators.py`
  - `mainMap/templates/mainMap.html`
  - `core/DAG.dot`, `core/indicator_help.py`, `mainMap/styles/rasterStyles.py`

## Phasing
1. Equations, constants, `daily_series` and tests; reproduce the doc's §5 demo exactly.
2. AquiferProperties with defaults, the GVG catalog entry, the pipeline and the map tool. This works without BRP by using the land-cover class.
3. BRP crop parcels and crop prices, and the € output.
4. The dashboard slider and the €/m³ fed into `ExtractionWater`/OPEX.
5. Later:
   - Tier 3 calibration with `pyswap` (emulator fit per soil group);
   - `pastas` drawdown where BRO head series exist;
   - a REGIS import;
   - oxygen stress.

## Verification
- **Unit tests** in `watersupply/tests/test_drought.py`:
  - Theis and De Glee against textbook values; the §5 demo table (0.49 m / 0.08 m; 1.9 %-pt at 2.0 m).
  - Q = 0 gives zero damage.
  - Damage is monotone in Q.
  - Waternood trapezoid edges.
  - Dashboard/stored parity: slider 0 % equals the run's Q × 1 total.
- **Pipeline test** on a small synthetic grid, with `DROUGHT_BACKGROUND = False` in `settings_test`.
- **Command:** `uv run python manage.py test watersupply --settings=DigitalTwin.settings_test --keepdb --noinput`.
- **Manual:**
  - Import the KNMI daily rows for 1991–2020, the GHG/GLG/GVG rasters and the BRP parcels for Enschede.
  - Open the map → Drought Damage → Calculate, and check the drawdown cone and the € layer.
  - In the water panel, move the extraction slider and confirm € per year rises non-linearly.
