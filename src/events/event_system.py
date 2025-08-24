"""
Sistema de Eventos Centralizado para QuantumTrader
Baseado em arquitetura event-driven para gerenciar ordens, posições e trades
"""

import logging
import threading
from datetime import datetime
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict
import queue
import json

logger = logging.getLogger(__name__)

# ==================== TIPOS DE EVENTOS ====================

class EventType(Enum):
    """Tipos de eventos do sistema"""
    # Eventos de Ordem
    ORDER_SUBMITTED = auto()
    ORDER_FILLED = auto()
    ORDER_PARTIAL_FILLED = auto()
    ORDER_CANCELLED = auto()
    ORDER_REJECTED = auto()
    ORDER_EXPIRED = auto()
    
    # Eventos de Posição
    POSITION_OPENED = auto()
    POSITION_CLOSED = auto()
    POSITION_UPDATED = auto()
    
    # Eventos de Stop/Take
    STOP_TRIGGERED = auto()
    TAKE_TRIGGERED = auto()
    OCO_CANCELLED = auto()
    
    # Eventos de Mercado
    PRICE_UPDATE = auto()
    BOOK_UPDATE = auto()
    TRADE_EXECUTED = auto()
    
    # Eventos de Sistema
    SYSTEM_STARTED = auto()
    SYSTEM_STOPPED = auto()
    CONNECTION_LOST = auto()
    CONNECTION_RESTORED = auto()
    
    # Eventos de Risco
    RISK_LIMIT_REACHED = auto()
    DAILY_LOSS_LIMIT = auto()
    MARGIN_CALL = auto()
    
    # Eventos de ML/Trading
    SIGNAL_GENERATED = auto()
    PREDICTION_MADE = auto()
    CONFIDENCE_CHANGED = auto()

# ==================== ESTRUTURAS DE EVENTOS ====================

@dataclass
class Event:
    """Evento base do sistema"""
    type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    priority: int = 5  # 1-10, sendo 10 mais prioritário
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.name,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "source": self.source,
            "priority": self.priority
        }
    
    def __str__(self) -> str:
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.type.name} from {self.source}"
    
    def __lt__(self, other):
        """Necessário para PriorityQueue"""
        if not isinstance(other, Event):
            return NotImplemented
        return self.timestamp < other.timestamp

@dataclass
class OrderEvent(Event):
    """Evento específico de ordem"""
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: int = 0
    price: float = 0.0
    status: str = ""
    
    def __post_init__(self):
        # Adicionar dados específicos de ordem ao data dict
        self.data.update({
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status
        })

@dataclass
class PositionEvent(Event):
    """Evento específico de posição"""
    position_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: int = 0
    entry_price: float = 0.0
    current_price: float = 0.0
    pnl: float = 0.0
    
    def __post_init__(self):
        self.data.update({
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "pnl": self.pnl
        })

@dataclass
class MarketEvent(Event):
    """Evento de mercado"""
    symbol: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    
    def __post_init__(self):
        self.data.update({
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "volume": self.volume
        })

# ==================== EVENT BUS CENTRAL ====================

