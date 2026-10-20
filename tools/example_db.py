"""Package the current database as example data, or load such a package.

    python tools/example_db.py dump [-o example/crosstwin_example_data.zip]
    python tools/example_db.py load [example/crosstwin_example_data.zip]

Both default to example/crosstwin_example_data.zip.

`dump` writes one zip with:
  - crosstwin.dump  pg_dump custom format, no owners/privileges, without the
                    rows of PRIVATE_TABLES (users, sessions, edit backups);
  - cogs/...        every COG file a raster row points to. Some rasters live
                    only as a COG (e.g. a DSM loaded from a GeoTIFF has no
                    raster in Postgres), so export_cogs cannot rebuild them;
  - manifest.json   CrossTwin version, PostgreSQL version, date, COG paths.

`load` restores the dump into the (empty) database of .env, copies the COGs
into this checkout's cogs/ and rewrites each row's absolute `cog_path` to it.
Create the database and the postgis/postgis_raster extensions first
(README > Installation); run `migrate` and `createsuperuser` afterwards.

Uses the DATABASE_* settings of .env, like tools/check_postgres.py, and the
pg_dump/pg_restore found on PATH or in the default PostgreSQL install folders.
"""
import argparse
import datetime
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_PACKAGE = ROOT / "example" / "crosstwin_example_data.zip"
DUMP_NAME = "crosstwin.dump"
MANIFEST_NAME = "manifest.json"

# Schema is kept, rows are not: password hashes, live sessions, the map
# editor's restore point (and the tables that reference auth_user).
PRIVATE_TABLES = [
    "auth_user",
    "auth_user_groups",
    "auth_user_user_permissions",
    "django_session",
    "django_admin_log",
    '"mainMap_editbackup"',
    '"mainMap_editbackuprow"',
]


def _say(kind, text):
    print(f"[{kind}] {text}")


def _db_settings():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    settings = {
        "dbname": os.environ.get("DATABASE_NAME"),
        "user": os.environ.get("DATABASE_USER"),
        "password": os.environ.get("DATABASE_PASSWORD"),
        "host": os.environ.get("DATABASE_HOST") or "localhost",
        "port": os.environ.get("DATABASE_PORT") or "5432",
    }
    if not settings["dbname"]:
        sys.exit("[ERROR] DATABASE_NAME is not set. Create .env first (README > Installation).")
    return settings


def _pg_tool(name):
    """Path of pg_dump/pg_restore: PATH first, then the newest default install."""
    on_path = shutil.which(name)
    if on_path:
        return on_path
    exe = name + (".exe" if platform.system() == "Windows" else "")
    patterns = [
        rf"C:\Program Files\PostgreSQL\*\bin\{exe}",
        f"/opt/homebrew/opt/postgresql@*/bin/{exe}",
        f"/Applications/Postgres.app/Contents/Versions/*/bin/{exe}",
        f"/usr/lib/postgresql/*/bin/{exe}",
    ]
    found = [p for pattern in patterns for p in glob.glob(pattern)]
    if not found:
        sys.exit(f"[ERROR] {name} not found. Add PostgreSQL's bin folder to PATH.")
    return sorted(found, key=lambda p: [int(n) for n in re.findall(r"\d+", p)])[-1]


def _run(cmd, settings, **kwargs):
    env = {**os.environ, "PGPASSWORD": settings["password"] or ""}
    return subprocess.run(cmd, env=env, **kwargs)


def _connection_args(settings):
    return ["-h", settings["host"], "-p", settings["port"],
            "-U", settings["user"], "-d", settings["dbname"]]


def _django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "DigitalTwin.settings")
    import django
    django.setup()


def _raster_models_with_cogs():
    from core.utils import RASTER_REGISTRY
    return [m for m in RASTER_REGISTRY.values()
            if "cog_path" in {f.name for f in m._meta.fields}]


def _relative_cog(path):
    """'C:/.../CrossTwin/cogs/physicalEnv/x.tif' -> 'physicalEnv/x.tif'."""
    parts = Path(path.replace("\\", "/")).parts
    return "/".join(parts[parts.index("cogs") + 1:]) if "cogs" in parts else None


# -- dump -----------------------------------------------------------------------

def dump(output):
    settings = _db_settings()
    _django()
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("SHOW server_version")
        server_version = cur.fetchone()[0]

    cogs = []
    for model in _raster_models_with_cogs():
        for path in model.objects.exclude(cog_path__isnull=True).exclude(cog_path="") \
                                 .values_list("cog_path", flat=True):
            relative = _relative_cog(path)
            if relative and (ROOT / "cogs" / relative).is_file():
                cogs.append(relative)
            else:
                _say("WARN", f"{model._meta.label}: COG {path} not found, not packaged.")

    with tempfile.TemporaryDirectory() as tmp:
        dump_path = Path(tmp) / DUMP_NAME
        cmd = [_pg_tool("pg_dump"), *_connection_args(settings),
               "-Fc", "--no-owner", "--no-privileges", "-f", str(dump_path)]
        cmd += [f"--exclude-table-data={table}" for table in PRIVATE_TABLES]
        _say("INFO", f"pg_dump of '{settings['dbname']}' (PostgreSQL {server_version}) ...")
        if _run(cmd, settings).returncode != 0:
            sys.exit("[ERROR] pg_dump failed (see above).")

        manifest = {
            "crosstwin_version": _crosstwin_version(),
            "postgresql_version": server_version,
            "created": datetime.date.today().isoformat(),
            "excluded_table_data": PRIVATE_TABLES,
            "cogs": sorted(set(cogs)),
        }
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(dump_path, DUMP_NAME)
            for relative in manifest["cogs"]:
                zf.write(ROOT / "cogs" / relative, f"cogs/{relative}")
            zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))

    size_mb = Path(output).stat().st_size / 1e6
    _say("OK", f"{output} ({size_mb:.1f} MB): database + {len(manifest['cogs'])} COG file(s).")
    _say("INFO", "Check the licences of the data inside before publishing it (README > Sharing your database as example data).")


