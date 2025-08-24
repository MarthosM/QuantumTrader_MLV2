#!/usr/bin/env python3
"""
Script para detectar ordens órfãs - grupos OCO sem posição real
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import json

# Carregar configurações
load_dotenv('.env.production')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.connection_manager_oco import ConnectionManagerOCO

def detect_orphan_orders():
    """Detecta se há ordens órfãs no sistema"""
    
    print("\n" + "="*70)
    print("DETECÇÃO DE ORDENS ÓRFÃS")
    print("="*70)
    
    # Configurações
    dll_path = Path(__file__).parent / "ProfitDLL64.dll"
    
    if not dll_path.exists():
        # Tentar caminhos alternativos
        alt_paths = [
            Path("C:/Users/marth/OneDrive/Programacao/Python/QuantumTrader_Production/ProfitDLL64.dll"),
            Path.cwd() / "ProfitDLL64.dll"
        ]
        
        for alt_path in alt_paths:
            if alt_path.exists():
                dll_path = alt_path
                break
        else:
            print("[ERRO] DLL não encontrada")
            return False
    
    print(f"[OK] DLL encontrada: {dll_path}")
    
    # Criar conexão
    print("\n1. Conectando ao sistema...")
    connection = ConnectionManagerOCO(str(dll_path.absolute()))
    
    # Inicializar
    key = os.getenv('PROFIT_KEY', '')
    username = os.getenv('PROFIT_USERNAME', '')
    password = os.getenv('PROFIT_PASSWORD', '')
    
    if not all([key, username, password]):
        print("[ERRO] Credenciais não configuradas")
        return False
    
    print("2. Fazendo login...")
    if not connection.initialize(key, username, password):
        print("[ERRO] Falha no login")
        return False
    
    print("[OK] Login realizado")
    
    # Aguardar conexão
    print("\n3. Verificando mercado...")
    import time
    for i in range(5):
        if connection.bMarketConnected:
            print("[OK] Conectado ao mercado")
            break
        time.sleep(1)
    
    # Verificar posição
    print("\n4. Verificando posição atual...")
    symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
    
    has_position = False
    quantity = 0
    side = None
    
    try:
        has_position, quantity, side = connection.check_position_exists(symbol)
        
        if has_position:
            print(f"[INFO] POSIÇÃO DETECTADA: {quantity} {side}")
        else:
            print("[INFO] SEM POSIÇÃO ABERTA")
    except Exception as e:
        print(f"[ERRO] Falha ao verificar posição: {e}")
    
    # Verificar grupos OCO
    print("\n5. Verificando grupos OCO...")
    
    oco_groups_found = False
    orphan_orders = []
    
    if hasattr(connection, 'oco_monitor') and connection.oco_monitor:
        oco_monitor = connection.oco_monitor
        
        if hasattr(oco_monitor, 'oco_groups'):
            active_groups = 0
            
            for group_id, group in oco_monitor.oco_groups.items():
                if group.get('active', False):
                    active_groups += 1
                    stop_id = group.get('stop_order_id') or group.get('stop')
                    take_id = group.get('take_order_id') or group.get('take')
                    
                    print(f"\n[GRUPO OCO ATIVO] ID: {group_id}")
                    print(f"  Stop Order: {stop_id}")
                    print(f"  Take Order: {take_id}")
                    
                    if stop_id:
                        orphan_orders.append(stop_id)
                    if take_id:
                        orphan_orders.append(take_id)
                    
                    oco_groups_found = True
            
            if active_groups == 0:
                print("[OK] Nenhum grupo OCO ativo")
    
    # Análise final
    print("\n" + "="*70)
    print("ANÁLISE")
    print("="*70)
    
    if not has_position and oco_groups_found:
        print("\n[ALERTA] ORDENS ÓRFÃS DETECTADAS!")
        print("Há grupos OCO ativos mas SEM posição aberta.")
        print("\nOrdens que devem ser canceladas:")
        for order_id in orphan_orders:
            print(f"  - {order_id}")
        
        print("\nRECOMENDAÇÃO:")
        print("1. Execute: python cleanup_current_orphans.py")
        print("2. Ou cancele manualmente no ProfitChart")
        
    elif has_position and oco_groups_found:
        print("\n[OK] SITUAÇÃO NORMAL")
        print("Há posição aberta protegida por ordens OCO.")
        print("Não é necessária nenhuma ação.")
        
    elif has_position and not oco_groups_found:
        print("\n[PERIGO] POSIÇÃO SEM PROTEÇÃO!")
        print("Há posição aberta mas SEM ordens de proteção.")
        print("\nRECOMENDAÇÃO:")
        print("1. Adicione stop/take manualmente no ProfitChart")
        print("2. Ou feche a posição")
        
    else:
        print("\n[OK] SISTEMA LIMPO")
        print("Sem posição e sem ordens pendentes.")
        print("Sistema pronto para novos trades.")
    
    # Verificar arquivos de status
    print("\n6. Verificando arquivos de status...")
    
    status_files = [
        'hmarl_status.json',
        'ml_status.json',
        'data/monitor/ml_status.json',
        'data/monitor/hmarl_status.json'
    ]
    
    for file in status_files:
        if Path(file).exists():
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    
                # Verificar se há indicação de posição
                if 'position' in str(data).lower() or 'has_position' in str(data).lower():
                    print(f"  {file}: pode conter info de posição")
            except:
                pass
    
    # Finalizar
    print("\n7. Finalizando...")
    if connection.dll:
        try:
            connection.dll.Finalize()
            print("[OK] Conexão finalizada")
        except:
            pass
    
    print("\n" + "="*70)
    print("DETECÇÃO CONCLUÍDA")
    print("="*70)
    
    return True

if __name__ == "__main__":
    try:
        detect_orphan_orders()
    except KeyboardInterrupt:
        print("\n[CANCELADO] Operação interrompida")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)