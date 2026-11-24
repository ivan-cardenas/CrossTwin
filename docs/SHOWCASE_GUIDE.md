# CrossTwin Showcase Guide — Intro to Urban Digital Twins

A step-by-step demo script for students who already know GIS (layers, CRS, vector vs raster, WMS) and are meeting Urban Digital Twins (UDTs) for the first time. It moves from **looking** → **asking** → **changing** → **building**, so each step adds one idea on top of the last one.

**Format:** ~90 min (60 min guided demo + 30 min hands-on). Each step lists *what to click*, *what to say* (the UDT idea behind it) and *a question for the room*. Steps marked ⏱ can be shortened if time runs out; steps marked 🔑 need a staff login.

---

## 0. Before the session (instructor checklist)

| Check | How |
|---|---|
| Database has data | `uv run python tools/example_db.py load` into an empty DB (Enschede example data) |
| PostgreSQL + PostGIS run | `uv run python tools/check_postgres.py` |
| Django **and** TiTiler run | `start.bat` (or `runserver 8000` + `uvicorn tiler:app --port 8001`) |
| Raster tiles show | Open the map, switch on a DSM or land-cover raster layer |
| Staff account exists | `uv run python manage.py createsuperuser` — needed for steps 8–10 |
| Optional tools | SOLWEIG: `uv sync --inexact --extra solweig` (GPU helps). LST: `GEE_PROJECT_ID` in `.env`. Live weather: internet access |
| Backup point | Create a restore point in the backup bar before step 9, so you can undo the demo edits |

Rehearse once at the zoom level you will present at. Keep a second browser tab with `docs/dag_view.html` open for step 10.

---

## Level 1 — What is a twin? (Look) · 5 min

### Step 1. The landing page — `/welcome/`
- **Click:** scroll slowly through the 3D city.
- **Say:** a UDT is not one map; it is a set of linked *systems* (built-up, water, heat, housing, nature) on one shared geography. The graph at the end is the causal model that links them — we will come back to it at the end.
- **Ask:** *"What makes this different from a GIS project with many layers?"* Keep the answers on the board; revisit them in step 11.

---

## Level 2 — The twin as a GIS you already know (Look) · 10 min

### Step 2. The map and the layer catalog — `/`
- **Click:** the **Layers** panel → *Select all* / *Select none* / *Fit all*. Switch on one vector layer (buildings), one raster (DSM or land cover) and one WMS layer.
- **Say:**
  - Vector, raster and WMS live side by side, like in QGIS.
  - Data is **stored** in EPSG:28992 (RD New), **served** as GeoJSON in EPSG:4326, and rasters are **tiled** as Cloud-Optimized GeoTIFFs in EPSG:3857 (TiTiler). Same CRS questions they know, solved on a server.
  - Large layers load **only for the current view** and reload when you pan — a twin of a whole city cannot be sent to the browser at once.
- **Ask:** *"Why store in RD New and not in WGS84?"* (metric areas/distances for the calculations).

### Step 3. Click a feature
- **Click:** a building, then a soil polygon.
- **Say:** the popup shows attributes **and** related tables (the soil polygon shows its soil type and hydrologic group, joined from another table). Use **3D tilt** (camera button) to show extruded building heights — measured from the DSM, not typed in.

---

## Level 3 — Places, people and time (Ask) · 10 min

### Step 4. Administrative hierarchy — toolbar 📑 *Administrative Data*
- **Click:** a neighbourhood, then its district and city. Open the **population dock**.
- **Say:** Province › City › District › Neighbourhood. Neighbourhood population is the input; districts, cities and provinces **sum themselves automatically** when it changes. This is the first sign of a *living* model rather than a static map.

### Step 5. Time — Actions menu (bottom bar) → *Select year*
- **Click:** switch 2025 → 2030 → 2050.
- **Say:** future years come from CBS population forecasts; beyond them the panels label values as *trend extrapolation*. A twin has a time axis, and it must be honest about which values are observed and which are projected.