class EventBus:
    """
    Barramento de eventos centralizado
    Gerencia publicação e subscrição de eventos
    """
    
    def __init__(self, max_queue_size: int = 10000):
        self.subscribers: Dict[EventType, List[Callable]] = defaultdict(list)
        self.event_queue = queue.PriorityQueue(maxsize=max_queue_size)
        self.is_running = False
        self.processor_thread = None
        self.lock = threading.RLock()
        
        # Estatísticas
        self.stats = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "events_by_type": defaultdict(int)
        }
        
        # Histórico de eventos (últimos N eventos)
        self.event_history: List[Event] = []
        self.max_history_size = 1000
        
        logger.info("EventBus inicializado")
    
    def start(self):
        """Inicia o processamento de eventos"""
        if self.is_running:
            return
        
        self.is_running = True
        self.processor_thread = threading.Thread(target=self._process_events, daemon=True)
        self.processor_thread.start()
        logger.info("EventBus iniciado")
    
    def stop(self):
        """Para o processamento de eventos"""
        self.is_running = False
        if self.processor_thread:
            self.processor_thread.join(timeout=5)
        logger.info("EventBus parado")
    
    def subscribe(self, event_type: EventType, handler: Callable, priority: int = 5):
        """
        Inscreve um handler para um tipo de evento
        
        Args:
            event_type: Tipo do evento
            handler: Função callback a ser chamada
            priority: Prioridade do handler (maior = executado primeiro)
        """
        with self.lock:
            # Adicionar handler com prioridade
            self.subscribers[event_type].append((priority, handler))
            # Ordenar por prioridade (maior primeiro)
            self.subscribers[event_type].sort(key=lambda x: x[0], reverse=True)
            
            logger.debug(f"Handler inscrito para {event_type.name}")
    
    def unsubscribe(self, event_type: EventType, handler: Callable):
        """Remove inscrição de um handler"""
        with self.lock:
            self.subscribers[event_type] = [
                (p, h) for p, h in self.subscribers[event_type] 
                if h != handler
            ]
    
    def publish(self, event: Event):
        """
        Publica um evento no barramento
        
        Args:
            event: Evento a ser publicado
        """
        try:
            # Adicionar à fila com prioridade invertida (menor valor = maior prioridade)
            priority_value = -event.priority  # Inverter para PriorityQueue
            self.event_queue.put((priority_value, event.timestamp, event))
            
            # Atualizar estatísticas
            self.stats["events_published"] += 1
            self.stats["events_by_type"][event.type] += 1
            
            # Adicionar ao histórico
            self._add_to_history(event)
            
            logger.debug(f"Evento publicado: {event}")
            
        except queue.Full:
            logger.error(f"Fila de eventos cheia! Evento perdido: {event}")
            self.stats["events_failed"] += 1
    
    def publish_immediate(self, event: Event):
        """
        Publica e processa um evento imediatamente (síncrono)
        Útil para eventos críticos que precisam ser processados na hora
        """
        with self.lock:
            self._process_single_event(event)
    
    def _process_events(self):
        """Thread principal de processamento de eventos"""
        logger.info("Processador de eventos iniciado")
        
        while self.is_running:
            try:
                # Pegar evento da fila com timeout
                priority, timestamp, event = self.event_queue.get(timeout=0.1)
                self._process_single_event(event)
                self.stats["events_processed"] += 1
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Erro processando evento: {e}")
                self.stats["events_failed"] += 1
    
    def _process_single_event(self, event: Event):
        """Processa um único evento"""
        try:
            # Buscar handlers para este tipo de evento
            handlers = self.subscribers.get(event.type, [])
            
            # Executar cada handler
            for priority, handler in handlers:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Erro em handler para {event.type.name}: {e}")
                    
        except Exception as e:
            logger.error(f"Erro processando evento {event}: {e}")
    
    def _add_to_history(self, event: Event):
        """Adiciona evento ao histórico"""
        with self.lock:
            self.event_history.append(event)
            
            # Limitar tamanho do histórico
            if len(self.event_history) > self.max_history_size:
                self.event_history = self.event_history[-self.max_history_size:]
    
    def get_stats(self) -> dict:
        """Retorna estatísticas do EventBus"""
        with self.lock:
            return {
                "published": self.stats["events_published"],
                "processed": self.stats["events_processed"],
                "failed": self.stats["events_failed"],
                "queue_size": self.event_queue.qsize(),
                "by_type": dict(self.stats["events_by_type"])
            }
    
    def get_recent_events(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """
        Retorna eventos recentes do histórico
        
        Args:
            event_type: Filtrar por tipo (None = todos)
            limit: Número máximo de eventos
        """
        with self.lock:
            events = self.event_history
            
            if event_type:
                events = [e for e in events if e.type == event_type]
            
            return events[-limit:]

# ==================== SINGLETON GLOBAL ====================

_event_bus_instance = None
_lock = threading.Lock()

def get_event_bus() -> EventBus:
    """Retorna instância singleton do EventBus"""
    global _event_bus_instance
    
    if _event_bus_instance is None:
        with _lock:
            if _event_bus_instance is None:
                _event_bus_instance = EventBus()
                _event_bus_instance.start()
    
    return _event_bus_instance

# ==================== DECORATORS ====================

def on_event(event_type: EventType, priority: int = 5):
    """
    Decorator para registrar automaticamente handlers de eventos
    
    Uso:
        @on_event(EventType.ORDER_FILLED)
        def handle_order_filled(event: OrderEvent):
            print(f"Ordem executada: {event.order_id}")
    """
    def decorator(func):
        bus = get_event_bus()
        bus.subscribe(event_type, func, priority)
        return func
    return decorator

# ==================== HELPERS ====================

def emit_order_event(event_type: EventType, order_id: str, **kwargs):
    """Helper para emitir eventos de ordem"""
    event = OrderEvent(
        type=event_type,
        order_id=order_id,
        **kwargs
    )
    get_event_bus().publish(event)

def emit_position_event(event_type: EventType, position_id: str, **kwargs):
    """Helper para emitir eventos de posição"""
    event = PositionEvent(
        type=event_type,
        position_id=position_id,
        **kwargs
    )
    get_event_bus().publish(event)

def emit_market_event(symbol: str, **kwargs):
    """Helper para emitir eventos de mercado"""
    event = MarketEvent(
        type=EventType.PRICE_UPDATE,
        symbol=symbol,
        **kwargs
    )
    get_event_bus().publish(event)