---
name: sync-generated
description: Regenerate CrossTwin's derived files (docs/DATA_SOURCES.md, docs/dag_view.html, requirements.txt, optionally the architecture diagrams) and run their drift tests.
argument-hint: "[diagrams]"
disable-model-invocation: true
---

# Sync generated files

Run each step from the repo root, stop at the first failure and show its output. Arguments: $ARGUMENTS

1. `uv run python tools/data_sources.py` → `docs/DATA_SOURCES.md`
2. `uv run python tools/dag_view.py` → `docs/dag_view.html`
3. `uv export --format requirements-txt --no-hashes -o requirements.txt` (only after `uv.lock` changed: check `git status --short uv.lock requirements.txt`; skip otherwise)
4. Only if the arguments contain `diagrams`: `uv run python tools/palette_check.py && uv run python tools/arch_diagrams.py && uv run python tools/arch_export.py`
5. Drift tests: `uv run python manage.py test core.tests.test_dag core.tests.test_data_sources core.tests.test_indicator_help --settings=DigitalTwin.settings_test --keepdb --noinput`
6. `uv run python manage.py makemigrations --check --dry-run` (reports models without a migration; do not create one unless asked)

Report: which files changed (`git status --short`), test result, and any missing migration.
