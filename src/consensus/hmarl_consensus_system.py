"""
Sistema de Consenso HMARL
Combina sinais de múltiplos agentes com ML para decisão final
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import json
from collections import deque

logger = logging.getLogger(__name__)


class TradingAction(Enum):
    """Ações de trading possíveis"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    WEAK_BUY = "WEAK_BUY"
    HOLD = "HOLD"
    WEAK_SELL = "WEAK_SELL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass
class ConsensusDecision:
    """Decisão de consenso do sistema"""
    timestamp: datetime
    action: TradingAction
    confidence: float
    ml_signal: float
    agent_consensus: float
    combined_signal: float
    reasoning: Dict
    agent_votes: Dict
    risk_assessment: Dict


class RiskAssessor:
    """Avaliador de risco para decisões de trading"""
    
    def __init__(self):
        self.max_position_size = 1
        self.max_daily_trades = 10
        self.max_drawdown_pct = 5.0
        self.current_position = 0
        self.daily_trades = 0
        self.peak_capital = 100000
        self.current_capital = 100000
        
    def assess_risk(self, action: TradingAction, confidence: float) -> Dict:
        """Avalia risco da ação proposta"""
        risk_score = 0
        warnings = []
        allow_trade = True
        
        # Verificar limites de trading
        if self.daily_trades >= self.max_daily_trades:
            warnings.append("Limite diário de trades atingido")
            allow_trade = False
            risk_score += 0.5
        
        # Verificar drawdown
        drawdown = (self.peak_capital - self.current_capital) / self.peak_capital * 100
        if drawdown > self.max_drawdown_pct:
            warnings.append(f"Drawdown alto: {drawdown:.1f}%")
            allow_trade = False
            risk_score += 0.3
        
        # Verificar tamanho da posição
        if abs(self.current_position) >= self.max_position_size:
            if (action in [TradingAction.BUY, TradingAction.STRONG_BUY] and self.current_position > 0) or \
               (action in [TradingAction.SELL, TradingAction.STRONG_SELL] and self.current_position < 0):
                warnings.append("Posição máxima atingida")
                allow_trade = False
                risk_score += 0.2
        
        # Ajustar por confiança
        if confidence < 0.5:
            warnings.append("Confiança baixa")
            risk_score += 0.2
        
        # Calcular score final
        risk_level = "LOW" if risk_score < 0.3 else "MEDIUM" if risk_score < 0.6 else "HIGH"
        
        return {
            'risk_score': round(risk_score, 3),
            'risk_level': risk_level,
            'allow_trade': allow_trade,
            'warnings': warnings,
            'current_position': self.current_position,
            'daily_trades': self.daily_trades,
            'drawdown_pct': round(drawdown, 2)
        }


