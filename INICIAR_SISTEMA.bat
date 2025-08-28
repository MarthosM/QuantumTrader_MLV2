@echo off
echo ================================================================================
echo  QUANTUM TRADER V3 - SISTEMA DE PRODUCAO
echo ================================================================================
echo.
echo Iniciando sistema de trading...
echo.

REM Ativar ambiente Python se existir
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

REM Iniciar sistema com monitor
python START_PRODUCTION_WITH_MONITOR.py

pause