def _crosstwin_version():
    match = re.search(r'^version:\s*"?([^"\n]+)"?', (ROOT / "CITATION.cff").read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else None


# -- load -----------------------------------------------------------------------

def load(package):
    settings = _db_settings()
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(package) as zf:
            zf.extractall(tmp)
        tmp = Path(tmp)
        manifest = json.loads((tmp / MANIFEST_NAME).read_text(encoding="utf-8"))
        _say("INFO", f"Package of CrossTwin {manifest.get('crosstwin_version')}, "
                     f"created {manifest.get('created')}, PostgreSQL {manifest.get('postgresql_version')}.")

        _check_target_db(settings)
        _restore(tmp / DUMP_NAME, settings)

        for relative in manifest["cogs"]:
            target = ROOT / "cogs" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp / "cogs" / relative, target)
        _say("OK", f"Copied {len(manifest['cogs'])} COG file(s) to {ROOT / 'cogs'}.")

    _rewrite_cog_paths()
    _say("OK", "Example data loaded. Next:")
    print("    python manage.py migrate          # applies migrations newer than the package")
    print("    python manage.py createsuperuser  # users are not part of the package")


def _check_target_db(settings):
    """The database must exist, have PostGIS and hold no CrossTwin tables yet."""
    import psycopg
    kwargs = {k: v for k, v in settings.items() if v}
    try:
        conn = psycopg.connect(connect_timeout=5, **kwargs)
    except psycopg.OperationalError as exc:
        sys.exit(f"[ERROR] {exc}\n        Run python tools/check_postgres.py for what to fix.")
    with conn, conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension")
        missing = {"postgis", "postgis_raster"} - {row[0] for row in cur.fetchall()}
        cur.execute("SELECT to_regclass('public.django_migrations') IS NOT NULL")
        has_tables = cur.fetchone()[0]
    if missing:
        sys.exit(f"[ERROR] Extension(s) missing in '{settings['dbname']}': {', '.join(sorted(missing))}. "
                 "Create them as superuser (README > Installation).")
    if has_tables:
        sys.exit(f"[ERROR] '{settings['dbname']}' already has CrossTwin tables. Load into an empty "
                 "database (DROP DATABASE / CREATE DATABASE, then the extensions).")


def _restore(dump_path, settings):
    """pg_restore without the extension entries: they exist already, and
    re-creating or commenting them needs superuser rights."""
    pg_restore = _pg_tool("pg_restore")
    toc = subprocess.run([pg_restore, "-l", str(dump_path)],
                         capture_output=True, text=True, check=True).stdout
    keep = [line for line in toc.splitlines() if " EXTENSION " not in line]
    list_path = dump_path.with_suffix(".list")
    list_path.write_text("\n".join(keep), encoding="utf-8")

    _say("INFO", f"pg_restore into '{settings['dbname']}' ...")
    cmd = [pg_restore, *_connection_args(settings), "--no-owner", "--no-privileges",
           "--exit-on-error", "-L", str(list_path), str(dump_path)]
    if _run(cmd, settings).returncode != 0:
        sys.exit("[ERROR] pg_restore failed (see above). The database may be half-filled: "
                 "drop and re-create it before trying again.")


def _rewrite_cog_paths():
    """Point every cog_path at this checkout's cogs/. update(), not save():
    a post_save on a raster model would export the COG all over again."""
    _django()
    from core.rasterOperations import COG_DIRECTORY
    base = COG_DIRECTORY.replace("\\", "/")
    for model in _raster_models_with_cogs():
        for pk, path in model.objects.exclude(cog_path__isnull=True).values_list("pk", "cog_path"):
            relative = _relative_cog(path or "")
            if relative:
                model.objects.filter(pk=pk).update(cog_path=f"{base}/{relative}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_dump = sub.add_parser("dump", help="package the database of .env + its COG files")
    p_dump.add_argument("-o", "--output", default=str(DEFAULT_PACKAGE))
    p_load = sub.add_parser("load", help="restore a package into the (empty) database of .env")
    p_load.add_argument("package", nargs="?", default=str(DEFAULT_PACKAGE))
    args = parser.parse_args()
    if args.command == "dump":
        dump(args.output)
    else:
        load(args.package)


if __name__ == "__main__":
    main()
