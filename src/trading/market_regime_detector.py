"""
Detector de Regime de Mercado - Identifica se o mercado está em tendência ou lateralizado
Otimizado para WDO (Mini Índice Bovespa)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import deque
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class MarketRegimeDetector:
    """Detecta o regime atual do mercado (tendência vs lateralização)"""
    
    def __init__(self, window_sizes: Dict[str, int] = None):
        """
        Inicializa o detector de regime
        
        Args:
            window_sizes: Tamanhos das janelas para análise
        """
        self.window_sizes = window_sizes or {
            'atr': 14,         # Para ATR (Average True Range)
            'trend': 20,       # Para análise de tendência
            'range': 50,       # Para análise de range
            'volatility': 30   # Para análise de volatilidade
        }
        
        # Buffers de dados
        self.price_buffer = deque(maxlen=max(self.window_sizes.values()))
        self.high_buffer = deque(maxlen=max(self.window_sizes.values()))
        self.low_buffer = deque(maxlen=max(self.window_sizes.values()))
        self.volume_buffer = deque(maxlen=max(self.window_sizes.values()))
        
        # Estado atual
        self.current_regime = 'UNDEFINED'
        self.regime_confidence = 0.0
        self.last_update = None
        
        # Métricas do regime
        self.regime_metrics = {
            'atr': 0,
            'directional_strength': 0,
            'range_bound_score': 0,
            'volatility': 0,
            'trend_consistency': 0
        }
        
        # Histórico de regimes
        self.regime_history = deque(maxlen=100)
        
        logger.info("MarketRegimeDetector inicializado")
    
    def update(self, price: float, high: float = None, low: float = None, 
               volume: float = 0) -> Dict:
        """
        Atualiza com novo dado de mercado
        
        Args:
            price: Preço atual
            high: Máxima do período
            low: Mínima do período
            volume: Volume negociado
            
        Returns:
            Dict com regime atual e métricas
        """
        # Atualizar buffers
        self.price_buffer.append(price)
        self.high_buffer.append(high or price)
        self.low_buffer.append(low or price)
        self.volume_buffer.append(volume)
        
        self.last_update = datetime.now()
        
        # Analisar regime se tiver dados suficientes
        if len(self.price_buffer) >= self.window_sizes['trend']:
            self._analyze_regime()
        
        return self.get_current_regime()
    
    def _analyze_regime(self):
        """Analisa e classifica o regime atual do mercado"""
        
        # 1. Calcular ATR (Average True Range)
        atr = self._calculate_atr()
        self.regime_metrics['atr'] = atr
        
        # 2. Calcular força direcional
        directional_strength = self._calculate_directional_strength()
        self.regime_metrics['directional_strength'] = directional_strength
        
        # 3. Calcular score de range-bound
        range_bound_score = self._calculate_range_bound_score()
        self.regime_metrics['range_bound_score'] = range_bound_score
        
        # 4. Calcular volatilidade normalizada
        volatility = self._calculate_normalized_volatility()
        self.regime_metrics['volatility'] = volatility
        
        # 5. Calcular consistência da tendência
        trend_consistency = self._calculate_trend_consistency()
        self.regime_metrics['trend_consistency'] = trend_consistency
        
        # Classificar regime com base nas métricas
        regime, confidence = self._classify_regime()
        
        # Atualizar estado
        if self.current_regime != regime:
            logger.info(f"Mudança de regime: {self.current_regime} → {regime} (confiança: {confidence:.1%})")
            self._on_regime_change(self.current_regime, regime)
        
        self.current_regime = regime
        self.regime_confidence = confidence
        
        # Adicionar ao histórico
        self.regime_history.append({
            'timestamp': self.last_update,
            'regime': regime,
            'confidence': confidence,
            'metrics': self.regime_metrics.copy()
        })
    
    def _calculate_atr(self) -> float:
        """Calcula o Average True Range"""
        if len(self.high_buffer) < self.window_sizes['atr']:
            return 0
        
        window = self.window_sizes['atr']
        true_ranges = []
        
        prices = list(self.price_buffer)[-window-1:]
        highs = list(self.high_buffer)[-window:]
        lows = list(self.low_buffer)[-window:]
        
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],  # High - Low
                abs(highs[i] - prices[i-1]),  # High - Previous Close
                abs(lows[i] - prices[i-1])    # Low - Previous Close
            )
            true_ranges.append(tr)
        
        return np.mean(true_ranges) if true_ranges else 0
    
    def _calculate_directional_strength(self) -> float:
        """
        Calcula a força direcional do movimento
        Retorna valor entre -1 (forte baixa) e +1 (forte alta)
        """
        window = self.window_sizes['trend']
        if len(self.price_buffer) < window:
            return 0
        
        prices = list(self.price_buffer)[-window:]
        
        # Calcular regressão linear
        x = np.arange(len(prices))
        slope, _ = np.polyfit(x, prices, 1)
        
        # Normalizar slope pelo preço médio
        avg_price = np.mean(prices)
        normalized_slope = slope / avg_price * 100
        
        # Calcular R-squared para medir consistência
        y_pred = np.polyval([slope, _], x)
        ss_res = np.sum((prices - y_pred) ** 2)
        ss_tot = np.sum((prices - np.mean(prices)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Combinar slope e R-squared
        directional_strength = normalized_slope * r_squared
        
        # Limitar entre -1 e 1
        return np.clip(directional_strength, -1, 1)
    
    def _calculate_range_bound_score(self) -> float:
        """
        Calcula o score de lateralização (range-bound)
        Retorna valor entre 0 (tendência forte) e 1 (lateralização perfeita)
        """
        window = self.window_sizes['range']
        if len(self.price_buffer) < window:
            return 0.5
        
        prices = list(self.price_buffer)[-window:]
        
        # Calcular níveis de suporte e resistência
        high = max(prices)
        low = min(prices)
        range_size = high - low
        
        if range_size == 0:
            return 1.0
        
        # Contar quantas vezes o preço tocou suporte/resistência
        touch_threshold = range_size * 0.05  # 5% do range
        
        resistance_touches = sum(1 for p in prices if abs(p - high) < touch_threshold)
        support_touches = sum(1 for p in prices if abs(p - low) < touch_threshold)
        
        # Calcular porcentagem de tempo dentro do range central
        upper_bound = low + range_size * 0.8
        lower_bound = low + range_size * 0.2
        time_in_range = sum(1 for p in prices if lower_bound <= p <= upper_bound) / len(prices)
        
        # Combinar métricas
        touch_score = min((resistance_touches + support_touches) / 10, 1.0)
        range_score = time_in_range
        
        return (touch_score + range_score) / 2
    
    def _calculate_normalized_volatility(self) -> float:
        """
        Calcula volatilidade normalizada pelo preço
        """
        window = self.window_sizes['volatility']
        if len(self.price_buffer) < window:
            return 0
        
        prices = list(self.price_buffer)[-window:]
        returns = np.diff(prices) / prices[:-1]
        
        # Volatilidade anualizada (considerando ~252 dias de trading)
        volatility = np.std(returns) * np.sqrt(252)
        
        return volatility
    
    def _calculate_trend_consistency(self) -> float:
        """
        Calcula a consistência da tendência
        Retorna valor entre 0 (sem consistência) e 1 (tendência muito consistente)
        """
        window = self.window_sizes['trend']
        if len(self.price_buffer) < window:
            return 0
        
        prices = list(self.price_buffer)[-window:]
        
        # Calcular médias móveis
        sma_short = np.mean(prices[-5:])
        sma_long = np.mean(prices)
        
        # Contar candles na direção da tendência
        if sma_short > sma_long:  # Tendência de alta
            bullish_candles = sum(1 for i in range(1, len(prices)) if prices[i] > prices[i-1])
            consistency = bullish_candles / (len(prices) - 1)
        elif sma_short < sma_long:  # Tendência de baixa
            bearish_candles = sum(1 for i in range(1, len(prices)) if prices[i] < prices[i-1])
            consistency = bearish_candles / (len(prices) - 1)
        else:
            consistency = 0.5
        
        return consistency
    
    def _classify_regime(self) -> Tuple[str, float]:
        """
        Classifica o regime com base nas métricas calculadas
        
        Returns:
            Tuple (regime, confidence)
            regime: 'TRENDING_UP', 'TRENDING_DOWN', 'RANGING', 'VOLATILE'
            confidence: 0.0 a 1.0
        """
        
        # Extrair métricas
        directional = self.regime_metrics['directional_strength']
        range_bound = self.regime_metrics['range_bound_score']
        volatility = self.regime_metrics['volatility']
        consistency = self.regime_metrics['trend_consistency']
        
        # Decisão baseada em múltiplos critérios
        regime_scores = {
            'TRENDING_UP': 0,
            'TRENDING_DOWN': 0,
            'RANGING': 0,
            'VOLATILE': 0
        }
        
        # Score para tendência de alta
        if directional > 0.2:
            regime_scores['TRENDING_UP'] = (
                directional * 0.4 +           # Peso da força direcional
                consistency * 0.3 +            # Peso da consistência
                (1 - range_bound) * 0.3        # Inverso do range-bound
            )
        
        # Score para tendência de baixa
        elif directional < -0.2:
            regime_scores['TRENDING_DOWN'] = (
                abs(directional) * 0.4 +      # Peso da força direcional
                consistency * 0.3 +            # Peso da consistência
                (1 - range_bound) * 0.3        # Inverso do range-bound
            )
        
        # Score para lateralização
        if abs(directional) < 0.3:
            regime_scores['RANGING'] = (
                range_bound * 0.5 +            # Peso do range-bound
                (1 - abs(directional)) * 0.3 + # Inverso da força direcional
                (0.5 - abs(consistency - 0.5)) * 0.2  # Consistência próxima a 50%
            )
        
        # Score para volatilidade extrema
        if volatility > 0.3:  # 30% de volatilidade anualizada
            regime_scores['VOLATILE'] = min(volatility, 1.0)
        
        # Determinar regime vencedor
        best_regime = max(regime_scores, key=regime_scores.get)
        confidence = regime_scores[best_regime]
        
        # Se confiança muito baixa, classificar como UNDEFINED
        if confidence < 0.3:
            return 'UNDEFINED', confidence
        
        return best_regime, confidence
    
    def _on_regime_change(self, old_regime: str, new_regime: str):
        """
        Callback executado quando há mudança de regime
        """
        logger.info(f"[REGIME CHANGE] {old_regime} → {new_regime}")
        
        # Aqui podemos adicionar lógica adicional como:
        # - Notificações
        # - Ajuste de parâmetros
        # - Log especial
        pass
    
    def get_current_regime(self) -> Dict:
        """
        Retorna o regime atual e suas métricas
        """
        return {
            'regime': self.current_regime,
            'confidence': self.regime_confidence,
            'metrics': self.regime_metrics.copy(),
            'last_update': self.last_update,
            'recommendations': self._get_recommendations()
        }
    
    def _get_recommendations(self) -> Dict:
        """
        Retorna recomendações baseadas no regime atual
        """
        recommendations = {
            'stop_loss': 10,  # Padrão: 10 pontos
            'take_profit': 20,  # Padrão: 20 pontos
            'position_size': 1.0,  # Tamanho padrão
            'max_trades': 10,  # Trades por dia
            'min_confidence': 0.6  # Confiança mínima
        }
        
        if self.current_regime == 'TRENDING_UP':
            recommendations.update({
                'stop_loss': 8,
                'take_profit': 25,  # Alvo maior em tendência
                'position_size': 1.2,  # Posição maior
                'min_confidence': 0.55  # Pode ser menos conservador
            })
            
        elif self.current_regime == 'TRENDING_DOWN':
            recommendations.update({
                'stop_loss': 8,
                'take_profit': 25,
                'position_size': 1.2,
                'min_confidence': 0.55
            })
            
        elif self.current_regime == 'RANGING':
            recommendations.update({
                'stop_loss': 5,  # Stop mais apertado
                'take_profit': 8,  # Alvo menor em lateralização
                'position_size': 0.8,  # Posição menor
                'min_confidence': 0.65  # Mais conservador
            })
            
        elif self.current_regime == 'VOLATILE':
            recommendations.update({
                'stop_loss': 15,  # Stop mais largo
                'take_profit': 30,  # Alvo maior
                'position_size': 0.5,  # Posição reduzida
                'min_confidence': 0.70,  # Muito conservador
                'max_trades': 5  # Menos trades
            })
        
        return recommendations
    
    def get_regime_stats(self, lookback_hours: int = 24) -> Dict:
        """
        Retorna estatísticas dos regimes nas últimas horas
        """
        cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        
        recent_regimes = [
            entry for entry in self.regime_history 
            if entry['timestamp'] > cutoff_time
        ]
        
        if not recent_regimes:
            return {}
        
        # Contar tempo em cada regime
        regime_times = {}
        total_time = 0
        
        for i, entry in enumerate(recent_regimes):
            if i < len(recent_regimes) - 1:
                duration = (recent_regimes[i+1]['timestamp'] - entry['timestamp']).total_seconds()
            else:
                duration = (datetime.now() - entry['timestamp']).total_seconds()
            
            regime = entry['regime']
            if regime not in regime_times:
                regime_times[regime] = 0
            regime_times[regime] += duration
            total_time += duration
        
        # Calcular porcentagens
        regime_percentages = {
            regime: (time / total_time * 100) if total_time > 0 else 0
            for regime, time in regime_times.items()
        }
        
        return {
            'regime_distribution': regime_percentages,
            'total_changes': len(recent_regimes) - 1,
            'current_duration': (datetime.now() - recent_regimes[-1]['timestamp']).total_seconds() / 60,  # minutos
            'dominant_regime': max(regime_percentages, key=regime_percentages.get) if regime_percentages else 'UNDEFINED'
        }
    
    def is_regime_favorable(self, for_action: str = 'BUY') -> bool:
        """
        Verifica se o regime atual é favorável para uma ação
        
        Args:
            for_action: 'BUY' ou 'SELL'
            
        Returns:
            True se favorável, False caso contrário
        """
        if self.current_regime == 'TRENDING_UP' and for_action == 'BUY':
            return True
        elif self.current_regime == 'TRENDING_DOWN' and for_action == 'SELL':
            return True
        elif self.current_regime == 'RANGING':
            # Em lateralização, pode operar em ambas direções
            return self.regime_confidence > 0.5
        elif self.current_regime == 'UNDEFINED':
            # UNDEFINED - permitir trades no início quando ainda está coletando dados
            # Mas com confiança reduzida
            return True
        else:
            # VOLATILE - não favorável
            return False