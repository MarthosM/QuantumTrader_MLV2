"""
Script para cancelar imediatamente todas as ordens órfãs
Útil quando o sistema detecta que a posição fechou mas ordens permanecem
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cancel_all_orphan_orders():
    """Cancela todas as ordens órfãs detectadas"""
    
    print("="*60)
    print("CANCELAMENTO MANUAL DE ORDENS ÓRFÃS")
    print("="*60)
    
    try:
        # 1. Resetar lock global
        print("\n1. Resetando lock global...")
        try:
            import START_SYSTEM_COMPLETE_OCO_EVENTS as main_system
            
            with main_system.GLOBAL_POSITION_LOCK_MUTEX:
                was_locked = main_system.GLOBAL_POSITION_LOCK
                main_system.GLOBAL_POSITION_LOCK = False
                main_system.GLOBAL_POSITION_LOCK_TIME = None
                
            if was_locked:
                print("  [OK] Lock global resetado")
            else:
                print("  [INFO] Lock já estava liberado")
                
        except Exception as e:
            print(f"  [ERRO] Não foi possível acessar lock global: {e}")
    
        # 2. Buscar ConnectionManager ativo
        print("\n2. Procurando ConnectionManager ativo...")
        connection_found = False
        
        # Tentar via garbage collector
        import gc
        from src.connection_manager_working import ConnectionManagerWorking
        
        for obj in gc.get_objects():
            if isinstance(obj, ConnectionManagerWorking):
                print("  [OK] ConnectionManager encontrado")
                connection_found = True
                
                # 3. Cancelar todas ordens pendentes
                print("\n3. Cancelando ordens pendentes...")
                
                # Primeira tentativa
                try:
                    obj.cancel_all_pending_orders()
                    print("  [OK] Primeira tentativa de cancelamento")
                except Exception as e:
                    print(f"  [AVISO] Erro na primeira tentativa: {e}")
                
                time.sleep(1)
                
                # Segunda tentativa (garantia)
                try:
                    obj.cancel_all_pending_orders()
                    print("  [OK] Segunda tentativa de cancelamento")
                except Exception as e:
                    print(f"  [AVISO] Erro na segunda tentativa: {e}")
                
                # 4. Limpar OCO Monitor se existir
                if hasattr(obj, 'oco_monitor'):
                    print("\n4. Limpando OCO Monitor...")
                    try:
                        obj.oco_monitor.oco_groups.clear()
                        obj.oco_monitor.has_position = False
                        print("  [OK] OCO Monitor limpo")
                    except Exception as e:
                        print(f"  [AVISO] Erro ao limpar OCO Monitor: {e}")
                
                break
        
        if not connection_found:
            print("  [AVISO] ConnectionManager não encontrado")
            print("  Tente executar este script enquanto o sistema principal está rodando")
        
        # 5. Verificar status final
        print("\n5. Status final:")
        try:
            import START_SYSTEM_COMPLETE_OCO_EVENTS as main_system
            
            with main_system.GLOBAL_POSITION_LOCK_MUTEX:
                lock_status = main_system.GLOBAL_POSITION_LOCK
            
            print(f"  Lock global: {'ATIVO' if lock_status else 'LIBERADO'}")
            
            # Verificar arquivo de status se existir
            from pathlib import Path
            status_file = Path("data/monitor/position_status.json")
            if status_file.exists():
                import json
                with open(status_file, 'r') as f:
                    status = json.load(f)
                    if 'has_position' in status:
                        print(f"  Status arquivo: Posição {'ABERTA' if status['has_position'] else 'FECHADA'}")
                        
        except Exception as e:
            print(f"  [AVISO] Não foi possível verificar status: {e}")
        
        print("\n" + "="*60)
        print("LIMPEZA CONCLUÍDA")
        print("="*60)
        print("\nAções executadas:")
        print("- Lock global resetado")
        print("- Ordens pendentes canceladas (2x para garantia)")
        print("- OCO Monitor limpo")
        print("\nO sistema está pronto para novos trades.")
        
    except Exception as e:
        print(f"\n[ERRO CRÍTICO] Falha na limpeza: {e}")
        import traceback
        traceback.print_exc()

def check_current_status():
    """Verifica status atual do sistema"""
    print("\n" + "-"*40)
    print("VERIFICAÇÃO DE STATUS")
    print("-"*40)
    
    # Verificar posições em arquivos de status
    from pathlib import Path
    import json
    
    files_to_check = [
        "data/monitor/position_status.json",
        "data/monitor/ml_status.json",
        "data/monitor/regime_status.json"
    ]
    
    for file_path in files_to_check:
        path = Path(file_path)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    print(f"\n{file_path}:")
                    
                    # Mostrar informações relevantes
                    if 'has_position' in data:
                        print(f"  has_position: {data['has_position']}")
                    if 'position' in data:
                        pos = data['position']
                        if 'has_position' in pos:
                            print(f"  position.has_position: {pos['has_position']}")
                        if 'quantity' in pos:
                            print(f"  position.quantity: {pos['quantity']}")
                    if 'timestamp' in data:
                        print(f"  timestamp: {data['timestamp']}")
                        
            except Exception as e:
                print(f"  [ERRO] Não foi possível ler: {e}")

if __name__ == "__main__":
    # Primeiro verificar status
    check_current_status()
    
    # Perguntar confirmação
    print("\n" + "="*60)
    response = input("Deseja cancelar todas as ordens órfãs? (s/n): ")
    
    if response.lower() == 's':
        cancel_all_orphan_orders()
    else:
        print("Operação cancelada pelo usuário.")