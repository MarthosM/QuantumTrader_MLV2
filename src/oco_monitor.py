"""
Monitor OCO - Gerencia cancelamento automático de ordens OCO
"""

import threading
import time
import logging
from typing import Dict, Set, Optional

logger = logging.getLogger('OCOMonitor')

class OCOMonitor:
    """
    Monitora ordens OCO e cancela automaticamente a ordem pendente
    quando uma é executada
    """
    
    def __init__(self, connection_manager):
        """
        Args:
            connection_manager: Instância do ConnectionManagerOCO
        """
        self.conn = connection_manager
        self.is_running = False
        self.monitor_thread = None
        self.check_interval = 2.0  # Verificar a cada 2 segundos para detectar execuções
        
        # Rastreamento de ordens
        self.oco_groups = {}  # main_order_id -> {stop_id, take_id}
        self.executed_orders = set()
        self.pending_cancellations = set()
        
        # Callback para quando posição fecha
        self.position_closed_callback = None
        
    def register_oco_group(self, main_order_id: int, stop_order_id: int, take_order_id: int):
        """
        Registra um grupo OCO para monitoramento
        
        Args:
            main_order_id: ID da ordem principal
            stop_order_id: ID da ordem stop loss
            take_order_id: ID da ordem take profit
        """
        self.oco_groups[main_order_id] = {
            'stop': stop_order_id,
            'take': take_order_id,
            'active': True
        }
        logger.info(f"[OCO Monitor] Registrado grupo: Main={main_order_id}, Stop={stop_order_id}, Take={take_order_id}")
        
    def start(self):
        """Inicia o monitoramento OCO"""
        if self.is_running:
            return
            
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("[OCO Monitor] Iniciado")
        
    def stop(self):
        """Para o monitoramento OCO"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("[OCO Monitor] Parado")
        
    def _monitor_loop(self):
        """Loop principal de monitoramento"""
        while self.is_running:
            try:
                self._check_oco_executions()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"[OCO Monitor] Erro no loop: {e}")
                time.sleep(5)
                
    def _check_oco_executions(self):
        """
        Verifica se alguma ordem OCO foi executada
        e cancela a ordem pendente correspondente
        """
        for main_id, group in list(self.oco_groups.items()):
            if not group['active']:
                continue
                
            stop_id = group['stop']
            take_id = group['take']
            
            # Verificar status real das ordens via connection manager
            stop_executed = self._is_order_executed(stop_id)
            take_executed = self._is_order_executed(take_id)
            
            # Log periódico para debug (a cada 10 verificações)
            if not hasattr(self, '_check_count'):
                self._check_count = 0
            self._check_count += 1
            
            if self._check_count % 10 == 0:  # Log a cada 20 segundos
                logger.debug(f"[OCO Monitor] Verificando grupo {main_id}: Stop={stop_id} Take={take_id}")
                if hasattr(self.conn, 'get_order_status'):
                    stop_status = self.conn.get_order_status(stop_id)
                    take_status = self.conn.get_order_status(take_id)
                    logger.debug(f"[OCO Monitor] Status - Stop: {stop_status}, Take: {take_status}")
            
            # Se stop foi executado, cancelar take
            if stop_executed:
                if take_id not in self.pending_cancellations:
                    logger.info(f"[OCO Monitor] Stop executado ({stop_id}), cancelando Take ({take_id})")
                    
                    # Notificar que posição fechou (stop atingido)
                    if self.position_closed_callback:
                        logger.info("[OCO Monitor] Notificando fechamento de posição por STOP")
                        try:
                            self.position_closed_callback("stop_executed")
                        except Exception as e:
                            logger.error(f"[OCO Monitor] Erro ao chamar callback: {e}")
                    
                    self._cancel_order(take_id)
                    self.pending_cancellations.add(take_id)
                    group['active'] = False
                    
            # Se take foi executado, cancelar stop
            elif take_executed:
                if stop_id not in self.pending_cancellations:
                    logger.info(f"[OCO Monitor] Take executado ({take_id}), cancelando Stop ({stop_id})")
                    
                    # Notificar que posição fechou (take atingido)
                    if self.position_closed_callback:
                        logger.info("[OCO Monitor] Notificando fechamento de posição por TAKE")
                        try:
                            self.position_closed_callback("take_executed")
                        except Exception as e:
                            logger.error(f"[OCO Monitor] Erro ao chamar callback: {e}")
                    
                    self._cancel_order(stop_id)
                    self.pending_cancellations.add(stop_id)
                    group['active'] = False
                    
    def _is_order_executed(self, order_id: int) -> bool:
        """
        Verifica se uma ordem foi executada usando o status real
        
        Args:
            order_id: ID da ordem a verificar
            
        Returns:
            bool: True se a ordem foi executada, False caso contrário
        """
        # Verificar primeiro no cache local
        if order_id in self.executed_orders:
            return True
        
        # Verificar status real via connection manager
        if hasattr(self.conn, 'get_order_status'):
            try:
                status = self.conn.get_order_status(order_id)
                
                # Considerar como executada se status for FILLED ou PARTIALLY_FILLED
                if status in ["FILLED", "PARTIALLY_FILLED"]:
                    # Adicionar ao cache para não verificar novamente
                    self.executed_orders.add(order_id)
                    logger.info(f"[OCO Monitor] Ordem {order_id} detectada como EXECUTADA (status: {status})")
                    return True
                
                # Log apenas se for primeira verificação ou mudança de status
                if order_id not in self.pending_cancellations:
                    logger.debug(f"[OCO Monitor] Ordem {order_id} status: {status}")
                    
                return False
                
            except Exception as e:
                logger.error(f"[OCO Monitor] Erro ao verificar status da ordem {order_id}: {e}")
                return False
        else:
            # Fallback: verificar apenas no cache local
            return order_id in self.executed_orders
        
    def _cancel_order(self, order_id: int):
        """
        Cancela uma ordem específica
        
        Args:
            order_id: ID da ordem a cancelar
        """
        try:
            if hasattr(self.conn, 'cancel_order_by_id'):
                result = self.conn.cancel_order_by_id(order_id)
                if result:
                    logger.info(f"[OCO Monitor] Ordem {order_id} cancelada com sucesso")
                else:
                    logger.warning(f"[OCO Monitor] Falha ao cancelar ordem {order_id}")
            else:
                logger.warning(f"[OCO Monitor] Método cancel_order_by_id não disponível")
        except Exception as e:
            logger.error(f"[OCO Monitor] Erro ao cancelar ordem {order_id}: {e}")
            
    def mark_order_executed(self, order_id: int):
        """
        Marca manualmente uma ordem como executada
        Útil para integração com callbacks externos
        
        Args:
            order_id: ID da ordem executada
        """
        if order_id in self.executed_orders:
            return
            
        self.executed_orders.add(order_id)
        
        # Procurar em todos os grupos OCO
        for main_id, group in self.oco_groups.items():
            if not group['active']:
                continue
                
            stop_id = group['stop']
            take_id = group['take']
            
            if order_id == stop_id:
                # Stop executado, cancelar take
                logger.info(f"[OCO Monitor] Stop {stop_id} marcado como executado, cancelando Take {take_id}")
                self._cancel_order(take_id)
                group['active'] = False
                break
                
            elif order_id == take_id:
                # Take executado, cancelar stop
                logger.info(f"[OCO Monitor] Take {take_id} marcado como executado, cancelando Stop {stop_id}")
                self._cancel_order(stop_id)
                group['active'] = False
                break