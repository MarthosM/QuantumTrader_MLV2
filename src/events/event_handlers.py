"""
Event Handlers - Processadores de eventos específicos
Gerencia lógica de negócio para cada tipo de evento
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from .event_system import (
    Event, OrderEvent, PositionEvent, MarketEvent,
    EventType, on_event, get_event_bus
)

logger = logging.getLogger(__name__)

# ==================== OCO HANDLER ====================

class OCOEventHandler:
    """
    Gerencia eventos relacionados a ordens OCO
    Cancela automaticamente ordem pendente quando outra é executada
    """
    
    def __init__(self):
        self.oco_pairs: Dict[str, str] = {}  # order_id -> paired_order_id
        self.executed_orders: Set[str] = set()
        self.cancelled_orders: Set[str] = set()
        self.connection_manager = None  # Será injetado
        
        # Registrar handlers
        self._register_handlers()
        
        logger.info("OCOEventHandler inicializado")
    
    def _register_handlers(self):
        """Registra handlers para eventos relevantes"""
        bus = get_event_bus()
        
        # Alta prioridade para eventos de execução
        bus.subscribe(EventType.ORDER_FILLED, self.handle_order_filled, priority=9)
        bus.subscribe(EventType.ORDER_PARTIAL_FILLED, self.handle_order_partial, priority=9)
        bus.subscribe(EventType.STOP_TRIGGERED, self.handle_stop_triggered, priority=10)
        bus.subscribe(EventType.TAKE_TRIGGERED, self.handle_take_triggered, priority=10)
    
    def register_oco_pair(self, order1_id: str, order2_id: str):
        """Registra um par OCO"""
        self.oco_pairs[order1_id] = order2_id
        self.oco_pairs[order2_id] = order1_id
        logger.info(f"Par OCO registrado: {order1_id} <-> {order2_id}")
    
    def handle_order_filled(self, event: OrderEvent):
        """Processa ordem executada e cancela par OCO"""
        order_id = event.order_id
        
        # Marcar como executada
        self.executed_orders.add(order_id)
        
        # Verificar se tem par OCO
        if order_id in self.oco_pairs:
            paired_order_id = self.oco_pairs[order_id]
            
            # Cancelar ordem pareada se ainda não foi
            if paired_order_id not in self.executed_orders and paired_order_id not in self.cancelled_orders:
                self._cancel_order(paired_order_id)
                
                # Emitir evento de OCO cancelado
                get_event_bus().publish(Event(
                    type=EventType.OCO_CANCELLED,
                    data={
                        "executed_order": order_id,
                        "cancelled_order": paired_order_id
                    }
                ))
    
    def handle_order_partial(self, event: OrderEvent):
        """Processa ordem parcialmente executada"""
        # Por enquanto, não cancelar em execução parcial
        # Pode ser configurável
        logger.info(f"Ordem {event.order_id} parcialmente executada")
    
    def handle_stop_triggered(self, event: Event):
        """Processa ativação de stop loss"""
        order_id = event.data.get("order_id")
        
        if order_id:
            # Cancelar take profit associado
            if order_id in self.oco_pairs:
                take_order_id = self.oco_pairs[order_id]
                self._cancel_order(take_order_id)
                logger.info(f"Stop triggered: Cancelando take profit {take_order_id}")
    
    def handle_take_triggered(self, event: Event):
        """Processa ativação de take profit"""
        order_id = event.data.get("order_id")
        
        if order_id:
            # Cancelar stop loss associado
            if order_id in self.oco_pairs:
                stop_order_id = self.oco_pairs[order_id]
                self._cancel_order(stop_order_id)
                logger.info(f"Take triggered: Cancelando stop loss {stop_order_id}")
    
    def _cancel_order(self, order_id: str):
        """Cancela uma ordem"""
        try:
            if self.connection_manager:
                success = self.connection_manager.cancel_order(order_id)
                if success:
                    self.cancelled_orders.add(order_id)
                    logger.info(f"Ordem {order_id} cancelada com sucesso")
                else:
                    logger.error(f"Falha ao cancelar ordem {order_id}")
            else:
                logger.warning("Connection manager não configurado")
                
        except Exception as e:
            logger.error(f"Erro cancelando ordem {order_id}: {e}")

# ==================== POSITION HANDLER ====================

class PositionEventHandler:
    """
    Gerencia eventos de posição
    Cancela ordens pendentes quando posição fecha
    """
    
    def __init__(self):
        self.open_positions: Dict[str, Dict] = {}
        self.position_orders: Dict[str, List[str]] = {}  # position_id -> [order_ids]
        self.connection_manager = None
        
        self._register_handlers()
        logger.info("PositionEventHandler inicializado")
    
    def _register_handlers(self):
        """Registra handlers para eventos de posição"""
        bus = get_event_bus()
        
        bus.subscribe(EventType.POSITION_OPENED, self.handle_position_opened, priority=8)
        bus.subscribe(EventType.POSITION_CLOSED, self.handle_position_closed, priority=9)
        bus.subscribe(EventType.POSITION_UPDATED, self.handle_position_updated, priority=7)
    
    def register_position_orders(self, position_id: str, order_ids: List[str]):
        """Associa ordens a uma posição"""
        self.position_orders[position_id] = order_ids
        logger.info(f"Ordens {order_ids} associadas à posição {position_id}")
    
    def handle_position_opened(self, event: PositionEvent):
        """Processa abertura de posição"""
        position_id = event.position_id
        
        self.open_positions[position_id] = {
            "symbol": event.symbol,
            "side": event.side,
            "quantity": event.quantity,
            "entry_price": event.entry_price,
            "opened_at": datetime.now()
        }
        
        logger.info(f"Posição aberta: {position_id} - {event.side} {event.quantity} @ {event.entry_price}")
    
    def handle_position_closed(self, event: PositionEvent):
        """
        Processa fechamento de posição
        IMPORTANTE: Cancela todas as ordens pendentes associadas
        """
        position_id = event.position_id
        
        # Remover da lista de posições abertas
        if position_id in self.open_positions:
            del self.open_positions[position_id]
        
        # Cancelar ordens pendentes associadas
        if position_id in self.position_orders:
            pending_orders = self.position_orders[position_id]
            
            for order_id in pending_orders:
                try:
                    if self.connection_manager:
                        self.connection_manager.cancel_order(order_id)
                        logger.info(f"Ordem pendente {order_id} cancelada (posição {position_id} fechada)")
                except Exception as e:
                    logger.error(f"Erro cancelando ordem {order_id}: {e}")
            
            # Limpar lista de ordens
            del self.position_orders[position_id]
        
        logger.info(f"Posição fechada: {position_id} - PnL: {event.pnl}")
    
    def handle_position_updated(self, event: PositionEvent):
        """Processa atualização de posição"""
        position_id = event.position_id
        
        if position_id in self.open_positions:
            self.open_positions[position_id].update({
                "current_price": event.current_price,
                "pnl": event.pnl,
                "updated_at": datetime.now()
            })

# ==================== RISK HANDLER ====================

class RiskEventHandler:
    """
    Gerencia eventos de risco
    Executa ações de proteção quando limites são atingidos
    """
    
    def __init__(self, max_daily_loss: float = 1000.0, max_position_loss: float = 500.0):
        self.max_daily_loss = max_daily_loss
        self.max_position_loss = max_position_loss
        self.daily_pnl = 0.0
        self.is_trading_allowed = True
        self.connection_manager = None
        
        self._register_handlers()
        logger.info(f"RiskEventHandler inicializado - Max Daily Loss: {max_daily_loss}")
    
    def _register_handlers(self):
        """Registra handlers para eventos de risco"""
        bus = get_event_bus()
        
        # Máxima prioridade para eventos de risco
        bus.subscribe(EventType.RISK_LIMIT_REACHED, self.handle_risk_limit, priority=10)
        bus.subscribe(EventType.DAILY_LOSS_LIMIT, self.handle_daily_loss_limit, priority=10)
        bus.subscribe(EventType.POSITION_CLOSED, self.update_daily_pnl, priority=8)
    
    def handle_risk_limit(self, event: Event):
        """Processa limite de risco atingido"""
        logger.warning(f"LIMITE DE RISCO ATINGIDO: {event.data}")
        
        # Parar novos trades
        self.is_trading_allowed = False
        
        # Fechar todas as posições abertas
        self._close_all_positions()
    
    def handle_daily_loss_limit(self, event: Event):
        """Processa limite diário de perda"""
        logger.critical(f"LIMITE DIÁRIO DE PERDA ATINGIDO: {event.data}")
        
        # Parar trading pelo resto do dia
        self.is_trading_allowed = False
        
        # Fechar tudo
        self._close_all_positions()
        self._cancel_all_pending_orders()
        
        # Emitir evento de sistema parado
        get_event_bus().publish(Event(
            type=EventType.SYSTEM_STOPPED,
            data={"reason": "Daily loss limit reached"},
            priority=10
        ))
    
    def update_daily_pnl(self, event: PositionEvent):
        """Atualiza PnL diário"""
        self.daily_pnl += event.pnl
        
        # Verificar se atingiu limite
        if self.daily_pnl <= -self.max_daily_loss:
            get_event_bus().publish(Event(
                type=EventType.DAILY_LOSS_LIMIT,
                data={"daily_pnl": self.daily_pnl},
                priority=10
            ))
    
    def _close_all_positions(self):
        """Fecha todas as posições abertas"""
        if self.connection_manager:
            try:
                self.connection_manager.close_all_positions()
                logger.info("Todas as posições fechadas por limite de risco")
            except Exception as e:
                logger.error(f"Erro fechando posições: {e}")
    
    def _cancel_all_pending_orders(self):
        """Cancela todas as ordens pendentes"""
        if self.connection_manager:
            try:
                self.connection_manager.cancel_all_orders()
                logger.info("Todas as ordens pendentes canceladas")
            except Exception as e:
                logger.error(f"Erro cancelando ordens: {e}")

# ==================== LOGGER HANDLER ====================

class EventLoggerHandler:
    """
    Registra todos os eventos importantes em log
    Útil para auditoria e debug
    """
    
    def __init__(self, log_level: str = "INFO"):
        self.log_level = log_level
        self._register_handlers()
        logger.info("EventLoggerHandler inicializado")
    
    def _register_handlers(self):
        """Registra handler para todos os eventos importantes"""
        bus = get_event_bus()
        
        # Eventos importantes para log
        important_events = [
            EventType.ORDER_FILLED,
            EventType.ORDER_REJECTED,
            EventType.POSITION_OPENED,
            EventType.POSITION_CLOSED,
            EventType.STOP_TRIGGERED,
            EventType.TAKE_TRIGGERED,
            EventType.RISK_LIMIT_REACHED,
            EventType.CONNECTION_LOST,
            EventType.SYSTEM_STOPPED
        ]
        
        for event_type in important_events:
            bus.subscribe(event_type, self.log_event, priority=1)
    
    def log_event(self, event: Event):
        """Registra evento no log"""
        log_msg = f"[EVENT] {event.type.name} - {event.data}"
        
        if event.type in [EventType.RISK_LIMIT_REACHED, EventType.DAILY_LOSS_LIMIT]:
            logger.critical(log_msg)
        elif event.type in [EventType.ORDER_REJECTED, EventType.CONNECTION_LOST]:
            logger.error(log_msg)
        elif event.type in [EventType.STOP_TRIGGERED, EventType.TAKE_TRIGGERED]:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

# ==================== METRICS HANDLER ====================

class MetricsEventHandler:
    """
    Coleta métricas baseadas em eventos
    Para análise de performance
    """
    
    def __init__(self):
        self.metrics = {
            "total_orders": 0,
            "filled_orders": 0,
            "rejected_orders": 0,
            "cancelled_orders": 0,
            "positions_opened": 0,
            "positions_closed": 0,
            "stop_losses_triggered": 0,
            "take_profits_triggered": 0,
            "total_pnl": 0.0,
            "win_count": 0,
            "loss_count": 0
        }
        
        self._register_handlers()
        logger.info("MetricsEventHandler inicializado")
    
    def _register_handlers(self):
        """Registra handlers para coletar métricas"""
        bus = get_event_bus()
        
        bus.subscribe(EventType.ORDER_SUBMITTED, lambda e: self._increment("total_orders"))
        bus.subscribe(EventType.ORDER_FILLED, lambda e: self._increment("filled_orders"))
        bus.subscribe(EventType.ORDER_REJECTED, lambda e: self._increment("rejected_orders"))
        bus.subscribe(EventType.ORDER_CANCELLED, lambda e: self._increment("cancelled_orders"))
        bus.subscribe(EventType.POSITION_OPENED, lambda e: self._increment("positions_opened"))
        bus.subscribe(EventType.POSITION_CLOSED, self._handle_position_closed)
        bus.subscribe(EventType.STOP_TRIGGERED, lambda e: self._increment("stop_losses_triggered"))
        bus.subscribe(EventType.TAKE_TRIGGERED, lambda e: self._increment("take_profits_triggered"))
    
    def _increment(self, metric: str):
        """Incrementa uma métrica"""
        self.metrics[metric] += 1
    
    def _handle_position_closed(self, event: PositionEvent):
        """Processa fechamento de posição para métricas"""
        self.metrics["positions_closed"] += 1
        self.metrics["total_pnl"] += event.pnl
        
        if event.pnl > 0:
            self.metrics["win_count"] += 1
        else:
            self.metrics["loss_count"] += 1
    
    def get_metrics(self) -> dict:
        """Retorna métricas atuais"""
        win_rate = 0
        if self.metrics["positions_closed"] > 0:
            win_rate = self.metrics["win_count"] / self.metrics["positions_closed"]
        
        return {
            **self.metrics,
            "win_rate": win_rate,
            "avg_pnl": self.metrics["total_pnl"] / max(1, self.metrics["positions_closed"])
        }