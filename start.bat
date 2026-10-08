@echo off
rem Check PostgreSQL + PostGIS first (tools\check_postgres.py prints how to fix what is missing)
".venv\Scripts\python.exe" tools\check_postgres.py
if errorlevel 1 (
    echo.
    echo Fix the database problem above, then run start.bat again.
    pause
    exit /b 1
)
start "Django" cmd /k ".venv\Scripts\Activate && uv run manage.py runserver 8000"
start "TiTiler" cmd /k ".venv\Scripts\Activate && uvicorn tiler:app --port 8001 --reload"
