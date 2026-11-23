# Map UI simplification — step 0: baseline

Step 0 of the plan in [`CrossTwin Map Simplification.html`](CrossTwin%20Map%20Simplification.html).
It changes no code: it records how hard the current map screen is to use, so step 7
can repeat the same test and show whether steps 1–6 helped.

Screen under test: `mainMap/templates/mainMap.html` on branch `Redesign-UI` at 75a09c7
(23 Nov 2026). Rerun the dry run below if the screen changes before the sessions.

## Participants

3–5 people who have never used CrossTwin: urban planners, planning or geo students.
No staff accounts for tasks 1–2; task 3 needs a staff login (the generator is staff only),
which the facilitator logs in before the task.

Record per participant only: role, map/GIS experience (none / some / daily), date.
No names in this file.

## Setup

- Fresh browser profile (no cached tour state, no dragged overlays), 1920 × 1080 window.
- Database: the example data (`uv run python tools/example_db.py load`), city Enschede,
  TiTiler running (`start.bat`).
- Start every task from the map as it opens: Overview tool active, year 2025, current climate,
  no panels open. Reload the page between tasks.
- Screen + audio recording; the facilitator also counts clicks live.

## Protocol

1. Read the task aloud; hand over the card with the task text. Do not name controls.
2. Ask the participant to think aloud. Start the timer at the first mouse move.
3. Stop when the participant states the answer (task 1–2) or the layout is stored or
   previewed with ~300 homes (task 3), or after **5 minutes** (= not completed).
4. Help only after 60 s without progress, and log it as an assist.
5. At task end, before anything is closed, count the open overlays (see below).
6. After all tasks: "What was the hardest part?" and "What did you expect to find where?"

## Tasks

The minimum paths are today's shortest routes; walk them once before the first session
(dry run) and correct them here if the count differs.

| # | Task (read aloud) | Done when | Minimum path today | Clicks | Target after step 7 |
|---|---|---|---|---|---|
| 1 | "How hot does my neighbourhood get in 2050?" (point at a neighbourhood in Enschede) | Participant reads the PET/UTCI value of that neighbourhood for 2050 | Heat tool (🌡️) → neighbourhood on the map → Scenarios → 2050 High-dry → heat mode *Heat-wave day* → read the heat panel | 6 | 3 |
| 2 | "Which homes have no water supply?" | Participant points at the drop markers and says how many / where | Water Supply tool (🚰) → read the drops (legend explains them) | 2 | 2, with the advisor tray naming the count |
| 3 | "Sketch 300 homes on this field." (point at an empty field) | Preview shows ≈ 300 dwellings | Actions → Neighbourhood generator → draw outline → set target dwellings (21-field form) | 4 + form | 4, with a 4-field form |

## What to record

Per participant and task:

- **Time** (s) to done, or `DNF` at 5 min.
- **Clicks** (all mouse clicks incl. misclicks; drawing vertices in task 3 count as one).
- **Detours**: each control opened that is not on the minimum path (e.g. Layers panel,
  Actions menu in task 1, Dashboard). Name them.
- **Stuck points**: where the participant paused > 10 s or said they were lost, with a quote.
- **Assists**: number and what was said.
- **Open overlays at task end** (count rule below).
- **Hover-reliance**: did they need the toolbar tooltips to identify a topic? (yes/no)

### Overlay count rule

Count every floating element over the map that is open at task end, from this list
(17 that can be open together today):

toolbar · onboarding hint · guided tour card · layers panel · side panel · population dock ·
LST card · SVF card · Degree of Urbanisation card · generator card · thermal comfort card
(+ person panel counts as its own) · map settings card · legend stack (count 1 if any legend
shows) · weather pill (+ radar button counts if shown) · WMS time dock · actions menu ·
backup bar.

Not counted: the bottom bar and the camera buttons (always present).

## Results

Fill in after the sessions. One row per participant × task.

| P | Role | GIS exp. | Task | Time (s) | Clicks | Detours | Stuck points | Assists | Overlays | Hover-reliant |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 | | | 1 | | | | | | | |
| P1 | | | 2 | | | | | | | |
| P1 | | | 3 | | | | | | | |

### Summary

| Task | Median time | Median clicks | Completed | Median overlays |
|---|---|---|---|---|
| 1 | | | /n | |
| 2 | | | /n | |
| 3 | | | /n | |

Recurring stuck points (seen in ≥ 2 participants), and which plan step addresses each:

-

## Inventory facts at baseline

Counted from the markup at 75a09c7, for comparison after each step:

- Left toolbar: 9 topic buttons, emoji only, labels on hover. Energy, Green and Blue Space
  and Physical Environment open no indicator panel.
- Bottom bar: Layers / Features / Visible / Population counters, Actions (with year),
  Dashboard, Scenarios.
- Year is set in two places: Actions menu year slider and the Scenarios panel (synced both ways).
- Neighbourhood generator card: 21 inputs. Thermal comfort card: 22 inputs (incl. the
  person panel).
- Guided tour: 8 text steps.

## Step 1 — declutter (done 23 Nov 2026)

- Toolbar: emoji → Bootstrap Icons with always-visible labels (Overview, Areas, Built-up,
  Housing, Energy, Heat, Green, Water, Ground); full names in `title`/`aria-label`
  (labels hide below 768 px, where the toolbar is a row of round buttons). Toolbar 64 px wide.
- Bottom bar: Layers / Features / Visible counters removed; a **Layers** button opens the
  layers panel, whose footer now shows the three counts (`.layers-stats`).
