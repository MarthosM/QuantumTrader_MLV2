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
        
        # NOVO: Histórico de regimes para análise de tendência
        self.regime_history = deque(maxlen=20)
        self.trend_strength_history = deque(maxlen=20)
        
    def update(self, price: float, volume: float):
        """Atualiza buffers com novo preço e volume"""
        self.price_buffer.append(price)
        self.volume_buffer.append(volume)
        
    def detect_regime(self) -> Tuple[MarketRegime, float]:
        """
        Detecta o regime atual do mercado com análise multi-período
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
        
        # NOVO: Análise multi-período para tendência mais robusta
        # Tendência curto prazo (5 períodos)
        if len(prices) >= 5:
            short_slope, _ = np.polyfit(np.arange(5), prices[-5:], 1)
            short_trend = short_slope / np.mean(prices[-5:])
        else:
            short_trend = 0
            
        # Tendência médio prazo (10 períodos)
        if len(prices) >= 10:
            medium_slope, _ = np.polyfit(np.arange(10), prices[-10:], 1)
            medium_trend = medium_slope / np.mean(prices[-10:])
        else:
            medium_trend = 0
        
        # 3. Calcular volatilidade
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) if len(returns) > 0 else 0
        
        # 4. Calcular ADX simplificado (força da tendência)
        high_low = np.max(prices[-14:]) - np.min(prices[-14:])
        atr = high_low / np.mean(prices[-14:])
        
        # NOVO: Calcular força direcional
        directional_strength = abs(normalized_slope) * (1 + atr)
        
        # 5. Detectar regime baseado em múltiplos indicadores
        confidence = 0.0
        regime = MarketRegime.UNDEFINED
        
        # Tendência forte de alta - requer confirmação multi-período
        if (normalized_slope > self.strong_trend_threshold and 
            short_trend > self.trend_threshold and  # Curto prazo também alta
            medium_trend > self.trend_threshold/2 and  # Médio prazo positivo
            sma_5 > sma_10 > sma_20 and
            directional_strength > 0.0015):  # Força direcional forte
            regime = MarketRegime.STRONG_UPTREND
            confidence = min(0.95, 0.5 + directional_strength * 50)
            
        # Tendência de alta
        elif (normalized_slope > self.trend_threshold and
              (short_trend > 0 or medium_trend > 0) and  # Pelo menos um período positivo
              sma_5 > sma_20):
            regime = MarketRegime.UPTREND
            confidence = min(0.85, 0.4 + normalized_slope * 50)
            
        # Tendência forte de baixa - requer confirmação multi-período
        elif (normalized_slope < -self.strong_trend_threshold and
              short_trend < -self.trend_threshold and  # Curto prazo também baixa
              medium_trend < -self.trend_threshold/2 and  # Médio prazo negativo
              sma_5 < sma_10 < sma_20 and
              directional_strength > 0.0015):  # Força direcional forte
            regime = MarketRegime.STRONG_DOWNTREND
            confidence = min(0.95, 0.5 + directional_strength * 50)
            
        # Tendência de baixa
        elif (normalized_slope < -self.trend_threshold and
              (short_trend < 0 or medium_trend < 0) and  # Pelo menos um período negativo
              sma_5 < sma_20):
            regime = MarketRegime.DOWNTREND
            confidence = min(0.85, 0.4 + abs(normalized_slope) * 50)
            
        # Lateralização - somente quando não há tendência clara em nenhum período
        else:
            # Verificar se realmente está lateral (tendências conflitantes ou fracas)
            trends_conflict = (short_trend * medium_trend < 0)  # Sinais opostos
            trends_weak = (abs(short_trend) < self.lateral_threshold and 
                          abs(medium_trend) < self.lateral_threshold and
                          abs(normalized_slope) < self.lateral_threshold * 2)
            
            if trends_conflict or trends_weak:
                regime = MarketRegime.LATERAL
                confidence = max(0.5, min(0.8, 0.7 - directional_strength * 30))
            else:
                # Se não está claramente lateral, manter tendência anterior se houver
                regime = MarketRegime.LATERAL
                confidence = 0.5
        
        # Armazenar no histórico
        self.regime_history.append(regime)
        self.trend_strength_history.append(directional_strength)
            
        return regime, confidence
    
    def get_trend_consistency(self) -> float:
        """
        NOVO: Retorna a consistência da tendência (0-1)
        1 = tendência muito consistente
        0 = sem tendência ou mudando constantemente
        """
        if len(self.regime_history) < 5:
            return 0.5
            
        # Converter deque para lista para permitir slicing
        history_list = list(self.regime_history)
        
        # Contar regimes de tendência vs lateral
        trend_count = sum(1 for r in history_list[-10:] 
                         if r in [MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND,
                                 MarketRegime.DOWNTREND, MarketRegime.STRONG_DOWNTREND])
        
        # Verificar mudanças de direção
        changes = 0
        for i in range(1, min(10, len(history_list))):
            prev = history_list[-i-1]
            curr = history_list[-i]
            
            # Mudança de alta para baixa ou vice-versa
            if ((prev in [MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND] and
                 curr in [MarketRegime.DOWNTREND, MarketRegime.STRONG_DOWNTREND]) or
                (prev in [MarketRegime.DOWNTREND, MarketRegime.STRONG_DOWNTREND] and
                 curr in [MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND])):
                changes += 1
        
        # Calcular consistência
        trend_ratio = trend_count / min(10, len(history_list))
        change_penalty = changes * 0.2
        
        return max(0, min(1, trend_ratio - change_penalty))

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
    """Estratégia para mercados lateralizados com validação de tendência"""
    
    def __init__(self, risk_reward_ratio: float = 1.0):  # Lateralização aceita 1:1
        self.risk_reward_ratio = risk_reward_ratio
        self.support_resistance_buffer = 0.003  # 0.3% buffer (~16 ticks)
        self.levels_lookback = 50
        self.min_distance_between_levels = 0.002  # Mínimo 0.2% entre níveis
        
        # NOVO: Controle de tendência recente
        self.recent_trend = None  # Armazena tendência dos últimos 20 períodos
        self.trend_strength = 0.0  # Força da tendência recente
        
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
                       hmarl_signal: Optional[Dict] = None,
                       regime_detector: Optional['RegimeDetector'] = None) -> Optional[RegimeSignal]:
        """
        Gera sinal de trading para lateralização
        Opera reversão em suporte/resistência, respeitando tendência recente
        """
        if regime != MarketRegime.LATERAL or len(price_buffer) < 30:  # Reduzido de 50 para 30
            return None
            
        prices = np.array(price_buffer)
        
        # NOVO: Analisar tendência recente mesmo em lateralização
        if len(prices) >= 20:
            # Calcular tendência dos últimos 20 períodos
            recent_prices = prices[-20:]
            x = np.arange(len(recent_prices))
            slope, _ = np.polyfit(x, recent_prices, 1)
            self.recent_trend = slope / np.mean(recent_prices)
            self.trend_strength = abs(self.recent_trend)
            
            # Se tendência recente é forte, evitar operar contra ela
            strong_trend_threshold = 0.0005  # 0.05% é considerado forte
            if self.trend_strength > strong_trend_threshold:
                if not hasattr(self, '_trend_warning_count'):
                    self._trend_warning_count = 0
                self._trend_warning_count += 1
                
                if self._trend_warning_count % 50 == 1:
                    trend_dir = "ALTA" if self.recent_trend > 0 else "BAIXA"
                    logger.info(f"[LATERAL] Tendência recente de {trend_dir} detectada "
                              f"(força: {self.trend_strength:.4f}). Evitando trades contrários.")
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
            # NOVO: Verificar se não está operando contra tendência recente forte
            if self.trend_strength > 0.0005 and self.recent_trend < 0:
                # Tendência recente de BAIXA, evitar compra em lateral
                if self._call_count % 100 == 0:
                    logger.info("[BLOQUEADO] BUY em suporte bloqueado - tendência recente de BAIXA")
                return None
                
            signal = 1  # BUY
            stop_loss = nearest_support * 0.998  # 0.2% abaixo do suporte (mais apertado)
            
            # Alvo na próxima resistência ou RR 1:1 (lateralização aceita menor RR)
            risk = current_price - stop_loss
            # Se a resistência está muito próxima, aceitar RR menor (mínimo 1:1)
            ideal_target = current_price + (risk * self.risk_reward_ratio)
            # CORREÇÃO: Para BUY, take profit deve ser ACIMA do preço atual
            # Usar MAX ao invés de MIN para garantir que take está acima
            take_profit = max(ideal_target, nearest_resistance * 0.995)
            
            # Validar que take profit está acima do preço atual
            if take_profit <= current_price:
                take_profit = current_price + (risk * 1.5)  # Forçar RR mínimo de 1.5:1
            
            return RegimeSignal(
                regime=regime,
                signal=signal,
                confidence=0.85 * hmarl_confidence,  # Aumentado para gerar mais sinais
                entry_price=round_to_tick(current_price),
                stop_loss=round_to_tick(stop_loss),
                take_profit=round_to_tick(take_profit),
                risk_reward=abs((take_profit - current_price) / risk) if risk > 0 else 1.0,  # Sempre positivo
                strategy="support_resistance"
            )
            
        # Venda em resistência (adicionar verificação para evitar trades repetidos)
        price_to_resistance_ratio = abs(current_price - nearest_resistance) / nearest_resistance
        if price_to_resistance_ratio < self.support_resistance_buffer and current_price < nearest_resistance:
            # NOVO: Verificar se não está operando contra tendência recente forte
            if self.trend_strength > 0.0005 and self.recent_trend > 0:
                # Tendência recente de ALTA, evitar venda em lateral
                if self._call_count % 100 == 0:
                    logger.info("[BLOQUEADO] SELL em resistência bloqueado - tendência recente de ALTA")
                return None
                
            signal = -1  # SELL
            stop_loss = nearest_resistance * 1.002  # 0.2% acima da resistência (CORRETO - stop acima para SELL)
            
            # CORREÇÃO: Para SELL, o take profit deve estar ABAIXO do preço atual
            risk = stop_loss - current_price  # Distância até o stop (prejuízo)
            # Take profit deve estar abaixo (lucro)
            ideal_target = current_price - (risk * self.risk_reward_ratio)
            # CORREÇÃO: Usar min() para garantir que take está ABAIXO do preço
            take_profit = min(ideal_target, nearest_support * 1.005)  # Target não pode passar do suporte
            
            return RegimeSignal(
                regime=regime,
                signal=signal,
                confidence=0.85 * hmarl_confidence,  # Aumentado para gerar mais sinais
                entry_price=round_to_tick(current_price),
                stop_loss=round_to_tick(stop_loss),
                take_profit=round_to_tick(take_profit),
                risk_reward=abs((current_price - take_profit) / risk) if risk > 0 else 1.0,  # Sempre positivo
                strategy="support_resistance"
            )
            
        return None

class RegimeBasedTradingSystem:
    """Sistema completo de trading baseado em regime com validação anti-contra-tendência"""
    
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
        
        # Armazenar últimos níveis de suporte/resistência
        self.last_support_levels = []
        self.last_resistance_levels = []
        
        # NOVO: Métricas de trades bloqueados
        self.trades_blocked_by_trend = 0
        self.total_validations = 0
        
        logger.info("Sistema de Trading Baseado em Regime inicializado")
        logger.info(f"Confiança mínima: {min_confidence:.0%}")
        logger.info("Risk/Reward: Tendência 1.5:1 | Lateralização 1.0:1")
        logger.info("✓ Sistema Anti-Contra-Tendência ATIVO")
        
    def update(self, price: float, volume: float):
        """Atualiza o sistema com novos dados"""
        self.regime_detector.update(price, volume)
        self.bars_since_last_signal += 1
    
    def validate_trend_alignment(self, signal: int, regime: MarketRegime, 
                                 confidence: float = 1.0) -> Tuple[bool, str]:
        """
        NOVO: Valida se o sinal está alinhado com a tendência
        
        Args:
            signal: 1 para BUY, -1 para SELL
            regime: Regime atual do mercado
            confidence: Confiança do sinal (opcional)
            
        Returns:
            (is_valid, reason): Tupla indicando se é válido e o motivo
        """
        self.total_validations += 1
        
        # Em tendências fortes, NUNCA operar contra
        if regime == MarketRegime.STRONG_UPTREND:
            if signal < 0:  # Tentando SELL em tendência forte de alta
                self.trades_blocked_by_trend += 1
                return False, "SELL bloqueado em STRONG_UPTREND"
            return True, "BUY alinhado com STRONG_UPTREND"
            
        elif regime == MarketRegime.STRONG_DOWNTREND:
            if signal > 0:  # Tentando BUY em tendência forte de baixa
                self.trades_blocked_by_trend += 1
                return False, "BUY bloqueado em STRONG_DOWNTREND"
            return True, "SELL alinhado com STRONG_DOWNTREND"
        
        # Em tendências normais, permitir apenas a favor
        elif regime == MarketRegime.UPTREND:
            if signal < 0:  # SELL em tendência de alta
                # Verificar consistência da tendência
                consistency = self.regime_detector.get_trend_consistency()
                if consistency > 0.6:  # Tendência consistente
                    self.trades_blocked_by_trend += 1
                    return False, f"SELL bloqueado em UPTREND consistente ({consistency:.0%})"
                # Se tendência não é muito consistente, permitir com aviso
                return True, f"SELL permitido em UPTREND fraco ({consistency:.0%})"
            return True, "BUY alinhado com UPTREND"
            
        elif regime == MarketRegime.DOWNTREND:
            if signal > 0:  # BUY em tendência de baixa
                # Verificar consistência da tendência
                consistency = self.regime_detector.get_trend_consistency()
                if consistency > 0.6:  # Tendência consistente
                    self.trades_blocked_by_trend += 1
                    return False, f"BUY bloqueado em DOWNTREND consistente ({consistency:.0%})"
                # Se tendência não é muito consistente, permitir com aviso
                return True, f"BUY permitido em DOWNTREND fraco ({consistency:.0%})"
            return True, "SELL alinhado com DOWNTREND"
        
        # Em lateralização, verificar tendência recente
        elif regime == MarketRegime.LATERAL:
            # Verificar se a lateral strategy já fez validação de tendência
            # Se sim, confiar na estratégia
            return True, "Trade em LATERAL após validação de tendência recente"
        
        # Regime indefinido - ser conservador
        else:
            if confidence < 0.75:  # Só permitir com alta confiança
                self.trades_blocked_by_trend += 1
                return False, f"Trade bloqueado em regime UNDEFINED com baixa confiança ({confidence:.0%})"
            return True, f"Trade permitido em UNDEFINED com alta confiança ({confidence:.0%})"
        
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
            # Usar estratégia de suporte/resistência com validação de tendência
            signal = self.lateral_strategy.generate_signal(
                regime, current_price,
                self.regime_detector.price_buffer,
                hmarl_signal,
                self.regime_detector  # Passar detector para análise de tendência
            )
            
            # Armazenar níveis de S/R quando em lateralização
            if len(self.regime_detector.price_buffer) >= 30:
                prices = np.array(self.regime_detector.price_buffer)
                supports, resistances = self.lateral_strategy.find_support_resistance(prices)
                self.last_support_levels = supports if supports else []
                self.last_resistance_levels = resistances if resistances else []
            
        # 3. Validar sinal e aplicar cooldown
        if signal and signal.confidence >= self.min_confidence:
            # Verificar cooldown entre trades
            if self.bars_since_last_signal < self.min_bars_between_signals:
                return None  # Ainda em cooldown
            
            # NOVO: Validar alinhamento com tendência
            is_valid, validation_reason = self.validate_trend_alignment(
                signal.signal, regime, signal.confidence
            )
            
            if not is_valid:
                # Trade bloqueado por ir contra tendência
                logger.warning(f"[TREND VALIDATION] {validation_reason}")
                logger.info(f"  Sinal bloqueado: {'BUY' if signal.signal == 1 else 'SELL'} @ {current_price:.2f}")
                logger.info(f"  Trades bloqueados por tendência: {self.trades_blocked_by_trend}/{self.total_validations} "
                          f"({100*self.trades_blocked_by_trend/max(1,self.total_validations):.1f}%)")
                return None
                
            self.total_signals += 1
            self.bars_since_last_signal = 0  # Resetar contador
            
            # Log do sinal aprovado
            logger.info(f"[SIGNAL] {signal.strategy.upper()} - "
                       f"{'BUY' if signal.signal == 1 else 'SELL'} @ {current_price:.2f}")
            logger.info(f"  Stop: {signal.stop_loss:.2f}, "
                       f"Target: {signal.take_profit:.2f}, "
                       f"RR: {signal.risk_reward:.1f}:1")
            logger.info(f"  Confidence: {signal.confidence:.0%}")
            logger.info(f"  [TREND OK] {validation_reason}")
            
            return signal
            
        return None
        
    def get_support_resistance(self) -> Dict[str, List[float]]:
        """Retorna os últimos níveis de suporte e resistência identificados"""
        return {
            'supports': self.last_support_levels,
            'resistances': self.last_resistance_levels
        }
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do sistema com métricas de validação de tendência"""
        regime_counts = {}
        for regime in self.regime_history:
            regime_counts[regime.value] = regime_counts.get(regime.value, 0) + 1
            
        # Calcular taxa de bloqueio
        block_rate = 0
        if self.total_validations > 0:
            block_rate = self.trades_blocked_by_trend / self.total_validations
            
        return {
            'total_signals': self.total_signals,
            'current_regime': self.regime_history[-1].value if self.regime_history else 'undefined',
            'regime_distribution': regime_counts,
            'buffer_size': len(self.regime_detector.price_buffer),
            # NOVO: Métricas de validação de tendência
            'trades_blocked_by_trend': self.trades_blocked_by_trend,
            'total_validations': self.total_validations,
            'trend_block_rate': f"{block_rate:.1%}",
            'trend_consistency': f"{self.regime_detector.get_trend_consistency():.1%}"
        }