class ConsensusEngine:
    """Motor de consenso que combina ML e agentes HMARL"""
    
    def __init__(self):
        self.ml_weight = 0.4  # Peso do modelo ML
        self.agent_weight = 0.6  # Peso dos agentes HMARL
        
        # Histórico de decisões
        self.decision_history = deque(maxlen=100)
        
        # Avaliador de risco
        self.risk_assessor = RiskAssessor()
        
        # Métricas de performance
        self.performance_metrics = {
            'total_decisions': 0,
            'buy_decisions': 0,
            'sell_decisions': 0,
            'hold_decisions': 0,
            'avg_confidence': 0,
            'successful_trades': 0,
            'failed_trades': 0
        }
        
        # Adaptive weights baseado em performance
        self.adaptive_weights = True
        self.weight_update_frequency = 20  # Atualizar a cada 20 decisões
        
    def calculate_consensus(self, 
                           ml_prediction: float,
                           agent_signals: Dict,
                           features: Dict) -> ConsensusDecision:
        """
        Calcula consenso entre ML e agentes HMARL
        
        Args:
            ml_prediction: Predição do modelo ML (0-1)
            agent_signals: Sinais dos agentes HMARL
            features: Features completas para análise adicional
        """
        
        # 1. Processar sinal ML
        ml_signal = self._process_ml_signal(ml_prediction)
        
        # 2. Processar consenso dos agentes
        agent_consensus, agent_votes = self._process_agent_consensus(agent_signals)
        
        # 3. Combinar sinais com pesos adaptativos
        combined_signal = self._combine_signals(ml_signal, agent_consensus)
        
        # 4. Determinar ação de trading
        action = self._determine_action(combined_signal)
        
        # 5. Calcular confiança
        confidence = self._calculate_confidence(
            ml_signal, agent_consensus, agent_votes, features
        )
        
        # 6. Avaliar risco
        risk_assessment = self.risk_assessor.assess_risk(action, confidence)
        
        # 7. Ajustar decisão baseado em risco
        if not risk_assessment['allow_trade'] and action != TradingAction.HOLD:
            action = TradingAction.HOLD
            confidence *= 0.5
        
        # 8. Criar reasoning detalhado
        reasoning = self._create_reasoning(
            ml_signal, agent_consensus, combined_signal, 
            confidence, risk_assessment
        )
        
        # 9. Criar decisão final
        decision = ConsensusDecision(
            timestamp=datetime.now(),
            action=action,
            confidence=confidence,
            ml_signal=ml_signal,
            agent_consensus=agent_consensus,
            combined_signal=combined_signal,
            reasoning=reasoning,
            agent_votes=agent_votes,
            risk_assessment=risk_assessment
        )
        
        # 10. Atualizar histórico e métricas
        self._update_metrics(decision)
        
        # 11. Adaptar pesos se necessário
        if self.adaptive_weights and self.performance_metrics['total_decisions'] % self.weight_update_frequency == 0:
            self._adapt_weights()
        
        logger.info(f"Consenso: {action.value} (conf={confidence:.2f}, signal={combined_signal:.3f})")
        
        return decision
    
    def _process_ml_signal(self, ml_prediction: float) -> float:
        """Processa predição ML para sinal normalizado [-1, 1]"""
        # Converter de [0, 1] para [-1, 1]
        return (ml_prediction - 0.5) * 2
    
    def _process_agent_consensus(self, agent_signals: Dict) -> Tuple[float, Dict]:
        """Processa sinais dos agentes para consenso"""
        if not agent_signals:
            return 0.0, {}
        
        weighted_sum = 0
        weight_sum = 0
        agent_votes = {}
        
        for agent_name, signal_data in agent_signals.items():
            # Extrair informações do sinal
            signal_value = signal_data.get('consensus_signal', 0)
            confidence = signal_data.get('confidence', 0.5)
            
            # Ponderar por confiança
            weighted_sum += signal_value * confidence
            weight_sum += confidence
            
            # Registrar voto
            agent_votes[agent_name] = {
                'signal': signal_value,
                'confidence': confidence
            }
        
        # Calcular consenso
        consensus = weighted_sum / weight_sum if weight_sum > 0 else 0
        
        return consensus, agent_votes
    
    def _combine_signals(self, ml_signal: float, agent_consensus: float) -> float:
        """Combina sinais ML e agentes com pesos adaptativos"""
        combined = (
            ml_signal * self.ml_weight + 
            agent_consensus * self.agent_weight
        )
        
        # Normalizar para [-1, 1]
        return np.clip(combined, -1, 1)
    
    def _determine_action(self, combined_signal: float) -> TradingAction:
        """Determina ação baseada no sinal combinado"""
        if combined_signal > 0.6:
            return TradingAction.STRONG_BUY
        elif combined_signal > 0.3:
            return TradingAction.BUY
        elif combined_signal > 0.1:
            return TradingAction.WEAK_BUY
        elif combined_signal < -0.6:
            return TradingAction.STRONG_SELL
        elif combined_signal < -0.3:
            return TradingAction.SELL
        elif combined_signal < -0.1:
            return TradingAction.WEAK_SELL
        else:
            return TradingAction.HOLD
    
    def _calculate_confidence(self, ml_signal: float, agent_consensus: float, 
                             agent_votes: Dict, features: Dict) -> float:
        """Calcula confiança na decisão"""
        confidence_factors = []
        
        # 1. Concordância entre ML e agentes
        agreement = 1 - abs(ml_signal - agent_consensus) / 2
        confidence_factors.append(agreement * 0.3)
        
        # 2. Força do sinal
        signal_strength = abs(ml_signal + agent_consensus) / 2
        confidence_factors.append(signal_strength * 0.3)
        
        # 3. Consenso entre agentes
        if agent_votes:
            agent_signals = [v['signal'] for v in agent_votes.values()]
            if len(agent_signals) > 1:
                agent_std = np.std(agent_signals)
                agent_agreement = 1 - min(agent_std, 1)
                confidence_factors.append(agent_agreement * 0.2)
            else:
                confidence_factors.append(0.1)
        
        # 4. Qualidade das features
        feature_quality = self._assess_feature_quality(features)
        confidence_factors.append(feature_quality * 0.2)
        
        # Calcular confiança final
        confidence = sum(confidence_factors)
        
        return np.clip(confidence, 0, 1)
    
    def _assess_feature_quality(self, features: Dict) -> float:
        """Avalia qualidade das features disponíveis"""
        if not features:
            return 0.0
        
        # Verificar quantas features não são zero/NaN
        valid_features = sum(1 for v in features.values() 
                           if v is not None and v != 0 and not np.isnan(v))
        
        # Qualidade baseada na proporção de features válidas
        quality = valid_features / max(len(features), 1)
        
        return min(quality, 1.0)
    
    def _create_reasoning(self, ml_signal: float, agent_consensus: float,
                         combined_signal: float, confidence: float,
                         risk_assessment: Dict) -> Dict:
        """Cria reasoning detalhado da decisão"""
        return {
            'ml_signal': round(ml_signal, 4),
            'agent_consensus': round(agent_consensus, 4),
            'combined_signal': round(combined_signal, 4),
            'confidence': round(confidence, 3),
            'ml_weight': self.ml_weight,
            'agent_weight': self.agent_weight,
            'risk_level': risk_assessment['risk_level'],
            'risk_warnings': risk_assessment['warnings']
        }
    
    def _update_metrics(self, decision: ConsensusDecision):
        """Atualiza métricas de performance"""
        self.performance_metrics['total_decisions'] += 1
        
        if decision.action in [TradingAction.BUY, TradingAction.STRONG_BUY]:
            self.performance_metrics['buy_decisions'] += 1
        elif decision.action in [TradingAction.SELL, TradingAction.STRONG_SELL]:
            self.performance_metrics['sell_decisions'] += 1
        else:
            self.performance_metrics['hold_decisions'] += 1
        
        # Atualizar média de confiança
        n = self.performance_metrics['total_decisions']
        prev_avg = self.performance_metrics['avg_confidence']
        self.performance_metrics['avg_confidence'] = (
            (prev_avg * (n - 1) + decision.confidence) / n
        )
        
        # Adicionar ao histórico
        self.decision_history.append(decision)
    
    def _adapt_weights(self):
        """Adapta pesos baseado em performance recente"""
        if len(self.decision_history) < 10:
            return
        
        # Analisar últimas decisões
        recent_decisions = list(self.decision_history)[-20:]
        
        # Calcular performance de ML vs Agentes
        ml_correct = 0
        agent_correct = 0
        
        for i in range(len(recent_decisions) - 1):
            current = recent_decisions[i]
            next_decision = recent_decisions[i + 1]
            
            # Verificar se a direção estava correta (simplificado)
            if current.ml_signal > 0 and next_decision.combined_signal > 0:
                ml_correct += 1
            elif current.ml_signal < 0 and next_decision.combined_signal < 0:
                ml_correct += 1
                
            if current.agent_consensus > 0 and next_decision.combined_signal > 0:
                agent_correct += 1
            elif current.agent_consensus < 0 and next_decision.combined_signal < 0:
                agent_correct += 1
        
        # Ajustar pesos
        total = ml_correct + agent_correct
        if total > 0:
            new_ml_weight = ml_correct / total
            new_agent_weight = agent_correct / total
            
            # Aplicar mudança gradual
            self.ml_weight = 0.7 * self.ml_weight + 0.3 * new_ml_weight
            self.agent_weight = 0.7 * self.agent_weight + 0.3 * new_agent_weight
            
            # Normalizar
            total_weight = self.ml_weight + self.agent_weight
            self.ml_weight /= total_weight
            self.agent_weight /= total_weight
            
            logger.info(f"Pesos adaptados: ML={self.ml_weight:.2f}, Agents={self.agent_weight:.2f}")
    
    def get_performance_summary(self) -> Dict:
        """Retorna resumo de performance"""
        total = self.performance_metrics['total_decisions']
        if total == 0:
            return {}
        
        return {
            'total_decisions': total,
            'buy_rate': self.performance_metrics['buy_decisions'] / total,
            'sell_rate': self.performance_metrics['sell_decisions'] / total,
            'hold_rate': self.performance_metrics['hold_decisions'] / total,
            'avg_confidence': self.performance_metrics['avg_confidence'],
            'current_weights': {
                'ml': self.ml_weight,
                'agents': self.agent_weight
            }
        }


