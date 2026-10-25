"""
Per-request SQL statistics

Enabled with QUERY_STATS=true in .env (default: on when DEBUG). For every
request it counts the SQL statements and the time spent in the database, and

- adds a `Server-Timing` header, so the browser's DevTools (Network ->
  Timing) shows DB time and query count next to each API call,
- adds `X-DB-Queries`,
- logs one line per request on the `crosstwin.querystats` logger, at
  WARNING when the request took longer than QUERY_STATS_SLOW_MS.

Unlike django.db.backends logging this needs no DEBUG=True, and it adds no
dependency. Time spent iterating a streaming response is not included.
"""
import logging
import time
from contextlib import ExitStack

from django.conf import settings
from django.db import connections

logger = logging.getLogger("crosstwin.querystats")


class QueryStatsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.slow_ms = getattr(settings, "QUERY_STATS_SLOW_MS", 500)

    def __call__(self, request):
        stats = {"count": 0, "seconds": 0.0}

        def count_query(execute, sql, params, many, context):
            start = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                stats["count"] += 1
                stats["seconds"] += time.perf_counter() - start

        start = time.perf_counter()
        with ExitStack() as stack:
            for conn in connections.all():
                stack.enter_context(conn.execute_wrapper(count_query))
            response = self.get_response(request)
        total_ms = (time.perf_counter() - start) * 1000
        db_ms = stats["seconds"] * 1000

        timing = f'db;dur={db_ms:.1f};desc="{stats["count"]} queries", app;dur={total_ms:.1f}'
        # Keep entries the view added itself (e.g. the WMS proxy's upstream time)
        if response.has_header("Server-Timing"):
            timing = f'{response["Server-Timing"]}, {timing}'
        response["Server-Timing"] = timing
        response["X-DB-Queries"] = str(stats["count"])

        level = logging.WARNING if total_ms > self.slow_ms else logging.INFO
        logger.log(level, "%s %s -> %s | %d queries, db %.1f ms, total %.1f ms",
                   request.method, request.get_full_path(), response.status_code,
                   stats["count"], db_ms, total_ms)
        return response
