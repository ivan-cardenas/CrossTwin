"""Check that PostgreSQL is reachable with the .env settings and has PostGIS.

Run before starting the servers (start.bat does this):

    python tools/check_postgres.py

Exit code 0 when the database is usable, 1 otherwise. Each failure prints
what is wrong and how to fix it: install PostgreSQL (winget on Windows),
start its service, install the PostGIS bundle, or create the extensions.
Standalone on purpose (no django.setup()), so it runs in well under a second.
"""
import glob
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# DigitalTwin.settings uses the PostGIS backend and RasterField models.
REQUIRED_EXTENSIONS = ["postgis", "postgis_raster"]
# Listed in the README's database setup; nothing breaks at startup without them.
OPTIONAL_EXTENSIONS = ["postgis_topology", "postgis_sfcgal", "pgrouting"]

# PostgreSQL version recommended for a new install (PostGIS bundles exist for it).
RECOMMENDED_PG = 17

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"


def _say(kind, text):
    print(f"[{kind}] {text}")


def _steps(lines):
    for line in lines:
        print(f"    {line}")
    print()


# -- installation detection ---------------------------------------------------

def _postgres_binaries():
    """Paths of psql found on PATH or in the default install folders."""
    found = []
    on_path = shutil.which("psql")
    if on_path:
        found.append(on_path)
    if IS_WINDOWS:
        found += sorted(glob.glob(r"C:\Program Files\PostgreSQL\*\bin\psql.exe"))
    elif IS_MAC:
        found += sorted(glob.glob("/opt/homebrew/opt/postgresql@*/bin/psql"))
        found += sorted(glob.glob("/Applications/Postgres.app/Contents/Versions/*/bin/psql"))
    else:
        found += sorted(glob.glob("/usr/lib/postgresql/*/bin/psql"))
    return list(dict.fromkeys(found))


