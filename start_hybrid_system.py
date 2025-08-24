#!/usr/bin/env python3
"""
Script para iniciar o Sistema Híbrido Completo de Trading
Com re-treinamento diário automático
"""

import sys
import os
import json
import logging
from datetime import datetime
from pathlib import Path
import argparse

# Adicionar diretório ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hybrid_production_system import HybridProductionSystem

def check_prerequisites():
    """Verifica pré-requisitos do sistema"""
    print("\n" + "=" * 80)
    print(" VERIFICANDO PRÉ-REQUISITOS")
    print("=" * 80)
    
    checks = {
        "Modelos híbridos": Path("models/hybrid/context/regime_detector.pkl").exists(),
        "Configuração": Path("config_hybrid.json").exists(),
        "Diretório de dados": Path("data").exists(),
        "Diretório de logs": Path("logs").exists(),
    }
    
    all_ok = True
    for item, status in checks.items():
        status_text = "[OK]" if status else "[FALTANDO]"
        print(f"  {item}: {status_text}")
        if not status:
            all_ok = False
    
    if not all_ok:
        print("\n[ERRO] Alguns pré-requisitos estão faltando!")
        print("\nDicas:")
        print("  1. Execute 'python train_hybrid_pipeline.py' para treinar modelos")
        print("  2. Certifique-se que config_hybrid.json existe")
        return False
    
    return True

def show_system_info(config):
    """Mostra informações do sistema"""
    print("\n" + "=" * 80)
    print(" CONFIGURAÇÃO DO SISTEMA")
    print("=" * 80)
    
    print("\n[TRADING]")
    print(f"  Symbol: {config['trading']['symbol']}")
    print(f"  Min Confidence: {config['trading']['min_confidence']:.0%}")
    print(f"  Stop Loss: {config['trading']['stop_loss']:.1%}")
    print(f"  Take Profit: {config['trading']['take_profit']:.1%}")
    
    print("\n[MODELOS]")
    print(f"  Sistema Híbrido: {'ATIVADO' if config['models']['use_hybrid'] else 'DESATIVADO'}")
    print(f"  Peso ML: {config['models']['ml_weight']:.0%}")
    print(f"  Peso HMARL: {config['models']['hmarl_weight']:.0%}")
    
    print("\n[TREINAMENTO DIÁRIO]")
    if config['training']['enable_daily_training']:
        print(f"  Status: ATIVADO")
        print(f"  Horário: {config['training']['training_hour']:02d}:{config['training']['training_minute']:02d}")
        print(f"  Min Samples: {config['training']['training_min_samples']:,}")
    else:
        print(f"  Status: DESATIVADO")
    
    print("\n[COLETA DE DADOS]")
    print(f"  Status: {'ATIVADA' if config['data_collection']['enable_collection'] else 'DESATIVADA'}")
    print(f"  Buffer Size: {config['data_collection']['buffer_size']:,}")
    
    print("\n[GESTÃO DE RISCO]")
    print(f"  Max Daily Loss: R$ {config['risk_management']['max_daily_loss']:.2f}")
    print(f"  Max Daily Trades: {config['risk_management']['max_daily_trades']}")

def create_status_dashboard():
    """Cria dashboard de status em arquivo HTML"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Hybrid Trading System - Status</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body { 
                font-family: Arial, sans-serif; 
                background: #1a1a1a; 
                color: #fff;
                padding: 20px;
            }
            .header { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
            }
            .metric-card {
                background: #2a2a2a;
                padding: 15px;
                border-radius: 8px;
                margin: 10px;
                display: inline-block;
                min-width: 200px;
            }
            .metric-value {
                font-size: 24px;
                font-weight: bold;
                color: #4ade80;
            }
            .metric-label {
                color: #9ca3af;
                font-size: 12px;
                text-transform: uppercase;
            }
            .status-online { color: #4ade80; }
            .status-offline { color: #f87171; }
            .log-area {
                background: #1f1f1f;
                padding: 15px;
                border-radius: 8px;
                font-family: monospace;
                font-size: 12px;
                max-height: 300px;
                overflow-y: auto;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🤖 Hybrid Trading System</h1>
            <p>Status: <span class="status-online">● ONLINE</span></p>
            <p>Última atualização: {timestamp}</p>
        </div>
        
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-label">Trades Hoje</div>
                <div class="metric-value">0</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value">0.0%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">P&L Diário</div>
                <div class="metric-value">R$ 0.00</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Modelo</div>
                <div class="metric-value">v1.0</div>
            </div>
        </div>
        
        <h3>Próximo Treinamento</h3>
        <p>Agendado para: 18:30</p>
        
        <h3>Logs Recentes</h3>
        <div class="log-area">
            <p>Sistema iniciado...</p>
        </div>
    </body>
    </html>
    """.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    dashboard_path = Path("dashboard.html")
    dashboard_path.write_text(html_content)
    print(f"\n[INFO] Dashboard criado: {dashboard_path.absolute()}")

