@echo off
rem Everything runs through uv run: it uses .venv without activating it and syncs it
rem with uv.lock first. Check PostgreSQL + PostGIS first (tools\check_postgres.py
rem prints how to fix what is missing); this also does the sync once, before the servers start.
uv run python tools\check_postgres.py
if errorlevel 1 (
    echo.
    echo Fix the problem above, then run start.bat again.
    pause
    exit /b 1
)
start "Django" cmd /k "uv run python manage.py runserver 8000"
start "TiTiler" cmd /k "uv run uvicorn tiler:app --port 8001 --reload"
