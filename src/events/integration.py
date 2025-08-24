"""
Integration Module - Integra o novo sistema de eventos com componentes existentes
Conecta EventBus com OCOMonitor, ConnectionManager e OrderManager
"""

import logging
from typing import Optional
from .event_system import (
    Event, OrderEvent, PositionEvent,
    EventType, get_event_bus, emit_order_event, emit_position_event
)
from .event_handlers import (
    OCOEventHandler, PositionEventHandler, 
    RiskEventHandler, EventLoggerHandler, MetricsEventHandler
)

logger = logging.getLogger(__name__)

class EventSystemIntegration:
    """
    Classe de integração do sistema de eventos com componentes existentes
    """
    
    def __init__(self, connection_manager=None, order_manager=None):
        """
        Args:
            connection_manager: Instância do ConnectionManagerOCO
            order_manager: Instância do WDOOrderManager
        """
        self.connection_manager = connection_manager
        self.order_manager = order_manager
        self.event_bus = get_event_bus()
        
        # Inicializar handlers
        self.oco_handler = OCOEventHandler()
        self.position_handler = PositionEventHandler()
        self.risk_handler = RiskEventHandler()
        self.logger_handler = EventLoggerHandler()
        self.metrics_handler = MetricsEventHandler()
        
        # Injetar connection_manager nos handlers que precisam
        self.oco_handler.connection_manager = connection_manager
        self.position_handler.connection_manager = connection_manager
        self.risk_handler.connection_manager = connection_manager
        
        # Configurar integrações
        self._setup_integrations()
        
        logger.info("Sistema de eventos integrado com sucesso")
    
    def _setup_integrations(self):
        """Configura integrações com componentes existentes"""
        
        # Integrar com OCOMonitor existente
        if self.connection_manager and hasattr(self.connection_manager, 'oco_monitor'):
            self._integrate_oco_monitor()
        
        # Integrar com OrderManager
        if self.order_manager:
            self._integrate_order_manager()
    
    def _integrate_oco_monitor(self):
        """
        Integra com OCOMonitor existente
        Substitui callbacks por eventos
        """
        oco_monitor = self.connection_manager.oco_monitor
        
        # Substituir callback de posição fechada
        original_callback = oco_monitor.position_closed_callback
        
        def enhanced_position_closed_callback(reason: str):
            # Chamar callback original se existir
            if original_callback:
                original_callback(reason)
            
            # Emitir evento
            event_type = EventType.STOP_TRIGGERED if "stop" in reason else EventType.TAKE_TRIGGERED
            self.event_bus.publish(Event(
                type=event_type,
                data={"reason": reason},
                source="oco_monitor"
            ))
        
        oco_monitor.position_closed_callback = enhanced_position_closed_callback
        logger.info("OCOMonitor integrado com sistema de eventos")
    
    def _integrate_order_manager(self):
        """
        Integra com WDOOrderManager
        Adiciona emissão de eventos em operações críticas
        """
        # Guardar métodos originais
        original_create_order = self.order_manager.create_order
        original_cancel_order = None
        if hasattr(self.order_manager, 'cancel_order'):
            original_cancel_order = self.order_manager.cancel_order
        
        # Criar wrapper para create_order
        def wrapped_create_order(*args, **kwargs):
            order = original_create_order(*args, **kwargs)
            
            # Emitir evento de ordem criada
            emit_order_event(
                EventType.ORDER_SUBMITTED,
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side.value,
                quantity=order.quantity,
                price=order.entry_price,
                source="order_manager"
            )
            
            return order
        
        # Substituir método
        self.order_manager.create_order = wrapped_create_order
        
        logger.info("OrderManager integrado com sistema de eventos")
    
    # ==================== MÉTODOS BRIDGE ====================
    
    def on_order_filled(self, order_id: str, symbol: str, side: str, 
                        quantity: int, price: float):
        """
        Bridge method - chamado quando ordem é executada
        Converte callback em evento
        """
        emit_order_event(
            EventType.ORDER_FILLED,
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            status="FILLED",
            source="connection_manager"
        )
    
    def on_order_cancelled(self, order_id: str):
        """Bridge method - ordem cancelada"""
        self.event_bus.publish(Event(
            type=EventType.ORDER_CANCELLED,
            data={"order_id": order_id},
            source="connection_manager"
        ))
    
    def on_order_rejected(self, order_id: str, reason: str):
        """Bridge method - ordem rejeitada"""
        self.event_bus.publish(Event(
            type=EventType.ORDER_REJECTED,
            data={"order_id": order_id, "reason": reason},
            source="connection_manager"
        ))
    
    def on_position_opened(self, position_id: str, symbol: str, side: str,
                          quantity: int, entry_price: float):
        """Bridge method - posição aberta"""
        emit_position_event(
            EventType.POSITION_OPENED,
            position_id=position_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            source="trading_system"
        )
    
    def on_position_closed(self, position_id: str, pnl: float):
        """Bridge method - posição fechada"""
        emit_position_event(
            EventType.POSITION_CLOSED,
            position_id=position_id,
            pnl=pnl,
            source="trading_system"
        )
    
    def register_oco_pair(self, order1_id: str, order2_id: str):
        """Registra par OCO no novo sistema"""
        self.oco_handler.register_oco_pair(order1_id, order2_id)
    
    def register_position_orders(self, position_id: str, order_ids: list):
        """Associa ordens a uma posição"""
        self.position_handler.register_position_orders(position_id, order_ids)
    
    def get_metrics(self) -> dict:
        """Retorna métricas do sistema"""
        return {
            "event_stats": self.event_bus.get_stats(),
            "trading_metrics": self.metrics_handler.get_metrics()
        }

