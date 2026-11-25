@echo off
title Sentinel Home - Live PC Server + Cloudflare Quick Tunnel
echo ====================================================================
echo   SENTINEL HOME - CLOUDFLARE QUICK TUNNEL (RAPIDE, GRATUIT, SANS VPS)
echo   1. Demarrage du serveur unifie (Webcam PC + Web + 3D + APK)
echo   2. Ouverture du tunnel Cloudflare HTTPS rapide
echo ====================================================================
start /b python -m uvicorn pc_door_server:app --host 0.0.0.0 --port 8085
timeout /t 3 /nobreak >nul
echo.
echo Copiez l'URL https://xxxxx.trycloudflare.com ci-dessous dans votre telephone et APK !
echo.
.\cloudflared.exe tunnel --url http://127.0.0.1:8085
pause
