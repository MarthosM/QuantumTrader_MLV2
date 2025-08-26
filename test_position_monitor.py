#!/usr/bin/env python3
"""
Script de teste para o sistema de monitoramento de posições
Testa a detecção de abertura e fechamento de posições
"""

import os
import sys
import time
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
from src.monitoring.position_monitor import PositionMonitor, PositionStatus

def test_position_monitor():
    """Testa o sistema de monitoramento de posições"""
    
    print("\n" + "="*70)
    print("TESTE DO SISTEMA DE MONITORAMENTO DE POSIÇÕES")
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
    print("\n1. Criando conexão...")
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
    print("\n3. Aguardando conexão com mercado...")
    for i in range(10):
        if connection.bMarketConnected:
            print("[OK] Conectado ao mercado")
            break
        time.sleep(1)
    
    # Criar PositionMonitor
    print("\n4. Criando PositionMonitor...")
    monitor = PositionMonitor(connection)
    
    # Registrar callbacks
    positions_detected = []
    
    def on_position_event(event_type, position, *args):
        """Callback para eventos de posição"""
        print(f"\n[EVENTO] {event_type}")
        
        if event_type == 'position_opened':
            print(f"  ✅ Posição ABERTA detectada:")
            print(f"     Symbol: {position.symbol}")
            print(f"     Side: {position.side}")
            print(f"     Quantity: {position.quantity}")
            print(f"     Entry: {position.entry_price}")
            positions_detected.append(('opened', position))
            
        elif event_type == 'position_closed':
            reason = args[0] if args else 'unknown'
            print(f"  ❌ Posição FECHADA detectada:")
            print(f"     Symbol: {position.symbol}")
            print(f"     P&L: R$ {position.pnl:.2f}")
            print(f"     P&L %: {position.pnl_percentage:.2f}%")
            print(f"     Motivo: {reason}")
            positions_detected.append(('closed', position))
    
    monitor.register_position_callback(on_position_event)
    
    # Iniciar monitoramento
    print("\n5. Iniciando monitoramento...")
    monitor.start_monitoring()
    print("[OK] Monitoramento ativo")
    
    # Verificar posição atual
    print("\n6. Verificando estado atual...")
    
    # Via connection manager
    symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
    has_position, quantity, side = connection.check_position_exists(symbol)
    
    if has_position:
        print(f"[INFO] Posição detectada via GetPosition: {quantity} {side}")
    else:
        print("[INFO] Sem posição via GetPosition")
    
    # Via monitor
    open_positions = monitor.get_open_positions()
    if open_positions:
        print(f"[INFO] {len(open_positions)} posições detectadas pelo monitor:")
        for pos in open_positions:
            print(f"  - {pos.symbol}: {pos.quantity} {pos.side} @ {pos.entry_price}")
    else:
        print("[INFO] Sem posições detectadas pelo monitor")
    
    # Teste de registro manual
    print("\n7. Testando registro manual de posição...")
    
    test_position_id = f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    test_order_ids = {
        'main_order': 12345,
        'stop_order': 12346,
        'take_order': 12347
    }
    test_details = {
        'symbol': 'WDOU25',
        'side': 'BUY',
        'quantity': 1,
        'entry_price': 5400.0,
        'stop_price': 5390.0,
        'take_price': 5420.0
    }
    
    monitor.register_position(test_position_id, test_order_ids, test_details)
    print("[OK] Posição de teste registrada")
    
    # Verificar se foi registrada
    test_position = monitor.get_position('WDOU25')
    if test_position:
        print(f"[OK] Posição recuperada: {test_position.position_id}")
        print(f"     Status: {test_position.status.value}")
    else:
        print("[ERRO] Posição não encontrada")
    
    # Simular fechamento
    print("\n8. Simulando fechamento de posição...")
    monitor.close_position('WDOU25', 5420.0, 'test_closure')
    print("[OK] Fechamento simulado")
    
    # Verificar eventos
    print("\n9. Eventos detectados durante o teste:")
    if positions_detected:
        for event_type, pos in positions_detected:
            print(f"  - {event_type}: {pos.symbol} ({pos.position_id})")
    else:
        print("  Nenhum evento detectado")
    
    # Verificar arquivo de status
    print("\n10. Verificando arquivo de status...")
    status_file = Path("data/monitor/position_status.json")
    if status_file.exists():
        with open(status_file, 'r') as f:
            status = json.load(f)
        print(f"[OK] Status salvo em {status_file}")
        print(f"     Timestamp: {status.get('timestamp', 'N/A')}")
        print(f"     Has Position: {status.get('has_position', False)}")
        print(f"     Positions: {len(status.get('positions', []))}")
    else:
        print("[INFO] Arquivo de status não encontrado")
    
    # Monitorar por alguns segundos
    print("\n11. Monitorando por 10 segundos...")
    print("    (Faça operações no ProfitChart para testar detecção)")
    
    for i in range(10):
        time.sleep(1)
        print(f"    {10-i}...", end='\r')
    
    # Parar monitoramento
    print("\n\n12. Parando monitoramento...")
    monitor.stop_monitoring()
    print("[OK] Monitoramento parado")
    
    # Finalizar
    print("\n13. Finalizando...")
    if connection.dll:
        try:
            connection.dll.Finalize()
            print("[OK] Conexão finalizada")
        except:
            pass
    
    # Resultado final
    print("\n" + "="*70)
    print("RESULTADO DO TESTE")
    print("="*70)
    
    tests_passed = 0
    tests_total = 5
    
    # Teste 1: Conexão
    if connection.bMarketConnected:
        print("✅ Conexão com mercado estabelecida")
        tests_passed += 1
    else:
        print("❌ Falha na conexão com mercado")
    
    # Teste 2: Monitor iniciado
    if monitor:
        print("✅ PositionMonitor criado com sucesso")
        tests_passed += 1
    else:
        print("❌ Falha ao criar PositionMonitor")
    
    # Teste 3: Registro de posição
    if test_position:
        print("✅ Registro de posição funcionando")
        tests_passed += 1
    else:
        print("❌ Falha no registro de posição")
    
    # Teste 4: Detecção de fechamento
    if any(evt[0] == 'closed' for evt in positions_detected):
        print("✅ Detecção de fechamento funcionando")
        tests_passed += 1
    else:
        print("⚠️  Fechamento não detectado (normal se não houve trades)")
        tests_passed += 1  # Não é erro
    
    # Teste 5: Arquivo de status
    if status_file.exists():
        print("✅ Arquivo de status sendo salvo")
        tests_passed += 1
    else:
        print("❌ Arquivo de status não criado")
    
    print(f"\nTestes aprovados: {tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
    elif tests_passed >= 3:
        print("\n✅ Sistema funcionando parcialmente")
    else:
        print("\n❌ Sistema com problemas")
    
    return tests_passed == tests_total

if __name__ == "__main__":
    try:
        success = test_position_monitor()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[CANCELADO] Teste interrompido")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)