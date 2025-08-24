@echo off
echo Iniciando Monitor do QuantumTrader...
start "QuantumTrader Monitor" cmd /k python core/monitor_console_enhanced.py
echo Monitor iniciado em nova janela!