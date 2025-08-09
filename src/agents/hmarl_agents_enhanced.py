"""
Agentes HMARL Enhanced - Adaptados para 65 Features
Integração completa com o novo sistema de features
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import json

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """Força do sinal de trading"""
    STRONG_BUY = 2
    BUY = 1
    NEUTRAL = 0
    SELL = -1
    STRONG_SELL = -2


@dataclass
class AgentSignal:
    """Sinal emitido por um agente"""
    agent_name: str
    signal: SignalStrength
    confidence: float
    reasoning: Dict
    timestamp: datetime


class BaseAgent:
    """Classe base para todos os agentes HMARL"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Agent_{name}")
        self.feature_requirements = []
        self.last_signal = None
        self.performance_metrics = {
            'signals_generated': 0,
            'correct_signals': 0,
            'confidence_sum': 0
        }
    
    def analyze(self, features: Dict) -> AgentSignal:
        """Método abstrato para análise - deve ser implementado por subclasses"""
        raise NotImplementedError
    
    def validate_features(self, features: Dict) -> bool:
        """Valida se todas as features necessárias estão presentes"""
        missing = [f for f in self.feature_requirements if f not in features]
        if missing:
            self.logger.warning(f"Features faltando: {missing}")
            return False
        return True
    
    def update_performance(self, was_correct: bool, confidence: float):
        """Atualiza métricas de performance do agente"""
        self.performance_metrics['signals_generated'] += 1
        if was_correct:
            self.performance_metrics['correct_signals'] += 1
        self.performance_metrics['confidence_sum'] += confidence
    
    def get_accuracy(self) -> float:
        """Retorna a acurácia do agente"""
        if self.performance_metrics['signals_generated'] == 0:
            return 0.5
        return (self.performance_metrics['correct_signals'] / 
                self.performance_metrics['signals_generated'])


class OrderFlowSpecialistAgent(BaseAgent):
    """Agente especialista em order flow e microestrutura"""
    
    def __init__(self):
        super().__init__("OrderFlowSpecialist")
        self.feature_requirements = [
            'order_flow_imbalance_5', 'order_flow_imbalance_10',
            'signed_volume_5', 'signed_volume_10',
            'bid_volume_total', 'ask_volume_total',
            'book_imbalance', 'book_pressure',
            'micro_price', 'weighted_mid_price'
        ]
    
    def analyze(self, features: Dict) -> AgentSignal:
        """Analisa order flow e gera sinal"""
        if not self.validate_features(features):
            return AgentSignal(
                agent_name=self.name,
                signal=SignalStrength.NEUTRAL,
                confidence=0.0,
                reasoning={'error': 'missing_features'},
                timestamp=datetime.now()
            )
        
        # Análise de order flow imbalance
        ofi_5 = features['order_flow_imbalance_5']
        ofi_10 = features['order_flow_imbalance_10']
        
        # Análise de volume assinado
        signed_vol_5 = features['signed_volume_5']
        signed_vol_10 = features['signed_volume_10']
        
        # Análise de book
        book_imbalance = features['book_imbalance']
        book_pressure = features['book_pressure']
        
        # Calcular score composto
        ofi_score = (ofi_5 * 0.6 + ofi_10 * 0.4)
        volume_score = (signed_vol_5 * 0.6 + signed_vol_10 * 0.4)
        book_score = (book_imbalance * 0.5 + book_pressure * 0.5)
        
        # Score final ponderado
        final_score = (
            ofi_score * 0.4 +
            volume_score * 0.3 +
            book_score * 0.3
        )
        
        # Determinar sinal
        if final_score > 0.3:
            signal = SignalStrength.STRONG_BUY if final_score > 0.5 else SignalStrength.BUY
        elif final_score < -0.3:
            signal = SignalStrength.STRONG_SELL if final_score < -0.5 else SignalStrength.SELL
        else:
            signal = SignalStrength.NEUTRAL
        
        # Calcular confiança
        confidence = min(abs(final_score) * 1.5, 1.0)
        
        # Reasoning detalhado
        reasoning = {
            'ofi_score': round(ofi_score, 4),
            'volume_score': round(volume_score, 4),
            'book_score': round(book_score, 4),
            'final_score': round(final_score, 4),
            'ofi_5': round(ofi_5, 4),
            'book_imbalance': round(book_imbalance, 4)
        }
        
        agent_signal = AgentSignal(
            agent_name=self.name,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            timestamp=datetime.now()
        )
        
        self.last_signal = agent_signal
        return agent_signal