class IntegratedHMARLSystem:
    """Sistema integrado HMARL com consenso"""
    
    def __init__(self):
        # Importar componentes
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
        from src.agents.hmarl_agents_enhanced import HMARLCoordinator
        from src.broadcasting.feature_broadcaster import BroadcastOrchestrator
        
        self.logger = logging.getLogger("IntegratedHMARL")
        
        # Componentes do sistema
        self.hmarl_coordinator = HMARLCoordinator()
        self.consensus_engine = ConsensusEngine()
        self.broadcast_orchestrator = BroadcastOrchestrator(port=5559)
        
        # Estatísticas
        self.stats = {
            'decisions_made': 0,
            'broadcasts_sent': 0,
            'errors': 0
        }
    
    def process_features_and_decide(self, 
                                   features: Dict[str, float],
                                   ml_prediction: float) -> ConsensusDecision:
        """
        Processa features e toma decisão de trading
        
        Args:
            features: 65 features calculadas
            ml_prediction: Predição do modelo ML
        """
        try:
            # 1. Broadcast features para agentes
            success = self.broadcast_orchestrator.broadcast_to_agents(
                features=features,
                ml_prediction=ml_prediction,
                regime='UNKNOWN'  # Pode ser determinado pelas features
            )
            
            if success:
                self.stats['broadcasts_sent'] += 1
            
            # 2. Obter decisão dos agentes HMARL
            agent_decision = self.hmarl_coordinator.get_trading_decision(features)
            
            # 3. Calcular consenso final
            consensus_decision = self.consensus_engine.calculate_consensus(
                ml_prediction=ml_prediction,
                agent_signals={'hmarl': agent_decision},
                features=features
            )
            
            self.stats['decisions_made'] += 1
            
            # 4. Log da decisão
            self.logger.info(
                f"Decisão integrada: {consensus_decision.action.value} "
                f"(conf={consensus_decision.confidence:.2f})"
            )
            
            return consensus_decision
            
        except Exception as e:
            self.logger.error(f"Erro no processamento: {e}")
            self.stats['errors'] += 1
            
            # Retornar decisão conservadora em caso de erro
            return ConsensusDecision(
                timestamp=datetime.now(),
                action=TradingAction.HOLD,
                confidence=0.0,
                ml_signal=0.0,
                agent_consensus=0.0,
                combined_signal=0.0,
                reasoning={'error': str(e)},
                agent_votes={},
                risk_assessment={'risk_level': 'HIGH', 'allow_trade': False}
            )
    
    def get_system_status(self) -> Dict:
        """Retorna status do sistema integrado"""
        return {
            'stats': self.stats,
            'consensus_performance': self.consensus_engine.get_performance_summary(),
            'agent_weights': self.hmarl_coordinator.agent_weights,
            'broadcast_history': len(self.broadcast_orchestrator.feature_buffer)
        }
    
    def close(self):
        """Fecha sistema integrado"""
        self.broadcast_orchestrator.close()
        self.logger.info("Sistema integrado HMARL fechado")


