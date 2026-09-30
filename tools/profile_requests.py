"""
Profile requests the way the browser makes them, and show where the time goes.

    python tools/profile_requests.py "/api/admin-unit/?lng=6.895&lat=52.219"
    python tools/profile_requests.py "/watersupply/indicators/neighborhood/City/2025/" --runs 3
    python tools/profile_requests.py "/api/layers/" --save layers.prof     # open with snakeviz

Each URL runs --runs times in one fresh process: run 1 includes the one-off
startup costs (imports, caches), later runs show the steady state.

Reading the tables:
- "cumulative" = time in a function INCLUDING everything it calls. Read it
  top-down to follow the call chain to the expensive branch.
- "tottime" = time spent INSIDE the function itself. Its top rows are the
  actual hot spots.
- Many `importlib`/`_find_and_load` rows -> import time; find the module with
  `python -X importtime` (see docs/PERFORMANCE.md §0).

Only use it with GET requests: it runs against the database configured in .env.
"""
import argparse
import cProfile
import io
import os
import pstats
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "DigitalTwin.settings")

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("urls", nargs="+", help="paths to GET, e.g. /api/layers/")
    parser.add_argument("--runs", type=int, default=2, help="requests per URL in the same process (default 2)")
    parser.add_argument("--top", type=int, default=20, help="rows per table (default 20)")
    parser.add_argument("--save", help="write the first run's profile to this file (for snakeviz)")
    args = parser.parse_args()

    # HX-Request: the map loads its panels through htmx, which sends this header
    client = Client(HTTP_HOST="localhost", HTTP_HX_REQUEST="true")

    for url in args.urls:
        for run in range(1, args.runs + 1):
            profiler = cProfile.Profile()
            start = time.perf_counter()
            profiler.enable()
            response = client.get(url)
            profiler.disable()
            ms = (time.perf_counter() - start) * 1000
            print(f"\n=== {url}  run {run}: HTTP {response.status_code}, {ms:.0f} ms  "
                  f"[{response.get('Server-Timing', 'no Server-Timing: set QUERY_STATS=True')}]")

            if args.save and run == 1:
                profiler.dump_stats(args.save)
                print(f"(profile saved to {args.save})")

            for order, title in (("cumulative", "time including what each function calls"),
                                 ("tottime", "time spent inside each function itself")):
                out = io.StringIO()
                pstats.Stats(profiler, stream=out).strip_dirs().sort_stats(order).print_stats(args.top)
                rows = [line for line in out.getvalue().splitlines() if line.strip()][4:]  # skip header
                print(f"\n-- top {args.top} by {order}: {title}")
                print("\n".join(rows))


if __name__ == "__main__":
    main()