class LiquidityAgent(BaseAgent):
    """Agente especialista em liquidez e profundidade de mercado"""
    
    def __init__(self):
        super().__init__("LiquidityAgent")
        self.feature_requirements = [
            'bid_volume_total', 'ask_volume_total',
            'bid_levels_active', 'ask_levels_active',
            'book_depth_imbalance', 'volume_depth_ratio',
            'spread', 'spread_ma', 'spread_std',
            'volume_20', 'volume_50'
        ]
    
    def analyze(self, features: Dict) -> AgentSignal:
        """Analisa liquidez e gera sinal"""
        if not self.validate_features(features):
            return AgentSignal(
                agent_name=self.name,
                signal=SignalStrength.NEUTRAL,
                confidence=0.0,
                reasoning={'error': 'missing_features'},
                timestamp=datetime.now()
            )
        
        # Análise de volumes
        bid_volume = features['bid_volume_total']
        ask_volume = features['ask_volume_total']
        volume_ratio = bid_volume / (ask_volume + 1e-10)
        
        # Análise de spread
        spread = features['spread']
        spread_ma = features['spread_ma']
        spread_std = features['spread_std']
        
        # Spread normalizado
        if spread_std > 0:
            spread_z = (spread - spread_ma) / spread_std
        else:
            spread_z = 0
        
        # Análise de profundidade
        depth_imbalance = features['book_depth_imbalance']
        volume_depth = features['volume_depth_ratio']
        
        # Níveis ativos
        bid_levels = features['bid_levels_active']
        ask_levels = features['ask_levels_active']
        level_ratio = bid_levels / (ask_levels + 1)
        
        # Score de liquidez
        liquidity_score = 0
        
        # Volume ratio favorece compra/venda
        if volume_ratio > 1.2:
            liquidity_score += 0.3
        elif volume_ratio < 0.8:
            liquidity_score -= 0.3
        
        # Spread estreito indica boa liquidez
        if spread_z < -1:  # Spread menor que o normal
            liquidity_score += 0.2 * abs(spread_z)
        elif spread_z > 1:  # Spread maior que o normal
            liquidity_score -= 0.1 * spread_z
        
        # Profundidade do book
        liquidity_score += depth_imbalance * 0.3
        
        # Níveis ativos
        if level_ratio > 1.3:
            liquidity_score += 0.2
        elif level_ratio < 0.7:
            liquidity_score -= 0.2
        
        # Determinar sinal
        if liquidity_score > 0.3:
            signal = SignalStrength.BUY
        elif liquidity_score < -0.3:
            signal = SignalStrength.SELL
        else:
            signal = SignalStrength.NEUTRAL
        
        # Confiança baseada na clareza do sinal
        confidence = min(abs(liquidity_score), 0.9)
        
        reasoning = {
            'volume_ratio': round(volume_ratio, 3),
            'spread_z': round(spread_z, 3),
            'depth_imbalance': round(depth_imbalance, 3),
            'level_ratio': round(level_ratio, 3),
            'liquidity_score': round(liquidity_score, 3)
        }
        
        return AgentSignal(
            agent_name=self.name,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            timestamp=datetime.now()
        )


