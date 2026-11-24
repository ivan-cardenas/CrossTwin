@echo off
rem Everything runs through uv run: it uses .venv without activating it and syncs it
rem with uv.lock first. Check PostgreSQL + PostGIS first (tools\check_postgres.py
rem prints how to fix what is missing); this also does the sync once, before the servers start.
rem --inexact: the sync adds what uv.lock needs but keeps packages it does not list, so
rem an installed optional extra (uv sync --inexact --extra solweig: torch, solweig-gpu) survives a
rem restart. A plain uv run would remove it and the thermal comfort runs would answer
rem "SOLWEIG is not installed".
uv run --inexact python tools\check_postgres.py
if errorlevel 1 (
    echo.
    echo Fix the problem above, then run start.bat again.
    pause
    exit /b 1
)
start "Django" cmd /k "uv run --inexact python manage.py runserver 8000"
start "TiTiler" cmd /k "uv run --inexact uvicorn tiler:app --port 8001 --reload"
