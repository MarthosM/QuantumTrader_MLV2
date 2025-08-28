#!/usr/bin/env python3
"""
INICIA SISTEMA DE PRODUÇÃO COM MONITOR VISUAL
Abre o sistema principal e o monitor em janelas separadas
"""

import os
import sys
import time
import subprocess
import threading
from pathlib import Path

def start_production_system():
    """Inicia o sistema principal de produção"""
    print("[1/2] Iniciando Sistema de Produção...")
    subprocess.Popen(
        [sys.executable, "START_SYSTEM_PRODUCTION_FINAL.py"],
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    )
    print("    [OK] Sistema de produção iniciado")

def start_monitor():
    """Inicia o monitor visual"""
    print("[2/2] Iniciando Monitor Visual...")
    time.sleep(3)  # Aguardar sistema iniciar
    
    monitor_path = Path("core/monitor_console_enhanced.py")
    if monitor_path.exists():
        subprocess.Popen(
            [sys.executable, str(monitor_path)],
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
        )
        print("    [OK] Monitor visual iniciado")
    else:
        print("    [AVISO] Monitor não encontrado, criando versão básica...")
        create_basic_monitor()

def create_basic_monitor():
    """Cria um monitor básico se o enhanced não existir"""
    monitor_code = '''"""
Monitor Básico do Sistema Quantum Trader
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

def clear_screen():
    """Limpa a tela do console"""
    os.system('cls' if os.name == 'nt' else 'clear')

def load_metrics():
    """Carrega métricas do sistema"""
    metrics_file = Path("metrics/current_metrics.json")
    if metrics_file.exists():
        try:
            with open(metrics_file, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def display_monitor():
    """Exibe o monitor"""
    while True:
        clear_screen()
        
        # Cabeçalho
        print("=" * 80)
        print(" QUANTUM TRADER V3 - MONITOR DO SISTEMA")
        print("=" * 80)
        print(f" Horário: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print("=" * 80)
        
        # Carregar métricas
        metrics = load_metrics()
        
        if metrics:
            # Status geral
            print("\\n[STATUS GERAL]")
            print(f"  Sistema: {'ATIVO' if metrics.get('running', False) else 'PARADO'}")
            print(f"  Símbolo: {metrics.get('symbol', 'WDOU25')}")
            print(f"  Trading: {metrics.get('trading_mode', 'SIMULADO')}")
            
            # Dados de mercado
            print("\\n[DADOS DE MERCADO]")
            print(f"  Último preço: {metrics.get('last_price', 0):.2f}")
            print(f"  Spread: {metrics.get('spread', 0):.2f}")
            print(f"  Book updates: {metrics.get('book_count', 0)}")
            print(f"  Ticks: {metrics.get('tick_count', 0)}")
            
            # Posição
            position = metrics.get('position', {})
            if position.get('has_position'):
                print("\\n[POSIÇÃO ABERTA]")
                print(f"  Side: {position.get('side', 'N/A')}")
                print(f"  Quantidade: {position.get('quantity', 0)}")
                print(f"  Entry: {position.get('entry_price', 0):.2f}")
                print(f"  P&L: R$ {position.get('current_pnl', 0):.2f}")
            else:
                print("\\n[POSIÇÃO]")
                print("  Sem posição aberta")
            
            # Estatísticas
            stats = metrics.get('stats', {})
            print("\\n[ESTATÍSTICAS DO DIA]")
            print(f"  Trades: {stats.get('trades_today', 0)}/{stats.get('max_trades', 10)}")
            print(f"  Wins: {stats.get('wins', 0)}")
            print(f"  Losses: {stats.get('losses', 0)}")
            print(f"  P&L Total: R$ {stats.get('total_pnl', 0):.2f}")
            print(f"  Sinais gerados: {stats.get('signals_generated', 0)}")
            
            # Último sinal
            last_signal = metrics.get('last_signal', {})
            if last_signal:
                print("\\n[ÚLTIMO SINAL]")
                print(f"  Tipo: {last_signal.get('type', 'N/A')}")
                print(f"  Confiança: {last_signal.get('confidence', 0)*100:.1f}%")
                print(f"  Horário: {last_signal.get('timestamp', 'N/A')}")
        else:
            print("\\n[AGUARDANDO DADOS...]")
            print("  Sistema iniciando ou sem conexão com métricas")
        
        print("\\n" + "=" * 80)
        print(" Pressione Ctrl+C para sair | Atualização automática a cada 2s")
        print("=" * 80)
        
        time.sleep(2)

if __name__ == "__main__":
    try:
        display_monitor()
    except KeyboardInterrupt:
        print("\\n\\nMonitor finalizado.")
'''
    
    # Salvar monitor básico
    monitor_path = Path("monitor_basic.py")
    monitor_path.write_text(monitor_code)
    
    # Executar
    subprocess.Popen(
        [sys.executable, str(monitor_path)],
        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
    )
    print("    [OK] Monitor básico criado e iniciado")

def main():
    """Função principal"""
    print("\n" + "=" * 80)
    print(" INICIANDO QUANTUM TRADER V3 COM MONITOR")
    print("=" * 80 + "\n")
    
    # Criar diretórios necessários
    Path("logs").mkdir(exist_ok=True)
    Path("metrics").mkdir(exist_ok=True)
    
    # Iniciar sistema principal
    start_production_system()
    
    # Iniciar monitor
    start_monitor()
    
    print("\n" + "=" * 80)
    print(" SISTEMA INICIADO COM SUCESSO")
    print("=" * 80)
    print("\nDuas janelas foram abertas:")
    print("  1. Sistema de Produção (trading)")
    print("  2. Monitor Visual (estatísticas)")
    print("\nPara parar o sistema, feche ambas as janelas ou use Ctrl+C")
    print("=" * 80 + "\n")
    
    # Manter script rodando
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nFinalizando sistema...")

if __name__ == "__main__":
    main()