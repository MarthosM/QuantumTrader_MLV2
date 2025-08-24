@echo off
echo ============================================
echo CORRIGINDO PROBLEMA DE PORTA 5559
echo ============================================
echo.

REM Encontrar e matar processo na porta 5559
echo Procurando processo na porta 5559...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5559 ^| findstr LISTENING') do (
    echo Matando processo PID: %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo Verificando outras portas ZMQ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5555 ^| findstr LISTENING') do (
    echo Matando processo na porta 5555 PID: %%a
    taskkill /F /PID %%a 2>nul
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5556 ^| findstr LISTENING') do (
    echo Matando processo na porta 5556 PID: %%a
    taskkill /F /PID %%a 2>nul
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5557 ^| findstr LISTENING') do (
    echo Matando processo na porta 5557 PID: %%a
    taskkill /F /PID %%a 2>nul
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5558 ^| findstr LISTENING') do (
    echo Matando processo na porta 5558 PID: %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo Aguardando 3 segundos...
timeout /t 3 /nobreak >nul

echo.
echo Portas liberadas! Agora execute START_SYSTEM.bat
echo.
pause