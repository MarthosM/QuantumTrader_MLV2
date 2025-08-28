@echo off
cls
echo ================================================================================
echo  QUANTUM TRADER v3.0 - SISTEMA SEGURO COM MONITOR
echo ================================================================================
echo.
echo  ML com dados reais + HMARL + OCO + Monitor
echo  Sistema com protecao contra crashes e auto-recuperacao
echo.
echo ================================================================================
echo.

:: Verificar horário do mercado
for /f "tokens=1-2 delims=:" %%a in ("%time%") do (
    set hour=%%a
    set min=%%b
)

:: Remover espaços
set hour=%hour: =%

:: Converter para número
set /a hour_num=%hour%

:: Verificar se mercado está aberto (9-18)
if %hour_num% GEQ 9 (
    if %hour_num% LSS 18 (
        echo [OK] Mercado ABERTO - Horario: %time%
    ) else (
        echo [AVISO] Mercado FECHADO - Horario: %time%
        echo         Mercado opera das 09:00 as 18:00
        echo         Sistema iniciara em modo de espera...
    )
) else (
    echo [AVISO] Mercado FECHADO - Horario: %time%
    echo         Mercado opera das 09:00 as 18:00
    echo         Sistema iniciara em modo de espera...
)

echo.
echo Iniciando em 3 segundos...
timeout /t 3 /nobreak >nul

echo.
echo [1/2] Iniciando Monitor Visual...
start "Monitor QuantumTrader" cmd /k python core/monitor_console_enhanced.py

echo [1/2] Aguardando monitor inicializar...
timeout /t 2 /nobreak >nul

echo.
echo [2/2] Iniciando Sistema de Trading Seguro...
echo.

:: Executar sistema seguro com proteção
python START_SYSTEM_SAFE.py

if errorlevel 1 (
    echo.
    echo ================================================================================
    echo  [ERRO] Sistema encerrou com erro
    echo ================================================================================
    echo.
    echo Possiveis causas:
    echo  1. Erro de conexao com ProfitChart
    echo  2. Callbacks da DLL com problema
    echo  3. Mercado fechado
    echo.
    echo Solucoes:
    echo  1. Verifique se o ProfitChart esta aberto e conectado
    echo  2. Confirme credenciais em .env.production
    echo  3. Tente novamente em horario de mercado
    echo.
) else (
    echo.
    echo ================================================================================
    echo  Sistema encerrado normalmente
    echo ================================================================================
)

echo.
echo Pressione qualquer tecla para fechar...
pause >nul