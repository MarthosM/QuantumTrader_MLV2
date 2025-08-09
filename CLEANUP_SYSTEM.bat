@echo off
REM QuantumTrader System Cleanup Utility
REM Run weekly to maintain system performance

echo ========================================
echo  QuantumTrader System Cleanup
echo ========================================
echo.

REM Check if virtual environment is activated
if "%VIRTUAL_ENV%"=="" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

echo Running cleanup in DRY RUN mode first...
echo.
python cleanup.py --dry-run

echo.
echo ========================================
set /p confirm="Proceed with actual cleanup? (Y/N): "

if /i "%confirm%"=="Y" (
    echo.
    echo Starting actual cleanup...
    python cleanup.py
    echo.
    echo Cleanup completed!
) else (
    echo Cleanup cancelled.
)

echo.
pause