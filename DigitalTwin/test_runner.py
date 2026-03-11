# DigitalTwin/test_runner.py
from django.test.runner import DiscoverRunner
from django.contrib.gis.db.backends.postgis.base import DatabaseWrapper
import psycopg


EXTENSIONS = [
    "postgis",
    "postgis_raster",
    "postgis_topology",
    "fuzzystrmatch",
]


def _patched_prepare_database(self):
    """
    Replace the PostGIS backend's prepare_database so it does NOT try to
    CREATE EXTENSION postgis — our runner handles that before Django touches
    the DB. Without this patch Django recreates the DB bare and tries to
    install extensions itself, failing on non-superuser accounts.
    """
    pass  # intentionally empty


class PostGISTestRunner(DiscoverRunner):

    def _get_db_settings(self):
        from django.conf import settings
        return settings.DATABASES['default']

    def _get_connection_params(self, db):
        return {
            'host':     db.get('HOST', 'localhost'),
            'port':     int(db.get('PORT', 5432)),
            'user':     db.get('USER', 'postgres'),
            'password': db.get('PASSWORD', ''),
        }

    def _get_test_db_name(self, db):
        """
        Return the exact test DB name — respecting explicit TEST.NAME.
        Do NOT add 'test_' prefix here; Django does that automatically
        when TEST.NAME is not set. Since we set TEST.NAME explicitly,
        use it as-is.
        """
        return db.get('TEST', {}).get('NAME') or f"test_{db['NAME']}"

    def _install_extensions(self, dbname, params):
        with psycopg.connect(dbname=dbname, autocommit=True, **params) as conn:
            with conn.cursor() as cur:
                for ext in EXTENSIONS:
                    try:
                        cur.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
                        print(f"  [TestRunner] Extension '{ext}' ready.")
                    except psycopg.errors.InsufficientPrivilege:
                        print(f"  [TestRunner] WARNING: No permission for '{ext}'. "
                              f"Ask your DBA: CREATE EXTENSION {ext} ON {dbname};")
                    except Exception as e:
                        print(f"  [TestRunner] WARNING: Could not create '{ext}': {e}")

    def setup_databases(self, **kwargs):
        db     = self._get_db_settings()
        params = self._get_connection_params(db)
        test_db = self._get_test_db_name(db)

        # --- Step 1: Create the test DB if it doesn't exist ---
        with psycopg.connect(dbname='postgres', autocommit=True, **params) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (test_db,))
                if not cur.fetchone():
                    print(f"\n  [TestRunner] Creating '{test_db}'...")
                    cur.execute(f'CREATE DATABASE "{test_db}"')
                else:
                    print(f"\n  [TestRunner] '{test_db}' exists, reusing.")

        # --- Step 2: Install extensions BEFORE Django runs migrations ---
        self._install_extensions(test_db, params)

        # --- Step 3: Patch PostGIS backend to skip its own CREATE EXTENSION ---
        # This prevents Django from wiping our work when it calls prepare_database()
        DatabaseWrapper.prepare_database = _patched_prepare_database

        # --- Step 4: Hand off to Django ---
        return super().setup_databases(**kwargs)