---
name: dag-edge
description: Implement, change or remove an edge of core/DAG.dot in CrossTwin (the DPSIR causal graph) following the signal/receiver contract — target save(), chain.py equation, receiver in signals.py, bulk deferral, tests, and every doc/status file that must follow (functions_and_equations.tex, docs/DAG_COVERAGE.md, core/dag_status.py, landing graph.js, dag_view.html). Use whenever a task makes a stored or dashboard value depend on another node, adds a receiver, or says an edge is now implemented/partial/removed.
argument-hint: "<Source> -> <Target>"
---

# Implement a DAG edge: $ARGUMENTS

The full contract is "Implementing a DAG Edge" in `.claude/CLAUDE.md`; `watersupply/` is the reference implementation. This is the checklist. Work through it in order and report each item as done / not applicable (with the reason).

## 0. Ground truth first

- Find both nodes in `core/DAG.dot` (exact names; a lagged edge `[lag=1]` never gets a receiver, see `docs/DAG_REVISIONS.md`).
- Read the edge's current status in `core/dag_status.py` and its entry in `docs/DAG_COVERAGE.md`. Do not claim it is a gap or implemented without reading the code that would implement it.
- Identify the source and target **models** and the apps they live in. If the target is not stored and nothing downstream reads it, it may stay a dashboard-only function in `calculations/indicators.py` (still document `DAG edges:`); skip to step 6.

## 1. Equation (rule 2)

- Pure function in `<target_app>/calculations/chain.py`: no ORM queries (at most one clearly named DB helper), named + cited constants (Reproducibility), docstring with units and `DAG edges: Source -> Target`.
- Heavy libraries are imported inside the function.

## 2. Node (rule 1)

- The target's `save()` reads its inputs and calls the chain function. Docstring lists `DAG edges: Source -> Target`.
- A missing input keeps the stored value, never writes 0 (rule 4).
- Store the inputs used (source, year, parameters) on the row when they can vary (Reproducibility).

## 3. Edge receiver (rule 3) in `<target_app>/signals.py`

- `@receiver(post_save, sender=Source, dispatch_uid="<app>_<source>_saved")` plus `post_delete` (`..._deleted`) when deleting the source changes the target.
- `if raw: return` first. If the source can be restored by map editing, make sure Restore triggers the cascade itself.
- Body only selects the affected target rows and calls `_resave(queryset)`. No value computed here, one edge per receiver.
- Comment/docstring: `DAG edge: Source -> Target`.
- Cross-app: the downstream app imports the upstream one, never the reverse (rule 6). If the source is written with `update()`, subscribe to (or add, in the upstream app) a custom `Signal`.
- `apps.py::ready()` imports `signals`.
- No upstream writes, no cycles (rule 5). Run `core.tests.test_dag`.

## 4. Bulk path (rule 7)

- If the source is imported in bulk: the refresh helper checks the app's thread-local deferral and queues the parent id; the context manager is registered in `importer/batching.py::deferred_cascades()` in the right `ExitStack` order.
- If the source is in `BULK_IMPORT_MODELS` (`bulk_create`, no signals), replay the receiver in its finalizer.
- Writes via `update()` on vector models call `bump_layer_version()`.

## 5. Dashboard (rules 2, 8)

- `views._build_indicators` calls the same chain function with what-if overrides; it never saves.
- Parity test: with default controls the dashboard equals the stored value.

## 6. Tests (rule 10) in `<target_app>/tests/`

- Saving (and deleting, if handled) the source updates the target.
- A pinned numeric result for a known input.
- A deferral test when the source is bulk-imported: `mock.patch.object(signals, "_resave", wraps=signals._resave)` and assert one refresh per parent.
- Run: `uv run python manage.py test <app> --settings=DigitalTwin.settings_test --keepdb --noinput`.

## 7. Docs and status (all must agree)

1. `docs/functions_and_equations.tex`: equation, `<app>/calculations/<module>.py::function`, status.
2. `docs/DAG_COVERAGE.md`: recount implemented / partial / gap (and %), add a dated note to the change list, remove the edge from the gap list of its app, add a row to the edge → function table.
3. `core/dag_status.py`: the edge's status.
4. `core/static/js/landing/graph.js`: the `computed` flag if the edge is drawn there, and the "just over half" sentence in `mainMap/templates/mainMap/landing.html` if the share crosses a threshold.
5. If you added/removed/renamed an edge in `core/DAG.dot`: argue it in `docs/DAG_REVISIONS.md`.
6. Regenerate: `uv run python tools/dag_view.py`, then run `core.tests.test_dag` (checks `dag_status.py` against `DAG.dot` and the landing graph).
7. If a new external source or cited rule was used: add it to `importer/external_catalog.py` or `core/data_sources.py` and run `uv run python tools/data_sources.py`.

Finish with a short report: edge, files changed, tests run (with result), new coverage count.
