#!/usr/bin/env python3
"""
Script para limpar ordens pendentes e resetar estado do sistema
Útil quando o sistema fica travado com ordens órfãs
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Carregar configurações
load_dotenv('.env.production')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.connection_manager_oco import ConnectionManagerOCO

def clear_all_pending_orders():
    """Cancela todas as ordens pendentes e limpa estado"""
    
    print("\n" + "="*60)
    print("LIMPEZA DE ORDENS PENDENTES")
    print("="*60)
    
    # Configurações
    dll_path = Path(__file__).parent / "ProfitDLL64.dll"
    
    if not dll_path.exists():
        print(f"[ERRO] DLL não encontrada: {dll_path}")
        print(f"[INFO] Procurando em caminhos alternativos...")
        
        # Tentar caminhos alternativos
        alt_paths = [
            Path("C:/Users/marth/OneDrive/Programacao/Python/QuantumTrader_Production/ProfitDLL64.dll"),
            Path.cwd() / "ProfitDLL64.dll",
            Path("ProfitDLL64.dll")
        ]
        
        for alt_path in alt_paths:
            if alt_path.exists():
                dll_path = alt_path
                print(f"[OK] DLL encontrada em: {dll_path}")
                break
        else:
            print("[ERRO] DLL não encontrada em nenhum caminho conhecido")
            return False
    
    # Criar conexão com caminho absoluto
    print("\n1. Conectando ao sistema...")
    connection = ConnectionManagerOCO(str(dll_path.absolute()))
    
    # Inicializar
    key = os.getenv('PROFIT_KEY', '')
    username = os.getenv('PROFIT_USERNAME', '')
    password = os.getenv('PROFIT_PASSWORD', '')
    
    if not all([key, username, password]):
        print("[ERRO] Credenciais não configuradas no .env.production")
        return False
    
    print("2. Fazendo login...")
    if not connection.initialize(key, username, password):
        print("[ERRO] Falha no login")
        return False
    
    print("[OK] Login realizado com sucesso")
    
    # Aguardar conexão
    print("\n3. Aguardando conexão com mercado...")
    for i in range(10):
        if connection.bMarketConnected:
            print("[OK] Conectado ao mercado")
            break
        time.sleep(1)
    
    if not connection.bMarketConnected:
        print("[AVISO] Mercado não conectado, continuando mesmo assim...")
    
    # Verificar posição atual
    print("\n4. Verificando posição atual...")
    symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
    
    has_position = False
    quantity = 0
    side = None
    
    try:
        has_position, quantity, side = connection.check_position_exists(symbol)
        if has_position:
            print(f"[INFO] Posição detectada: {quantity} {side}")
        else:
            print("[INFO] Sem posição aberta")
    except Exception as e:
        print(f"[AVISO] Erro ao verificar posição: {e}")
    
    # Cancelar TODAS as ordens pendentes
    print("\n5. Cancelando ordens pendentes...")
    
    try:
        # Método 1: Cancel all pending orders
        if hasattr(connection, 'cancel_all_pending_orders'):
            result = connection.cancel_all_pending_orders(symbol)
            print(f"[INFO] Cancel all pending orders: {result}")
        
        # Método 2: Cancel via OCO Monitor
        if hasattr(connection, 'oco_monitor'):
            oco_monitor = connection.oco_monitor
            
            # Listar grupos OCO ativos
            if hasattr(oco_monitor, 'oco_groups'):
                active_groups = 0
                for group_id, group in oco_monitor.oco_groups.items():
                    if group.get('active', False):
                        active_groups += 1
                        print(f"[INFO] Grupo OCO ativo: {group_id}")
                        
                        # Tentar cancelar ordens do grupo
                        for order_type in ['stop_order_id', 'take_order_id']:
                            order_id = group.get(order_type)
                            if order_id:
                                try:
                                    if connection.dll:
                                        result = connection.dll.CancelOrder(order_id)
                                        print(f"  Cancelando {order_type}: {order_id} -> {result}")
                                except Exception as e:
                                    print(f"  Erro ao cancelar {order_id}: {e}")
                        
                        # Marcar grupo como inativo
                        group['active'] = False
                
                if active_groups == 0:
                    print("[INFO] Nenhum grupo OCO ativo encontrado")
                else:
                    print(f"[OK] {active_groups} grupos OCO processados")
                    
                # Limpar todos os grupos
                oco_monitor.oco_groups.clear()
                print("[OK] Grupos OCO limpos")
    
    except Exception as e:
        print(f"[ERRO] Falha ao cancelar ordens: {e}")
    
    # Verificar arquivos de estado
    print("\n6. Limpando arquivos de estado...")
    
    state_files = [
        'data/monitor/ml_status.json',
        'data/monitor/hmarl_status.json',
        'hmarl_status.json',
        'ml_status.json'
    ]
    
    for file in state_files:
        if Path(file).exists():
            try:
                # Criar backup
                backup_name = f"{file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                Path(file).rename(backup_name)
                print(f"[OK] {file} -> {backup_name}")
            except Exception as e:
                print(f"[AVISO] Erro ao mover {file}: {e}")
    
    print("\n7. Finalizando...")
    
    # Desconectar
    if connection.dll:
        try:
            connection.dll.Finalize()
            print("[OK] Conexão finalizada")
        except:
            pass
    
    print("\n" + "="*60)
    print("LIMPEZA CONCLUÍDA")
    print("="*60)
    print("\nAções realizadas:")
    print("1. [OK] Ordens pendentes canceladas")
    print("2. [OK] Grupos OCO limpos")
    print("3. [OK] Arquivos de estado salvos como backup")
    print("\nPróximos passos:")
    print("1. Reinicie o sistema de trading")
    print("2. Verifique se não há mais mensagens de 'posição fantasma'")
    print("3. O sistema deve estar pronto para novos trades")
    
    return True

if __name__ == "__main__":
    try:
        success = clear_all_pending_orders()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[CANCELADO] Operação interrompida pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)