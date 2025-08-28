"""
Sistema de Gestão Dinâmica de Posições
Implementa trailing stop, breakeven, saídas parciais e outras estratégias
"""

from typing import Optional, Dict, List
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import threading

logger = logging.getLogger('PositionManager')

@dataclass
class ManagementStrategy:
    """Configuração de estratégia de gestão"""
    trailing_stop_enabled: bool = False
    trailing_stop_distance: float = 0.02  # 2% padrão
    breakeven_enabled: bool = True
    breakeven_threshold: float = 0.005  # 0.5% de lucro para mover stop
    partial_exit_enabled: bool = False
    partial_exit_levels: List[Dict] = None  # Lista de níveis de saída

class PositionManager:
    """
    Gerenciador ativo de posições com estratégias de gestão.
    Implementa trailing stop, saídas parciais, breakeven, etc.
    """
    
    def __init__(self, position_monitor, connection_manager):
        """
        Inicializa o gerenciador de posições
        
        Args:
            position_monitor: PositionMonitor instance
            connection_manager: ConnectionManagerOCO instance
        """
        self.monitor = position_monitor
        self.connection = connection_manager
        self.logger = logger
        
        # Estratégias de gestão por símbolo
        self.strategies: Dict[str, ManagementStrategy] = {}
        
        # Estado de gestão
        self.management_state: Dict[str, dict] = {}
        
        # Registrar callbacks com o monitor
        self.monitor.register_position_callback(self._on_position_event)
        
        # Thread de gestão
        self.management_thread = None
        self.management_active = False
        self.management_interval = 2.0  # Verificar a cada 2 segundos
        
        # Mutex para thread safety
        self.management_lock = threading.Lock()
        
        logger.info("[PositionManager] Inicializado")
    
    def _on_position_event(self, event_type: str, position, *args):
        """Callback para eventos de posição"""
        
        if event_type == 'position_opened':
            self._on_position_opened(position)
            
        elif event_type == 'position_closed':
            reason = args[0] if args else 'unknown'
            self._on_position_closed(position, reason)
            
        elif event_type == 'position_updated':
            self._on_position_updated(position)
    
    def _on_position_opened(self, position):
        """Tratamento quando posição é aberta"""
        
        self.logger.info(f"[PositionManager] Posição aberta: {position.symbol} {position.side} @ {position.entry_price}")
        
        with self.management_lock:
            # Inicializar estado de gestão
            self.management_state[position.symbol] = {
                'breakeven_moved': False,
                'partial_exits': [],
                'trailing_stop_active': False,
                'last_trailing_update': None,
                'highest_price': position.entry_price if position.side == 'BUY' else float('inf'),
                'lowest_price': position.entry_price if position.side == 'SELL' else 0,
                'original_stop': position.stop_price,
                'current_stop': position.stop_price
            }
            
            # Aplicar estratégia padrão se não houver específica
            if position.symbol not in self.strategies:
                self.strategies[position.symbol] = ManagementStrategy()
                self.logger.info(f"[PositionManager] Usando estratégia padrão para {position.symbol}")
    
    def _on_position_closed(self, position, reason: str):
        """Tratamento quando posição é fechada"""
        
        self.logger.info(f"[PositionManager] Posição fechada: {position.symbol} "
                        f"P&L: {position.pnl:.2f} ({position.pnl_percentage:.2f}%) "
                        f"Motivo: {reason}")
        
        with self.management_lock:
            # Limpar estado de gestão
            if position.symbol in self.management_state:
                del self.management_state[position.symbol]
    
    def _on_position_updated(self, position):
        """Tratamento quando posição é atualizada"""
        
        # Verificar condições para gestão dinâmica
        self._check_breakeven_condition(position)
        self._check_trailing_stop_condition(position)
        
        if self.strategies.get(position.symbol, ManagementStrategy()).partial_exit_enabled:
            self._check_partial_exit_condition(position)
    
    def _check_breakeven_condition(self, position):
        """Verifica e move stop para breakeven quando apropriado"""
        
        strategy = self.strategies.get(position.symbol)
        if not strategy or not strategy.breakeven_enabled:
            return
        
        with self.management_lock:
            state = self.management_state.get(position.symbol, {})
            if state.get('breakeven_moved', False):
                return
            
            # Calcular distância do preço de entrada
            profit_percentage = 0
            
            if position.side == 'BUY':
                if position.entry_price > 0:
                    profit_percentage = (position.current_price - position.entry_price) / position.entry_price
                
                if profit_percentage >= strategy.breakeven_threshold:
                    # Mover stop para breakeven + pequeno lucro
                    new_stop = position.entry_price + 1.0  # +1 ponto de lucro
                    
                    if self._modify_stop_order(position, new_stop):
                        state['breakeven_moved'] = True
                        state['current_stop'] = new_stop
                        self.logger.info(f"[BREAKEVEN] Stop movido para breakeven: {position.symbol} -> {new_stop:.2f}")
                        
            else:  # SELL
                if position.entry_price > 0:
                    profit_percentage = (position.entry_price - position.current_price) / position.entry_price
                
                if profit_percentage >= strategy.breakeven_threshold:
                    new_stop = position.entry_price - 1.0  # -1 ponto de lucro
                    
                    if self._modify_stop_order(position, new_stop):
                        state['breakeven_moved'] = True
                        state['current_stop'] = new_stop
                        self.logger.info(f"[BREAKEVEN] Stop movido para breakeven: {position.symbol} -> {new_stop:.2f}")
    
    def _check_trailing_stop_condition(self, position):
        """Implementa trailing stop dinâmico"""
        
        strategy = self.strategies.get(position.symbol)
        if not strategy or not strategy.trailing_stop_enabled:
            return
        
        with self.management_lock:
            state = self.management_state.get(position.symbol, {})
            
            # Trailing stop para posição comprada
            if position.side == 'BUY':
                # Atualizar maior preço
                if position.current_price > state.get('highest_price', 0):
                    state['highest_price'] = position.current_price
                    
                    # Calcular novo stop (X% abaixo do máximo)
                    trailing_distance = position.current_price * strategy.trailing_stop_distance
                    new_stop = position.current_price - trailing_distance
                    
                    # Só mover se for maior que stop atual
                    current_stop = state.get('current_stop', position.stop_price)
                    if new_stop > current_stop:
                        if self._modify_stop_order(position, new_stop):
                            state['current_stop'] = new_stop
                            state['last_trailing_update'] = datetime.now()
                            self.logger.info(f"[TRAILING] Stop atualizado: {position.symbol} -> {new_stop:.2f}")
                            
            else:  # SELL
                # Atualizar menor preço
                if state.get('lowest_price', float('inf')) == float('inf') or position.current_price < state['lowest_price']:
                    state['lowest_price'] = position.current_price
                    
                    trailing_distance = position.current_price * strategy.trailing_stop_distance
                    new_stop = position.current_price + trailing_distance
                    
                    current_stop = state.get('current_stop', position.stop_price)
                    if new_stop < current_stop:
                        if self._modify_stop_order(position, new_stop):
                            state['current_stop'] = new_stop
                            state['last_trailing_update'] = datetime.now()
                            self.logger.info(f"[TRAILING] Stop atualizado: {position.symbol} -> {new_stop:.2f}")
    
    def _check_partial_exit_condition(self, position):
        """Verifica condições para saída parcial"""
        
        strategy = self.strategies.get(position.symbol)
        if not strategy or not strategy.partial_exit_enabled:
            return
        
        with self.management_lock:
            state = self.management_state.get(position.symbol, {})
            partial_exits = state.get('partial_exits', [])
            
            # Níveis padrão de saída parcial
            exit_levels = strategy.partial_exit_levels or [
                {'profit_pct': 0.01, 'exit_pct': 0.33},  # 1% lucro, sair 33%
                {'profit_pct': 0.02, 'exit_pct': 0.50},  # 2% lucro, sair 50% do restante
                {'profit_pct': 0.03, 'exit_pct': 1.00},  # 3% lucro, sair tudo
            ]
            
            if position.pnl_percentage <= 0:
                return  # Só fazer saída parcial em lucro
            
            current_profit_pct = position.pnl_percentage / 100
            
            for i, level in enumerate(exit_levels):
                # Verificar se este nível já foi executado
                if any(exit['level'] == i for exit in partial_exits):
                    continue
                    
                if current_profit_pct >= level['profit_pct']:
                    # Calcular quantidade para saída
                    remaining_qty = position.quantity
                    for prev_exit in partial_exits:
                        remaining_qty -= prev_exit['quantity']
                    
                    exit_qty = int(remaining_qty * level['exit_pct'])
                    
                    if exit_qty > 0:
                        if self._execute_partial_exit(position, exit_qty):
                            partial_exits.append({
                                'level': i,
                                'quantity': exit_qty,
                                'price': position.current_price,
                                'time': datetime.now()
                            })
                            state['partial_exits'] = partial_exits
                            self.logger.info(f"[PARTIAL EXIT] Nível {i+1}: {exit_qty} contratos @ {position.current_price:.2f}")
    
    def _modify_stop_order(self, position, new_stop_price: float) -> bool:
        """
        Modifica ordem de stop loss
        
        Args:
            position: PositionInfo object
            new_stop_price: Novo preço de stop
            
        Returns:
            bool: True se modificação foi bem sucedida
        """
        try:
            # Verificar se connection manager tem método de modificação
            if hasattr(self.connection, 'modify_stop_order'):
                # Buscar ID da ordem de stop
                stop_order_id = position.orders.get('stop_order') or position.orders.get('stop')
                
                if stop_order_id:
                    success = self.connection.modify_stop_order(stop_order_id, new_stop_price)
                    if success:
                        position.stop_price = new_stop_price
                        return True
                    else:
                        self.logger.warning(f"[PositionManager] Falha ao modificar stop: ordem {stop_order_id}")
                else:
                    self.logger.warning(f"[PositionManager] ID da ordem de stop não encontrado para {position.symbol}")
            else:
                self.logger.debug("[PositionManager] Modificação de stop não implementada no connection manager")
                
        except Exception as e:
            self.logger.error(f"[PositionManager] Erro ao modificar stop: {e}")
        
        return False
    
    def _execute_partial_exit(self, position, quantity: int) -> bool:
        """
        Executa saída parcial da posição
        
        Args:
            position: PositionInfo object
            quantity: Quantidade a sair
            
        Returns:
            bool: True se saída foi executada
        """
        try:
            # Verificar se connection manager suporta saída parcial
            if hasattr(self.connection, 'send_partial_exit'):
                success = self.connection.send_partial_exit(
                    symbol=position.symbol,
                    side='SELL' if position.side == 'BUY' else 'BUY',
                    quantity=quantity
                )
                if success:
                    self.logger.info(f"[PositionManager] Saída parcial executada: {quantity} contratos")
                    return True
            else:
                self.logger.debug("[PositionManager] Saída parcial não implementada no connection manager")
                
        except Exception as e:
            self.logger.error(f"[PositionManager] Erro na saída parcial: {e}")
        
        return False
    
    def apply_strategy(self, symbol: str, strategy: ManagementStrategy):
        """
        Aplica estratégia de gestão a uma posição
        
        Args:
            symbol: Símbolo do ativo
            strategy: Estratégia de gestão
        """
        with self.management_lock:
            self.strategies[symbol] = strategy
            self.logger.info(f"[PositionManager] Estratégia aplicada para {symbol}:")
            self.logger.info(f"  Trailing Stop: {strategy.trailing_stop_enabled} ({strategy.trailing_stop_distance*100:.1f}%)")
            self.logger.info(f"  Breakeven: {strategy.breakeven_enabled} ({strategy.breakeven_threshold*100:.1f}%)")
            self.logger.info(f"  Partial Exit: {strategy.partial_exit_enabled}")
            
            # Se posição já existe, começar a aplicar imediatamente
            position = self.monitor.get_position(symbol)
            if position and position.status.value == 'open':
                self._on_position_updated(position)
    
    def start_management(self):
        """Inicia thread de gestão ativa"""
        if self.management_active:
            self.logger.warning("[PositionManager] Já está gerenciando")
            return
        
        self.management_active = True
        self.management_thread = threading.Thread(target=self._management_loop, daemon=True)
        self.management_thread.start()
        self.logger.info("[PositionManager] Gestão ativa iniciada")
    
    def stop_management(self):
        """Para thread de gestão"""
        self.management_active = False
        if self.management_thread:
            self.management_thread.join(timeout=2)
        self.logger.info("[PositionManager] Gestão ativa parada")
    
    def _management_loop(self):
        """Loop de gestão ativa"""
        while self.management_active:
            try:
                # Obter posições abertas
                open_positions = self.monitor.get_open_positions()
                
                for position in open_positions:
                    # Aplicar estratégias de gestão
                    self._on_position_updated(position)
                
                import time
                time.sleep(self.management_interval)
                
            except Exception as e:
                self.logger.error(f"[PositionManager] Erro no loop de gestão: {e}")
                import time
                time.sleep(1)
    
    def get_management_status(self, symbol: str) -> Optional[dict]:
        """
        Retorna status de gestão de uma posição
        
        Args:
            symbol: Símbolo do ativo
            
        Returns:
            dict: Status de gestão ou None
        """
        with self.management_lock:
            return self.management_state.get(symbol)
    
    def reset_management(self, symbol: str):
        """
        Reseta estado de gestão de uma posição
        
        Args:
            symbol: Símbolo do ativo
        """
        with self.management_lock:
            if symbol in self.management_state:
                del self.management_state[symbol]
                self.logger.info(f"[PositionManager] Estado resetado para {symbol}")