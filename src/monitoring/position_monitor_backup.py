"""
Sistema de Monitoramento de Posições em Tempo Real
Monitora o status de posições abertas e suas ordens relacionadas
"""

import threading
import time
from datetime import datetime
from typing import Dict, Optional, List, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import ctypes
from ctypes import c_int, c_double, c_bool, POINTER, Structure, c_wchar_p, c_longlong, c_wchar
import logging
import json
from pathlib import Path

logger = logging.getLogger('PositionMonitor')

class PositionStatus(Enum):
    """Status possíveis da posição"""
    NO_POSITION = "no_position"
    OPENING = "opening"  # Ordem enviada, aguardando execução
    OPEN = "open"  # Posição aberta
    CLOSING = "closing"  # Ordem de fechamento enviada
    CLOSED = "closed"  # Posição fechada
    PARTIALLY_FILLED = "partially_filled"

@dataclass
class PositionInfo:
    """Informações detalhadas da posição"""
    symbol: str
    side: str  # 'BUY' ou 'SELL'
    quantity: int
    entry_price: float
    current_price: float
    stop_price: float
    take_price: float
    pnl: float
    pnl_percentage: float
    status: PositionStatus
    open_time: datetime
    last_update: datetime
    orders: Dict[str, any]  # IDs das ordens relacionadas
    position_id: str = ""  # ID único da posição

