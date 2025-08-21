"""
Filtro de Concordância ML + HMARL
Só permite trades quando há concordância entre os sistemas
"""

import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ConcordanceFilter:
    """Filtro que exige concordância entre ML e HMARL para executar trades"""
    
    def __init__(self, config: Dict = None):
        """
        Inicializa o filtro de concordância
        
        Args:
            config: Configuração do filtro
        """
        self.config = config or {
            'min_ml_confidence': 0.6,      # Confiança mínima ML
            'min_hmarl_confidence': 0.55,  # Confiança mínima HMARL
            'min_combined_confidence': 0.58,  # Confiança mínima combinada
            'direction_match_required': True,  # Exige mesma direção
            'strength_threshold': 0.3,     # Threshold de força do sinal
            'regime_filters': {
                'TRENDING_UP': {
                    'allow_sell': False,    # Não vende em tendência de alta
                    'min_confidence': 0.55
                },
                'TRENDING_DOWN': {
                    'allow_buy': False,     # Não compra em tendência de baixa
                    'min_confidence': 0.55
                },
                'RANGING': {
                    'allow_buy': True,
                    'allow_sell': True,
                    'min_confidence': 0.65   # Mais conservador em lateralização
                },
                'VOLATILE': {
                    'allow_buy': True,
                    'allow_sell': True,
                    'min_confidence': 0.70   # Muito conservador em volatilidade
                }
            }
        }
        
        # Estatísticas
        self.stats = {
            'total_signals': 0,
            'filtered_signals': 0,
            'concordance_rate': 0,
            'filters_applied': {
                'ml_confidence': 0,
                'hmarl_confidence': 0,
                'direction_mismatch': 0,
                'combined_confidence': 0,
                'regime_block': 0,
                'strength_low': 0
            }
        }
        
        # Histórico recente
        self.recent_decisions = []
        
        logger.info("ConcordanceFilter inicializado")
    
    def check_concordance(self,
                         ml_prediction: Dict,
                         hmarl_consensus: Dict,
                         regime_data: Dict = None) -> Tuple[bool, Dict]:
        """
        Verifica concordância entre ML e HMARL
        
        Args:
            ml_prediction: Predição do ML
            hmarl_consensus: Consenso HMARL
            regime_data: Dados do regime atual (opcional)
            
        Returns:
            Tuple (aprovado, detalhes)
        """
        self.stats['total_signals'] += 1
        
        # Extrair dados ML
        ml_signal = ml_prediction.get('signal', 0)
        ml_confidence = ml_prediction.get('confidence', 0)
        ml_action = self._signal_to_action(ml_signal)
        
        # Extrair dados HMARL
        hmarl_signal = hmarl_consensus.get('signal', 0)
        hmarl_confidence = hmarl_consensus.get('confidence', 0)
        hmarl_action = hmarl_consensus.get('action', 'HOLD')
        
        # Resultado inicial
        result = {
            'approved': False,
            'ml_action': ml_action,
            'ml_confidence': ml_confidence,
            'hmarl_action': hmarl_action,
            'hmarl_confidence': hmarl_confidence,
            'combined_confidence': 0,
            'filters_failed': [],
            'timestamp': datetime.now()
        }
        
        # Filtro 1: Confiança mínima ML
        if ml_confidence < self.config['min_ml_confidence']:
            result['filters_failed'].append('ml_confidence_low')
            self.stats['filters_applied']['ml_confidence'] += 1
            self._log_decision(result, approved=False)
            return False, result
        
        # Filtro 2: Confiança mínima HMARL
        if hmarl_confidence < self.config['min_hmarl_confidence']:
            result['filters_failed'].append('hmarl_confidence_low')
            self.stats['filters_applied']['hmarl_confidence'] += 1
            self._log_decision(result, approved=False)
            return False, result
        
        # Filtro 3: Verificar concordância de direção
        if self.config['direction_match_required']:
            if ml_action != hmarl_action or ml_action == 'HOLD':
                result['filters_failed'].append('direction_mismatch')
                self.stats['filters_applied']['direction_mismatch'] += 1
                self._log_decision(result, approved=False)
                return False, result
        
        # Calcular confiança combinada
        combined_confidence = self._calculate_combined_confidence(
            ml_confidence, hmarl_confidence, ml_signal, hmarl_signal
        )
        result['combined_confidence'] = combined_confidence
        
        # Filtro 4: Confiança combinada mínima
        if combined_confidence < self.config['min_combined_confidence']:
            result['filters_failed'].append('combined_confidence_low')
            self.stats['filters_applied']['combined_confidence'] += 1
            self._log_decision(result, approved=False)
            return False, result
        
        # Filtro 5: Força do sinal
        signal_strength = abs((ml_signal + hmarl_signal) / 2)
        if signal_strength < self.config['strength_threshold']:
            result['filters_failed'].append('signal_strength_low')
            self.stats['filters_applied']['strength_low'] += 1
            self._log_decision(result, approved=False)
            return False, result
        
        # Filtro 6: Regime de mercado (se fornecido)
        if regime_data:
            regime = regime_data.get('regime', 'UNDEFINED')
            regime_filter = self.config['regime_filters'].get(regime, {})
            
            # Verificar se ação é permitida no regime
            if ml_action == 'BUY' and not regime_filter.get('allow_buy', True):
                result['filters_failed'].append(f'buy_blocked_in_{regime}')
                self.stats['filters_applied']['regime_block'] += 1
                self._log_decision(result, approved=False)
                return False, result
            
            if ml_action == 'SELL' and not regime_filter.get('allow_sell', True):
                result['filters_failed'].append(f'sell_blocked_in_{regime}')
                self.stats['filters_applied']['regime_block'] += 1
                self._log_decision(result, approved=False)
                return False, result
            
            # Ajustar confiança mínima por regime
            regime_min_conf = regime_filter.get('min_confidence', 0.6)
            if combined_confidence < regime_min_conf:
                result['filters_failed'].append(f'confidence_low_for_{regime}')
                self._log_decision(result, approved=False)
                return False, result
        
        # Passou em todos os filtros
        result['approved'] = True
        result['signal_strength'] = signal_strength
        result['final_action'] = ml_action  # Usa ação do ML como final
        
        self.stats['filtered_signals'] += 1
        self.stats['concordance_rate'] = self.stats['filtered_signals'] / self.stats['total_signals']
        
        # Log de aprovação
        logger.info(
            f"[CONCORDANCE] APROVADO: {ml_action} | "
            f"ML: {ml_confidence:.1%} | HMARL: {hmarl_confidence:.1%} | "
            f"Combined: {combined_confidence:.1%}"
        )
        
        self._log_decision(result, approved=True)
        return True, result
    
    def _signal_to_action(self, signal: float) -> str:
        """Converte sinal numérico em ação"""
        if signal > 0.3:
            return 'BUY'
        elif signal < -0.3:
            return 'SELL'
        else:
            return 'HOLD'
    
    def _calculate_combined_confidence(self,
                                      ml_conf: float,
                                      hmarl_conf: float,
                                      ml_signal: float,
                                      hmarl_signal: float) -> float:
        """
        Calcula confiança combinada considerando concordância
        
        Returns:
            Confiança combinada (0.0 a 1.0)
        """
        # Média ponderada das confianças
        base_confidence = (ml_conf * 0.6 + hmarl_conf * 0.4)
        
        # Bonus por concordância forte
        signal_correlation = 1 - abs(ml_signal - hmarl_signal) / 2
        concordance_bonus = signal_correlation * 0.1
        
        # Penalidade se sinais têm magnitudes muito diferentes
        magnitude_diff = abs(abs(ml_signal) - abs(hmarl_signal))
        magnitude_penalty = magnitude_diff * 0.05
        
        combined = base_confidence + concordance_bonus - magnitude_penalty
        
        return max(0.0, min(1.0, combined))
    
    def _log_decision(self, result: Dict, approved: bool):
        """Registra decisão no histórico"""
        decision = {
            'timestamp': result['timestamp'],
            'approved': approved,
            'ml_action': result['ml_action'],
            'ml_confidence': result['ml_confidence'],
            'hmarl_action': result['hmarl_action'],
            'hmarl_confidence': result['hmarl_confidence'],
            'combined_confidence': result.get('combined_confidence', 0),
            'filters_failed': result.get('filters_failed', [])
        }
        
        self.recent_decisions.append(decision)
        
        # Manter apenas últimas 100 decisões
        if len(self.recent_decisions) > 100:
            self.recent_decisions.pop(0)
        
        # Log detalhado se rejeitado
        if not approved and result.get('filters_failed'):
            logger.debug(
                f"[CONCORDANCE] Rejeitado - Filtros: {', '.join(result['filters_failed'])} | "
                f"ML: {result['ml_action']}@{result['ml_confidence']:.1%} | "
                f"HMARL: {result['hmarl_action']}@{result['hmarl_confidence']:.1%}"
            )
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do filtro"""
        return {
            'total_signals': self.stats['total_signals'],
            'approved_signals': self.stats['filtered_signals'],
            'rejection_rate': 1 - self.stats['concordance_rate'] if self.stats['total_signals'] > 0 else 0,
            'concordance_rate': self.stats['concordance_rate'],
            'filters_triggered': self.stats['filters_applied'],
            'recent_approvals': sum(1 for d in self.recent_decisions[-20:] if d['approved']),
            'recent_rejections': sum(1 for d in self.recent_decisions[-20:] if not d['approved'])
        }
    
    def should_trade(self,
                    ml_prediction: Dict,
                    hmarl_consensus: Dict,
                    regime_data: Dict = None,
                    additional_checks: Dict = None) -> bool:
        """
        Método simplificado para verificar se deve executar trade
        
        Args:
            ml_prediction: Predição ML
            hmarl_consensus: Consenso HMARL
            regime_data: Dados do regime
            additional_checks: Verificações adicionais
            
        Returns:
            True se deve executar trade
        """
        # Verificar concordância básica
        approved, details = self.check_concordance(ml_prediction, hmarl_consensus, regime_data)
        
        if not approved:
            return False
        
        # Verificações adicionais opcionais
        if additional_checks:
            # Verificar horário
            if not additional_checks.get('market_open', True):
                logger.debug("[CONCORDANCE] Mercado fechado")
                return False
            
            # Verificar limite de trades
            if additional_checks.get('daily_trades', 0) >= additional_checks.get('max_daily_trades', 10):
                logger.debug("[CONCORDANCE] Limite diário atingido")
                return False
            
            # Verificar posição aberta
            if additional_checks.get('has_position', False):
                logger.debug("[CONCORDANCE] Já possui posição")
                return False
        
        return True
    
    def reset_stats(self):
        """Reseta estatísticas"""
        self.stats = {
            'total_signals': 0,
            'filtered_signals': 0,
            'concordance_rate': 0,
            'filters_applied': {
                'ml_confidence': 0,
                'hmarl_confidence': 0,
                'direction_mismatch': 0,
                'combined_confidence': 0,
                'regime_block': 0,
                'strength_low': 0
            }
        }
        self.recent_decisions = []
        logger.info("[CONCORDANCE] Estatísticas resetadas")