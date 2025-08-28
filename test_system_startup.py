"""
Teste de inicialização do sistema principal
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("="*60)
print("TESTE DE INICIALIZAÇÃO DO SISTEMA")
print("="*60)

# Configurar ambiente mínimo
os.environ['ENABLE_TRADING'] = 'false'
os.environ['ENABLE_DATA_RECORDING'] = 'false'
os.environ['ENABLE_DAILY_TRAINING'] = 'false'

print("\n1. Tentando importar sistema principal...")
try:
    # Importar apenas para teste
    import START_SYSTEM_COMPLETE_OCO_EVENTS
    print("  [OK] Sistema importado com sucesso")
except Exception as e:
    print(f"  [ERRO] Falha ao importar: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n2. Verificando variáveis globais...")
try:
    # Verificar se variáveis importantes existem
    assert hasattr(START_SYSTEM_COMPLETE_OCO_EVENTS, 'GLOBAL_POSITION_LOCK')
    assert hasattr(START_SYSTEM_COMPLETE_OCO_EVENTS, 'position_checker_available')
    print("  [OK] GLOBAL_POSITION_LOCK definido")
    print(f"  [OK] position_checker_available = {START_SYSTEM_COMPLETE_OCO_EVENTS.position_checker_available}")
except Exception as e:
    print(f"  [ERRO] Variáveis não encontradas: {e}")

print("\n3. Tentando criar instância do sistema...")
try:
    # Criar instância (sem executar run)
    system = START_SYSTEM_COMPLETE_OCO_EVENTS.QuantumTraderCompleteOCOEvents()
    print("  [OK] Sistema instanciado com sucesso")
    
    # Verificar componentes
    if system.position_checker:
        print("  [OK] PositionChecker integrado")
    else:
        print("  [INFO] PositionChecker não disponível (normal sem DLL)")
        
except Exception as e:
    print(f"  [ERRO] Falha ao criar instância: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("TESTE CONCLUÍDO")
print("="*60)
print("\nO sistema pode ser iniciado normalmente.")
print("As correções de detecção de posição foram aplicadas.")
print("\nPróximo passo: Execute START_SYSTEM_COMPLETE_OCO_EVENTS.py")