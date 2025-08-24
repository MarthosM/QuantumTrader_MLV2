"""
Adaptive Risk Manager - Gestão de Risco Adaptativa baseada em Volatilidade
Ajusta stop loss e take profit dinamicamente baseado nas condições do mercado
"""

import numpy as np
from typing import Tuple, Dict, Optional
from dataclasses import dataclass
import logging
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class MarketCondition:
    """Condições atuais do mercado"""
    volatility: float           # Volatilidade atual (ATR)
    volatility_regime: str      # 'LOW', 'NORMAL', 'HIGH'
    trend_strength: float       # Força da tendência (0-1)
    market_phase: str          # 'TRENDING', 'LATERAL', 'BREAKOUT'
    support: float             # Nível de suporte próximo
    resistance: float          # Nível de resistência próximo
    avg_range: float           # Range médio das últimas N candles
    
class AdaptiveRiskManager:
    """
    Gerenciador de risco adaptativo que ajusta stop/take baseado em:
    - Volatilidade atual (ATR)
    - Regime de mercado (lateral/tendência)
    - Níveis de suporte/resistência
    - Horário do dia
    """
    
    def __init__(self, symbol: str = "WDOU25"):
        self.symbol = symbol
        self.tick_size = 0.5
        self.tick_value = 10.0  # R$ por ponto
        
        # Buffers de dados
        self.price_buffer = deque(maxlen=100)
        self.high_buffer = deque(maxlen=100)
        self.low_buffer = deque(maxlen=100)
        self.volume_buffer = deque(maxlen=100)
        
        # Configurações por regime de volatilidade
        self.volatility_configs = {
            'LOW': {
                'stop_points': 5.0,     # Stop fixo de 5 pontos
                'take_multiplier': 1.5,  # Take = Stop * 1.5 (7.5 pts)
                'max_stop': 8.0,
                'max_take': 12.0
            },
            'NORMAL': {
                'stop_atr_mult': 0.8,   # Stop = ATR * 0.8
                'take_atr_mult': 1.5,   # Take = ATR * 1.5
                'min_stop': 6.0,
                'max_stop': 12.0,
                'min_take': 10.0,
                'max_take': 20.0
            },
            'HIGH': {
                'stop_atr_mult': 1.0,   # Stop = ATR * 1.0
                'take_atr_mult': 2.0,   # Take = ATR * 2.0
                'min_stop': 10.0,
                'max_stop': 20.0,
                'min_take': 15.0,
                'max_take': 40.0
            }
        }
        
        # Ajustes por horário
        self.time_adjustments = {
            'opening': {'stop_mult': 1.2, 'take_mult': 1.2},  # 09:00-10:00
            'morning': {'stop_mult': 1.0, 'take_mult': 1.0},  # 10:00-12:00
            'lunch': {'stop_mult': 0.8, 'take_mult': 0.8},    # 12:00-14:00
            'afternoon': {'stop_mult': 1.0, 'take_mult': 1.0}, # 14:00-17:00
            'closing': {'stop_mult': 1.2, 'take_mult': 0.9}   # 17:00-18:00
        }
        
        logger.info(f"AdaptiveRiskManager inicializado para {symbol}")
    
    def update_buffers(self, price: float, high: float = None, 
                       low: float = None, volume: float = None):
        """Atualiza buffers com novos dados"""
        self.price_buffer.append(price)
        if high:
            self.high_buffer.append(high)
        if low:
            self.low_buffer.append(low)
        if volume:
            self.volume_buffer.append(volume)
    
    def calculate_atr(self, period: int = 14) -> float:
        """Calcula Average True Range"""
        if len(self.high_buffer) < period or len(self.low_buffer) < period:
            # Se não temos dados suficientes, usar range fixo
            if len(self.price_buffer) >= 2:
                prices = list(self.price_buffer)
                return np.std(prices) * 2.0  # Aproximação
            return 10.0  # Default para WDO
        
        # Calcular True Range
        tr_values = []
        for i in range(1, min(period, len(self.high_buffer))):
            high = self.high_buffer[-i]
            low = self.low_buffer[-i]
            prev_close = self.price_buffer[-i-1] if i < len(self.price_buffer) else high
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_values.append(tr)
        
        return np.mean(tr_values) if tr_values else 10.0
    
    def detect_volatility_regime(self, atr: float) -> str:
        """Detecta regime de volatilidade atual"""
        # Thresholds específicos para WDO
        if atr < 8.0:
            return 'LOW'
        elif atr < 15.0:
            return 'NORMAL'
        else:
            return 'HIGH'
    
    def detect_market_phase(self) -> str:
        """Detecta fase do mercado (lateral/tendência/rompimento)"""
        if len(self.price_buffer) < 20:
            return 'LATERAL'
        
        prices = list(self.price_buffer)[-20:]
        
        # Calcular inclinação da regressão linear
        x = np.arange(len(prices))
        slope = np.polyfit(x, prices, 1)[0]
        
        # Calcular desvio padrão
        std = np.std(prices)
        
        # Calcular ADX simplificado (força da tendência)
        price_changes = np.diff(prices)
        directional_movement = sum(1 for p in price_changes if p > 0) / len(price_changes)
        
        # Classificar mercado
        if abs(slope) < std * 0.1:  # Inclinação baixa
            return 'LATERAL'
        elif abs(slope) > std * 0.3:  # Inclinação alta
            return 'BREAKOUT'
        else:
            return 'TRENDING'
    
    def find_support_resistance(self, lookback: int = 50) -> Tuple[float, float]:
        """Encontra níveis de suporte e resistência próximos"""
        if len(self.price_buffer) < 10:
            current = self.price_buffer[-1] if self.price_buffer else 5400.0
            return current - 20.0, current + 20.0
        
        prices = list(self.price_buffer)[-min(lookback, len(self.price_buffer)):]
        current = prices[-1]
        
        # Encontrar mínimos e máximos locais
        lows = []
        highs = []
        
        for i in range(2, len(prices) - 2):
            if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                lows.append(prices[i])
            if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                highs.append(prices[i])
        
        # Suporte: menor low abaixo do preço atual
        support_candidates = [p for p in lows if p < current]
        support = max(support_candidates) if support_candidates else current - 15.0
        
        # Resistência: maior high acima do preço atual
        resistance_candidates = [p for p in highs if p > current]
        resistance = min(resistance_candidates) if resistance_candidates else current + 15.0
        
        return support, resistance
    
    def get_time_period(self) -> str:
        """Retorna período do dia para ajustes"""
        now = datetime.now()
        hour = now.hour
        
        if 9 <= hour < 10:
            return 'opening'
        elif 10 <= hour < 12:
            return 'morning'
        elif 12 <= hour < 14:
            return 'lunch'
        elif 14 <= hour < 17:
            return 'afternoon'
        elif 17 <= hour < 18:
            return 'closing'
        else:
            return 'morning'  # Default
    
    def calculate_adaptive_levels(self, entry_price: float, side: str,
                                 confidence: float = 0.6) -> Dict[str, float]:
        """
        Calcula níveis adaptativos de stop loss e take profit
        
        Args:
            entry_price: Preço de entrada
            side: 'BUY' ou 'SELL'
            confidence: Confiança do sinal (0-1)
            
        Returns:
            Dict com stop_loss, take_profit e métricas
        """
        # Calcular indicadores de mercado
        atr = self.calculate_atr()
        volatility_regime = self.detect_volatility_regime(atr)
        market_phase = self.detect_market_phase()
        support, resistance = self.find_support_resistance()
        time_period = self.get_time_period()
        
        logger.info(f"Condições de mercado: ATR={atr:.1f}, Regime={volatility_regime}, "
                   f"Fase={market_phase}, Período={time_period}")
        
        # Obter configuração base para o regime
        config = self.volatility_configs[volatility_regime]
        
        # Calcular stop e take base
        if volatility_regime == 'LOW':
            # Em baixa volatilidade, usar valores fixos
            stop_points = config['stop_points']
            take_points = stop_points * config['take_multiplier']
            
            # Em mercado lateral, reduzir ainda mais
            if market_phase == 'LATERAL':
                stop_points = 5.0  # Stop fixo de 5 pontos
                take_points = 8.0  # Take fixo de 8 pontos
                
        else:
            # Em volatilidade normal/alta, usar ATR
            stop_points = atr * config['stop_atr_mult']
            take_points = atr * config['take_atr_mult']
            
            # Aplicar limites
            stop_points = max(config.get('min_stop', 5.0), 
                            min(stop_points, config.get('max_stop', 20.0)))
            take_points = max(config.get('min_take', 8.0),
                            min(take_points, config.get('max_take', 30.0)))
        
        # Ajustar por fase do mercado
        if market_phase == 'LATERAL':
            # Em mercado lateral, usar suporte/resistência
            if side == 'BUY':
                # Para compra, stop abaixo do suporte, take na resistência
                stop_distance = min(entry_price - support, stop_points)
                take_distance = min(resistance - entry_price, take_points)
            else:
                # Para venda, stop acima da resistência, take no suporte
                stop_distance = min(resistance - entry_price, stop_points)
                take_distance = min(entry_price - support, take_points)
            
            # Garantir mínimos
            stop_points = max(5.0, stop_distance)
            take_points = max(7.0, take_distance)
            
        elif market_phase == 'BREAKOUT':
            # Em rompimento, aumentar stop e take
            stop_points *= 1.2
            take_points *= 1.5
        
        # Ajustar por horário
        time_adj = self.time_adjustments[time_period]
        stop_points *= time_adj['stop_mult']
        take_points *= time_adj['take_mult']
        
        # Ajustar por confiança
        if confidence > 0.7:
            # Alta confiança: pode usar stop menor e take maior
            stop_points *= 0.9
            take_points *= 1.1
        elif confidence < 0.5:
            # Baixa confiança: stop maior e take menor
            stop_points *= 1.1
            take_points *= 0.9
        
        # Arredondar para tick size
        stop_points = round(stop_points / self.tick_size) * self.tick_size
        take_points = round(take_points / self.tick_size) * self.tick_size
        
        # Garantir ratio mínimo de 1:1.2
        if take_points < stop_points * 1.2:
            take_points = stop_points * 1.2
        
        # Calcular preços finais
        if side == 'BUY':
            stop_loss = entry_price - stop_points
            take_profit = entry_price + take_points
        else:
            stop_loss = entry_price + stop_points
            take_profit = entry_price - take_points
        
        # Arredondar para tick size
        stop_loss = round(stop_loss / self.tick_size) * self.tick_size
        take_profit = round(take_profit / self.tick_size) * self.tick_size
        
        # Calcular métricas
        risk_reward = take_points / stop_points
        risk_money = stop_points * self.tick_value
        reward_money = take_points * self.tick_value
        
        result = {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'stop_points': stop_points,
            'take_points': take_points,
            'risk_reward': risk_reward,
            'risk_money': risk_money,
            'reward_money': reward_money,
            'volatility_regime': volatility_regime,
            'market_phase': market_phase,
            'atr': atr,
            'support': support,
            'resistance': resistance
        }
        
        logger.info(f"Níveis adaptativos calculados:")
        logger.info(f"  Stop: {stop_points:.1f} pts ({risk_money:.2f} R$)")
        logger.info(f"  Take: {take_points:.1f} pts ({reward_money:.2f} R$)")
        logger.info(f"  R:R: 1:{risk_reward:.2f}")
        logger.info(f"  Regime: {volatility_regime}, Fase: {market_phase}")
        
        return result
    
    def should_trade(self, market_condition: Dict) -> bool:
        """
        Decide se deve operar baseado nas condições de mercado
        
        Returns:
            True se condições favoráveis para trade
        """
        # Não operar em volatilidade extrema
        if market_condition.get('atr', 10) > 30:
            logger.warning("Volatilidade muito alta, evitando trade")
            return False
        
        # Não operar se risk:reward < 1:1
        if market_condition.get('risk_reward', 0) < 1.0:
            logger.warning("Risk:Reward desfavorável, evitando trade")
            return False
        
        # Evitar horário de almoço em mercado lateral
        time_period = self.get_time_period()
        if time_period == 'lunch' and market_condition.get('market_phase') == 'LATERAL':
            logger.warning("Horário de almoço + mercado lateral, evitando trade")
            return False
        
        return True


# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Criar gerenciador
    risk_mgr = AdaptiveRiskManager("WDOU25")
    
    # Simular alguns dados
    for i in range(50):
        price = 5400 + np.random.randn() * 10
        risk_mgr.update_buffers(
            price=price,
            high=price + np.random.uniform(0, 5),
            low=price - np.random.uniform(0, 5),
            volume=np.random.uniform(1000, 5000)
        )
    
    # Calcular níveis adaptativos
    levels = risk_mgr.calculate_adaptive_levels(
        entry_price=5400.0,
        side='BUY',
        confidence=0.65
    )
    
    print("\nNíveis Adaptativos Calculados:")
    print(f"Stop Loss: {levels['stop_loss']:.1f} ({levels['stop_points']:.1f} pts)")
    print(f"Take Profit: {levels['take_profit']:.1f} ({levels['take_points']:.1f} pts)")
    print(f"Risk:Reward: 1:{levels['risk_reward']:.2f}")
    print(f"Regime: {levels['volatility_regime']}")
    print(f"Fase: {levels['market_phase']}")