### Step 6. Live data — weather pill (top centre) ⏱
- **Click:** the pill; pan to another town and watch it update.
- **Say:** the "digital twin" idea of **synchronisation**: some inputs are live (Open-Meteo, KNMI radar when it rains). Most urban data is updated yearly — part of a twin is knowing how fresh each input is.

---

## Level 4 — Indicators: from data to decisions (Ask) · 15 min

### Step 7. The domain dashboards — toolbar buttons
Open them in this order (least → most chained):

| Button | Show | Talking point |
|---|---|---|
| 🏗️ **Built-up** | building stock, coverage/FAR, park area per inhabitant, Degree of Urbanisation | Indicators are queries over the spatial data, clipped to the selected unit |
| 🏘️ **Housing** | supply vs demand, household size, affordability | Demand is derived from population × household size — change one, the other follows |
| 🚰 **Water Supply** | production, NRW, groundwater recharge, homes without supply (drop icons on the map) | Recharge = rain − runoff − evapotranspiration, using soil, land cover and KNMI rain |
| 🌡️ **Heat** | PET, UTCI, green and shade shares, weather-based heat stress | Heat depends on buildings, trees, surfaces *and* weather |

- **Click:** any **"?"** button on a card.
- **Say:** every number shows *what* it is, *how* it is measured and the *equation*. A twin used for planning must be explainable and reproducible — every stored number records its source data, parameters and method.
- **Ask:** *"Which of these indicators would you trust for a council decision, and what would you want to check first?"*

---

## Level 5 — What-ifs: asking "what happens if…?" (Change, safely) · 10 min

### Step 8. Sliders and scenarios
1. **Water panel:** move the **Rain Event** slider (25 → 60 mm) and switch the groundwater **season** (wet/dry). Watch runoff and infiltration change.
2. **Heat panel:** move air temperature / wind / radiation. The weather pill gets a **What-if** badge.
3. **Bottom bar → 🧩 Scenarios:** pick *2050 high (Hd)*, then switch heat mode *average* → *warmest* (heat-wave day). Note the year changes with it. Open *Quick what-if*.

- **Say:** the key distinction of this session:
  - The **database holds the baseline** (the best description of today).
  - A **what-if is a deviation** from it, computed per request with the *same equations* — **nothing is stored**.
  - Scenarios use the KNMI'23 climate scenarios; LST is **not** projected (it is a satellite observation), so future heat uses modelled thermal comfort (PET/UTCI/WBGT).
- **Ask:** *"Why should a slider never overwrite the stored data?"*

---

## Level 6 — Computing new layers for the view (Build) · 10 min 🔑

Actions menu → **Calculate for this view**. Zoom to one neighbourhood first; each tool works on what is on screen.

| Tool | What it does | GIS link |
|---|---|---|
| **Sky View Factor** | share of visible sky per cell from the DSM | a classic raster analysis, run server-side, stored as COG |
| **Land Surface Temperature** ⏱ | lists Landsat scenes over the view, computes LST (needs Earth Engine) | remote sensing → raster layer, scene id stored with the result |
| **Thermal Comfort (SOLWEIG)** ⏱ | Tmrt, UTCI and PET for one hour (needs the solweig extra) | combines DSM, land cover, sun position and weather |
| **Degree of Urbanisation** | the UN/EU DEGURBA classification at 1 km **and** a local 100 m version | same method, two scales: show how the grid size changes the answer (MAUP!) |

- **Say:** a twin is not only a viewer; it *produces* new data, and each result records its inputs (DSM id, radius, cell size, scene, weather) so it can be recomputed.
- **Ask (DEGURBA):** *"The 1 km grid and the 100 m grid disagree at the city edge. Which one is right?"*

---

## Level 7 — Editing the twin: cause and effect (Change, for real) · 10 min 🔑

### Step 9. Edit and watch the cascade
1. Create a **backup point** in the backup bar.
2. In **Map settings → Editable layers**, make sure buildings are editable.
3. **Draw a new building** (or delete one) in a street.
4. Point out what follows *automatically*:
   - the street canyon height/width (H/W) updates,
   - the land cover gets an urban-fabric patch,
   - the edited DSM is rewritten,
   - a **stale dot** appears on the Actions button: SVF / thermal comfort here are now out of date.