def test_consensus_system():
    """Teste do sistema de consenso"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Criar sistema integrado
    system = IntegratedHMARLSystem()
    
    # Simular features (65 features)
    test_features = {f'feature_{i}': np.random.random() for i in range(65)}
    
    # Adicionar features específicas que os agentes precisam
    test_features.update({
        'order_flow_imbalance_5': 0.15,
        'order_flow_imbalance_10': 0.12,
        'signed_volume_5': 1000,
        'signed_volume_10': 1500,
        'bid_volume_total': 5000,
        'ask_volume_total': 4500,
        'book_imbalance': 0.05,
        'book_pressure': 0.1,
        'micro_price': 5450.5,
        'weighted_mid_price': 5450.3,
        'spread': 1.0,
        'spread_ma': 1.2,
        'spread_std': 0.2,
        'bid_levels_active': 5,
        'ask_levels_active': 5,
        'book_depth_imbalance': 0.1,
        'volume_depth_ratio': 1.2,
        'trade_flow_5': 0.08,
        'trade_flow_10': 0.06,
        'buy_intensity': 0.6,
        'sell_intensity': 0.4,
        'large_trade_ratio': 0.25,
        'trade_velocity': 1.3,
        'vwap': 5450.0,
        'vwap_distance': 0.0001,
        'aggressive_buy_ratio': 0.55,
        'aggressive_sell_ratio': 0.45,
        'volume_profile_skew': 0.15,
        'volume_concentration': 0.4,
        'top_trader_ratio': 0.35,
        'top_trader_side_bias': 0.2,
        'volatility_5': 0.015,
        'volatility_20': 0.020,
        'returns_5': 0.003,
        'returns_20': 0.005,
        'volume_20': 100000,
        'volume_50': 95000
    })
    
    # Testar múltiplas decisões
    logger.info("\n" + "=" * 60)
    logger.info("TESTE DO SISTEMA DE CONSENSO")
    logger.info("=" * 60)
    
    for i in range(5):
        logger.info(f"\n--- Decisão {i+1} ---")
        
        # Simular predição ML variada
        ml_prediction = 0.3 + 0.4 * np.random.random()
        
        # Processar e decidir
        decision = system.process_features_and_decide(test_features, ml_prediction)
        
        # Exibir resultado
        logger.info(f"ML Prediction: {ml_prediction:.3f}")
        logger.info(f"Action: {decision.action.value}")
        logger.info(f"Confidence: {decision.confidence:.3f}")
        logger.info(f"Combined Signal: {decision.combined_signal:.3f}")
        logger.info(f"Risk Level: {decision.risk_assessment['risk_level']}")
        
        # Variar features para próxima iteração
        for key in test_features:
            if np.random.random() > 0.7:
                test_features[key] *= (0.9 + 0.2 * np.random.random())
    
    # Status final
    logger.info("\n" + "=" * 60)
    logger.info("STATUS DO SISTEMA")
    logger.info("=" * 60)
    status = system.get_system_status()
    logger.info(json.dumps(status, indent=2))
    
    # Cleanup
    system.close()
    
    logger.info("\nTeste concluído com sucesso!")


if __name__ == "__main__":
    test_consensus_system()