# ==================== EXEMPLO DE USO ====================

def integrate_with_existing_system(connection_manager, order_manager):
    """
    Função helper para integrar sistema de eventos com componentes existentes
    
    Uso no hybrid_production_system.py:
    
    from src.events.integration import integrate_with_existing_system
    
    # Após inicializar connection_manager e order_manager
    event_integration = integrate_with_existing_system(connection_manager, order_manager)
    
    # Usar bridge methods quando eventos ocorrem
    event_integration.on_order_filled(order_id, symbol, side, qty, price)
    """
    
    integration = EventSystemIntegration(
        connection_manager=connection_manager,
        order_manager=order_manager
    )
    
    logger.info("Sistema de eventos pronto para uso")
    
    return integration

# ==================== MODIFICAÇÕES PARA CONNECTION_MANAGER_OCO ====================

def enhance_connection_manager_oco(ConnectionManagerOCO):
    """
    Adiciona emissão de eventos ao ConnectionManagerOCO existente
    
    Adicionar no __init__ do ConnectionManagerOCO:
    
    from src.events.integration import enhance_connection_manager_oco
    enhance_connection_manager_oco(self)
    """
    
    # Guardar método original send_order_with_bracket
    original_send_bracket = ConnectionManagerOCO.send_order_with_bracket
    
    def enhanced_send_bracket(self, *args, **kwargs):
        """Versão melhorada que emite eventos"""
        result = original_send_bracket(self, *args, **kwargs)
        
        if result and 'main_order' in result:
            # Emitir evento de ordem principal
            emit_order_event(
                EventType.ORDER_SUBMITTED,
                order_id=str(result['main_order']),
                symbol=args[0] if args else kwargs.get('symbol'),
                side=args[1] if len(args) > 1 else kwargs.get('side'),
                quantity=args[2] if len(args) > 2 else kwargs.get('quantity'),
                source="connection_oco"
            )
            
            # Registrar par OCO se stop e take foram criados
            if 'stop_order' in result and 'take_order' in result:
                if result['stop_order'] > 0 and result['take_order'] > 0:
                    bus = get_event_bus()
                    bus.publish(Event(
                        type=EventType.ORDER_SUBMITTED,
                        data={
                            "oco_group": {
                                "main": result['main_order'],
                                "stop": result['stop_order'],
                                "take": result['take_order']
                            }
                        },
                        source="connection_oco"
                    ))
        
        return result
    
    # Substituir método
    ConnectionManagerOCO.send_order_with_bracket = enhanced_send_bracket
    
    logger.info("ConnectionManagerOCO aprimorado com eventos")

# ==================== INIT MODULE ====================

def init_event_system():
    """
    Inicializa o sistema de eventos
    Deve ser chamado no início da aplicação
    """
    bus = get_event_bus()
    bus.start()
    
    logger.info("Sistema de eventos iniciado")
    
    return bus