5. **Restore** the backup — everything returns.

- **Say:** this is the *twin* part of a digital twin: change the physical model and dependent values recompute, one causal link at a time. Unlike a what-if, an edit **is stored**, which is why it is journalled and reversible.

### Step 10. Neighbourhood generator ⏱
- **Click:** Actions → *Neighbourhood generator* → *Draw outline* on an empty field. Try styles (Vinex, garden city, urban block), street pattern, and *Shuffle*.
- **Say:** the preview checks protected nature (Natura 2000 / NNN), zoning and Dutch building rules (minimum dwelling size, fire gaps, daylight), and reports density (FSI, GSI, dwellings/ha). The seed is stored, so the same layout comes back — design exploration that stays reproducible.

---

## Level 8 — Under the hood (Understand) · 5 min

### Step 11. The causal graph — `docs/dag_view.html`
- **Show:** the DPSIR graph (Driver → Pressure → State → Impact → Response). Highlight one chain you demonstrated, e.g. *Population → Housing demand* or *Buildings → Street canyon → Heat*.
- **Say:** each arrow is either implemented, partial or a gap. Every edge in code is a node that recomputes itself when its input changes — there is no hidden central engine. Honest coverage is part of the model.
- **Return to the board from step 1:** what makes this a twin and not a GIS project? Expected answers: linked systems, causal links, time axis, live inputs, what-ifs vs baseline, two-way edits with propagation, reproducibility.

### Step 12. Where the data comes from ⏱
- **Click:** Actions → **Retrieve Data from APIs**.
- **Say:** PDOK (BAG, BGT, AHN, zoning), CBS, KNMI, OSM, Klimaateffectatlas, Earth Engine — all open Dutch/global data, listed with versions in `docs/DATA_SOURCES.md`. A twin is only as good as its data pipeline.

---

## Your turn — hands-on (30 min)

Work in pairs. Pick a neighbourhood in Enschede. Do the levels in order and stop where your time ends.

**🟢 Explore (everyone)**
1. Find the neighbourhood with the highest building coverage. What is its park area per inhabitant?
2. Switch the year to 2050. Which indicators change, and which are marked as extrapolated?
3. Open three "?" help popovers and write down one equation that surprised you.

**🟡 Ask "what if" (no login needed)**
4. Water: at which Rain Event (mm) does runoff exceed half of the rain in your neighbourhood? Does the dry season change it?
5. Heat: set the *2050 high, warmest* scenario. How much does the heat-wave day differ from the *average* mode?
6. Housing: lower the household size slider by 0.2 persons per home. How many extra dwellings does your neighbourhood need?

**🔴 Build (staff account, with a backup point first)**
7. Add a building in a narrow street. Report the canyon H/W before and after, then recompute SVF for the view.
8. Generate a neighbourhood on an empty plot with two styles. Compare FSI, GSI and dwellings/ha. Which passes all site checks?
9. Compare the 100 m and 1 km Degree of Urbanisation for your city. Where do they disagree, and why?

**Reflect (5 min, as a group)**
- Which value would you *not* trust yet, and what data would fix it?
- Pick one gap in the DAG view. What data and equation would implement it?

---

## Invitation

CrossTwin is open for you to use in your own coursework and thesis:
- **Use it:** run it locally (`uv sync`, `setup_db.bat`, `start.bat`) and load the example data, or ask for an account on the course instance.
- **Bring your data:** *Upload Data* takes GeoJSON/Shapefiles and maps their fields onto any model; *Retrieve Data from APIs* pulls another Dutch city from PDOK/CBS/OSM.
- **Extend it:** implement a missing edge from the DAG — a new indicator, a new data source, a better equation. Every contribution comes with its source, a test and its equation in the docs, so your work is citable.
- **Question it:** the most useful feedback is a number you think is wrong and why.

Further reading in the repository: `docs/DAG_COVERAGE.md` (what is and is not modelled), `docs/MAP_EDITING.md`, `docs/THERMAL_COMFORT.md`, `docs/DEGREE_OF_URBANISATION.md`, `docs/DATA_SOURCES.md`.