def main():
    """Função principal"""
    
    parser = argparse.ArgumentParser(description='Sistema Híbrido de Trading')
    parser.add_argument('--config', default='config_hybrid.json', help='Arquivo de configuração')
    parser.add_argument('--test', action='store_true', help='Modo de teste')
    parser.add_argument('--no-training', action='store_true', help='Desabilitar re-treinamento')
    parser.add_argument('--dashboard', action='store_true', help='Criar dashboard HTML')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print(" SISTEMA HÍBRIDO DE TRADING - v2.0")
    print("=" * 80)
    print(f"\nTimestamp: {datetime.now()}")
    
    # Verificar pré-requisitos
    if not check_prerequisites():
        sys.exit(1)
    
    # Carregar configuração
    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"\n[ERRO] Falha ao carregar configuração: {e}")
        sys.exit(1)
    
    # Aplicar argumentos de linha de comando
    if args.no_training:
        config['training']['enable_daily_training'] = False
        print("\n[INFO] Re-treinamento diário DESATIVADO via linha de comando")
    
    if args.test:
        print("\n[INFO] Modo de TESTE ativado")
        config['trading']['max_daily_trades'] = 5
        config['risk_management']['max_daily_loss'] = 100.0
    
    # Mostrar configuração
    show_system_info(config)
    
    # Criar dashboard se solicitado
    if args.dashboard:
        create_status_dashboard()
    
    # Confirmar início (pular em modo teste ou --no-confirm)
    print("\n" + "=" * 80)
    
    if not args.test and not getattr(args, 'no_confirm', False):
        response = input("\nIniciar sistema? (s/n): ")
        
        if response.lower() != 's':
            print("\n[INFO] Início cancelado pelo usuário")
            sys.exit(0)
    else:
        print("\n[INFO] Iniciando automaticamente (modo teste/no-confirm)")
    
    # Iniciar sistema
    print("\n[INFO] Iniciando sistema...")
    
    # Salvar configuração temporária
    config_temp = Path("config_production.json")
    with open(config_temp, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Criar e iniciar sistema
    system = HybridProductionSystem(config_path=str(config_temp))
    
    try:
        if system.start():
            print("\n" + "=" * 80)
            print(" SISTEMA RODANDO")
            print("=" * 80)
            print("\nComandos disponíveis:")
            print("  [Ctrl+C] - Parar sistema")
            print("  [H] - Mostrar ajuda")
            print("  [S] - Mostrar status")
            print("\nLogs em: logs/")
            
            if args.dashboard:
                print(f"Dashboard em: file://{Path('dashboard.html').absolute()}")
            
            print("\n" + "-" * 80)
            
            # Loop principal
            import threading
            while True:
                threading.Event().wait(1)
                
    except KeyboardInterrupt:
        print("\n\n[!] Sinal de parada recebido...")
        
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n[INFO] Parando sistema...")
        system.stop()
        
        # Limpar arquivo temporário
        if config_temp.exists():
            config_temp.unlink()
        
        print("\n[INFO] Sistema parado com sucesso")
        print("\n" + "=" * 80)
        print(" FIM DA EXECUÇÃO")
        print("=" * 80)


if __name__ == "__main__":
    main()