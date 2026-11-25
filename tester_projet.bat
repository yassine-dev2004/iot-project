@echo off
title Smart Door Camera - Test & Verification Launcher
cls
echo ======================================================================
echo           SMART DOOR CAMERA - VERIFICATION & TEST MENU
echo ======================================================================
echo.
echo   1. Lancer la Simulation 3D & Digital Twin (Three.js)
echo   2. Lancer le Tableau de Bord Web (SSE Dashboard)
echo   3. Executer la suite complete de Tests Unitaires (Pytest)
echo   4. Lancer la Surveillance Edge sur Video Simulée (CLI Edge)
echo   5. Enregistrer un visage localement (CLI Enroll "Alice")
echo   6. Envoyer des faux evenements au Backend (Seed Events)
echo   7. Lancer le Simulateur MQTT ESP32 IoT
echo   8. Quitter
echo.
echo ======================================================================
set /p choice="Choisissez une option [1-8]: "

if "%choice%"=="1" (
    echo Ouverture de la simulation 3D dans votre navigateur...
    start "" "sim\index.html"
    goto end
)
if "%choice%"=="2" (
    echo Ouverture du Dashboard Web...
    start "" "web\index.html"
    goto end
)
if "%choice%"=="3" (
    echo.
    echo Execution des tests pytest...
    python -m pytest edge/tests -v
    pause
    goto end
)
if "%choice%"=="4" (
    echo.
    echo Demarrage du pipeline Edge sur video simulee...
    python -m edge.main run --source video.mp4
    pause
    goto end
)
if "%choice%"=="5" (
    echo.
    echo Enregistrement de "Alice" via source video...
    python -m edge.main enroll --name "Alice" --source video.mp4
    pause
    goto end
)
if "%choice%"=="6" (
    echo.
    echo Generation d'evenements et snapshots vers le backend...
    python seed_events.py
    pause
    goto end
)
if "%choice%"=="7" (
    echo.
    echo Lancement du simulateur IoT ESP32 (PIR + Sonnette)...
    python iot/esp32_simulator.py
    pause
    goto end
)
if "%choice%"=="8" exit

:end
