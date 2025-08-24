"""
Sistema de Eventos do QuantumTrader
Arquitetura event-driven para gerenciamento de ordens e posições
"""

from .event_system import (
    # Classes principais
    Event,
    OrderEvent,
    PositionEvent,
    MarketEvent,
    EventBus,
    EventType,
    
    # Funções helpers
    get_event_bus,
    emit_order_event,
    emit_position_event,
    emit_market_event,
    
    # Decorator
    on_event
)

from .event_handlers import (
    OCOEventHandler,
    PositionEventHandler,
    RiskEventHandler,
    EventLoggerHandler,
    MetricsEventHandler
)

from .integration import (
    EventSystemIntegration,
    integrate_with_existing_system,
    enhance_connection_manager_oco,
    init_event_system
)

__all__ = [
    # Event System
    'Event',
    'OrderEvent', 
    'PositionEvent',
    'MarketEvent',
    'EventBus',
    'EventType',
    'get_event_bus',
    'emit_order_event',
    'emit_position_event',
    'emit_market_event',
    'on_event',
    
    # Handlers
    'OCOEventHandler',
    'PositionEventHandler',
    'RiskEventHandler',
    'EventLoggerHandler',
    'MetricsEventHandler',
    
    # Integration
    'EventSystemIntegration',
    'integrate_with_existing_system',
    'enhance_connection_manager_oco',
    'init_event_system'
]

# Versão do módulo
__version__ = '1.0.0'