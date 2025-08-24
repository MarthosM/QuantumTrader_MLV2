"""
Smart Targets Calculator
Sistema inteligente para cálculo de stop loss e take profit
Combina ATR, Microestrutura e Suporte/Resistência
"""

import numpy as np
from typing import Dict, Tuple, List, Optional
from collections import deque
from dataclasses import dataclass
import logging

logger = logging.getLogger('SmartTargets')

@dataclass
class TargetLevels:
    """Estrutura para armazenar níveis calculados"""
    stop_loss: float
    take_profit: float
    risk_reward: float
    method_weights: Dict[str, float]
    confidence: float
    reasoning: str

class SmartTargetsCalculator:
    """
    Calculador inteligente de targets que combina múltiplas técnicas:
    1. ATR (Average True Range) para volatilidade
    2. Microestrutura do book para dinâmica de curto prazo
    3. Suporte/Resistência para níveis estruturais
    """
    
    def __init__(self):
        # Histórico para cálculos
        self.price_history = deque(maxlen=200)
        self.high_history = deque(maxlen=200)
        self.low_history = deque(maxlen=200)
        
        # Configurações de ATR
        self.atr_period = 14
        self.atr_values = deque(maxlen=self.atr_period)
        
        # Limites em pontos do WDO
        self.limits = {
            'min_stop': 5.0,      # Mínimo 5 pontos
            'max_stop': 30.0,     # Máximo 30 pontos
            'min_take': 5.0,      # Mínimo 5 pontos
            'max_take': 40.0,     # Máximo 40 pontos
            'min_rr': 0.8,        # Risk/Reward mínimo 0.8:1
            'ideal_rr': 1.5       # Risk/Reward ideal 1.5:1
        }
        
        # Multiplicadores ATR por tipo
        self.atr_multipliers = {
            'scalping': {
                'stop': 0.5,      # 0.5x ATR para stop
                'take': 0.75      # 0.75x ATR para take
            },
            'swing': {
                'stop': 1.0,      # 1x ATR para stop
                'take': 2.0       # 2x ATR para take
            },
            'hybrid': {
                'stop': 0.75,     # 0.75x ATR para stop
                'take': 1.25      # 1.25x ATR para take
            }
        }
        
        # Pesos dos métodos por tipo de trade
        self.method_weights = {
            'hmarl_signal': {     # Sinais de curto prazo do HMARL
                'microstructure': 0.5,
                'atr': 0.3,
                'support_resistance': 0.2
            },
            'regime_signal': {    # Sinais de regime/tendência
                'support_resistance': 0.4,
                'atr': 0.4,
                'microstructure': 0.2
            },
            'default': {          # Padrão balanceado
                'atr': 0.4,
                'support_resistance': 0.3,
                'microstructure': 0.3
            }
        }
    
    def update_price_data(self, price: float, high: float = None, low: float = None):
        """Atualiza histórico de preços"""
        self.price_history.append(price)
        if high is not None:
            self.high_history.append(high)
        if low is not None:
            self.low_history.append(low)
        
        # Calcular ATR se tiver dados suficientes
        if len(self.price_history) >= 2:
            self._update_atr()
    
    def _update_atr(self):
        """Calcula e atualiza ATR (Average True Range)"""
        if len(self.price_history) < 2:
            return
        
        # True Range simplificado (diferença entre high e low ou variação de preço)
        if len(self.high_history) > 0 and len(self.low_history) > 0:
            high = self.high_history[-1]
            low = self.low_history[-1]
            tr = high - low
        else:
            # Usar variação de preço como proxy
            tr = abs(self.price_history[-1] - self.price_history[-2])
        
        self.atr_values.append(tr)
    
    def get_current_atr(self) -> float:
        """Retorna ATR atual em pontos"""
        if len(self.atr_values) == 0:
            return 10.0  # Valor padrão
        
        atr = np.mean(list(self.atr_values))
        # Garantir que está em range razoável
        return max(5.0, min(30.0, atr))
    
    def calculate_atr_targets(self, 
                             current_price: float,
                             signal_type: int,
                             trade_type: str = 'hybrid') -> Tuple[float, float]:
        """
        Calcula targets baseados em ATR
        
        Args:
            current_price: Preço atual
            signal_type: 1 para BUY, -1 para SELL
            trade_type: 'scalping', 'swing' ou 'hybrid'
        
        Returns:
            Tuple (stop_loss, take_profit)
        """
        atr = self.get_current_atr()
        multipliers = self.atr_multipliers.get(trade_type, self.atr_multipliers['hybrid'])
        
        stop_distance = atr * multipliers['stop']
        take_distance = atr * multipliers['take']
        
        # Aplicar limites
        stop_distance = max(self.limits['min_stop'], min(self.limits['max_stop'], stop_distance))
        take_distance = max(self.limits['min_take'], min(self.limits['max_take'], take_distance))
        
        if signal_type > 0:  # BUY
            stop_loss = current_price - stop_distance
            take_profit = current_price + take_distance
        else:  # SELL
            stop_loss = current_price + stop_distance
            take_profit = current_price - take_distance
        
        return stop_loss, take_profit
    
    def calculate_microstructure_targets(self,
                                        current_price: float,
                                        signal_type: int,
                                        book_features: Dict) -> Tuple[float, float]:
        """
        Calcula targets baseados na microestrutura do book
        
        Args:
            current_price: Preço atual
            signal_type: 1 para BUY, -1 para SELL
            book_features: Features do book (spread, depth, etc)
        
        Returns:
            Tuple (stop_loss, take_profit)
        """
        # Extrair features relevantes
        spread = book_features.get('spread', 0.5)
        depth_imbalance = book_features.get('depth_imbalance', 0)
        bid_levels = book_features.get('bid_levels_active', 5)
        ask_levels = book_features.get('ask_levels_active', 5)
        volume_ratio = book_features.get('volume_ratio', 1.0)
        
        # Base é o spread atual (mínimo movimento viável)
        base_movement = max(spread * 2, 5.0)  # Pelo menos 2x spread ou 5 pontos
        
        # Ajustar baseado na profundidade do book
        if abs(depth_imbalance) > 0.3:  # Book desequilibrado
            # Mais espaço na direção do desequilíbrio
            if depth_imbalance > 0 and signal_type > 0:  # Pressão compradora + BUY
                take_multiplier = 1.5
                stop_multiplier = 0.8
            elif depth_imbalance < 0 and signal_type < 0:  # Pressão vendedora + SELL
                take_multiplier = 1.5
                stop_multiplier = 0.8
            else:  # Contra o fluxo
                take_multiplier = 0.8
                stop_multiplier = 1.2
        else:
            take_multiplier = 1.0
            stop_multiplier = 1.0
        
        # Ajustar baseado na liquidez (níveis ativos)
        liquidity_factor = (bid_levels + ask_levels) / 10.0  # Normalizar por 10 níveis
        liquidity_factor = max(0.5, min(1.5, liquidity_factor))
        
        # Calcular distâncias
        stop_distance = base_movement * stop_multiplier * (2.0 - liquidity_factor)
        take_distance = base_movement * take_multiplier * liquidity_factor
        
        # Ajustar baseado no volume ratio
        if volume_ratio > 1.2:  # Mais volume no bid
            if signal_type > 0:  # BUY alinhado com volume
                take_distance *= 1.2
                stop_distance *= 0.9
        elif volume_ratio < 0.8:  # Mais volume no ask
            if signal_type < 0:  # SELL alinhado com volume
                take_distance *= 1.2
                stop_distance *= 0.9
        
        # Aplicar limites
        stop_distance = max(self.limits['min_stop'], min(15.0, stop_distance))  # Máx 15 para micro
        take_distance = max(self.limits['min_take'], min(20.0, take_distance))  # Máx 20 para micro
        
        if signal_type > 0:  # BUY
            stop_loss = current_price - stop_distance
            take_profit = current_price + take_distance
        else:  # SELL
            stop_loss = current_price + stop_distance
            take_profit = current_price - take_distance
        
        return stop_loss, take_profit
    
    def calculate_support_resistance_targets(self,
                                           current_price: float,
                                           signal_type: int,
                                           support_levels: List[float],
                                           resistance_levels: List[float]) -> Tuple[float, float]:
        """
        Calcula targets baseados em suporte e resistência
        
        Args:
            current_price: Preço atual
            signal_type: 1 para BUY, -1 para SELL
            support_levels: Lista de níveis de suporte
            resistance_levels: Lista de níveis de resistência
        
        Returns:
            Tuple (stop_loss, take_profit)
        """
        if signal_type > 0:  # BUY
            # Stop abaixo do suporte mais próximo
            valid_supports = [s for s in support_levels if s < current_price]
            if valid_supports:
                stop_loss = max(valid_supports) - 2.0  # 2 pontos abaixo do suporte
            else:
                stop_loss = current_price - 10.0  # Fallback
            
            # Take na resistência mais próxima
            valid_resistances = [r for r in resistance_levels if r > current_price]
            if valid_resistances:
                take_profit = min(valid_resistances) - 2.0  # 2 pontos antes da resistência
            else:
                take_profit = current_price + 15.0  # Fallback
                
        else:  # SELL
            # Stop acima da resistência mais próxima
            valid_resistances = [r for r in resistance_levels if r > current_price]
            if valid_resistances:
                stop_loss = min(valid_resistances) + 2.0  # 2 pontos acima da resistência
            else:
                stop_loss = current_price + 10.0  # Fallback
            
            # Take no suporte mais próximo
            valid_supports = [s for s in support_levels if s < current_price]
            if valid_supports:
                take_profit = max(valid_supports) + 2.0  # 2 pontos após o suporte
            else:
                take_profit = current_price - 15.0  # Fallback
        
        return stop_loss, take_profit
    
    def calculate_smart_targets(self,
                              current_price: float,
                              signal_type: int,
                              signal_source: str = 'default',
                              trade_type: str = 'hybrid',
                              book_features: Optional[Dict] = None,
                              support_levels: Optional[List[float]] = None,
                              resistance_levels: Optional[List[float]] = None) -> TargetLevels:
        """
        Calcula targets inteligentes combinando múltiplos métodos
        
        Args:
            current_price: Preço atual
            signal_type: 1 para BUY, -1 para SELL
            signal_source: 'hmarl_signal', 'regime_signal' ou 'default'
            trade_type: 'scalping', 'swing' ou 'hybrid'
            book_features: Features do book (opcional)
            support_levels: Níveis de suporte (opcional)
            resistance_levels: Níveis de resistência (opcional)
        
        Returns:
            TargetLevels com stop_loss, take_profit e metadados
        """
        # Obter pesos dos métodos
        weights = self.method_weights.get(signal_source, self.method_weights['default'])
        
        # Calcular com cada método
        methods_results = {}
        
        # 1. ATR
        atr_stop, atr_take = self.calculate_atr_targets(current_price, signal_type, trade_type)
        methods_results['atr'] = (atr_stop, atr_take)
        
        # 2. Microestrutura (se disponível)
        if book_features and weights['microstructure'] > 0:
            micro_stop, micro_take = self.calculate_microstructure_targets(
                current_price, signal_type, book_features
            )
            methods_results['microstructure'] = (micro_stop, micro_take)
        else:
            # Usar ATR como fallback
            methods_results['microstructure'] = methods_results['atr']
            weights['microstructure'] = 0
            weights['atr'] += weights.get('microstructure', 0)
        
        # 3. Suporte/Resistência (se disponível)
        if support_levels and resistance_levels and weights['support_resistance'] > 0:
            sr_stop, sr_take = self.calculate_support_resistance_targets(
                current_price, signal_type, support_levels, resistance_levels
            )
            methods_results['support_resistance'] = (sr_stop, sr_take)
        else:
            # Usar ATR como fallback
            methods_results['support_resistance'] = methods_results['atr']
            weights['support_resistance'] = 0
            weights['atr'] += weights.get('support_resistance', 0)
        
        # Normalizar pesos
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v/total_weight for k, v in weights.items()}
        
        # Combinar resultados com média ponderada
        final_stop = 0
        final_take = 0
        
        for method, (stop, take) in methods_results.items():
            weight = weights.get(method, 0)
            final_stop += stop * weight
            final_take += take * weight
        
        # Arredondar para tick do WDO (0.5)
        final_stop = round(final_stop * 2) / 2
        final_take = round(final_take * 2) / 2
        
        # Calcular risk/reward
        if signal_type > 0:  # BUY
            risk = current_price - final_stop
            reward = final_take - current_price
        else:  # SELL
            risk = final_stop - current_price
            reward = current_price - final_take
        
        risk_reward = reward / risk if risk > 0 else 0
        
        # Ajustar se RR muito baixo
        if risk_reward < self.limits['min_rr']:
            # Aumentar take para melhorar RR
            adjustment = risk * self.limits['ideal_rr'] - reward
            if signal_type > 0:
                final_take += adjustment
            else:
                final_take -= adjustment
            
            # Recalcular RR
            if signal_type > 0:
                reward = final_take - current_price
            else:
                reward = current_price - final_take
            risk_reward = reward / risk if risk > 0 else 0
        
        # Garantir limites finais
        if signal_type > 0:  # BUY
            stop_distance = current_price - final_stop
            take_distance = final_take - current_price
        else:  # SELL
            stop_distance = final_stop - current_price
            take_distance = current_price - final_take
        
        stop_distance = max(self.limits['min_stop'], min(self.limits['max_stop'], stop_distance))
        take_distance = max(self.limits['min_take'], min(self.limits['max_take'], take_distance))
        
        if signal_type > 0:  # BUY
            final_stop = current_price - stop_distance
            final_take = current_price + take_distance
        else:  # SELL
            final_stop = current_price + stop_distance
            final_take = current_price - take_distance
        
        # Arredondar novamente
        final_stop = round(final_stop * 2) / 2
        final_take = round(final_take * 2) / 2
        
        # Calcular confiança baseada no alinhamento dos métodos
        stop_values = [v[0] for v in methods_results.values()]
        take_values = [v[1] for v in methods_results.values()]
        
        stop_std = np.std(stop_values) if len(stop_values) > 1 else 0
        take_std = np.std(take_values) if len(take_values) > 1 else 0
        
        # Menor desvio = maior confiança
        confidence = max(0.5, 1.0 - (stop_std + take_std) / 50.0)
        
        # Criar reasoning
        reasoning = f"ATR: {self.get_current_atr():.1f}, "
        reasoning += f"Pesos: {', '.join([f'{k}:{v:.1%}' for k,v in weights.items()])}, "
        reasoning += f"RR: {risk_reward:.2f}:1"
        
        return TargetLevels(
            stop_loss=final_stop,
            take_profit=final_take,
            risk_reward=risk_reward,
            method_weights=weights,
            confidence=confidence,
            reasoning=reasoning
        )