class TapeReadingAgent(BaseAgent):
    """Agente especialista em tape reading e análise de trades"""
    
    def __init__(self):
        super().__init__("TapeReadingAgent")
        self.feature_requirements = [
            'trade_flow_5', 'trade_flow_10',
            'buy_intensity', 'sell_intensity',
            'large_trade_ratio', 'trade_velocity',
            'vwap', 'vwap_distance',
            'aggressive_buy_ratio', 'aggressive_sell_ratio'
        ]
    
    def analyze(self, features: Dict) -> AgentSignal:
        """Analisa tape/trades e gera sinal"""
        if not self.validate_features(features):
            return AgentSignal(
                agent_name=self.name,
                signal=SignalStrength.NEUTRAL,
                confidence=0.0,
                reasoning={'error': 'missing_features'},
                timestamp=datetime.now()
            )
        
        # Trade flow
        trade_flow_5 = features['trade_flow_5']
        trade_flow_10 = features['trade_flow_10']
        
        # Intensidade de compra/venda
        buy_intensity = features['buy_intensity']
        sell_intensity = features['sell_intensity']
        intensity_diff = buy_intensity - sell_intensity
        
        # Large trades
        large_trade_ratio = features['large_trade_ratio']
        trade_velocity = features['trade_velocity']
        
        # VWAP analysis
        vwap_distance = features['vwap_distance']
        
        # Agressores
        aggr_buy = features['aggressive_buy_ratio']
        aggr_sell = features['aggressive_sell_ratio']
        aggressor_diff = aggr_buy - aggr_sell
        
        # Calcular tape score
        tape_score = 0
        
        # Trade flow indica direção
        flow_score = (trade_flow_5 * 0.6 + trade_flow_10 * 0.4)
        tape_score += flow_score * 0.3
        
        # Intensidade
        tape_score += intensity_diff * 0.25
        
        # Large trades (institucionais)
        if large_trade_ratio > 0.3:
            tape_score += 0.2 * np.sign(flow_score)
        
        # Velocidade alta indica momento
        if trade_velocity > 1.5:
            tape_score += 0.15 * np.sign(flow_score)
        
        # VWAP
        if vwap_distance > 0.002:  # Preço acima do VWAP
            tape_score += 0.1
        elif vwap_distance < -0.002:  # Preço abaixo do VWAP
            tape_score -= 0.1
        
        # Agressores
        tape_score += aggressor_diff * 0.2
        
        # Determinar sinal
        if tape_score > 0.35:
            signal = SignalStrength.STRONG_BUY if tape_score > 0.6 else SignalStrength.BUY
        elif tape_score < -0.35:
            signal = SignalStrength.STRONG_SELL if tape_score < -0.6 else SignalStrength.SELL
        else:
            signal = SignalStrength.NEUTRAL
        
        confidence = min(abs(tape_score) * 1.2, 0.95)
        
        reasoning = {
            'flow_score': round(flow_score, 4),
            'intensity_diff': round(intensity_diff, 4),
            'large_trade_ratio': round(large_trade_ratio, 3),
            'aggressor_diff': round(aggressor_diff, 4),
            'tape_score': round(tape_score, 4)
        }
        
        return AgentSignal(
            agent_name=self.name,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            timestamp=datetime.now()
        )


class FootprintPatternAgent(BaseAgent):
    """Agente especialista em padrões de footprint e clusters"""
    
    def __init__(self):
        super().__init__("FootprintPatternAgent")
        self.feature_requirements = [
            'volume_profile_skew', 'volume_concentration',
            'top_trader_ratio', 'top_trader_side_bias',
            'micro_price', 'weighted_mid_price',
            'volatility_5', 'volatility_20',
            'returns_5', 'returns_20'
        ]
        self.pattern_history = []
    
    def analyze(self, features: Dict) -> AgentSignal:
        """Analisa padrões de footprint e gera sinal"""
        if not self.validate_features(features):
            return AgentSignal(
                agent_name=self.name,
                signal=SignalStrength.NEUTRAL,
                confidence=0.0,
                reasoning={'error': 'missing_features'},
                timestamp=datetime.now()
            )
        
        # Volume profile
        vol_skew = features['volume_profile_skew']
        vol_concentration = features['volume_concentration']
        
        # Top traders
        top_ratio = features['top_trader_ratio']
        top_bias = features['top_trader_side_bias']
        
        # Preços
        micro_price = features['micro_price']
        weighted_mid = features['weighted_mid_price']
        price_diff = (micro_price - weighted_mid) / weighted_mid if weighted_mid != 0 else 0
        
        # Volatilidade
        vol_5 = features['volatility_5']
        vol_20 = features['volatility_20']
        vol_ratio = vol_5 / (vol_20 + 1e-10)
        
        # Retornos
        ret_5 = features['returns_5']
        ret_20 = features['returns_20']
        
        # Detectar padrões
        patterns_detected = []
        pattern_score = 0
        
        # Padrão: Volume skew com top traders
        if vol_skew > 0.2 and top_bias > 0.3:
            patterns_detected.append('bullish_accumulation')
            pattern_score += 0.4
        elif vol_skew < -0.2 and top_bias < -0.3:
            patterns_detected.append('bearish_distribution')
            pattern_score -= 0.4
        
        # Padrão: Concentração de volume
        if vol_concentration > 0.6:
            if price_diff > 0:
                patterns_detected.append('concentrated_buying')
                pattern_score += 0.3
            elif price_diff < 0:
                patterns_detected.append('concentrated_selling')
                pattern_score -= 0.3
        
        # Padrão: Expansão de volatilidade
        if vol_ratio > 1.5:
            patterns_detected.append('volatility_expansion')
            # Direção baseada em retornos recentes
            pattern_score += np.sign(ret_5) * 0.2
        
        # Padrão: Smart money
        if top_ratio > 0.4:
            patterns_detected.append('smart_money_active')
            pattern_score += top_bias * 0.3
        
        # Determinar sinal
        if pattern_score > 0.3:
            signal = SignalStrength.STRONG_BUY if pattern_score > 0.5 else SignalStrength.BUY
        elif pattern_score < -0.3:
            signal = SignalStrength.STRONG_SELL if pattern_score < -0.5 else SignalStrength.SELL
        else:
            signal = SignalStrength.NEUTRAL
        
        confidence = min(abs(pattern_score) * 1.3, 0.9)
        
        # Adicionar ao histórico
        self.pattern_history.append({
            'timestamp': datetime.now(),
            'patterns': patterns_detected,
            'score': pattern_score
        })
        
        # Manter apenas últimos 100 padrões
        if len(self.pattern_history) > 100:
            self.pattern_history.pop(0)
        
        reasoning = {
            'patterns_detected': patterns_detected,
            'vol_skew': round(vol_skew, 4),
            'top_bias': round(top_bias, 4),
            'vol_concentration': round(vol_concentration, 3),
            'pattern_score': round(pattern_score, 4)
        }
        
        return AgentSignal(
            agent_name=self.name,
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            timestamp=datetime.now()
        )


