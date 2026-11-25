@echo off
title KiddySentinel - Serveur Central FastAPI (2 IRM)
echo ========================================================
echo   Lancement du Serveur Central FastAPI (KiddySentinel)
echo   Session 2026 / Specialite 2 IRM - Yassine Mezghanni
echo ========================================================
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
