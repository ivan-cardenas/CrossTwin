"""Claude Code PostToolUse hook: project checks after an edit.

Wired in .claude/settings.json for Edit|Write|MultiEdit. Exit 2 sends stderr
back to Claude as feedback (the edit itself is already applied).

1. Import guard: modules loaded at startup or by the URLconf (models, signals,
   apps, views*, admin, urls, importer/utils.py, mainMap/styles/rasterStyles.py)
   must not import heavy libraries at module level.
2. Targeted checks for files with a fast drift test:
   - core/DAG.dot, core/dag_status.py      -> core.tests.test_dag
   - importer/external_catalog.py,
     core/data_sources.py                  -> regenerate docs/DATA_SOURCES.md
   - core/indicator_help.py                -> core.tests.test_indicator_help
"""
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():  # Linux/macOS venv layout
    PYTHON = ROOT / ".venv" / "bin" / "python"

HEAVY = {"numpy", "scipy", "pandas", "geopandas", "rasterio", "rio_cogeo",
         "rio_tiler", "openeo", "ee", "torch", "solweig_gpu", "xarray", "matplotlib"}
STARTUP_NAMES = {"models.py", "signals.py", "apps.py", "admin.py", "urls.py"}
STARTUP_PATHS = {"importer/utils.py", "mainMap/styles/rasterStyles.py"}

TEST_ARGS = ["manage.py", "test", "--settings=DigitalTwin.settings_test", "--keepdb", "--noinput"]
TESTS = {
    "core/DAG.dot": "core.tests.test_dag",
    "core/dag_status.py": "core.tests.test_dag",
    "core/indicator_help.py": "core.tests.test_indicator_help",
}
DATA_SOURCE_FILES = {"importer/external_catalog.py", "core/data_sources.py"}


def is_startup_module(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if "/migrations/" in rel or "/tests/" in rel or rel.startswith(("tools/", ".venv/")):
        return False
    return (name in STARTUP_NAMES or rel in STARTUP_PATHS
            or (name.startswith("views") and name.endswith(".py")))


def top_level_heavy_imports(source: str) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found = []

    def visit(body):
        for node in body:
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module]
            elif isinstance(node, ast.If):
                test = ast.unparse(node.test)
                if "TYPE_CHECKING" not in test:
                    visit(node.body)
                visit(node.orelse)
                continue
            elif isinstance(node, ast.Try):
                visit(node.body)
                continue
            else:
                continue
            for m in mods:
                if m.split(".")[0] in HEAVY:
                    found.append((node.lineno, m))

    visit(tree.body)
    return found


def run(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run([str(PYTHON), *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=240)
    return proc.returncode, (proc.stdout + proc.stderr)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not path:
        return 0
    p = Path(path).resolve()
    try:
        rel = p.relative_to(ROOT).as_posix()
    except ValueError:
        return 0

    problems = []

    if p.suffix == ".py" and is_startup_module(rel) and p.exists():
        hits = top_level_heavy_imports(p.read_text(encoding="utf-8", errors="replace"))
        if hits:
            lines = ", ".join(f"line {n}: {m}" for n, m in hits)
            problems.append(
                f"{rel} imports heavy libraries at module level ({lines}). It is loaded at "
                "startup/by the URLconf: move the import inside the function that uses it "
                )

    if rel in TESTS:
        code, out = run([*TEST_ARGS, TESTS[rel]])
        if code != 0:
            problems.append(f"{TESTS[rel]} failed after editing {rel}:\n" + out[-3000:])

    if rel in DATA_SOURCE_FILES:
        code, out = run(["tools/data_sources.py"])
        if code != 0:
            problems.append(f"tools/data_sources.py failed after editing {rel}:\n" + out[-3000:])
        else:
            print(f"docs/DATA_SOURCES.md regenerated after editing {rel}.")

    if problems:
        print("\n\n".join(problems), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