class HMARLCoordinator:
    """Coordenador central dos agentes HMARL"""
    
    def __init__(self):
        self.logger = logging.getLogger("HMARLCoordinator")
        
        # Inicializar agentes
        self.agents = {
            'order_flow': OrderFlowSpecialistAgent(),
            'liquidity': LiquidityAgent(),
            'tape_reading': TapeReadingAgent(),
            'footprint': FootprintPatternAgent()
        }
        
        # Pesos dos agentes (podem ser ajustados dinamicamente)
        self.agent_weights = {
            'order_flow': 0.3,
            'liquidity': 0.2,
            'tape_reading': 0.25,
            'footprint': 0.25
        }
        
        self.consensus_history = []
        
    def analyze_all_agents(self, features: Dict) -> Dict[str, AgentSignal]:
        """Coleta análise de todos os agentes"""
        signals = {}
        
        for name, agent in self.agents.items():
            try:
                signal = agent.analyze(features)
                signals[name] = signal
                self.logger.debug(f"Agente {name}: {signal.signal.name} (conf: {signal.confidence:.2f})")
            except Exception as e:
                self.logger.error(f"Erro no agente {name}: {e}")
                signals[name] = AgentSignal(
                    agent_name=name,
                    signal=SignalStrength.NEUTRAL,
                    confidence=0.0,
                    reasoning={'error': str(e)},
                    timestamp=datetime.now()
                )
        
        return signals
    
    def calculate_consensus(self, agent_signals: Dict[str, AgentSignal]) -> Tuple[float, float]:
        """
        Calcula consenso ponderado dos agentes
        Retorna: (sinal_consenso, confiança_consenso)
        """
        weighted_signal = 0
        weighted_confidence = 0
        total_weight = 0
        
        for name, signal in agent_signals.items():
            weight = self.agent_weights.get(name, 0.25)
            
            # Ajustar peso pela confiança do agente
            adjusted_weight = weight * signal.confidence
            
            # Adicionar ao consenso
            weighted_signal += signal.signal.value * adjusted_weight
            weighted_confidence += signal.confidence * weight
            total_weight += weight
        
        if total_weight > 0:
            consensus_signal = weighted_signal / total_weight
            consensus_confidence = weighted_confidence / total_weight
        else:
            consensus_signal = 0
            consensus_confidence = 0
        
        # Normalizar sinal para [-1, 1]
        consensus_signal = np.clip(consensus_signal / 2, -1, 1)
        
        return consensus_signal, consensus_confidence
    
    def get_trading_decision(self, features: Dict) -> Dict:
        """
        Obtém decisão de trading baseada no consenso dos agentes
        """
        # Coletar sinais de todos os agentes
        agent_signals = self.analyze_all_agents(features)
        
        # Calcular consenso
        consensus_signal, consensus_confidence = self.calculate_consensus(agent_signals)
        
        # Determinar ação
        if consensus_confidence < 0.3:
            action = 'HOLD'
            reasoning = 'Confiança insuficiente'
        elif consensus_signal > 0.3:
            action = 'BUY' if consensus_signal > 0.5 else 'WEAK_BUY'
            reasoning = 'Consenso bullish'
        elif consensus_signal < -0.3:
            action = 'SELL' if consensus_signal < -0.5 else 'WEAK_SELL'
            reasoning = 'Consenso bearish'
        else:
            action = 'HOLD'
            reasoning = 'Sinal neutro'
        
        # Preparar resposta
        decision = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'consensus_signal': round(consensus_signal, 4),
            'consensus_confidence': round(consensus_confidence, 4),
            'reasoning': reasoning,
            'agent_signals': {
                name: {
                    'signal': sig.signal.name,
                    'confidence': round(sig.confidence, 3),
                    'reasoning': sig.reasoning
                }
                for name, sig in agent_signals.items()
            }
        }
        
        # Adicionar ao histórico
        self.consensus_history.append(decision)
        if len(self.consensus_history) > 100:
            self.consensus_history.pop(0)
        
        self.logger.info(f"Decisão HMARL: {action} (sinal: {consensus_signal:.3f}, conf: {consensus_confidence:.3f})")
        
        return decision
    
    def update_agent_weights(self, performance_data: Dict):
        """
        Atualiza pesos dos agentes baseado em performance
        """
        total_accuracy = sum(performance_data.values())
        
        if total_accuracy > 0:
            for agent_name in self.agent_weights:
                if agent_name in performance_data:
                    # Novo peso proporcional à performance
                    self.agent_weights[agent_name] = performance_data[agent_name] / total_accuracy
        
        # Normalizar pesos
        total_weight = sum(self.agent_weights.values())
        if total_weight > 0:
            for agent_name in self.agent_weights:
                self.agent_weights[agent_name] /= total_weight
        
        self.logger.info(f"Pesos atualizados: {self.agent_weights}")


