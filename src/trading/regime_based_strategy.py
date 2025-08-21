"""
Sistema de Trading Baseado em Regime de Mercado
Detecta regime (tendência/lateralização) e aplica estratégias específicas
Usa HMARL para timing de entrada
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging
from collections import deque

logger = logging.getLogger(__name__)

def round_to_tick(price: float, tick_size: float = 0.5) -> float:
    """
    Arredonda preço para o tick mais próximo
    WDO usa tick de 0.5 pontos
    """
    return round(price / tick_size) * tick_size

class MarketRegime(Enum):
    """Regimes de mercado detectados"""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    LATERAL = "lateral"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    UNDEFINED = "undefined"

@dataclass
class RegimeSignal:
    """Sinal de trading baseado em regime"""
    regime: MarketRegime
    signal: int  # 1=BUY, -1=SELL, 0=HOLD
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    strategy: str  # "trend_following" ou "support_resistance"
    
class RegimeDetector:
    """Detecta o regime atual do mercado"""
    
    def __init__(self, lookback_periods: int = 50):
        self.lookback_periods = lookback_periods
        self.price_buffer = deque(maxlen=lookback_periods)
        self.volume_buffer = deque(maxlen=lookback_periods)
        
        # Parâmetros de detecção (ajustados para maior sensibilidade a tendências)
        self.trend_threshold = 0.0003  # 0.03% para considerar tendência (mais sensível)
        self.strong_trend_threshold = 0.001  # 0.1% para tendência forte (mais sensível)
        self.lateral_threshold = 0.0001  # 0.01% para lateralização
        
    def update(self, price: float, volume: float):
        """Atualiza buffers com novo preço e volume"""
        self.price_buffer.append(price)
        self.volume_buffer.append(volume)
        
    def detect_regime(self) -> Tuple[MarketRegime, float]:
        """
        Detecta o regime atual do mercado
        Returns: (regime, confidence)
        """
        if len(self.price_buffer) < 20:
            return MarketRegime.UNDEFINED, 0.0
            
        prices = np.array(self.price_buffer)
        
        # 1. Calcular médias móveis
        sma_5 = np.mean(prices[-5:])
        sma_10 = np.mean(prices[-10:])
        sma_20 = np.mean(prices[-20:])
        
        # 2. Calcular inclinação da tendência (mais sensível)
        x = np.arange(len(prices))
        # Usar apenas últimos 20 preços para tendência mais recente
        recent_prices = prices[-20:]
        x_recent = np.arange(len(recent_prices))
        slope, _ = np.polyfit(x_recent, recent_prices, 1)
        normalized_slope = slope / np.mean(recent_prices)
        
        # 3. Calcular volatilidade
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) if len(returns) > 0 else 0
        
        # 4. Calcular ADX simplificado (força da tendência)
        high_low = np.max(prices[-14:]) - np.min(prices[-14:])
        atr = high_low / np.mean(prices[-14:])
        
        # 5. Detectar regime baseado em múltiplos indicadores
        confidence = 0.0
        regime = MarketRegime.UNDEFINED
        
        # Tendência forte de alta
        if (normalized_slope > self.strong_trend_threshold and 
            sma_5 > sma_10 > sma_20 and
            atr > 0.01):
            regime = MarketRegime.STRONG_UPTREND
            confidence = min(0.95, 0.5 + normalized_slope * 100)
            
        # Tendência de alta
        elif (normalized_slope > self.trend_threshold and
              sma_5 > sma_20):
            regime = MarketRegime.UPTREND
            confidence = min(0.85, 0.4 + normalized_slope * 50)
            
        # Tendência forte de baixa
        elif (normalized_slope < -self.strong_trend_threshold and
              sma_5 < sma_10 < sma_20 and
              atr > 0.01):
            regime = MarketRegime.STRONG_DOWNTREND
            confidence = min(0.95, 0.5 + abs(normalized_slope) * 100)
            
        # Tendência de baixa
        elif (normalized_slope < -self.trend_threshold and
              sma_5 < sma_20):
            regime = MarketRegime.DOWNTREND
            confidence = min(0.85, 0.4 + abs(normalized_slope) * 50)
            
        # Lateralização (mais permissivo)
        else:
            regime = MarketRegime.LATERAL
            # Confiança baseada na falta de tendência clara
            confidence = max(0.5, min(0.8, 0.7 - abs(normalized_slope) * 50))
            
        return regime, confidence

class TrendFollowingStrategy:
    """Estratégia para mercados em tendência"""
    
    def __init__(self, risk_reward_ratio: float = 1.5):
        self.risk_reward_ratio = risk_reward_ratio
        self.atr_multiplier_stop = 2.0  # Stop mais largo
        self.atr_multiplier_target = 3.0  # Target mais ambicioso
        
    def generate_signal(self, 
                       regime: MarketRegime,
                       current_price: float,
                       price_buffer: deque,
                       hmarl_signal: Optional[Dict] = None) -> Optional[RegimeSignal]:
        """
        Gera sinal de trading para tendências
        Opera sempre a favor da tendência com RR 1.5:1
        """
        if len(price_buffer) < 20:
            return None
            
        prices = np.array(price_buffer)
        
        # Calcular ATR para stops
        high_low = []
        for i in range(1, len(prices)):
            high_low.append(abs(prices[i] - prices[i-1]))
        atr = np.mean(high_low[-14:]) if len(high_low) >= 14 else current_price * 0.002
        
        # Verificar confirmação HMARL
        hmarl_confidence = 0.95  # Alta confiança quando HMARL não disponível
        if hmarl_signal:
            hmarl_confidence = hmarl_signal.get('confidence', 0.5)
            
        signal = None
        
        if regime in [MarketRegime.STRONG_UPTREND, MarketRegime.UPTREND]:
            # Compra em tendência de alta
            # Verificar pullback para entrada
            sma_10 = np.mean(prices[-10:])
            
            if current_price <= sma_10 * 1.002:  # Próximo da média
                signal = 1  # BUY
                stop_loss = current_price - (atr * self.atr_multiplier_stop)
                take_profit = current_price + (atr * self.atr_multiplier_target)
                
                # Ajustar para garantir RR 1.5:1
                risk = current_price - stop_loss
                reward = take_profit - current_price
                if reward / risk < self.risk_reward_ratio:
                    take_profit = current_price + (risk * self.risk_reward_ratio)
                    
                return RegimeSignal(
                    regime=regime,
                    signal=signal,
                    confidence=0.7 * hmarl_confidence,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_reward=self.risk_reward_ratio,
                    strategy="trend_following"
                )
                
        elif regime in [MarketRegime.STRONG_DOWNTREND, MarketRegime.DOWNTREND]:
            # Venda em tendência de baixa
            # Verificar pullback para entrada
            sma_10 = np.mean(prices[-10:])
            
            if current_price >= sma_10 * 0.998:  # Próximo da média
                signal = -1  # SELL
                stop_loss = current_price + (atr * self.atr_multiplier_stop)
                take_profit = current_price - (atr * self.atr_multiplier_target)
                
                # Ajustar para garantir RR 1.5:1
                risk = stop_loss - current_price
                reward = current_price - take_profit
                if reward / risk < self.risk_reward_ratio:
                    take_profit = current_price - (risk * self.risk_reward_ratio)
                    
                return RegimeSignal(
                    regime=regime,
                    signal=signal,
                    confidence=0.7 * hmarl_confidence,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_reward=self.risk_reward_ratio,
                    strategy="trend_following"
                )
                
        return None

class SupportResistanceStrategy:
    """Estratégia para mercados lateralizados"""
    
    def __init__(self, risk_reward_ratio: float = 1.0):  # Lateralização aceita 1:1
        self.risk_reward_ratio = risk_reward_ratio
        self.support_resistance_buffer = 0.003  # 0.3% buffer (~16 ticks)
        self.levels_lookback = 50
        self.min_distance_between_levels = 0.002  # Mínimo 0.2% entre níveis
        
    def find_support_resistance(self, prices: np.ndarray) -> Tuple[List[float], List[float]]:
        """Encontra níveis de suporte e resistência"""
        if len(prices) < 20:
            return [], []
            
        # Encontrar máximos e mínimos locais
        supports = []
        resistances = []
        
        for i in range(10, len(prices) - 10):
            # Resistência: máximo local
            if prices[i] == max(prices[i-10:i+10]):
                resistances.append(prices[i])
                
            # Suporte: mínimo local
            if prices[i] == min(prices[i-10:i+10]):
                supports.append(prices[i])
                
        # Agrupar níveis próximos (melhorado)
        def cluster_levels(levels, tolerance=0.002):  # Aumentar tolerância
            if not levels:
                return []
            
            clustered = []
            levels_sorted = sorted(set(levels))  # Remover duplicatas
            current_cluster = [levels_sorted[0]]
            
            for level in levels_sorted[1:]:
                if abs(level - current_cluster[-1]) / current_cluster[-1] < tolerance:
                    current_cluster.append(level)
                else:
                    # Adicionar cluster (aceitar com 1 toque para dados com pouca variação)
                    if len(current_cluster) >= 1:
                        clustered.append(np.mean(current_cluster))
                    current_cluster = [level]
                    
            if current_cluster and len(current_cluster) >= 1:
                clustered.append(np.mean(current_cluster))
                
            return clustered
            
        supports = cluster_levels(supports)
        resistances = cluster_levels(resistances)
        
        return supports[-3:], resistances[-3:]  # Retornar os 3 níveis mais recentes
        
    def generate_signal(self,
                       regime: MarketRegime,
                       current_price: float,
                       price_buffer: deque,
                       hmarl_signal: Optional[Dict] = None) -> Optional[RegimeSignal]:
        """
        Gera sinal de trading para lateralização
        Opera reversão em suporte/resistência
        """
        if regime != MarketRegime.LATERAL or len(price_buffer) < 30:  # Reduzido de 50 para 30
            return None
            
        prices = np.array(price_buffer)
        supports, resistances = self.find_support_resistance(prices)
        
        # Log de debug a cada 100 chamadas
        if not hasattr(self, '_call_count'):
            self._call_count = 0
        self._call_count += 1
        
        if self._call_count % 100 == 0:
            logger.info(f"[S/R DEBUG] Supports: {supports[:3] if supports else 'None'}")
            logger.info(f"[S/R DEBUG] Resistances: {resistances[:3] if resistances else 'None'}")
            logger.info(f"[S/R DEBUG] Current Price: {current_price:.2f}")
        
        if not supports or not resistances:
            # Estratégia alternativa: usar máximos e mínimos recentes
            if len(prices) >= 20:
                recent_min = np.min(prices[-20:])
                recent_max = np.max(prices[-20:])
                supports = [recent_min]
                resistances = [recent_max]
                
                if self._call_count % 100 == 0:
                    logger.info(f"[S/R DEBUG] Using recent min/max: {recent_min:.2f}/{recent_max:.2f}")
            
        # Verificar confirmação HMARL
        hmarl_confidence = 0.95  # Alta confiança quando HMARL não disponível
        if hmarl_signal:
            hmarl_confidence = hmarl_signal.get('confidence', 0.5)
            
        # Encontrar suporte/resistência mais próximo
        nearest_support = min(supports, key=lambda x: abs(x - current_price))
        nearest_resistance = min(resistances, key=lambda x: abs(x - current_price))
        
        signal = None
        
        # Compra em suporte (adicionar verificação para evitar trades repetidos)
        price_to_support_ratio = abs(current_price - nearest_support) / nearest_support
        if price_to_support_ratio < self.support_resistance_buffer and current_price > nearest_support:
            signal = 1  # BUY
            stop_loss = nearest_support * 0.998  # 0.2% abaixo do suporte (mais apertado)
            
            # Alvo na próxima resistência ou RR 1:1 (lateralização aceita menor RR)
            risk = current_price - stop_loss
            # Se a resistência está muito próxima, aceitar RR menor (mínimo 1:1)
            ideal_target = current_price + (risk * self.risk_reward_ratio)
            take_profit = min(nearest_resistance * 0.995, ideal_target)
            
            return RegimeSignal(
                regime=regime,
                signal=signal,
                confidence=0.85 * hmarl_confidence,  # Aumentado para gerar mais sinais
                entry_price=round_to_tick(current_price),
                stop_loss=round_to_tick(stop_loss),
                take_profit=round_to_tick(take_profit),
                risk_reward=(take_profit - current_price) / risk,
                strategy="support_resistance"
            )
            
        # Venda em resistência (adicionar verificação para evitar trades repetidos)
        price_to_resistance_ratio = abs(current_price - nearest_resistance) / nearest_resistance
        if price_to_resistance_ratio < self.support_resistance_buffer and current_price < nearest_resistance:
            signal = -1  # SELL
            stop_loss = nearest_resistance * 1.002  # 0.2% acima da resistência (CORRETO - stop acima para SELL)
            
            # CORREÇÃO: Para SELL, o take profit deve estar ABAIXO do preço atual
            risk = stop_loss - current_price  # Distância até o stop (prejuízo)
            # Take profit deve estar abaixo (lucro)
            ideal_target = current_price - (risk * self.risk_reward_ratio)
            take_profit = max(nearest_support * 1.005, ideal_target)  # Garantir que está acima do suporte
            
            return RegimeSignal(
                regime=regime,
                signal=signal,
                confidence=0.85 * hmarl_confidence,  # Aumentado para gerar mais sinais
                entry_price=round_to_tick(current_price),
                stop_loss=round_to_tick(stop_loss),
                take_profit=round_to_tick(take_profit),
                risk_reward=(current_price - take_profit) / risk,
                strategy="support_resistance"
            )
            
        return None

class RegimeBasedTradingSystem:
    """Sistema completo de trading baseado em regime"""
    
    def __init__(self, min_confidence: float = 0.60):
        self.min_confidence = min_confidence
        
        # Componentes do sistema
        self.regime_detector = RegimeDetector(lookback_periods=50)
        self.trend_strategy = TrendFollowingStrategy(risk_reward_ratio=1.5)  # Tendência: RR 1.5:1
        self.lateral_strategy = SupportResistanceStrategy(risk_reward_ratio=1.0)  # Lateral: RR 1.0:1
        
        # Estatísticas
        self.total_signals = 0
        self.regime_history = deque(maxlen=100)
        
        # Controle de frequência de trades
        self.last_signal_time = None
        self.min_bars_between_signals = 10  # Mínimo de 10 barras entre sinais
        self.bars_since_last_signal = 0
        
        logger.info("Sistema de Trading Baseado em Regime inicializado")
        logger.info(f"Confiança mínima: {min_confidence:.0%}")
        logger.info("Risk/Reward: Tendência 1.5:1 | Lateralização 1.0:1")
        
    def update(self, price: float, volume: float):
        """Atualiza o sistema com novos dados"""
        self.regime_detector.update(price, volume)
        self.bars_since_last_signal += 1
        
    def get_trading_signal(self, 
                          current_price: float,
                          hmarl_signal: Optional[Dict] = None) -> Optional[RegimeSignal]:
        """
        Gera sinal de trading baseado no regime atual
        
        Args:
            current_price: Preço atual
            hmarl_signal: Sinal dos agentes HMARL para timing
            
        Returns:
            RegimeSignal ou None
        """
        # 1. Detectar regime atual
        regime, regime_confidence = self.regime_detector.detect_regime()
        self.regime_history.append(regime)
        
        # Log detalhado a cada 50 iterações
        if hasattr(self, '_update_count'):
            self._update_count += 1
        else:
            self._update_count = 0
            
        if self._update_count % 50 == 0:
            logger.info(f"[REGIME] {regime.value.upper()} (conf: {regime_confidence:.0%})")
            if len(self.regime_detector.price_buffer) >= 20:
                prices = list(self.regime_detector.price_buffer)[-20:]
                current = prices[-1] if prices else 0
                min_price = min(prices) if prices else 0
                max_price = max(prices) if prices else 0
                logger.info(f"  Price Range: {min_price:.2f} - {max_price:.2f} (Current: {current:.2f})")
            
        # 2. Aplicar estratégia baseada no regime
        signal = None
        
        if regime in [MarketRegime.STRONG_UPTREND, MarketRegime.UPTREND,
                     MarketRegime.STRONG_DOWNTREND, MarketRegime.DOWNTREND]:
            # Usar estratégia de tendência
            signal = self.trend_strategy.generate_signal(
                regime, current_price, 
                self.regime_detector.price_buffer,
                hmarl_signal
            )
            
        elif regime == MarketRegime.LATERAL:
            # Usar estratégia de suporte/resistência
            signal = self.lateral_strategy.generate_signal(
                regime, current_price,
                self.regime_detector.price_buffer,
                hmarl_signal
            )
            
        # 3. Validar sinal e aplicar cooldown
        if signal and signal.confidence >= self.min_confidence:
            # Verificar cooldown entre trades
            if self.bars_since_last_signal < self.min_bars_between_signals:
                return None  # Ainda em cooldown
                
            self.total_signals += 1
            self.bars_since_last_signal = 0  # Resetar contador
            
            # Log do sinal
            logger.info(f"[SIGNAL] {signal.strategy.upper()} - "
                       f"{'BUY' if signal.signal == 1 else 'SELL'} @ {current_price:.2f}")
            logger.info(f"  Stop: {signal.stop_loss:.2f}, "
                       f"Target: {signal.take_profit:.2f}, "
                       f"RR: {signal.risk_reward:.1f}:1")
            logger.info(f"  Confidence: {signal.confidence:.0%}")
            
            return signal
            
        return None
        
    def get_stats(self) -> Dict:
        """Retorna estatísticas do sistema"""
        regime_counts = {}
        for regime in self.regime_history:
            regime_counts[regime.value] = regime_counts.get(regime.value, 0) + 1
            
        return {
            'total_signals': self.total_signals,
            'current_regime': self.regime_history[-1].value if self.regime_history else 'undefined',
            'regime_distribution': regime_counts,
            'buffer_size': len(self.regime_detector.price_buffer)
        }