@echo off
echo ================================================================================
echo                     QUANTUM TRADER PRODUCTION SYSTEM
echo                   65 Features + 4 HMARL Agents + ML Models
echo ================================================================================
echo.
echo [INFO] Sistema de Trading Algoritmico Profissional
echo [INFO] Performance: Latencia ^< 2ms, 600+ features/seg
echo.
echo IMPORTANTE:
echo - Monitor Enhanced abrira em nova janela
echo - Profit Chart deve estar conectado
echo - Verifique .env.production antes de iniciar
echo.
pause

REM Verificar ambiente virtual
if exist .venv\Scripts\activate (
    echo [OK] Ambiente virtual encontrado
    call .venv\Scripts\activate
) else (
    echo [ERRO] Ambiente virtual nao encontrado!
    echo Execute: python -m venv .venv
    pause
    exit /b 1
)

REM Verificar pastas essenciais
if not exist models mkdir models
if not exist logs mkdir logs
if not exist data mkdir data
if not exist backups mkdir backups

REM Iniciar sistema
echo.
echo [INICIANDO] Sistema de producao...
python core\start_production_65features.py

echo.
echo [INFO] Sistema finalizado
pause