def create_hmarl_system() -> HMARLCoordinator:
    """Factory function para criar sistema HMARL"""
    return HMARLCoordinator()


if __name__ == "__main__":
    # Teste básico
    logging.basicConfig(level=logging.INFO)
    
    # Criar sistema
    hmarl = create_hmarl_system()
    
    # Simular features (65 features)
    test_features = {
        # Volatility (10)
        'volatility_5': 0.015, 'volatility_10': 0.018, 'volatility_20': 0.020,
        'volatility_50': 0.022, 'volatility_100': 0.025, 'volatility_gk': 0.016,
        'volatility_rs': 0.017, 'volatility_yz': 0.019, 'atr_14': 50.5, 'atr_20': 52.3,
        
        # Returns (10)
        'returns_1': 0.001, 'returns_2': 0.002, 'returns_5': 0.003,
        'returns_10': 0.004, 'returns_20': 0.005, 'returns_50': 0.006,
        'returns_100': 0.007, 'log_returns_1': 0.001, 'log_returns_5': 0.003,
        'log_returns_20': 0.005,
        
        # Order Flow (8)
        'order_flow_imbalance_5': 0.15, 'order_flow_imbalance_10': 0.12,
        'order_flow_imbalance_20': 0.10, 'signed_volume_5': 1000,
        'signed_volume_10': 1500, 'signed_volume_20': 2000,
        'trade_flow_5': 0.08, 'trade_flow_10': 0.06,
        
        # Volume (8)
        'volume_20': 100000, 'volume_50': 95000, 'volume_100': 90000,
        'volume_mean': 92000, 'volume_std': 5000, 'volume_skew': 0.5,
        'volume_kurt': 2.8, 'relative_volume': 1.1,
        
        # Technical (8)
        'rsi_14': 55, 'ma_5_20_ratio': 1.01, 'ma_20_50_ratio': 1.02,
        'ema_distance': 0.002, 'bb_position': 0.5, 'sharpe_20': 1.5,
        'sortino_20': 1.8, 'max_drawdown_20': 0.03,
        
        # Microstructure (15)
        'spread': 1.0, 'spread_ma': 1.2, 'spread_std': 0.2,
        'bid_volume_total': 5000, 'ask_volume_total': 4500,
        'bid_levels_active': 5, 'ask_levels_active': 5,
        'book_imbalance': 0.05, 'book_pressure': 0.1,
        'micro_price': 5450.5, 'weighted_mid_price': 5450.3,
        'vwap': 5450.0, 'vwap_distance': 0.0001,
        'top_trader_ratio': 0.35, 'top_trader_side_bias': 0.2,
        
        # Temporal (6)
        'hour': 14, 'minute': 30, 'hour_sin': 0.5, 'hour_cos': 0.866,
        'is_opening': 0, 'is_closing': 0,
        
        # Additional for agents
        'book_depth_imbalance': 0.1, 'volume_depth_ratio': 1.2,
        'buy_intensity': 0.6, 'sell_intensity': 0.4,
        'large_trade_ratio': 0.25, 'trade_velocity': 1.3,
        'aggressive_buy_ratio': 0.55, 'aggressive_sell_ratio': 0.45,
        'volume_profile_skew': 0.15, 'volume_concentration': 0.4
    }
    
    # Obter decisão
    decision = hmarl.get_trading_decision(test_features)
    
    print("\n" + "=" * 60)
    print("DECISÃO HMARL")
    print("=" * 60)
    print(json.dumps(decision, indent=2))