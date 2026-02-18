@echo off
start "Django" cmd /k ".venv\Scripts\Activate && uv run manage.py runserver 8000"
start "TiTiler" cmd /k ".venv\Scripts\Activate && uvicorn tiler:app --port 8001 --reload"