#!/usr/bin/env python3
"""
Iniciador do Sistema Completo com Regime + Monitor
Abre o sistema principal e o monitor em janelas separadas
"""

import subprocess
import sys
import time
import os
from pathlib import Path

def main():
    """Inicia sistema e monitor"""
    
    print("=" * 60)
    print("QUANTUM TRADER - REGIME-BASED SYSTEM")
    print("=" * 60)
    print()
    print("Iniciando componentes...")
    print()
    
    # Diretório base
    base_dir = Path(__file__).parent
    
    # 1. Iniciar o sistema principal
    print("1. Iniciando sistema de trading...")
    if os.name == 'nt':  # Windows
        system_process = subprocess.Popen(
            ['start', 'cmd', '/k', 'python', 'START_SYSTEM_COMPLETE_OCO_EVENTS.py'],
            shell=True,
            cwd=base_dir
        )
    else:  # Linux/Mac
        system_process = subprocess.Popen(
            ['gnome-terminal', '--', 'python3', 'START_SYSTEM_COMPLETE_OCO_EVENTS.py'],
            cwd=base_dir
        )
    
    # Aguardar sistema inicializar
    print("   Aguardando inicialização...")
    time.sleep(5)
    
    # 2. Iniciar o monitor
    print("2. Iniciando monitor do regime...")
    if os.name == 'nt':  # Windows
        monitor_process = subprocess.Popen(
            ['start', 'cmd', '/k', 'python', 'core/monitor_regime_enhanced.py'],
            shell=True,
            cwd=base_dir
        )
    else:  # Linux/Mac
        monitor_process = subprocess.Popen(
            ['gnome-terminal', '--', 'python3', 'core/monitor_regime_enhanced.py'],
            cwd=base_dir
        )
    
    print()
    print("✅ Sistema iniciado com sucesso!")
    print()
    print("Componentes rodando:")
    print("  - Sistema de Trading (janela 1)")
    print("  - Monitor de Regime (janela 2)")
    print()
    print("Configuração:")
    print("  - Detecção de Regime: ATIVO")
    print("  - Estratégias: Tendência (RR 1.5:1) | Lateral (RR 1.0:1)")
    print("  - HMARL: Timing de entrada")
    print()
    print("Para parar o sistema, feche as janelas ou pressione Ctrl+C")
    print()
    
    try:
        # Manter script rodando
        input("Pressione Enter para encerrar todos os componentes...")
    except KeyboardInterrupt:
        pass
    
    print("\nEncerrando sistema...")
    
    # Tentar encerrar processos
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], capture_output=True)
        else:
            system_process.terminate()
            monitor_process.terminate()
    except:
        pass
    
    print("Sistema encerrado.")

if __name__ == "__main__":
    main()