class PositionMonitor:
    """
    Sistema principal de monitoramento de posições.
    Monitora em tempo real o status de posições abertas e suas ordens relacionadas.
    """
    
    def __init__(self, connection_manager, callback_manager=None):
        """
        Inicializa o monitor de posições
        
        Args:
            connection_manager: ConnectionManagerOCO instance
            callback_manager: Opcional gerenciador de callbacks
        """
        self.connection = connection_manager
        self.callback_manager = callback_manager
        
        # Estado das posições
        self.positions: Dict[str, PositionInfo] = {}
        self.active_orders: Dict[str, dict] = {}
        
        # Callbacks personalizados
        self.position_callbacks: List[Callable] = []
        
        # Thread de monitoramento
        self.monitoring_thread = None
        self.monitoring_active = False
        self.monitor_interval = 1.0  # 1 segundo
        
        # Mutex para thread safety
        self.position_lock = threading.Lock()
        
        # Arquivo de status
        self.status_file = Path("data/monitor/position_status.json")
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Configurar callbacks se possível
        self._setup_callbacks()
        
        logger.info("[PositionMonitor] Inicializado")
    
    def _setup_callbacks(self):
        """Configura callbacks com o connection manager"""
        try:
            # Se connection manager suporta callbacks, registrar
            if hasattr(self.connection, 'register_order_callback'):
                self.connection.register_order_callback(self._on_order_change)
                logger.info("[PositionMonitor] Callback de ordem registrado")
            
            # Registrar com OCO Monitor se disponível
            if hasattr(self.connection, 'oco_monitor'):
                # OCO Monitor já existe, vamos usar seus eventos
                logger.info("[PositionMonitor] OCO Monitor detectado")
                
        except Exception as e:
            logger.warning(f"[PositionMonitor] Não foi possível registrar callbacks: {e}")
    
    def _on_order_change(self, order_info: dict):
        """
        Callback quando uma ordem muda de status
        
        Args:
            order_info: Informações da ordem
        """
        with self.position_lock:
            try:
                order_id = order_info.get('order_id', '')
                status = order_info.get('status', '')
                
                # Obter símbolo dinamicamente
                symbol = order_info.get('symbol')
                if not symbol:
                    if hasattr(self.connection, 'symbol'):
                        symbol = self.connection.symbol
                    else:
                        # Usar símbolo atualizado baseado no mês
                        try:
                            from src.utils.symbol_manager import SymbolManager
                            symbol = SymbolManager.get_current_wdo_symbol()
                        except:
                            symbol = 'WDOU25'  # Fallback
                
                logger.debug(f"[PositionMonitor] Ordem {order_id} mudou para {status}")
                
                # Atualizar informações da ordem
                if order_id in self.active_orders:
                    self.active_orders[order_id].update(order_info)
                    
                    # Verificar mudanças importantes
                    if status in ["Filled", "PartiallyFilled"]:
                        self._handle_order_filled(order_id, order_info)
                    elif status in ["Canceled", "Rejected", "Expired"]:
                        self._handle_order_canceled(order_id, order_info)
                        
            except Exception as e:
                logger.error(f"[PositionMonitor] Erro no callback de ordem: {e}")
    
    def _handle_order_filled(self, order_id: str, order_info: dict):
        """Trata ordem executada"""
        try:
            # Obter símbolo dinamicamente
            symbol = order_info.get('symbol')
            if not symbol:
                try:
                    from src.utils.symbol_manager import SymbolManager
                    symbol = SymbolManager.get_current_wdo_symbol()
                except:
                    symbol = 'WDOU25'
            order_type = order_info.get('order_type', '')
            avg_price = order_info.get('avg_price', 0)
            
            # Se é ordem principal (entrada)
            if order_type == 'main':
                if symbol not in self.positions:
                    # Nova posição aberta
                    self.positions[symbol] = PositionInfo(
                        symbol=symbol,
                        side=order_info.get('side', 'BUY'),
                        quantity=order_info.get('quantity', 1),
                        entry_price=avg_price,
                        current_price=avg_price,
                        stop_price=order_info.get('stop_price', 0),
                        take_price=order_info.get('take_price', 0),
                        pnl=0,
                        pnl_percentage=0,
                        status=PositionStatus.OPEN,
                        open_time=datetime.now(),
                        last_update=datetime.now(),
                        orders={'main': order_id},
                        position_id=order_info.get('position_id', f"POS_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                    )
                    self._trigger_position_opened(self.positions[symbol])
                    logger.info(f"[PositionMonitor] Nova posição aberta: {symbol}")
                    
            # Se é ordem de stop ou take (saída)
            elif order_type in ['stop', 'take']:
                if symbol in self.positions:
                    # Posição fechada
                    position = self.positions[symbol]
                    position.status = PositionStatus.CLOSED
                    
                    # Calcular P&L final
                    exit_price = avg_price
                    if position.side == 'BUY':
                        position.pnl = (exit_price - position.entry_price) * position.quantity
                    else:
                        position.pnl = (position.entry_price - exit_price) * position.quantity
                    
                    position.pnl_percentage = (position.pnl / (position.entry_price * position.quantity)) * 100
                    
                    self._trigger_position_closed(position, order_type)
                    logger.info(f"[PositionMonitor] Posição fechada por {order_type}: P&L = {position.pnl:.2f}")
                    
                    # Remover posição do tracking
                    del self.positions[symbol]
                    
        except Exception as e:
            logger.error(f"[PositionMonitor] Erro ao processar ordem executada: {e}")
    
    def _handle_order_canceled(self, order_id: str, order_info: dict):
        """Trata ordem cancelada"""
        try:
            logger.info(f"[PositionMonitor] Ordem {order_id} cancelada")
            # Remover ordem do tracking se necessário
            if order_id in self.active_orders:
                del self.active_orders[order_id]
        except Exception as e:
            logger.error(f"[PositionMonitor] Erro ao processar ordem cancelada: {e}")
    
    def start_monitoring(self):
        """Inicia monitoramento contínuo de posições"""
        if self.monitoring_active:
            logger.warning("[PositionMonitor] Já está monitorando")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("[PositionMonitor] Monitoramento iniciado")
    
    def stop_monitoring(self):
        """Para o monitoramento"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2)
        logger.info("[PositionMonitor] Monitoramento parado")
    
    def _monitoring_loop(self):
        """Loop principal de monitoramento"""
        while self.monitoring_active:
            try:
                # Atualizar posições
                self._update_positions_from_connection()
                
                # Atualizar P&L
                self._update_pnl()
                
                # Salvar status
                self._save_status()
                
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"[PositionMonitor] Erro no loop: {e}")
                time.sleep(1)
    
    def _update_positions_from_connection(self):
        """Atualiza posições consultando o connection manager"""
        with self.position_lock:
            try:
                # Verificar com o connection manager se há posição
                if hasattr(self.connection, 'check_position_exists'):
                    # Obter símbolo atualizado
                    try:
                        from src.utils.symbol_manager import SymbolManager
                        default_symbol = SymbolManager.get_current_wdo_symbol()
                    except:
                        default_symbol = 'WDOU25'
                    
                    symbol = getattr(self.connection, 'symbol', default_symbol)
                    has_position, quantity, side = self.connection.check_position_exists(symbol)
                    
                    # Se connection manager reporta posição mas não temos registro
                    if has_position and not self.positions:
                        # Criar registro de posição detectada
                        current_price = getattr(self.connection, 'last_price', 0)
                        
                        self.positions[symbol] = PositionInfo(
                            symbol=symbol,
                            side=side,
                            quantity=quantity,
                            entry_price=current_price,  # Não sabemos o preço real de entrada
                            current_price=current_price,
                            stop_price=0,
                            take_price=0,
                            pnl=0,
                            pnl_percentage=0,
                            status=PositionStatus.OPEN,
                            open_time=datetime.now(),
                            last_update=datetime.now(),
                            orders={},
                            position_id=f"DETECTED_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        )
                        logger.warning(f"[PositionMonitor] Posição detectada sem registro: {quantity} {side}")
                    
                    # Se não há posição mas temos registro
                    elif not has_position and self.positions:
                        for symbol in list(self.positions.keys()):
                            position = self.positions[symbol]
                            if position.status == PositionStatus.OPEN:
                                # Posição foi fechada
                                position.status = PositionStatus.CLOSED
                                self._trigger_position_closed(position, "detected_closure")
                                del self.positions[symbol]
                                logger.info(f"[PositionMonitor] Fechamento detectado: {symbol}")
                
                # Verificar com OCO Monitor
                if hasattr(self.connection, 'oco_monitor'):
                    oco_groups = getattr(self.connection.oco_monitor, 'oco_groups', {})
                    
                    # Se há grupos OCO ativos, provavelmente há posição
                    active_oco_groups = [g for g in oco_groups.values() if g.get('active')]
                    
                    if active_oco_groups and not self.positions:
                        logger.debug(f"[PositionMonitor] {len(active_oco_groups)} grupos OCO ativos mas sem posição registrada")
                        # OCO indica posição, vamos confiar nisso
                        # Mas não criar registro falso, apenas logar
                        
            except Exception as e:
                logger.error(f"[PositionMonitor] Erro ao atualizar posições: {e}")
    
    def _update_pnl(self):
        """Atualiza P&L das posições abertas"""
        with self.position_lock:
            try:
                for symbol, position in self.positions.items():
                    if position.status != PositionStatus.OPEN:
                        continue
                    
                    # Obter preço atual
                    current_price = self._get_current_price(symbol)
                    if current_price and current_price > 0:
                        position.current_price = current_price
                        
                        # Calcular P&L
                        if position.side == 'BUY':
                            position.pnl = (current_price - position.entry_price) * position.quantity
                        else:
                            position.pnl = (position.entry_price - current_price) * position.quantity
                        
                        if position.entry_price > 0:
                            position.pnl_percentage = (position.pnl / (position.entry_price * position.quantity)) * 100
                        
                        position.last_update = datetime.now()
                        
            except Exception as e:
                logger.error(f"[PositionMonitor] Erro ao atualizar P&L: {e}")
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Obtém preço atual do ativo"""
        try:
            # Tentar obter do connection manager
            if hasattr(self.connection, 'last_price'):
                price = self.connection.last_price
                if price > 0:
                    return price
            
            # Tentar obter do book
            if hasattr(self.connection, 'best_bid') and hasattr(self.connection, 'best_ask'):
                bid = self.connection.best_bid
                ask = self.connection.best_ask
                if bid > 0 and ask > 0:
                    return (bid + ask) / 2
            
            return None
            
        except Exception as e:
            logger.error(f"[PositionMonitor] Erro ao obter preço: {e}")
            return None
    
    def _save_status(self):
        """Salva status atual em arquivo JSON"""
        try:
            status = {
                'timestamp': datetime.now().isoformat(),
                'has_position': len(self.positions) > 0,
                'positions': []
            }
            
            for symbol, pos in self.positions.items():
                status['positions'].append({
                    'symbol': pos.symbol,
                    'side': pos.side,
                    'quantity': pos.quantity,
                    'entry_price': pos.entry_price,
                    'current_price': pos.current_price,
                    'pnl': pos.pnl,
                    'pnl_percentage': pos.pnl_percentage,
                    'status': pos.status.value,
                    'position_id': pos.position_id,
                    'open_time': pos.open_time.isoformat() if pos.open_time else None
                })
            
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
                
        except Exception as e:
            logger.error(f"[PositionMonitor] Erro ao salvar status: {e}")
    
    def register_position_callback(self, callback: Callable):
        """Registra callback para eventos de posição"""
        self.position_callbacks.append(callback)
        logger.debug(f"[PositionMonitor] Callback registrado: {callback.__name__}")
    
    def _trigger_position_opened(self, position: PositionInfo):
        """Dispara evento de posição aberta"""
        for callback in self.position_callbacks:
            try:
                callback('position_opened', position)
            except Exception as e:
                logger.error(f"[PositionMonitor] Erro em callback: {e}")
    
    def _trigger_position_closed(self, position: PositionInfo, reason: str):
        """Dispara evento de posição fechada"""
        for callback in self.position_callbacks:
            try:
                callback('position_closed', position, reason)
            except Exception as e:
                logger.error(f"[PositionMonitor] Erro em callback: {e}")
    
    def get_open_positions(self) -> List[PositionInfo]:
        """Retorna lista de posições abertas"""
        with self.position_lock:
            return [p for p in self.positions.values() 
                   if p.status in [PositionStatus.OPEN, PositionStatus.PARTIALLY_FILLED]]
    
    def get_position(self, symbol: str) -> Optional[PositionInfo]:
        """Retorna informações de uma posição específica"""
        with self.position_lock:
            return self.positions.get(symbol)
    
    def has_open_position(self) -> bool:
        """Verifica se há alguma posição aberta"""
        return len(self.get_open_positions()) > 0
    
    def register_new_order(self, order_id: str, order_info: dict):
        """
        Registra nova ordem para monitoramento
        
        Args:
            order_id: ID da ordem
            order_info: Informações da ordem (symbol, side, type, etc)
        """
        with self.position_lock:
            self.active_orders[order_id] = order_info
            logger.debug(f"[PositionMonitor] Ordem {order_id} registrada para monitoramento")
    
    def register_position(self, position_id: str, order_ids: dict, details: dict):
        """
        Registra nova posição com suas ordens
        
        Args:
            position_id: ID único da posição
            order_ids: Dict com IDs das ordens (main, stop, take)
            details: Detalhes da posição (symbol, side, quantity, prices, etc)
        """
        with self.position_lock:
            try:
                symbol = details.get('symbol', 'WDOU25')
                
                # Criar nova posição
                self.positions[symbol] = PositionInfo(
                    symbol=symbol,
                    side=details.get('side', 'BUY'),
                    quantity=details.get('quantity', 1),
                    entry_price=details.get('entry_price', 0),
                    current_price=details.get('entry_price', 0),
                    stop_price=details.get('stop_price', 0),
                    take_price=details.get('take_price', 0),
                    pnl=0,
                    pnl_percentage=0,
                    status=PositionStatus.OPENING,
                    open_time=datetime.now(),
                    last_update=datetime.now(),
                    orders=order_ids,
                    position_id=position_id
                )
                
                # Registrar ordens
                for order_type, order_id in order_ids.items():
                    if order_id:
                        self.active_orders[str(order_id)] = {
                            'symbol': symbol,
                            'order_type': order_type,
                            'position_id': position_id,
                            **details
                        }
                
                logger.info(f"[PositionMonitor] Posição {position_id} registrada com {len(order_ids)} ordens")
                
            except Exception as e:
                logger.error(f"[PositionMonitor] Erro ao registrar posição: {e}")
    
    def update_position_status(self, symbol: str, status: PositionStatus):
        """Atualiza status de uma posição"""
        with self.position_lock:
            if symbol in self.positions:
                old_status = self.positions[symbol].status
                self.positions[symbol].status = status
                self.positions[symbol].last_update = datetime.now()
                logger.info(f"[PositionMonitor] {symbol}: {old_status.value} -> {status.value}")
    
    def close_position(self, symbol: str, exit_price: float, reason: str = "manual"):
        """
        Marca posição como fechada
        
        Args:
            symbol: Símbolo da posição
            exit_price: Preço de saída
            reason: Motivo do fechamento
        """
        with self.position_lock:
            if symbol in self.positions:
                position = self.positions[symbol]
                position.status = PositionStatus.CLOSED
                
                # Calcular P&L final
                if position.side == 'BUY':
                    position.pnl = (exit_price - position.entry_price) * position.quantity
                else:
                    position.pnl = (position.entry_price - exit_price) * position.quantity
                
                if position.entry_price > 0:
                    position.pnl_percentage = (position.pnl / (position.entry_price * position.quantity)) * 100
                
                self._trigger_position_closed(position, reason)
                
                # Remover do tracking
                del self.positions[symbol]
                logger.info(f"[PositionMonitor] Posição {symbol} fechada: P&L = {position.pnl:.2f} ({position.pnl_percentage:.2f}%)")