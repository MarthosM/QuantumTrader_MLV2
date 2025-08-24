@echo off
echo ============================================================
echo         REINICIANDO SISTEMA COM TRADING REAL
echo ============================================================
echo.

REM Parar sistema atual
echo [1/3] Parando sistema atual...
python stop_production.py 2>nul
timeout /t 2 /nobreak >nul

REM Verificar configuracao
echo [2/3] Verificando configuracao...
echo.
echo ATENCAO: Trading REAL esta ATIVADO!
echo ========================================
echo.
echo Configuracoes atuais:
findstr "ENABLE_TRADING" .env.production
echo.
findstr "TRADING_SYMBOL" .env.production
echo.
findstr "DEFAULT_STOP_POINTS" .env.production
findstr "DEFAULT_TAKE_POINTS" .env.production
echo.
echo ========================================
echo.

REM Confirmar com usuario
set /p confirm="CONFIRMA iniciar sistema com TRADING REAL? (S/N): "
if /i "%confirm%" neq "S" (
    echo.
    echo Operacao cancelada pelo usuario.
    echo.
    pause
    exit /b
)

echo.
echo [3/3] Iniciando sistema com TRADING REAL...
echo.

REM Iniciar sistema com trading real
start "QuantumTrader - TRADING REAL" python START_HYBRID_COMPLETE.py

echo.
echo ============================================================
echo      SISTEMA INICIADO COM TRADING REAL ATIVADO!
echo ============================================================
echo.
echo IMPORTANTE:
echo - As ordens serao enviadas REALMENTE ao mercado
echo - Verifique o monitor para acompanhar as operacoes
echo - Use stop_production.py para parar o sistema
echo.
echo Para monitorar:
echo   python core/monitor_console_enhanced.py
echo.
pause