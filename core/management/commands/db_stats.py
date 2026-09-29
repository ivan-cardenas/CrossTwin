"""
Show the most expensive SQL statements recorded by pg_stat_statements
(docs/PERFORMANCE.md §0).

    python manage.py db_stats              # top 15 by total execution time
    python manage.py db_stats --limit 30 --order mean
    python manage.py db_stats --reset      # start a fresh measurement

Record a baseline, make a change, run --reset, repeat the same clicks in the
app, and compare. For any statement that stands out, run it through
`EXPLAIN (ANALYZE, BUFFERS)` and look for a Seq Scan on a large table or a
SubPlan executed once per row.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

ENABLE_HELP = """pg_stat_statements is not available in this database. To enable it:

  1. In postgresql.conf:   shared_preload_libraries = 'pg_stat_statements'
  2. Restart PostgreSQL.
  3. As a superuser, in this database:   CREATE EXTENSION pg_stat_statements;
"""

ORDER_COLUMNS = {
    "total": "total_exec_time",
    "mean": "mean_exec_time",
    "calls": "calls",
    "rows": "rows",
}


class Command(BaseCommand):
    help = "Top SQL statements by execution time, from pg_stat_statements."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=15)
        parser.add_argument("--order", choices=sorted(ORDER_COLUMNS), default="total")
        parser.add_argument("--width", type=int, default=160, help="Truncate each statement to this many characters.")
        parser.add_argument("--reset", action="store_true", help="Clear the collected statistics.")

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'")
            if cursor.fetchone() is None:
                raise CommandError(ENABLE_HELP)

            if options["reset"]:
                cursor.execute("SELECT pg_stat_statements_reset()")
                self.stdout.write(self.style.SUCCESS("pg_stat_statements reset."))
                return

            order = ORDER_COLUMNS[options["order"]]
            cursor.execute(
                f"""
                SELECT calls, total_exec_time, mean_exec_time, rows, query
                FROM pg_stat_statements
                WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
                ORDER BY {order} DESC
                LIMIT %s
                """,
                [options["limit"]],
            )
            rows = cursor.fetchall()

        self.stdout.write(f"{'calls':>8} {'total ms':>12} {'mean ms':>10} {'rows':>10}  statement")
        width = options["width"]
        for calls, total, mean, n_rows, query in rows:
            statement = " ".join(query.split())
            if len(statement) > width:
                statement = statement[: width - 3] + "..."   # ASCII: Windows consoles may be cp1252
            self.stdout.write(f"{calls:>8} {total:>12.1f} {mean:>10.2f} {n_rows:>10}  {statement}")
