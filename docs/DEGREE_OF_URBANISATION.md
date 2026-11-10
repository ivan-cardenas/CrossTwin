# Degree of Urbanisation on 100 m cells

CrossTwin's measure of how urban each place is: the GHSL / Eurostat **Degree of Urbanisation** (DEGURBA), computed from the population stored per neighborhood and the BAG residential properties, on a **100 m grid adapted to local measurement**. The original **1 km** method runs next to it on the same data. This document records the method, every deviation from the original and the reasons for them, so the implementation can be traced, explained and cited.

| | |
|---|---|
| DAG node | `Degree_Urbanisation` (State), replacing the former `Urbanization` node: see `docs/DAG_REVISIONS.md` (2026-11-10) |
| DAG edges | `Total_Population -> Degree_Urbanisation`, `Buildings -> Degree_Urbanisation`, `LandCover -> Degree_Urbanisation` |
| Grid rules | `builtup/degurba.py` (pure numpy / scipy) |
| Unit class, rate | `builtup/chain.py::classify_unit`, `urbanization_rate` |
| Allocation, refresh | `builtup/urbanisation.py` |
| Stored | `builtup.PopulationAllocation`, `builtup.UrbanisationCell` (map layers `UrbanisationCellLocal` 100 m, `UrbanisationCellOriginal` 1 km), `builtup.Urbanisation` (units), `administrative.City.urbanizationRate` |
| Receivers | `builtup/signals.py` (Degree of Urbanisation section) |
| UI | map: Actions menu → *Calculate for this view* → *Degree of Urbanisation* (`core/static/js/DegurbaTool.js`); built-up dashboard card (`builtup/views.py`) |
| Tests | `builtup/test_degurba.py`, `core/test_dag.py` |

## 1. The original method

The Degree of Urbanisation classifies 1 km² grid cells by population density, contiguity and cluster size, then classifies spatial units by where their population lives (Eurostat 2021; Dijkstra et al. 2021; GHSL definitions page, human-settlement.emergency.copernicus.eu/degurbaDefinitions.php).

**Grid, level 1:** urban centre, urban cluster, rural cell. **Level 2:**

| Code | Class | Rule (1 km cells) |
|---|---|---|
| 30 | Urban centre | cells ≥ 1 500 inh./km² (or ≥ 50 % built-up), **4-connected**, cluster ≥ 50 000 inh.; gaps < 15 km² filled; edges smoothed (a cell with ≥ 5 of its 8 neighbours in the centre joins it, repeated) |
| 23 | Dense urban cluster | ≥ 1 500 inh./km², 4-connected, 5 000–49 999 inh., not a centre |
| 22 | Semi-dense urban cluster | urban cluster (≥ 300 inh./km², **8-connected**, ≥ 5 000 inh.) not contiguous with and more than 2 km from a centre or dense cluster |
| 21 | Suburban or peri-urban | the remaining urban-cluster cells |
| 13 | Rural cluster | ≥ 300 inh./km², 8-connected, 500–4 999 inh. |
| 12 | Low density rural | ≥ 50 inh./km² |
| 11 | Very low density rural | < 50 inh./km² |
| 10 | Water | ≥ 50 % permanent water, no population |

**Spatial units, level 1:**
- *city* when ≥ 50 % of the population lives in urban centres;
- *town or semi-dense area* when < 50 % lives in centres and ≥ 50 % in urban clusters (centres included);
- *rural area* otherwise.

Level 2 splits towns into dense / semi-dense / suburban and rural areas into village / dispersed / mostly uninhabited.

## 2. Why 1 km does not fit a local twin

The 1 km grid was designed to compare **many cities** (countries, the globe) on a common footing: coarse cells absorb local noise and make the classes stable across data sources. CrossTwin measures **within one city**, where the question is which streets and blocks are urban and how the edge moves when dwellings are added.

At that scale, 1 km cells (or any 1 km support) have three problems:

- **Edge dilution.** A cell on the city edge is half fields. Its gross density halves, so the urban edge is drawn up to ~500 m inside the built-up area. Worked example (3 × 3 window, 100 m cells): three dwelling cells of 60 people (6 000 inh./km²), one street cell, five field cells. Over the whole window the density is 180 / 0.09 km² = 2 000 inh./km². Over a 1 km window it drops to about 800 inh./km² (≈ 8 inh./ha). Over the settlement land only (4 cells) it is 180 / 0.04 km² = **4 500 inh./km²** (45 inh./ha), the density the residents actually live at. Tested in `LocalVariantTests.test_worked_example_three_dwelling_cells_and_a_street`.
- **Edits disappear.** One new block of 40 dwellings changes a 1 km cell by a few percent and rarely changes its class, so a map edit has no visible effect.
- **Few cells.** A municipality of 140 km² has ~140 cells: too few to show where inside the city the classes change.

