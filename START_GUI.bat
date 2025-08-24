@echo off
echo ===============================================
echo   QuantumTrader v2.0 - Interface Grafica
echo ===============================================
echo.

REM Ativar ambiente virtual se existir
if exist venv\Scripts\activate.bat (
    echo [*] Ativando ambiente virtual...
    call venv\Scripts\activate.bat
)

REM Iniciar GUI
echo [*] Iniciando interface grafica...
python gui_trading_system.py

pause