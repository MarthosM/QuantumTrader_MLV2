"""
Módulo de Integração dos Sistemas de Otimização
Conecta todos os novos módulos ao sistema principal de trading
"""

import logging
from typing import Dict, Optional, Tuple, List
from datetime import datetime

# Importar todos os módulos de otimização
from .market_regime_detector import MarketRegimeDetector
from .adaptive_targets import AdaptiveTargetSystem
from .concordance_filter import ConcordanceFilter
from .partial_exit_manager import PartialExitManager
from .trailing_stop_manager import TrailingStopManager
from .regime_metrics_tracker import RegimeMetricsTracker

logger = logging.getLogger(__name__)

class OptimizationSystem:
    """Sistema integrado de otimização para trading"""
    
    def __init__(self, config: Dict = None):
        """
        Inicializa o sistema de otimização completo
        
        Args:
            config: Configuração geral do sistema
        """
        self.config = config or {
            'enable_regime_detection': True,
            'enable_adaptive_targets': True,
            'enable_concordance_filter': True,
            'enable_partial_exits': True,
            'enable_trailing_stop': True,
            'enable_metrics_tracking': True,
            'min_confidence': 0.60,
            'max_daily_trades': 10,
            'position_size': 1
        }
        
        # Inicializar componentes
        self.regime_detector = MarketRegimeDetector() if self.config['enable_regime_detection'] else None
        self.adaptive_targets = AdaptiveTargetSystem() if self.config['enable_adaptive_targets'] else None
        self.concordance_filter = ConcordanceFilter() if self.config['enable_concordance_filter'] else None
        self.partial_exit_manager = PartialExitManager() if self.config['enable_partial_exits'] else None
        self.trailing_stop_manager = TrailingStopManager() if self.config['enable_trailing_stop'] else None
        self.metrics_tracker = RegimeMetricsTracker() if self.config['enable_metrics_tracking'] else None
        
        # Estado do sistema
        self.current_regime = 'UNDEFINED'
        self.active_position = None
        self.daily_trades = 0
        self.last_update = None
        
        logger.info("OptimizationSystem inicializado com todos os módulos")
    
    def process_market_update(self, market_data: Dict) -> Dict:
        """
        Processa atualização de mercado através de todos os módulos
        
        Args:
            market_data: Dados atuais do mercado
            
        Returns:
            Análise completa do mercado
        """
        analysis = {
            'timestamp': datetime.now(),
            'regime': None,
            'recommendations': {},
            'signals': {},
            'actions': []
        }
        
        # 1. Detectar regime de mercado
        if self.regime_detector:
            regime_data = self.regime_detector.update(
                price=market_data.get('price', 0),
                high=market_data.get('high'),
                low=market_data.get('low'),
                volume=market_data.get('volume', 0)
            )
            
            analysis['regime'] = regime_data['regime']
            analysis['regime_confidence'] = regime_data['confidence']
            analysis['regime_metrics'] = regime_data['metrics']
            
            # Registrar mudança de regime
            if regime_data['regime'] != self.current_regime:
                if self.metrics_tracker:
                    self.metrics_tracker.record_regime_change(
                        self.current_regime, 
                        regime_data['regime']
                    )
                self.current_regime = regime_data['regime']
        
        # 2. Atualizar targets adaptativos
        if self.adaptive_targets and analysis['regime']:
            targets_config = self.adaptive_targets.update_regime(
                {'regime': analysis['regime'], 
                 'confidence': analysis.get('regime_confidence', 0.5)}
            )
            analysis['recommendations']['targets'] = targets_config
        
        # 3. Verificar posição ativa
        if self.active_position:
            analysis['actions'].extend(
                self._check_active_position(market_data, analysis['regime'])
            )
        
        self.last_update = datetime.now()
        return analysis
    
    def evaluate_trade_signal(self, 
                            ml_prediction: Dict,
                            hmarl_consensus: Dict,
                            market_data: Dict = None) -> Tuple[bool, Dict]:
        """
        Avalia se deve executar trade baseado em todos os filtros
        
        Args:
            ml_prediction: Predição do ML
            hmarl_consensus: Consenso HMARL
            market_data: Dados de mercado adicionais
            
        Returns:
            Tuple (deve_executar, detalhes)
        """
        result = {
            'approved': False,
            'direction': None,
            'confidence': 0,
            'targets': {},
            'position_size': self.config['position_size'],
            'filters_passed': [],
            'filters_failed': [],
            'timestamp': datetime.now()
        }
        
        # 1. Verificar concordância ML + HMARL
        if self.concordance_filter:
            regime_data = {'regime': self.current_regime} if self.current_regime else None
            concordance_ok, concordance_details = self.concordance_filter.check_concordance(
                ml_prediction, 
                hmarl_consensus,
                regime_data
            )
            
            if not concordance_ok:
                result['filters_failed'].append('concordance')
                result['details'] = concordance_details
                return False, result
            
            result['filters_passed'].append('concordance')
            result['direction'] = concordance_details['final_action']
            result['confidence'] = concordance_details['combined_confidence']
        else:
            # Sem filtro de concordância, usar ML
            result['direction'] = 'BUY' if ml_prediction.get('signal', 0) > 0 else 'SELL'
            result['confidence'] = ml_prediction.get('confidence', 0)
        
        # 2. Verificar regime favorável
        if self.regime_detector:
            if not self.regime_detector.is_regime_favorable(result['direction']):
                result['filters_failed'].append('unfavorable_regime')
                logger.debug(f"[OPTIMIZATION] Regime {self.current_regime} não favorável para {result['direction']}")
                return False, result
            result['filters_passed'].append('regime_check')
        
        # 3. Verificar limites diários
        if self.daily_trades >= self.config['max_daily_trades']:
            result['filters_failed'].append('daily_limit')
            return False, result
        result['filters_passed'].append('daily_limit')
        
        # 4. Verificar se já tem posição
        if self.active_position:
            result['filters_failed'].append('has_position')
            return False, result
        result['filters_passed'].append('no_position')
        
        # 5. Calcular targets adaptativos
        if self.adaptive_targets and market_data:
            entry_price = market_data.get('price', 0)
            regime_data = self.regime_detector.get_current_regime() if self.regime_detector else None
            
            targets = self.adaptive_targets.calculate_position_targets(
                entry_price=entry_price,
                direction=result['direction'],
                regime_data=regime_data
            )
            
            result['targets'] = targets
            result['position_size'] = self.config['position_size'] * targets.get('position_multiplier', 1.0)
        
        # 6. Ajustar confiança mínima por regime
        min_confidence = self.config['min_confidence']
        if self.adaptive_targets:
            min_confidence = self.adaptive_targets.get_confidence_threshold(min_confidence)
        
        if result['confidence'] < min_confidence:
            result['filters_failed'].append('low_confidence')
            return False, result
        
        result['approved'] = True
        result['filters_passed'].append('all_checks')
        
        logger.info(
            f"[OPTIMIZATION] Trade aprovado: {result['direction']} @ "
            f"{result['confidence']:.1%} | Regime: {self.current_regime}"
        )
        
        return True, result
    
    def register_new_position(self, position_data: Dict) -> Dict:
        """
        Registra nova posição em todos os sistemas
        
        Args:
            position_data: Dados da posição aberta
            
        Returns:
            Configuração completa da posição
        """
        position_id = position_data.get('id', f"pos_{datetime.now():%Y%m%d_%H%M%S}")
        
        # Registrar no gerenciador de saídas parciais
        if self.partial_exit_manager:
            self.partial_exit_manager.register_position(
                position_id=position_id,
                entry_price=position_data['entry_price'],
                direction=position_data['direction'],
                quantity=position_data.get('quantity', 1),
                regime=self.current_regime
            )
        
        # Preparar para trailing stop (será ativado depois)
        if self.trailing_stop_manager:
            position_data['trailing_ready'] = False
        
        # Salvar posição ativa
        self.active_position = {
            'id': position_id,
            'entry_time': datetime.now(),
            **position_data
        }
        
        # Incrementar contador diário
        self.daily_trades += 1
        
        logger.info(
            f"[OPTIMIZATION] Posição registrada: {position_id} | "
            f"{position_data['direction']} @ {position_data['entry_price']:.1f}"
        )
        
        return self.active_position
    
    def _check_active_position(self, market_data: Dict, regime: str) -> List[Dict]:
        """Verifica ações necessárias para posição ativa"""
        
        if not self.active_position:
            return []
        
        actions = []
        current_price = market_data.get('price', 0)
        position_id = self.active_position['id']
        
        # 1. Verificar saídas parciais
        if self.partial_exit_manager:
            exit_actions = self.partial_exit_manager.check_exit_conditions(
                position_id=position_id,
                current_price=current_price,
                current_volume=market_data.get('volume')
            )
            actions.extend(exit_actions)
        
        # 2. Verificar/Atualizar trailing stop
        if self.trailing_stop_manager:
            # Verificar se deve ativar trailing
            if not self.active_position.get('trailing_active', False):
                if self.trailing_stop_manager.should_convert_to_trailing(
                    self.active_position, current_price
                ):
                    trail_result = self.trailing_stop_manager.activate_trailing(
                        position_id=position_id,
                        entry_price=self.active_position['entry_price'],
                        current_price=current_price,
                        direction=self.active_position['direction'],
                        regime=regime,
                        initial_stop=self.active_position.get('stop_loss')
                    )
                    
                    if trail_result['activated']:
                        self.active_position['trailing_active'] = True
                        actions.append({
                            'type': 'ACTIVATE_TRAILING',
                            'position_id': position_id,
                            'new_stop': trail_result['stop']
                        })
            else:
                # Atualizar trailing existente
                new_stop, changed, action = self.trailing_stop_manager.update_trailing_stop(
                    position_id=position_id,
                    current_price=current_price,
                    market_data=market_data
                )
                
                if changed:
                    actions.append({
                        'type': 'UPDATE_STOP',
                        'position_id': position_id,
                        'new_stop': new_stop,
                        'reason': action
                    })
                
                if action == 'triggered':
                    actions.append({
                        'type': 'CLOSE_POSITION',
                        'position_id': position_id,
                        'reason': 'trailing_stop_triggered',
                        'exit_price': current_price
                    })
        
        # 3. Verificar targets adaptativos
        if self.adaptive_targets:
            should_exit, exit_reason = self.adaptive_targets.should_exit_position(
                position_targets=self.active_position.get('targets', {}),
                current_price=current_price,
                current_regime=regime
            )
            
            if should_exit:
                actions.append({
                    'type': 'CLOSE_POSITION',
                    'position_id': position_id,
                    'reason': exit_reason,
                    'exit_price': current_price
                })
        
        return actions
    
    def close_position(self, position_id: str, exit_data: Dict):
        """
        Fecha posição e registra métricas
        
        Args:
            position_id: ID da posição
            exit_data: Dados da saída
        """
        if not self.active_position or self.active_position['id'] != position_id:
            logger.warning(f"[OPTIMIZATION] Tentativa de fechar posição inexistente: {position_id}")
            return
        
        # Preparar dados do trade
        trade_data = {
            'id': position_id,
            'regime': self.current_regime,
            'direction': self.active_position['direction'],
            'entry_time': self.active_position['entry_time'],
            'exit_time': datetime.now(),
            'entry_price': self.active_position['entry_price'],
            'exit_price': exit_data.get('exit_price', 0),
            'quantity': self.active_position.get('quantity', 1),
            'ml_confidence': self.active_position.get('ml_confidence', 0),
            'hmarl_confidence': self.active_position.get('hmarl_confidence', 0),
            'combined_confidence': self.active_position.get('confidence', 0),
            'exit_reason': exit_data.get('reason', 'unknown')
        }
        
        # Registrar métricas
        if self.metrics_tracker:
            self.metrics_tracker.record_trade(trade_data)
        
        # Limpar posição ativa
        self.active_position = None
        
        logger.info(
            f"[OPTIMIZATION] Posição fechada: {position_id} | "
            f"Motivo: {exit_data.get('reason')} @ {exit_data.get('exit_price', 0):.1f}"
        )
    
    def get_system_status(self) -> Dict:
        """Retorna status completo do sistema de otimização"""
        
        status = {
            'timestamp': datetime.now(),
            'current_regime': self.current_regime,
            'has_position': self.active_position is not None,
            'daily_trades': self.daily_trades,
            'components': {
                'regime_detector': self.regime_detector is not None,
                'adaptive_targets': self.adaptive_targets is not None,
                'concordance_filter': self.concordance_filter is not None,
                'partial_exits': self.partial_exit_manager is not None,
                'trailing_stop': self.trailing_stop_manager is not None,
                'metrics_tracker': self.metrics_tracker is not None
            }
        }
        
        # Adicionar estatísticas se disponíveis
        if self.concordance_filter:
            status['concordance_stats'] = self.concordance_filter.get_stats()
        
        if self.metrics_tracker:
            status['performance'] = {
                'daily_pnl': self.metrics_tracker.current_session['daily_pnl'],
                'best_regime': self.metrics_tracker.get_best_regime()[0]
            }
        
        if self.active_position:
            status['active_position'] = {
                'id': self.active_position['id'],
                'direction': self.active_position['direction'],
                'entry_price': self.active_position['entry_price'],
                'current_targets': self.active_position.get('targets', {})
            }
        
        return status
    
    def get_performance_report(self) -> str:
        """Gera relatório de performance"""
        
        if self.metrics_tracker:
            return self.metrics_tracker.get_summary_report()
        
        return "Sistema de métricas não disponível"
    
    def reset_daily_counters(self):
        """Reseta contadores diários"""
        
        self.daily_trades = 0
        
        if self.metrics_tracker:
            self.metrics_tracker.reset_daily_metrics()
        
        if self.concordance_filter:
            self.concordance_filter.reset_stats()
        
        logger.info("[OPTIMIZATION] Contadores diários resetados")
    
    def save_state(self):
        """Salva estado do sistema"""
        
        if self.metrics_tracker:
            self.metrics_tracker.save_session_data()
        
        logger.info("[OPTIMIZATION] Estado do sistema salvo")