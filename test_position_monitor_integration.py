#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de integração do Position Monitor com o sistema completo
Verifica se o monitor está rastreando corretamente as posições
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Fix encoding for Windows
import locale
import codecs
if sys.platform == 'win32':
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TestPositionMonitor')

def test_position_monitor():
    """Testa o Position Monitor integrado ao sistema"""
    
    print("\n" + "=" * 60)
    print(" TESTE DO POSITION MONITOR")
    print("=" * 60)
    
    try:
        # 1. Verificar se os módulos estão disponíveis
        print("\n[1] Verificando módulos...")
        
        try:
            from src.monitoring.position_monitor import PositionMonitor, PositionStatus
            print("  [OK] PositionMonitor importado")
        except ImportError as e:
            print(f"  [ERRO] Erro ao importar PositionMonitor: {e}")
            return False
        
        try:
            from src.trading.position_manager import PositionManager, ManagementStrategy
            print("  [OK] PositionManager importado")
        except ImportError as e:
            print(f"  [ERRO] Erro ao importar PositionManager: {e}")
            return False
        
        try:
            from src.utils.symbol_manager import SymbolManager
            print("  [OK] SymbolManager importado")
        except ImportError as e:
            print(f"  [ERRO] Erro ao importar SymbolManager: {e}")
            return False
        
        # 2. Verificar símbolo atual
        print("\n[2] Verificando símbolo...")
        current_symbol = SymbolManager.get_current_wdo_symbol()
        next_symbol = SymbolManager.get_next_wdo_symbol()
        print(f"  Símbolo atual: {current_symbol}")
        print(f"  Próximo símbolo: {next_symbol}")
        
        if SymbolManager.is_near_expiry():
            print(f"  [AVISO]  AVISO: Próximo do vencimento!")
        
        # 3. Criar connection manager mock para teste
        print("\n[3] Criando connection manager mock...")
        
        class MockConnectionManager:
            def __init__(self):
                self.symbol = current_symbol
                self.last_price = 5500.0
                self.best_bid = 5499.5
                self.best_ask = 5500.5
                
            def check_position_exists(self, symbol):
                # Simular sem posição
                return False, 0, None
            
            def register_order_callback(self, callback):
                pass
        
        mock_connection = MockConnectionManager()
        print("  [OK] Connection manager mock criado")
        
        # 4. Criar Position Monitor
        print("\n[4] Criando Position Monitor...")
        position_monitor = PositionMonitor(mock_connection)
        
        # Registrar callback de teste
        events_received = []
        
        def position_callback(event_type, position, *args):
            events_received.append({
                'type': event_type,
                'position': position,
                'args': args,
                'time': datetime.now()
            })
            print(f"  [EVENTO] {event_type}: {position.symbol if position else 'N/A'}")
        
        position_monitor.register_position_callback(position_callback)
        print("  [OK] Position Monitor criado e callback registrado")
        
        # 5. Iniciar monitoramento
        print("\n[5] Iniciando monitoramento...")
        position_monitor.start_monitoring()
        print("  [OK] Monitoramento iniciado")
        
        # 6. Simular registro de posição
        print("\n[6] Simulando registro de posição...")
        
        position_id = f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        order_ids = {
            'main': 'ORDER_001',
            'stop': 'ORDER_002',
            'take': 'ORDER_003'
        }
        
        position_monitor.register_position(
            position_id=position_id,
            order_ids=order_ids,
            details={
                'symbol': current_symbol,
                'side': 'BUY',
                'quantity': 1,
                'entry_price': 5500.0,
                'stop_price': 5485.0,
                'take_price': 5530.0
            }
        )
        
        print(f"  [OK] Posição {position_id} registrada")
        
        # 7. Verificar estado
        print("\n[7] Verificando estado...")
        time.sleep(2)  # Aguardar processamento
        
        has_position = position_monitor.has_open_position()
        open_positions = position_monitor.get_open_positions()
        
        print(f"  Tem posição aberta? {has_position}")
        print(f"  Posições abertas: {len(open_positions)}")
        
        if open_positions:
            for pos in open_positions:
                print(f"    - {pos.symbol}: {pos.side} {pos.quantity} @ {pos.entry_price}")
                print(f"      Status: {pos.status.value}")
                print(f"      P&L: {pos.pnl:.2f} ({pos.pnl_percentage:.2f}%)")
        
        # 8. Criar Position Manager
        print("\n[8] Criando Position Manager...")
        position_manager = PositionManager(position_monitor, mock_connection)
        
        strategy = ManagementStrategy(
            trailing_stop_enabled=True,
            trailing_stop_distance=0.01,  # 1%
            breakeven_enabled=True,
            breakeven_threshold=0.005,  # 0.5%
            partial_exit_enabled=False
        )
        
        position_manager.apply_strategy(current_symbol, strategy)
        print("  [OK] Position Manager configurado com estratégia")
        
        # 9. Iniciar gestão
        print("\n[9] Iniciando gestão de posições...")
        position_manager.start_management()
        print("  [OK] Gestão iniciada")
        
        # 10. Simular atualização de preço
        print("\n[10] Simulando mudança de preço...")
        time.sleep(1)
        
        # Simular preço subindo (para testar breakeven)
        mock_connection.last_price = 5510.0
        mock_connection.best_bid = 5509.5
        mock_connection.best_ask = 5510.5
        print(f"  Novo preço: {mock_connection.last_price}")
        
        time.sleep(2)  # Aguardar processamento
        
        # 11. Verificar arquivo de status
        print("\n[11] Verificando arquivo de status...")
        status_file = Path("data/monitor/position_status.json")
        
        if status_file.exists():
            import json
            with open(status_file, 'r') as f:
                status_data = json.load(f)
            
            print(f"  [OK] Arquivo de status encontrado")
            print(f"  Timestamp: {status_data.get('timestamp', 'N/A')}")
            print(f"  Has position: {status_data.get('has_position', False)}")
            
            if status_data.get('positions'):
                for pos in status_data['positions']:
                    print(f"    - {pos['symbol']}: P&L = {pos['pnl']:.2f}")
        else:
            print("  [AVISO]  Arquivo de status não encontrado")
        
        # 12. Simular fechamento
        print("\n[12] Simulando fechamento de posição...")
        position_monitor.close_position(current_symbol, 5520.0, "test_closure")
        
        time.sleep(1)
        
        # 13. Verificar eventos recebidos
        print("\n[13] Eventos recebidos:")
        for event in events_received:
            print(f"  - {event['type']} às {event['time'].strftime('%H:%M:%S')}")
        
        # 14. Parar monitoramento
        print("\n[14] Parando monitoramento...")
        position_monitor.stop_monitoring()
        position_manager.stop_management()
        print("  [OK] Monitoramento parado")
        
        print("\n" + "=" * 60)
        print(" TESTE CONCLUÍDO COM SUCESSO!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n[ERRO] ERRO NO TESTE: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Executa o teste"""
    success = test_position_monitor()
    
    if success:
        print("\n[SUCESSO] Todos os testes passaram!")
        print("\nPróximos passos:")
        print("1. Execute o sistema completo: python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
        print("2. Monitore as posições em: data/monitor/position_status.json")
        print("3. Verifique os logs para eventos de posição")
    else:
        print("\n[FALHA] Alguns testes falharam. Verifique os erros acima.")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())