- Sentence-case panel titles (`.side-panel-title` no longer uppercased; JS and
  `data-panel-title` strings changed too). Panels refreshed via `htmx.ajax` take the title
  of their source button, else of the active topic, instead of "INFO".
- Topics without indicators (Areas, Energy, Green, Ground) open a "No indicators yet" panel
  that points at their layers (`Config.js::TOOL_CONTENT`).
- Remaining emoji in the bottom bar (Population, Dashboard, Scenarios) → Bootstrap Icons.

## Step 2 — topics become lenses (done 23 Nov 2026)

- `Config.js::LENSES` (+ `LENS_GROUPS`) replaces `TOOL_CATEGORIES` / `TOOL_CONTENT`: per lens
  its group, label, title, icon, `apps` (catalog app labels), `panel` URL builder or static
  `intro`, and `tools` (the Calculate tools step 4 moves into the panel).
  `mainMap.js::ADMIN_PANEL_TOOLS` is derived from it.
- The rail is drawn from that table (`MapUI.js::renderLensRail`): Overview, then
  *City systems* (Water, Energy), *People* (Housing, Built-up, Population),
  *Environment* (Heat, Green, Ground). Areas became the Population lens (administrative
  layers + the population dock).
- `Layers.js::openLens`: only the lens's layers on (legends follow), layers that arrive
  later with the background catalog follow the lens too. `closeLens` (Overview) puts back
  the layers shown before the first lens. A unit click under a lens without an indicator
  panel no longer opens the Water panel.
- `Map_init.js::syncLensDim`: a slate `background` layer (`#1c2529`, 42 %) between the
  basemap and our layers, 350 ms fade (none with reduced motion), re-added after a
  basemap switch.
- Layers panel: "<lens> layers" only, with an *All layers (n)* drawer; the counts show in
  the drawer and under Overview. Picking a lens no longer opens the layers panel.
- A lens click no longer resets the basemap to Default (that reset served the removed
  Satellite tool).

Not changed, seen while testing: the Heat lens switches on every stored heat raster
(9 legends in the example data) and each raster added zooms the map to itself; both were
already so with the old tool buttons.

## Step 3 — one clock and a status strip (done 23 Nov 2026)

- **Status strip** (`#status-strip`, top centre; centred in the part of the map an open
  side panel leaves free): city name, population (opens the dock), the **time chip**, the
  weather pill. The loader moved below it (`top: 60px`).
- **Time chip** → time menu: year slider (moved out of the Actions menu), climate pathway
  (Low/High × dry/wet, enabled for the decades 2030–2100), heat day, *Compare scenarios*
  (opens the Scenarios panel). A scenario colours the chip sky blue, the colour the panel
  already uses for "not observed". Pathway and heat-day choices come from
  `climate.PATHWAYS` / `HEAT_MODES` through the map view.
- **One state, no two-way sync:** `mainMap.js::setTime({year, pathway, heat})` is the only
  writer of `ACTIVE_YEAR`, `CLIMATE_PATHWAY`, `CLIMATE_HEAT` and the derived
  `CLIMATE_SCENARIO`. The Scenarios panel calls it after its swap; `setActiveYear`,
  `syncClimateToYear`, `chooseYear` and the Scenarios button badge are gone.
- **Bottom bar:** camera, Layers, Actions, Dashboard. Population, the year, the city name
  and the Scenarios button moved to the strip. The mode switch arrives with step 5.
- Not in this step: the advisor flag (its tray is step 6).

Seen while testing: with a scenario chosen and the Heat lens open, the weather pill
still shows its own scenario badge next to the time chip (same information twice).

## Step 4 — the same tabs in every lens panel (done 23 Nov 2026)

Choices (asked): Summary = four headline cards + "All indicators and what-ifs"; What-if =
sliders + every card (slider effects stay visible); a lens with cards opens with vector
layers only, rasters come with Show on map.

- Tabs *Summary / What-if / Calculate* in the side panel header for the Water, Heat,
  Housing and Built-up panels (`Panels.js::setPanelTab`). Calculate only where the lens has
  tools: Heat (LST, SVF, Thermal comfort), Built-up (Degree of urbanisation).
- Headline cards (`.is-headline`): Water — supply vs demand, supply security, non-revenue
  water, groundwater recharge; Heat — LST, PET, UTCI, vegetation; Housing — supply coverage,
  affordability, affordability stress, new units; Built-up — coverage, building stock,
  degree of urbanisation, park area.
- *Show on map* on every card with a layer behind it (26 cards; affordability, affordability
  stress, service time, OPEX and a few market cards have none). It focuses the map on that
  card's layers; the newest raster of a raster model. Pressed again: back to the lens.
- The four tool cards moved from the Actions menu into `#panel-calculate` (not draggable
  any more). The generator stays in the Actions menu until Edit mode (step 5). The stale
  SVF / thermal comfort dot moved from the Actions button to the Heat rail button.
- Standalone dashboards render the same grid partials; they have no map, so no Show on
  map, and no tabs (everything shown, as before).

Fixed on the way: the Heat lens no longer opens with nine raster legends.

Follow-up (asked): "newest raster by id" could show a climate scenario map under an observed
number (scenario rasters keep the observed hour as `date_time` and have higher ids, so a date
rule would not exclude them either). The heat cards now pass the exact raster row their number
was read from (`_raster_stats_sql` returns its `id`, `views._build_indicators` → `map_raster`);
no raster behind the number, no button. Pinned by
`test_show_on_map_gets_the_observed_raster_behind_the_number` and `core/tests/test_show_on_map.py`.