## 3. Data and allocation (people → dwellings → cells)

**Inputs:**
- `Neighborhood.currentPopulation` (CBS);
- `builtup.Property` rows whose `usageFunction` contains *Residential function* (BAG verblijfsobjecten with woonfunctie);
- `builtup.Building` footprints (BAG);
- `physicalEnv.LandCoverVector`, the newest survey year that touches each cell. Land-cover years can be partial updates that cover only the areas that changed, so taking the city's latest year would leave most cells without land cover.

**Dwellings, not buildings.** One building can hold many properties (a block of 40 flats), so the population is spread per dwelling:

```
p_d     = P_n / N_n                    each dwelling d of neighborhood n
                                       P_n = currentPopulation, N_n = residential properties in n
P_cell  = Σ_{d in cell} p_d
```

- A dwelling belongs to the neighborhood containing its point.
- Non-residential properties (a shop under the flats) get nothing.
- A neighborhood with people but no dwellings is spread by area: `P_cell = P_n · area(n ∩ cell) / area(n)`. Those cells are flagged `by_area`, and the card counts such neighborhoods.
- Persons per dwelling are uniform within a neighborhood, consistent with the CBS average household size the housing module already uses (`housing/signals.py`).

**Built-up surface** (for the ≥ 50 % rule): `Σ area(footprint ∩ cell)` of all buildings of the neighborhood (assigned by point on surface), residential or not, as GHSL's built-up surface.

**Settlement and water shares** of a cell = area of the cell covered by the settlement / water land-cover classes, over the cell's area (`builtup/urbanisation.py::landcover_shares`):
- *Settlement* keywords: urban (fabric, green), industrial, commercial, road, rail, port area, airport, construction, sport, leisure, built.
- *Water* keywords: water, sea and ocean, estuar, lagoon.
- A cell is **settlement land** when its settlement share is ≥ 50 %, **or when it holds a dwelling**: a dwelling placed on a field counts at once. People spread *by area* (a neighborhood without dwellings) do not make a cell settlement land. Otherwise the fallback would turn whole rural neighborhoods into settlement and inflate the urban classes.

**Grid.**
- Cells are aligned to multiples of the cell size in EPSG:28992, the CBS square-statistics grid.
- Codes are `E<x>N<y>` of the lower-left corner, in hm for 100 m cells and km for 1 km cells.
- A storage CRS that is not in metres falls back to EPSG:3035 (`grid_srid()`).
- The grid holds every cell inside an imported neighborhood. `coverage` is the share of the cell inside them.

**Stored as** `PopulationAllocation`, one row per neighborhood × cell × resolution × year. One set-based SQL statement per resolution writes the rows (`allocate`, `ST_SquareGrid`). Cell totals are sums of these rows, so population is conserved exactly (tested at both resolutions).

## 4. The 100 m variant: local, settlement-masked support

Decision of 2026-11-10: the support is local (300 m) and masked to settlement land, so city edges stay at the last dwellings. The original rules are kept wherever they do not depend on the cell size.

| Rule | 1 km original (`resolution_m=1000`) | 100 m CrossTwin (`resolution_m=100`) | Why |
|---|---|---|---|
| Density | people / land km² of the cell | **people in the 3 × 3 window / settlement land km² of the window**; a cell that is not settlement land uses the gross window density (people / land km²) | Density is scale-free, so the thresholds stay. The window bridges 0-people street and park cells; the mask keeps fields beyond the edge out of the denominator |
| Candidates | every cell | **settlement cells only** | a field next to a dense edge would otherwise inherit its neighbours' density |
| Built-up ≥ 50 % | cell | gross 3 × 3 window | a dense core at 300 m |
| Thresholds 1 500 / 300 / 50 inh./km² | as published | unchanged | densities |
| Cluster sizes 50 000 / 5 000 / 500 | as published | unchanged | absolute settlement sizes |
| Contiguity | 4 (centres, dense) / 8 (clusters) | unchanged, at cell level | topology rule |
| Hole filling | gaps < 15 km² | gaps < 15 km² **made only of settlement cells** (parks, streets, industry) | farmland, forest and water inside a ring stay open at local scale |
| Smoothing | ≥ 5 of 8 neighbours, repeated | same rule, **settlement cells only** | no growth into fields |
| Semi-dense distance | > 2 km edge to edge | unchanged (2 km = 20 cells) | separation between towns is not a local quantity |
| Water | ≥ 50 % water, no people | unchanged, per 100 m cell | — |

