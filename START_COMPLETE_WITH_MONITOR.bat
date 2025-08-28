@echo off
echo ================================================================================
echo  QUANTUM TRADER v2.1 - SISTEMA COMPLETO COM MONITOR
echo ================================================================================
echo.
echo Este script iniciara:
echo  1. Sistema de Trading (OCO + Position Monitor)
echo  2. Monitor Visual Integrado (em nova janela)
echo.
echo Pressione qualquer tecla para continuar...
pause >nul

echo.
echo [1/2] Iniciando Monitor Visual...
start "QuantumTrader Monitor" cmd /k python core/monitor_visual_integrated.py

echo [2/2] Aguardando 3 segundos...
timeout /t 3 /nobreak >nul

echo.
echo [2/2] Iniciando Sistema de Trading...
echo.
python START_SYSTEM_COMPLETE_OCO_EVENTS.py

echo.
echo Sistema encerrado.
pause