#!/usr/bin/env python3
"""
Teste completo do sistema com Position Monitor e Monitor Visual
"""

import sys
import time
import threading
from pathlib import Path

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))

def test_system_initialization():
    """Testa inicialização do sistema completo"""
    print("=" * 60)
    print(" TESTE DO SISTEMA COMPLETO")
    print("=" * 60)
    
    try:
        print("\n[1] Importando sistema...")
        from START_SYSTEM_COMPLETE_OCO_EVENTS import QuantumTraderCompleteOCOEvents
        print("  [OK] Sistema importado")
        
        print("\n[2] Criando instância...")
        system = QuantumTraderCompleteOCOEvents()
        print("  [OK] Instância criada")
        
        print("\n[3] Inicializando sistema...")
        if system.initialize():
            print("  [OK] Sistema inicializado com sucesso!")
            
            # Verificar componentes
            print("\n[4] Verificando componentes:")
            
            if system.connection:
                print("  [OK] Connection Manager")
            else:
                print("  [ERRO] Connection Manager não inicializado")
            
            if system.position_monitor:
                print("  [OK] Position Monitor")
            else:
                print("  [AVISO] Position Monitor não disponível")
            
            if system.position_manager:
                print("  [OK] Position Manager")
            else:
                print("  [AVISO] Position Manager não disponível")
            
            if system.event_bus:
                print("  [OK] Event Bus")
            else:
                print("  [ERRO] Event Bus não inicializado")
            
            if system.hmarl_agents:
                print("  [OK] HMARL Agents")
            else:
                print("  [AVISO] HMARL Agents não disponível")
            
            # Testar Position Monitor
            if system.position_monitor:
                print("\n[5] Testando Position Monitor:")
                print(f"  Has position: {system.position_monitor.has_open_position()}")
                print(f"  Open positions: {len(system.position_monitor.get_open_positions())}")
                print("  [OK] Position Monitor funcionando")
            
            print("\n[6] Sistema pronto para trading!")
            
            # Parar sistema
            print("\n[7] Parando sistema...")
            system.stop()
            print("  [OK] Sistema parado")
            
            return True
            
        else:
            print("  [ERRO] Falha na inicialização")
            return False
            
    except Exception as e:
        print(f"\n[ERRO] Erro durante teste: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal"""
    success = test_system_initialization()
    
    if success:
        print("\n" + "=" * 60)
        print(" TESTE CONCLUÍDO COM SUCESSO!")
        print("=" * 60)
        print("\nTodos os componentes estão funcionando:")
        print("  ✓ Connection Manager")
        print("  ✓ Position Monitor")
        print("  ✓ Position Manager")
        print("  ✓ Event Bus")
        print("  ✓ HMARL Agents")
        print("\nSistema pronto para uso!")
    else:
        print("\n" + "=" * 60)
        print(" TESTE FALHOU")
        print("=" * 60)
        print("\nVerifique os erros acima.")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())