Window size (`window_cells`) and the mask (`masked`) are parameters of `degurba.classify`. The sensitivity runs (1 = own cell, 3, 5, unmasked) use the same code; the UI and the dashboards use only the defaults (`degurba.variant`).

**Expected bias.** The masked density is a *net-like* density: it is ≥ the gross density for settlement cells. More cells pass 1 500 / 300 than in a gross 100 m grid, and centres hug the built-up area instead of extending into its surroundings. The 1 km run on the same data measures this bias (see §8).

## 5. Algorithm (`builtup/degurba.py::classify`)

```
input  pop, built_m2, water_share, settlement (bool), coverage   (2-D, one value per cell)
valid       = coverage > 0
settlement |= pop > 0
allowed     = valid AND settlement                (100 m)  |  valid  (1 km)
density     = masked window density (§4)                  |  people / land km²
dense_cell  = allowed AND (density ≥ 1500 OR built_share ≥ 0.5)
cluster_cell= allowed AND density ≥ 300

centre  = 4-connected components of dense_cell with Σpop ≥ 50 000
centre  = fill holes < 15 km² whose cells are all `allowed`        (_fill_holes)
centre  = repeat: add allowed cells with ≥ 5 of 8 neighbours in a centre   (_smooth)
dense   = 4-connected components of dense_cell − centre, 5 000 ≤ Σpop < 50 000
urban   = 8-connected components of cluster_cell ∪ centre ∪ dense, Σpop ≥ 5 000
semi    = whole urban components with no centre/dense cell and min distance to one > 2 km
suburban= urban − centre − dense − semi
rural_cluster = 8-connected components of cluster_cell − urban, 500 ≤ Σpop < 5 000
l2 = 30 centre, 23 dense, 22 semi, 21 suburban, 13 rural cluster,
     else 12 if density ≥ 50 (gross off settlement), 10 if water ≥ 50 % and pop = 0, else 11;
     0 outside the grid
edge_effect = the cell's cluster touches a cell with coverage < 0.99 or the grid border
```

## 6. Units and rate (`builtup/chain.py`)

```
L1(unit) = 3 city   if P_30 / P ≥ 0.5
           2 town   if (P_30 + P_23 + P_22 + P_21) / P ≥ 0.5
           1 rural  otherwise
L2(unit) = 30 for a city; otherwise the class with the largest population share in the
           unit's L1 group (towns: 23, 22, 21; rural: 13, 12, 11), ties to the denser class
rate     = ((A_t1 / A_t0)^(1 / (t1 − t0)) − 1) × 100   %/yr
           A = urban area of the unit = Σ area(unit ∩ cells of class 21–30), t0 = earliest stored year
```

- `P_k` is the unit's population in cells of class *k*. It comes from the allocation rows of the unit's neighborhoods, so it is exact per dwelling. A district or city is the sum of its neighborhoods.
- The rate measures urban *expansion* (sprawl), the change in the extent of the urban classes. The share of people in urban clusters is reported next to it.
- `City.urbanizationRate` mirrors the latest 100 m city rate (`mirror_city_rates`, an `update()`: administrative must not import builtup).
- Rates come **only from CrossTwin's own stored years**. Each population year (`Neighborhood.populationDate`) adds a point to the series, and earlier years are never overwritten.

## 7. Keeping it current (signals)

| Receiver (`builtup/signals.py`) | Source | Effect |
|---|---|---|
| `neighborhood_urbanisation_saved/_deleted` | `Neighborhood` (population or outline changed) | re-allocate it |
| `property_urbanisation_saved/_deleted` | `Property` and proxies (dwelling added, moved, (un)made residential) | re-allocate the old and new neighborhood |
| `building_urbanisation_saved/_deleted` | `Building` footprint drawn, moved, deleted | built-up share of its neighborhoods |
| `landcover_urbanisation_saved/_deleted`, `landcover_created` | `LandCoverVector` | settlement and water shares of the cells under it |

`builtup/urbanisation.py::refresh` runs in a savepoint. Errors are logged and never block the source save. A refresh:
1. re-allocates the scheduled neighborhoods;
2. upserts the cells;
3. re-reads land-cover shares where needed;
4. reclassifies **the whole grid** of both resolutions, because a new block can merge two distant clusters (milliseconds in numpy);
5. re-saves every `Urbanisation` unit row and sends `urbanisation_grid_changed`.

