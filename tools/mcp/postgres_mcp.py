"""Launch a read-only Postgres MCP server on the database of .env.

Used by .mcp.json so no credentials are committed: the connection string is
built here from DATABASE_NAME/USER/PASSWORD/HOST/PORT (the same keys Django
reads) and passed to the server as its connection argument.

Server: @modelcontextprotocol/server-postgres (npx), pinned. Every query runs
in a READ ONLY transaction; it exposes a `query` tool and each table's schema
as a resource. (Postgres MCP Pro / crystaldba was tried first: on Windows +
Python 3.13 its pinned pglast does not resolve.) Point .env at a development
database, never production.
"""
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
SERVER_VERSION = "0.6.2"


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:  # .venv not synced: fall back to the process environment
        pass

    env = os.environ.copy()
    if not env.get("DATABASE_URI"):
        user = quote(env.get("DATABASE_USER", ""), safe="")
        password = quote(env.get("DATABASE_PASSWORD", ""), safe="")
        host = env.get("DATABASE_HOST") or "localhost"
        port = env.get("DATABASE_PORT") or "5432"
        name = env.get("DATABASE_NAME", "")
        if not (user and name):
            print("postgres_mcp: DATABASE_USER/DATABASE_NAME missing in .env", file=sys.stderr)
            return 1
        env["DATABASE_URI"] = f"postgresql://{user}:{password}@{host}:{port}/{name}"

    npx = "npx.cmd" if os.name == "nt" else "npx"
    cmd = [npx, "-y", f"@modelcontextprotocol/server-postgres@{SERVER_VERSION}", env["DATABASE_URI"]]
    return subprocess.call(cmd, env=env, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
