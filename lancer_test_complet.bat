@echo off
title Smart Door Camera - TEST COMPLET DU SYSTEME
cls
echo ======================================================================
echo           SMART DOOR CAMERA - SCENARIO DE TEST COMPLET (E2E)
echo ======================================================================
echo.
echo Ce test va valider les 3 piliers essentiels :
echo   1. L'Intelligence Artificielle Locale (Reconnaissance + Anti-Spoof)
echo   2. L'Actionneur IoT (Ouverture automatique porte pour personne connue)
echo   3. La Simulation 3D et les Notifications Mobile / Web
echo.
echo ======================================================================
echo.

echo [ETAPE 1/4] Validation des Tests Unitaires Pytest...
python -m pytest edge/tests -v
if %errorlevel% neq 0 (
    echo [ERREUR] Les tests unitaires ont echoue.
    pause
    exit /b %errorlevel%
)
echo [OK] Tests unitaires valides a 100%%.
echo.

echo [ETAPE 2/4] Enregistrement d'un visage autorise ("Alice")...
python -m edge.main enroll --name "Alice" --source video.mp4
echo [OK] Alice est enregistree dans la base locale SQLite.
echo.

echo [ETAPE 3/4] Verification du statut du stockage et de l'Outbox...
python -m edge.main summary
echo.

echo [ETAPE 4/4] Lancement de la Simulation 3D et Surveillance en direct...
echo Ouverture de la simulation 3D dans votre navigateur...
start "" "sim\index.html"
echo Ouverture du Dashboard Web SSE...
start "" "web\index.html"

echo.
echo ======================================================================
echo   TEST COMPLET REUSSI !
echo.
echo   Dans la page 3D qui vient de s'ouvrir :
echo   - Cliquez sur "Known Person"   : Alice est reconnue -> La porte S'OUVRE !
echo   - Cliquez sur "Stranger Lingers": Inconnu -> La porte RESTE FERMEE + ALARME !
echo   - Cliquez sur "Delivery Courier": Colis detecte -> Notification generee !
echo ======================================================================
pause
