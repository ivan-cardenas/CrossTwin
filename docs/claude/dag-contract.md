<!-- Moved verbatim from .claude/CLAUDE.md on 2026-11-23. CLAUDE.md points here. -->

# DPSIR causal network and the DAG edge contract

## DPSIR causal network (`core/DAG.dot`)

The project follows the **DPSIR framework** (Driver → Pressure → State → Impact → Response) to model causal relationships between urban systems. The full causal graph is defined in `core/DAG.dot` (Graphviz format). Each domain app's `calculations/indicators.py` documents which DAG edges its functions implement via comments like `# DAG edges: Central_Bank -> Mortgage`.

When adding new calculations, trace the relevant DAG edges and document them in the function docstring to maintain traceability between the causal model and code. Edges whose target is stored must follow the signal/receiver contract in [Implementing a DAG Edge](dag-contract.md).

#### DAG Edge Coverage Gaps

The count of implemented / partial / gap edges and the verified gap list per app live in [`docs/DAG_COVERAGE.md`](../DAG_COVERAGE.md). Read it before claiming an edge is (not) implemented, and update it with every edge change. The `/dag-edge` skill walks through the whole contract.

## Implementing a DAG edge (signal/receiver contract)

**Every new or changed indicator that implements an edge of `core/DAG.dot` must follow this contract.** It is how the causal graph becomes executable: there is no central graph engine. Each node computes itself from its inputs, each edge is a receiver that re-runs the target when the source changes, and a change travels Driver → Impact one edge at a time. `watersupply/` is the reference implementation; copy its shape.

1. **Node = model, equation = the node's `save()`.** A stored DAG node is a model. Its derived fields are computed in its own `save()` from its inputs (its incoming edges). The `save()` docstring lists them as `DAG edges: Source -> Target`, using the node names from `DAG.dot` exactly. Never compute a node's value inside a receiver and write it onto the target. The receiver only triggers the target's `save()`.
2. **One equation, two callers: `<app>/calculations/chain.py`.** Any equation that both the stored path (`save()`) and the dashboard (`views._build_indicators`) need lives once, as a pure function in `<app>/calculations/chain.py` (no ORM queries; at most one clearly named DB helper such as `chain.baseline_population`). `save()` calls it with stored inputs; `_build_indicators` calls it with the request's what-if inputs. Never re-type an equation in `views.py`. Add a parity test: with default controls, the dashboard equals the stored value (`DashboardIsADeviationFromTheBaselineTests`).
3. **Edge = receiver in `<app>/signals.py`.** For an edge `A -> B`, add a `@receiver(post_save, sender=A)` (plus `post_delete` when deleting A changes B) whose body re-saves the affected B rows with `_resave(queryset)`. Re-saving B runs B's `save()` and fires B's own `post_save`, so the next edge (`B -> C`) runs automatically. Write that next edge as its own receiver; don't chain several edges inside one receiver. Every receiver:
   - has a unique `dispatch_uid` (`"<app>_<source>_<saved|deleted>"`);
   - returns early on `raw=True` (fixtures, backup restore). Map editing's restore must then trigger the cascade itself (see Map Editing);
   - names its edge(s) in a docstring or comment (`DAG edge: A -> B`);
   - is connected by the app's `apps.py::ready()` importing `signals`.
4. **Failures never block the source save.** Refresh dependents through `_resave()`, which logs `ValidationError` instead of raising it. A missing input in the target keeps its stored value rather than writing zero (e.g. `SupplySecurity.save()` without production).
5. **No loops.** The graph is acyclic (`core/test_dag.py`); a real feedback is drawn as a lagged edge `[lag=1, style=dashed]` (one planning step later, never a receiver; listed in `core/test_dag.py::LAGGED_EDGES`, argued in `docs/DAG_REVISIONS.md`; today only `Network -> New_Units`); keep the code acyclic too. A receiver never writes to a node upstream of its source. Aggregations that would re-trigger themselves (parent sums of children) are written with `queryset.update()`, which fires no signal. After an `update()`:
   - call `bump_layer_version()` for vector models;
   - if another app depends on the aggregated value, send a **custom signal** (`django.dispatch.Signal`, defined in the upstream app, e.g. `administrative.signals.city_population_changed`) and let the downstream app subscribe to it.
6. **Cross-sector edges point one way.** The downstream app imports and subscribes to the upstream app's model or signal. The upstream app never imports the downstream app. A new sector that depends on population, for instance, adds a receiver for `city_population_changed` / `PopulationProjection` in its own `signals.py`; `administrative` stays untouched.
7. **Bulk writes stay O(parents).** Each app's "refresh city X" helper must check a thread-local deferral and queue the id instead of working (pattern: `watersupply.signals.deferred_water_refresh` / `_refresh_city_water`). Register the context manager in `importer/batching.py::deferred_cascades()` (mind the `ExitStack` order: whatever is fed by another cascade must exit after it, i.e. be entered first). Run importer loops inside `deferred_cascades()`. `bulk_create` skips signals entirely, so a model written by `BulkWriter` needs its receivers replayed by its finalizer.
8. **What-ifs never write.** Sliders and switches run the `chain.py` functions per request with override values. They must not save models or fire signals. The stored database holds the baseline; a what-if is a deviation from it. Geometric what-ifs (map editing) are real saves and go through rule 3 like any import.
9. **Year semantics.** Stored records with a `year` use the baseline population of *that* year (`watersupply.calculations.chain.baseline_population(city, year)`: CBS median forecast, no extra growth, current population as fallback), not `City.currentPopulation`. Records without a year refresh only the latest dependent record (see the OPEX/SupplySecurity note under watersupply).
10. **Tests and docs, per edge.** For each new edge add:
    - a test that saving (and deleting, if handled) the source updates the target;
    - a deferral test when the source is bulk-imported (count refreshes with `mock.patch.object(signals, '_resave', wraps=...)`).

    Then update `docs/functions_and_equations.tex` (equation, source location, status), the coverage count, gap list and edge → function table in `docs/DAG_COVERAGE.md`. The `/dag-edge` skill is the checklist.

Pure dashboard-only statistics that no other node consumes (e.g. infiltration for a rain event, street density) may stay in `calculations/indicators.py` without a receiver. They still document their `DAG edges:`, and they move to rules 1–3 as soon as a downstream node needs their value stored.

#### Edge → function map (propagated edges)

The table of every propagated edge (target computed in, triggered by which receiver) is in [`docs/DAG_COVERAGE.md`](../DAG_COVERAGE.md#edge--function-map-propagated-edges). Add a row there for each new edge.
