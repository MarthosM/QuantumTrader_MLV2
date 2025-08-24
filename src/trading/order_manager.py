"""
Order Manager - Sistema de gestão de ordens com Stop Loss e Take Profit
Compatível com tick size do WDO (0.5 pontos)
"""

import logging
import math
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

@dataclass
class Order:
    """Estrutura de uma ordem"""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    entry_price: float
    stop_loss: float
    take_profit: float
    status: OrderStatus
    timestamp: datetime
    filled_qty: int = 0
    filled_price: float = 0
    commission: float = 0
    is_simulated: bool = False  # Flag para indicar se é ordem simulada
    
    def is_active(self) -> bool:
        return self.status in [OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIAL]

class WDOOrderManager:
    """Gerenciador de ordens específico para WDO"""
    
    def __init__(self):
        # Configurações do WDO
        self.TICK_SIZE = 0.5  # WDO varia de 0.5 em 0.5
        self.POINT_VALUE = 10.0  # Valor de 1 ponto = R$ 10
        self.MIN_STOP_POINTS = 3.0  # Stop mínimo de 3 pontos (6 ticks)
        self.MIN_TAKE_POINTS = 5.0  # Take mínimo de 5 pontos (10 ticks)
        
        # Configurações de risco padrão
        self.DEFAULT_STOP_POINTS = 5.0  # 5 pontos = 10 ticks = R$ 50 por contrato
        self.DEFAULT_TAKE_POINTS = 10.0  # 10 pontos = 20 ticks = R$ 100 por contrato
        
        # Risk-reward ratio
        self.MIN_RISK_REWARD_RATIO = 1.5  # Take deve ser pelo menos 1.5x o stop
        
        # Ordens ativas
        self.active_orders = {}
        self.order_history = []
        
        logger.info(f"OrderManager inicializado - Tick: {self.TICK_SIZE}, "
                   f"Stop padrão: {self.DEFAULT_STOP_POINTS}pts, "
                   f"Take padrão: {self.DEFAULT_TAKE_POINTS}pts")
    
    def round_to_tick(self, price: float) -> float:
        """Arredonda preço para o tick mais próximo (0.5)"""
        return round(price / self.TICK_SIZE) * self.TICK_SIZE
    
    def calculate_stop_take_levels(self, 
                                  entry_price: float, 
                                  side: OrderSide,
                                  stop_points: Optional[float] = None,
                                  take_points: Optional[float] = None,
                                  use_percentage: bool = False) -> Tuple[float, float]:
        """
        Calcula níveis de Stop Loss e Take Profit
        
        Args:
            entry_price: Preço de entrada
            side: BUY ou SELL
            stop_points: Pontos de stop (None = usar padrão)
            take_points: Pontos de take (None = usar padrão)
            use_percentage: Se True, interpreta stop/take como percentual
            
        Returns:
            (stop_loss_price, take_profit_price)
        """
        
        # Usar valores padrão se não especificado
        if stop_points is None:
            stop_points = self.DEFAULT_STOP_POINTS
        if take_points is None:
            take_points = self.DEFAULT_TAKE_POINTS
        
        # Converter percentual para pontos se necessário
        if use_percentage:
            stop_points = entry_price * (stop_points / 100)
            take_points = entry_price * (take_points / 100)
        
        # Garantir valores mínimos
        stop_points = max(stop_points, self.MIN_STOP_POINTS)
        take_points = max(take_points, self.MIN_TAKE_POINTS)
        
        # Garantir risk-reward ratio
        if take_points < stop_points * self.MIN_RISK_REWARD_RATIO:
            take_points = stop_points * self.MIN_RISK_REWARD_RATIO
            logger.warning(f"Take ajustado para manter ratio 1:{self.MIN_RISK_REWARD_RATIO}")
        
        # Calcular níveis baseado no lado
        if side == OrderSide.BUY:
            stop_loss = entry_price - stop_points
            take_profit = entry_price + take_points
        else:  # SELL
            stop_loss = entry_price + stop_points
            take_profit = entry_price - take_points
        
        # Arredondar para tick válido
        stop_loss = self.round_to_tick(stop_loss)
        take_profit = self.round_to_tick(take_profit)
        
        # Log dos níveis calculados
        logger.info(f"Níveis calculados para {side.value} @ {entry_price:.1f}:")
        logger.info(f"  Stop Loss: {stop_loss:.1f} ({stop_points:.1f} pts)")
        logger.info(f"  Take Profit: {take_profit:.1f} ({take_points:.1f} pts)")
        logger.info(f"  Risk: R$ {stop_points * self.POINT_VALUE:.2f}")
        logger.info(f"  Reward: R$ {take_points * self.POINT_VALUE:.2f}")
        logger.info(f"  R:R Ratio: 1:{take_points/stop_points:.2f}")
        
        return stop_loss, take_profit
    
    def create_order(self,
                    symbol: str,
                    side: OrderSide,
                    quantity: int,
                    entry_price: float,
                    stop_points: Optional[float] = None,
                    take_points: Optional[float] = None,
                    confidence: float = 1.0,
                    is_simulated: bool = False) -> Order:
        """
        Cria uma nova ordem com stop e take
        
        Args:
            symbol: Símbolo (ex: WDOU25)
            side: BUY ou SELL
            quantity: Quantidade de contratos
            entry_price: Preço de entrada desejado
            stop_points: Pontos de stop loss
            take_points: Pontos de take profit
            confidence: Confiança do sinal (ajusta tamanho do stop/take)
            is_simulated: Se True, ordem é apenas simulada (não enviada ao broker)
        """
        
        # Arredondar preço de entrada
        entry_price = self.round_to_tick(entry_price)
        
        # Ajustar stop/take baseado na confiança
        if confidence > 0.8:
            # Alta confiança: stop menor, take maior
            stop_adj = 0.8
            take_adj = 1.2
        elif confidence > 0.6:
            # Confiança média: valores padrão
            stop_adj = 1.0
            take_adj = 1.0
        else:
            # Baixa confiança: stop maior, take menor
            stop_adj = 1.2
            take_adj = 0.8
        
        # Aplicar ajustes
        if stop_points:
            stop_points *= stop_adj
        if take_points:
            take_points *= take_adj
        
        # Calcular níveis
        stop_loss, take_profit = self.calculate_stop_take_levels(
            entry_price, side, stop_points, take_points
        )
        
        # Criar ordem
        order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status=OrderStatus.PENDING,
            timestamp=datetime.now(),
            is_simulated=is_simulated
        )
        
        # Adicionar à lista de ordens ativas
        self.active_orders[order_id] = order
        
        mode_str = "[SIMULADA] " if is_simulated else ""
        logger.info(f"{mode_str}Ordem criada: {order_id}")
        logger.info(f"  {side.value} {quantity} {symbol} @ {entry_price:.1f}")
        logger.info(f"  SL: {stop_loss:.1f} | TP: {take_profit:.1f}")
        
        return order
    
    def update_order_price(self, order: Order, current_price: float) -> Optional[str]:
        """
        Verifica se ordem atingiu stop ou take
        
        Returns:
            'STOP_LOSS', 'TAKE_PROFIT', ou None
        """
        if not order.is_active():
            return None
        
        # Não verificar stop/take para ordens simuladas
        if order.is_simulated:
            return None
        
        current_price = self.round_to_tick(current_price)
        
        if order.side == OrderSide.BUY:
            # Para compra: stop abaixo, take acima
            if current_price <= order.stop_loss:
                logger.warning(f"STOP LOSS atingido! Ordem {order.order_id} @ {current_price:.1f}")
                order.status = OrderStatus.FILLED
                order.filled_price = order.stop_loss
                order.filled_qty = order.quantity
                return 'STOP_LOSS'
            elif current_price >= order.take_profit:
                logger.info(f"TAKE PROFIT atingido! Ordem {order.order_id} @ {current_price:.1f}")
                order.status = OrderStatus.FILLED
                order.filled_price = order.take_profit
                order.filled_qty = order.quantity
                return 'TAKE_PROFIT'
        else:  # SELL
            # Para venda: stop acima, take abaixo
            if current_price >= order.stop_loss:
                logger.warning(f"STOP LOSS atingido! Ordem {order.order_id} @ {current_price:.1f}")
                order.status = OrderStatus.FILLED
                order.filled_price = order.stop_loss
                order.filled_qty = order.quantity
                return 'STOP_LOSS'
            elif current_price <= order.take_profit:
                logger.info(f"TAKE PROFIT atingido! Ordem {order.order_id} @ {current_price:.1f}")
                order.status = OrderStatus.FILLED
                order.filled_price = order.take_profit
                order.filled_qty = order.quantity
                return 'TAKE_PROFIT'
        
        return None
    
    def update_simulated_order(self, order: Order, current_price: float) -> Optional[str]:
        """
        Verifica resultado de ordem simulada (para backtesting)
        
        Returns:
            'STOP_LOSS', 'TAKE_PROFIT', ou None
        """
        if not order.is_active() or not order.is_simulated:
            return None
        
        current_price = self.round_to_tick(current_price)
        
        if order.side == OrderSide.BUY:
            if current_price <= order.stop_loss:
                logger.info(f"[SIMULADA] STOP LOSS atingido! Ordem {order.order_id} @ {current_price:.1f}")
                order.status = OrderStatus.FILLED
                return 'STOP_LOSS'
            elif current_price >= order.take_profit:
                logger.info(f"[SIMULADA] TAKE PROFIT atingido! Ordem {order.order_id} @ {current_price:.1f}")
                order.status = OrderStatus.FILLED
                return 'TAKE_PROFIT'
        else:  # SELL
            if current_price >= order.stop_loss:
                logger.info(f"[SIMULADA] STOP LOSS atingido! Ordem {order.order_id} @ {current_price:.1f}")
                order.status = OrderStatus.FILLED
                return 'STOP_LOSS'
            elif current_price <= order.take_profit:
                logger.info(f"[SIMULADA] TAKE PROFIT atingido! Ordem {order.order_id} @ {current_price:.1f}")
                order.status = OrderStatus.FILLED
                return 'TAKE_PROFIT'
        
        return None
    
    def apply_trailing_stop(self, order: Order, current_price: float, trailing_points: float = 5.0):
        """
        Aplica trailing stop para proteger lucros
        
        Args:
            order: Ordem ativa
            current_price: Preço atual
            trailing_points: Distância do trailing stop em pontos
        """
        if not order.is_active() or order.is_simulated:
            return
        
        current_price = self.round_to_tick(current_price)
        trailing_points = max(trailing_points, self.MIN_STOP_POINTS)
        
        if order.side == OrderSide.BUY:
            # Para compra: ajustar stop para cima se preço subiu
            new_stop = current_price - trailing_points
            new_stop = self.round_to_tick(new_stop)
            
            if new_stop > order.stop_loss and new_stop < current_price:
                old_stop = order.stop_loss
                order.stop_loss = new_stop
                logger.info(f"Trailing stop ajustado: {old_stop:.1f} -> {new_stop:.1f}")
        else:  # SELL
            # Para venda: ajustar stop para baixo se preço caiu
            new_stop = current_price + trailing_points
            new_stop = self.round_to_tick(new_stop)
            
            if new_stop < order.stop_loss and new_stop > current_price:
                old_stop = order.stop_loss
                order.stop_loss = new_stop
                logger.info(f"Trailing stop ajustado: {old_stop:.1f} -> {new_stop:.1f}")
    
    def calculate_position_size(self, 
                               account_balance: float,
                               risk_per_trade: float = 0.02,
                               stop_points: float = None) -> int:
        """
        Calcula tamanho da posição baseado em gestão de risco
        
        Args:
            account_balance: Saldo da conta
            risk_per_trade: Percentual de risco por trade (2% padrão)
            stop_points: Pontos de stop loss
            
        Returns:
            Quantidade de contratos
        """
        if stop_points is None:
            stop_points = self.DEFAULT_STOP_POINTS
        
        # Risco máximo em R$
        max_risk_value = account_balance * risk_per_trade
        
        # Risco por contrato
        risk_per_contract = stop_points * self.POINT_VALUE
        
        # Quantidade de contratos
        contracts = int(max_risk_value / risk_per_contract)
        
        # Limitar entre 1 e 10 contratos
        contracts = max(1, min(contracts, 10))
        
        logger.info(f"Position sizing:")
        logger.info(f"  Saldo: R$ {account_balance:,.2f}")
        logger.info(f"  Risco máximo: R$ {max_risk_value:.2f} ({risk_per_trade*100:.1f}%)")
        logger.info(f"  Risco/contrato: R$ {risk_per_contract:.2f}")
        logger.info(f"  Contratos: {contracts}")
        
        return contracts
    
    def get_order_summary(self, order: Order) -> Dict:
        """Retorna resumo da ordem"""
        if order.side == OrderSide.BUY:
            stop_distance = order.entry_price - order.stop_loss
            take_distance = order.take_profit - order.entry_price
        else:
            stop_distance = order.stop_loss - order.entry_price
            take_distance = order.entry_price - order.take_profit
        
        return {
            'order_id': order.order_id,
            'symbol': order.symbol,
            'side': order.side.value,
            'quantity': order.quantity,
            'entry_price': order.entry_price,
            'stop_loss': order.stop_loss,
            'take_profit': order.take_profit,
            'stop_points': stop_distance,
            'take_points': take_distance,
            'risk_value': stop_distance * order.quantity * self.POINT_VALUE,
            'reward_value': take_distance * order.quantity * self.POINT_VALUE,
            'risk_reward_ratio': take_distance / stop_distance if stop_distance > 0 else 0,
            'status': order.status.value,
            'timestamp': order.timestamp.isoformat()
        }
    
    def close_all_orders(self):
        """Fecha todas as ordens ativas"""
        for order_id, order in self.active_orders.items():
            if order.is_active():
                order.status = OrderStatus.CANCELLED
                self.order_history.append(order)
                logger.info(f"Ordem {order_id} cancelada")
        
        self.active_orders.clear()
        logger.info("Todas as ordens foram fechadas")
    
    def clear_pending_orders(self):
        """Limpa ordens pendentes do gerenciador quando posição fecha"""
        # Remover apenas ordens com status PENDING ou OPEN
        orders_to_remove = []
        for order_id, order in self.active_orders.items():
            if order.status in [OrderStatus.PENDING, OrderStatus.OPEN]:
                orders_to_remove.append(order_id)
                order.status = OrderStatus.CANCELLED
                self.order_history.append(order)
        
        for order_id in orders_to_remove:
            del self.active_orders[order_id]
            logger.info(f"Ordem pendente/aberta removida: {order_id}")
        
        if orders_to_remove:
            logger.info(f"[LIMPEZA] {len(orders_to_remove)} ordens pendentes/abertas removidas após fechamento de posição")
        
        return len(orders_to_remove)

# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Criar gerenciador
    manager = WDOOrderManager()
    
    # Preço atual do WDO
    current_price = 5645.5
    
    # Criar ordem de compra
    buy_order = manager.create_order(
        symbol="WDOU25",
        side=OrderSide.BUY,
        quantity=2,
        entry_price=current_price,
        stop_points=15,  # Stop de 15 pontos
        take_points=30,  # Take de 30 pontos
        confidence=0.75
    )
    
    print("\nResumo da ordem:")
    print(manager.get_order_summary(buy_order))
    
    # Simular movimento de preço
    print("\n--- Simulando movimento de preço ---")
    
    # Preço sobe
    new_price = 5655.0
    result = manager.update_order_price(buy_order, new_price)
    print(f"Preço: {new_price:.1f} - Status: {result or 'Em aberto'}")
    
    # Aplicar trailing stop
    manager.apply_trailing_stop(buy_order, new_price, trailing_points=10)
    
    # Calcular tamanho de posição
    print("\n--- Cálculo de Position Sizing ---")
    contracts = manager.calculate_position_size(
        account_balance=50000,  # R$ 50.000
        risk_per_trade=0.02,    # 2% de risco
        stop_points=15          # Stop de 15 pontos
    )