@echo off
title QuantumTrader Project Board
color 0A

echo ===============================================
echo        QUANTUMTRADER PROJECT BOARD
echo ===============================================
echo.
echo Select an option:
echo.
echo 1. View Project Board Status
echo 2. View Detailed Status
echo 3. View Critical Items Only
echo 4. View Next Steps
echo 5. Start Project Board Server
echo 6. Start Board Integration Monitor
echo 7. Export Board to JSON
echo 8. Exit
echo.

set /p choice="Enter your choice (1-8): "

if "%choice%"=="1" (
    cls
    python view_project_board.py
    pause
    goto :eof
)

if "%choice%"=="2" (
    cls
    python view_project_board.py --detailed
    pause
    goto :eof
)

if "%choice%"=="3" (
    cls
    python view_project_board.py --section critical
    pause
    goto :eof
)

if "%choice%"=="4" (
    cls
    python view_project_board.py --section next
    pause
    goto :eof
)

if "%choice%"=="5" (
    cls
    echo Starting Project Board MCP Server...
    python start_project_board.py --mode server
    pause
    goto :eof
)

if "%choice%"=="6" (
    cls
    echo Starting Board Integration Monitor...
    python start_project_board.py --mode integration
    pause
    goto :eof
)

if "%choice%"=="7" (
    cls
    set filename=board_export_%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%.json
    set filename=%filename: =0%
    python view_project_board.py --export %filename%
    echo.
    echo Board exported to: %filename%
    pause
    goto :eof
)

if "%choice%"=="8" (
    exit
)

echo Invalid choice. Please try again.
pause
PROJECT_BOARD.bat