Scheduling and when refreshes run:
- Bulk imports run inside `importer/batching.py::deferred_cascades()` (`deferred_urbanisation_refresh`): one refresh per import.
- Nothing runs before the grid was built once from the map card, so imports and unrelated tests pay nothing.
- A refresh for a new population year re-allocates every neighborhood.
- **Restore** (map editing) re-saves rows raw. These rows are a pure derivation, so the receivers also react to raw saves while `core.editing.is_restoring()` is true, and the restored state is recomputed once when restore's deferral ends.

**What-if.** The built-up dashboard's population dock (scenario, extra growth) scales each neighborhood's allocation by its city's factor, then reclassifies the whole 100 m grid in memory and writes nothing (`urbanisation.whatif_unit`):

```
f = P(city, year, scenario, growth) / P(city, stored year, median, 0)
```

With the default controls in the stored year, f = 1 and the card shows the stored row.

## 8. Validation design

1. **100 m vs 1 km on the same data.** Both are stored for every year, so each run allows:
   - agreement of the 1 km class with the population-weighted majority class of its 100 cells;
   - units whose class changes between the two;
   - the difference in urban area concentrated at the city edge.
2. **GHSL as reference (visual only).** The importer's catalog entries `gee_ghsl_smod` (GHS-SMOD R2023A, 1 km, epochs 1975–2030) and `gee_ghsl_pop` (GHS-POP, 100 m) load GHSL's own grid as `SatelliteImagery` rasters (index `GHSL_SMOD` / `GHSL_POP`). GHS-SMOD is painted in the same colours as CrossTwin's layers. Its scale and inputs differ (modelled population, satellite built-up), so it is **never** used in any calculation or rate; it shows the past of the city for comparison.
3. **Sensitivity** of the window (1, 3, 5 cells) and the mask (on / off) with `degurba.classify(window_cells=, masked=)` on the stored inputs (`urbanisation.load_grid`).

## 9. Limitations

- Persons per dwelling are uniform within a neighborhood; large and small dwellings get the same share. `livingArea` weighting is a possible refinement.
- Population outside the imported neighborhoods is unknown and counted as 0. Clusters touching the import edge are flagged `edge_effect`.
- The settlement mask is as good as the land-cover map: a coarse class (CORINE "urban fabric") marks gardens and small parks as settlement, which is intended, but also misses new estates until the land cover is updated. Dwellings placed on non-settlement land count as settlement through their population.
- The 2 km semi-dense distance and the unit level-2 tie rule follow the EEA / Eurostat descriptions and should be checked against the 2021 manual (†).
- The 100 m thresholds keep their 1 km values. That is defensible for densities but not calibrated: §8 quantifies the effect.

## 10. Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-10 | New State node `Degree_Urbanisation`; `Urbanization` removed from the DAG | urbanisation is an outcome measured from population and built form, not a cause (`docs/DAG_REVISIONS.md`) |
| 2026-11-10 | 100 m cells with the GHSL thresholds | local measurement of a single city, map edits visible |
| 2026-11-10 | Population spread over **residential properties**, never buildings | a building can hold many dwellings |
| 2026-11-10 | 300 m window **masked to settlement land** instead of a 1 km window | a 1 km support suits many-city comparison but dilutes edge pixels within one city |
| 2026-11-10 | 1 km original stored next to 100 m | like-for-like comparison of the adaptation |
| 2026-11-10 | GHSL imported as a visual reference only | scales and inputs do not match; rates use CrossTwin data only |
| 2026-11-10 | Land cover: newest survey year per cell; settlement from dwellings, not from area-spread people | the stored land cover is a set of partial yearly updates; area spreading made whole neighborhoods count as settlement |
| 2026-11-10 | Everything runs from the UI (map card, dashboard, importer), no CLI | user workflow |

## References

- Eurostat (2021). *Applying the Degree of Urbanisation: A methodological manual to define cities, towns and rural areas for international comparisons*, 2021 edition. Publications Office of the EU.
- Dijkstra, L., Florczyk, A. J., Freire, S., Kemper, T., Melchiorri, M., Pesaresi, M., Schiavina, M. (2021). Applying the Degree of Urbanisation to the globe: A new harmonised definition reveals a different picture of global urbanisation. *Journal of Urban Economics*, 125, 103312.
- Schiavina, M., Melchiorri, M., Pesaresi, M. (2023). *GHS-SMOD R2023A — GHS settlement layers, application of the Degree of Urbanisation methodology (stage I) to GHS-POP R2023A and GHS-BUILT-S R2023A, multitemporal (1975–2030)*. European Commission, JRC.
- European Commission, GHSL. Degree of Urbanisation definitions: https://human-settlement.emergency.copernicus.eu/degurbaDefinitions.php
