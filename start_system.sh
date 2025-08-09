#!/bin/bash

echo "================================================================================"
echo "                    QUANTUM TRADER PRODUCTION SYSTEM"
echo "                  65 Features + 4 HMARL Agents + ML Models"
echo "================================================================================"
echo ""
echo "[INFO] Sistema de Trading Algorítmico Profissional"
echo "[INFO] Performance: Latência < 2ms, 600+ features/seg"
echo ""
echo "IMPORTANTE:"
echo "- Monitor Enhanced abrirá em nova janela"
echo "- Profit Chart deve estar conectado"
echo "- Verifique .env.production antes de iniciar"
echo ""
read -p "Pressione Enter para continuar..."

# Verificar ambiente virtual
if [ -d ".venv" ]; then
    echo "[OK] Ambiente virtual encontrado"
    source .venv/bin/activate
else
    echo "[ERRO] Ambiente virtual não encontrado!"
    echo "Execute: python3 -m venv .venv"
    exit 1
fi

# Verificar e criar pastas necessárias
for dir in models logs data backups; do
    if [ ! -d "$dir" ]; then
        echo "[INFO] Criando pasta $dir/"
        mkdir -p "$dir"
    fi
done

# Iniciar sistema
echo ""
echo "[INICIANDO] Sistema de produção..."

# Tentar abrir monitor em novo terminal
if command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- python3 core/monitor_console_enhanced.py &
elif command -v xterm &> /dev/null; then
    xterm -e python3 core/monitor_console_enhanced.py &
else
    echo "[AVISO] Execute 'python3 core/monitor_console_enhanced.py' em outro terminal"
fi

# Iniciar sistema principal
python3 core/start_production_65features.py

echo ""
echo "[INFO] Sistema finalizado"
read -p "Pressione Enter para sair..."