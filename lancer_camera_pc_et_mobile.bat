@echo off
title Sentinel Home - Live PC Camera & Mobile Server (Port 8085)
echo ====================================================================
echo   SENTINEL HOME - LIVE PC WEBCAM DOOR SERVER
echo   Android APK / Phone URL : http://172.16.19.206:8085
echo   Web Dashboard           : http://localhost:8090/web/index.html
echo   3D Full-House Twin      : http://localhost:8090/sim/index.html
echo ====================================================================
start /b python -m http.server 8090 --bind 0.0.0.0
python -m uvicorn pc_door_server:app --host 0.0.0.0 --port 8085
pause