def _windows_services():
    """Names of installed PostgreSQL Windows services, e.g. 'postgresql-x64-17'."""
    if not IS_WINDOWS:
        return []
    try:
        out = subprocess.run(
            ["sc", "query", "type=", "service", "state=", "all"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [
        line.split(":", 1)[1].strip()
        for line in out.splitlines()
        if line.strip().startswith("SERVICE_NAME") and "postgres" in line.lower()
    ]


# -- instructions -------------------------------------------------------------

def _install_postgres_help():
    _say("FIX", "Install PostgreSQL, then PostGIS, then create the database (README > Installation):")
    if IS_WINDOWS:
        _steps([
            "1. Install PostgreSQL with winget (ships with Windows 10/11 as 'App Installer'):",
            f"     winget install --id PostgreSQL.PostgreSQL.{RECOMMENDED_PG} -e",
            "   The installer asks for a password for the 'postgres' superuser; keep it.",
            "2. Install PostGIS (not on winget): open Stack Builder, which comes with the installer",
            f"     \"C:\\Program Files\\PostgreSQL\\{RECOMMENDED_PG}\\bin\\stackbuilder.exe\"",
            f"   choose your PostgreSQL {RECOMMENDED_PG} server > Spatial Extensions > PostGIS 3.x Bundle.",
            f"   Or use the OSGeo installer: https://download.osgeo.org/postgis/windows/pg{RECOMMENDED_PG}/",
            "3. Create the database, user and extensions with the SQL in the README,",
            "   and set DATABASE_* in .env.",
        ])
    elif IS_MAC:
        _steps([
            f"1. brew install postgresql@{RECOMMENDED_PG} postgis",
            f"2. brew services start postgresql@{RECOMMENDED_PG}",
            "3. Create the database, user and extensions with the SQL in the README.",
        ])
    else:
        _steps([
            f"1. sudo apt install postgresql-{RECOMMENDED_PG} postgresql-{RECOMMENDED_PG}-postgis-3",
            "   (PGDG repository: https://www.postgresql.org/download/linux/)",
            "2. Create the database, user and extensions with the SQL in the README.",
        ])


def _install_postgis_help(major):
    _say("FIX", f"Install PostGIS for PostgreSQL {major} on the database server:")
    if IS_WINDOWS:
        _steps([
            "PostGIS is not on winget. Open Stack Builder (Start menu > PostgreSQL > Application Stack Builder):",
            f"  \"C:\\Program Files\\PostgreSQL\\{major}\\bin\\stackbuilder.exe\"",
            f"choose your PostgreSQL {major} server > Spatial Extensions > PostGIS 3.x Bundle.",
            f"Or use the OSGeo installer: https://download.osgeo.org/postgis/windows/pg{major}/",
        ])
    elif IS_MAC:
        _steps(["brew install postgis   (or use Postgres.app, which includes PostGIS)"])
    else:
        _steps([f"sudo apt install postgresql-{major}-postgis-3"])


def _create_extensions_help(missing, db):
    _say("FIX", f"Create the extension(s) in database '{db}' as a superuser (e.g. postgres), with psql or pgAdmin:")
    _steps([f"\\c {db}"] + [f"CREATE EXTENSION IF NOT EXISTS {ext};" for ext in missing])


# -- checks ---------------------------------------------------------------------

def _connect(settings):
    try:
        import psycopg2 as driver
    except ImportError:
        import psycopg as driver
    kwargs = {k: v for k, v in settings.items() if v}
    return driver.connect(connect_timeout=5, **kwargs)


def _diagnose_connection_error(message, settings):
    text = message.lower()
    if "password authentication failed" in text or ("role" in text and "does not exist" in text):
        _say("ERROR", f"PostgreSQL rejected user '{settings['user']}': {message.strip()}")
        _say("FIX", "Check DATABASE_USER / DATABASE_PASSWORD in .env, or create the user (README > Installation).")
        return
    if "database" in text and "does not exist" in text:
        _say("ERROR", f"Database '{settings['dbname']}' does not exist.")
        _say("FIX", "Create it with the SQL in the README (CREATE DATABASE ...; then the extensions).")
        return

    # Not reachable: is PostgreSQL installed at all?
    _say("ERROR", f"Cannot reach PostgreSQL at {settings['host'] or 'localhost'}:{settings['port'] or 5432}.")
    print(f"    {message.strip().splitlines()[0]}\n")
    binaries, services = _postgres_binaries(), _windows_services()
    if not binaries and not services:
        _say("INFO", "PostgreSQL does not seem to be installed on this machine.")
        _install_postgres_help()
        return
    _say("INFO", "PostgreSQL is installed (" + ", ".join(services or binaries) + ") but not accepting connections.")
    if services:
        _say("FIX", "Start the service (as administrator), or via services.msc:")
        _steps([f"net start {services[-1]}"])
    elif IS_MAC:
        _say("FIX", f"brew services start postgresql@{RECOMMENDED_PG}")
    else:
        _say("FIX", "sudo systemctl start postgresql")
    _say("INFO", "If it runs on another host or port, set DATABASE_HOST / DATABASE_PORT in .env.")


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    settings = {
        "dbname": os.environ.get("DATABASE_NAME"),
        "user": os.environ.get("DATABASE_USER"),
        "password": os.environ.get("DATABASE_PASSWORD"),
        "host": os.environ.get("DATABASE_HOST"),
        "port": os.environ.get("DATABASE_PORT"),
    }
    if not settings["dbname"]:
        _say("ERROR", "DATABASE_NAME is not set. Create a .env file in the project root (README > Installation).")
        return 1

    try:
        conn = _connect(settings)
    except ImportError:
        _say("ERROR", "No PostgreSQL driver (psycopg2/psycopg). Run: pip install -r requirements.txt")
        return 1
    except Exception as exc:   # the driver's OperationalError; its message decides the advice
        _diagnose_connection_error(str(exc), settings)
        return 1

    with conn, conn.cursor() as cur:
        cur.execute("SHOW server_version_num")
        major = int(cur.fetchone()[0]) // 10000
        cur.execute("SELECT name FROM pg_available_extensions")
        available = {row[0] for row in cur.fetchall()}
        cur.execute("SELECT extname FROM pg_extension")
        created = {row[0] for row in cur.fetchall()}
    conn.close()

    _say("OK", f"PostgreSQL {major} reachable, database '{settings['dbname']}'.")
    ok = True

    unavailable = [e for e in REQUIRED_EXTENSIONS if e not in available]
    if unavailable:
        _say("ERROR", f"PostGIS is not installed on the server (missing: {', '.join(unavailable)}).")
        _install_postgis_help(major)
        _create_extensions_help(unavailable, settings["dbname"])
        ok = False

    not_created = [e for e in REQUIRED_EXTENSIONS if e in available and e not in created]
    if not_created:
        _say("ERROR", f"Extension(s) not created in '{settings['dbname']}': {', '.join(not_created)}.")
        _create_extensions_help(not_created, settings["dbname"])
        ok = False

    optional = [e for e in OPTIONAL_EXTENSIONS if e not in created]
    if optional:
        _say("WARN", f"Optional extension(s) not created: {', '.join(optional)} (README lists them).")
        missing_on_server = [e for e in optional if e not in available]
        if missing_on_server:
            print(f"    Not installed on the server: {', '.join(missing_on_server)} "
                  "(part of the PostGIS bundle; pgrouting is a separate Stack Builder option).")
        creatable = [e for e in optional if e in available]
        if creatable:
            _create_extensions_help(creatable, settings["dbname"])

    if ok:
        _say("OK", "PostGIS extensions present: " + ", ".join(e for e in REQUIRED_EXTENSIONS) + ".")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
