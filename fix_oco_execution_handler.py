#!/usr/bin/env python3
"""
Script para adicionar handler de execução OCO ao sistema
Detecta quando uma ordem OCO é executada e cancela automaticamente a ordem oposta
"""

import os
import sys
from pathlib import Path

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def create_oco_execution_patch():
    """Cria um patch para melhorar a detecção de execução OCO"""
    
    patch_content = '''
# OCO Execution Handler Patch
# Adicione este código ao START_SYSTEM_COMPLETE_OCO_EVENTS.py após a linha 300

def handle_order_execution(self, order_id: int, execution_type: str = "unknown"):
    """
    Handler para quando uma ordem é executada
    Cancela automaticamente a ordem OCO oposta
    """
    logger.info(f"[ORDER EXECUTED] Ordem {order_id} executada - Tipo: {execution_type}")
    
    # Verificar se faz parte de um grupo OCO
    if hasattr(self.connection, 'oco_monitor'):
        oco_monitor = self.connection.oco_monitor
        
        # Procurar o grupo OCO desta ordem
        for group_id, group in oco_monitor.oco_groups.items():
            if not group.get('active', False):
                continue
            
            stop_id = group.get('stop_order_id') or group.get('stop')
            take_id = group.get('take_order_id') or group.get('take')
            
            # Se a ordem executada é o stop, cancelar o take
            if order_id == stop_id:
                logger.warning(f"[OCO HANDLER] STOP {stop_id} executado! Cancelando TAKE {take_id}")
                
                if take_id and self.connection.dll:
                    try:
                        # Cancelar take profit
                        result = self.connection.dll.CancelOrder(take_id)
                        logger.info(f"[OCO HANDLER] Take {take_id} cancelado: {result}")
                    except Exception as e:
                        logger.error(f"[OCO HANDLER] Erro cancelando take: {e}")
                
                # Marcar posição como fechada
                self.handle_position_closed("stop_executed")
                group['active'] = False
                break
                
            # Se a ordem executada é o take, cancelar o stop
            elif order_id == take_id:
                logger.warning(f"[OCO HANDLER] TAKE {take_id} executado! Cancelando STOP {stop_id}")
                
                if stop_id and self.connection.dll:
                    try:
                        # Cancelar stop loss
                        result = self.connection.dll.CancelOrder(stop_id)
                        logger.info(f"[OCO HANDLER] Stop {stop_id} cancelado: {result}")
                    except Exception as e:
                        logger.error(f"[OCO HANDLER] Erro cancelando stop: {e}")
                
                # Marcar posição como fechada
                self.handle_position_closed("take_executed")
                group['active'] = False
                break
    
    # Limpar ordens pendentes
    if order_id in self.active_orders:
        del self.active_orders[order_id]
        logger.info(f"[OCO HANDLER] Ordem {order_id} removida de active_orders")

# Adicione também este callback melhorado no OnOrderUpdate:

def enhanced_on_order_update(order_id, status, filled_qty, avg_price):
    """Callback melhorado para atualizar status de ordens"""
    try:
        # Log de todas as atualizações
        logger.debug(f"[ORDER UPDATE] ID: {order_id}, Status: {status}, Filled: {filled_qty}, Price: {avg_price}")
        
        # Detectar execuções
        if status in [1, 4] or filled_qty > 0:  # 1=FILLED, 4=PARTIALLY_FILLED
            logger.warning(f"[ORDER EXECUTED] Ordem {order_id} EXECUTADA! Qty: {filled_qty} @ {avg_price}")
            
            # Chamar handler de execução
            if hasattr(system, 'handle_order_execution'):
                system.handle_order_execution(order_id, "filled")
            
            # Marcar no OCO Monitor
            if hasattr(system.connection, 'oco_monitor'):
                system.connection.oco_monitor.mark_order_executed(order_id)
        
        # Detectar cancelamentos
        elif status == 2:  # CANCELLED
            logger.info(f"[ORDER CANCELLED] Ordem {order_id} cancelada")
            
            # Remover de active_orders
            if order_id in system.active_orders:
                del system.active_orders[order_id]
    
    except Exception as e:
        logger.error(f"[ORDER UPDATE] Erro processando: {e}")
'''
    
    print("="*70)
    print("PATCH PARA HANDLER DE EXECUÇÃO OCO")
    print("="*70)
    print("\nEste patch adiciona detecção melhorada de execução de ordens OCO.")
    print("\nFuncionalidades:")
    print("1. Detecta quando stop ou take é executado")
    print("2. Cancela automaticamente a ordem oposta")
    print("3. Limpa o estado do sistema corretamente")
    print("4. Previne ordens órfãs")
    
    print("\n" + "="*70)
    print("INSTRUÇÕES DE APLICAÇÃO:")
    print("="*70)
    
    print("\n1. Abra o arquivo START_SYSTEM_COMPLETE_OCO_EVENTS.py")
    print("\n2. Localize a linha ~300 (após os imports e antes da classe)")
    print("\n3. Adicione o método handle_order_execution à classe SystemCompleteOCOEvents")
    print("\n4. Substitua o callback OnOrderUpdate existente pelo enhanced_on_order_update")
    print("\n5. Reinicie o sistema")
    
    # Salvar patch em arquivo
    patch_file = Path("oco_execution_handler.patch")
    with open(patch_file, 'w', encoding='utf-8') as f:
        f.write(patch_content)
    
    print(f"\nPatch salvo em: {patch_file}")
    print("\nAPLICAR MANUALMENTE as mudanças acima para corrigir o problema.")
    
    return True

if __name__ == "__main__":
    create_oco_execution_patch()