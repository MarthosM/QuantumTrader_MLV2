"""
Sistema de Targets Adaptativos - Ajusta stops e alvos baseado no regime de mercado
Otimizado para WDO (Mini Índice Bovespa)
"""

import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AdaptiveTargetSystem:
    """Sistema que ajusta dinamicamente stops e take profits baseado no regime de mercado"""
    
    def __init__(self, base_config: Dict = None):
        """
        Inicializa o sistema de targets adaptativos
        
        Args:
            base_config: Configuração base de stops/targets
        """
        # Configuração base (em pontos do WDO)
        self.base_config = base_config or {
            'stop_loss': 10,      # 10 pontos padrão
            'take_profit': 20,    # 20 pontos padrão
            'trailing_stop': 5,   # 5 pontos para trailing
            'breakeven_trigger': 10,  # Mover stop para breakeven após 10 pontos
            'partial_exit_1': 8,      # Primeira saída parcial
            'partial_exit_2': 15,     # Segunda saída parcial
        }
        
        # Configurações por regime de mercado
        self.regime_configs = {
            'TRENDING_UP': {
                'stop_loss': 8,           # Stop mais apertado em tendência clara
                'take_profit': 25,        # Alvo maior para aproveitar tendência
                'trailing_stop': 8,       # Trailing mais generoso
                'breakeven_trigger': 8,   # Breakeven mais cedo
                'partial_exit_1': 10,     # Saídas mais espaçadas
                'partial_exit_2': 18,
                'position_multiplier': 1.2,  # Posição 20% maior
                'confidence_adjustment': -0.05  # Pode aceitar 5% menos confiança
            },
            'TRENDING_DOWN': {
                'stop_loss': 8,
                'take_profit': 25,
                'trailing_stop': 8,
                'breakeven_trigger': 8,
                'partial_exit_1': 10,
                'partial_exit_2': 18,
                'position_multiplier': 1.2,
                'confidence_adjustment': -0.05
            },
            'RANGING': {
                'stop_loss': 5,           # Stop muito apertado em lateralização
                'take_profit': 8,         # Alvo pequeno (scalping)
                'trailing_stop': 3,       # Trailing agressivo
                'breakeven_trigger': 4,   # Breakeven rápido
                'partial_exit_1': 3,      # Saídas rápidas
                'partial_exit_2': 6,
                'position_multiplier': 0.8,  # Posição 20% menor
                'confidence_adjustment': 0.05  # Exige 5% mais confiança
            },
            'VOLATILE': {
                'stop_loss': 15,          # Stop largo para aguentar volatilidade
                'take_profit': 30,        # Alvo maior
                'trailing_stop': 10,      # Trailing mais largo
                'breakeven_trigger': 15,  # Breakeven após movimento maior
                'partial_exit_1': 12,
                'partial_exit_2': 22,
                'position_multiplier': 0.5,  # Posição 50% menor
                'confidence_adjustment': 0.10  # Exige 10% mais confiança
            },
            'UNDEFINED': {
                # Usa configuração base quando regime indefinido
                'stop_loss': self.base_config['stop_loss'],
                'take_profit': self.base_config['take_profit'],
                'trailing_stop': self.base_config['trailing_stop'],
                'breakeven_trigger': self.base_config['breakeven_trigger'],
                'partial_exit_1': self.base_config['partial_exit_1'],
                'partial_exit_2': self.base_config['partial_exit_2'],
                'position_multiplier': 0.7,  # Posição reduzida por segurança
                'confidence_adjustment': 0.08  # Mais conservador
            }
        }
        
        # Estado atual
        self.current_regime = 'UNDEFINED'
        self.current_targets = self.base_config.copy()
        self.active_positions = {}  # Posições ativas com seus targets
        
        logger.info("AdaptiveTargetSystem inicializado")
    
    def update_regime(self, regime_data: Dict) -> Dict:
        """
        Atualiza o sistema com novo regime de mercado
        
        Args:
            regime_data: Dados do regime (do MarketRegimeDetector)
            
        Returns:
            Novos targets ajustados
        """
        regime = regime_data.get('regime', 'UNDEFINED')
        confidence = regime_data.get('confidence', 0.5)
        
        if regime != self.current_regime:
            logger.info(f"[TARGETS] Mudança de regime: {self.current_regime} → {regime}")
            self.current_regime = regime
        
        # Obter configuração do regime
        regime_config = self.regime_configs.get(regime, self.regime_configs['UNDEFINED'])
        
        # Ajustar targets baseado na confiança do regime
        confidence_factor = confidence  # 0.0 a 1.0
        
        # Interpolar entre configuração base e regime
        self.current_targets = {}
        for key in self.base_config:
            base_value = self.base_config[key]
            regime_value = regime_config.get(key, base_value)
            
            # Interpolar baseado na confiança
            self.current_targets[key] = base_value + (regime_value - base_value) * confidence_factor
        
        # Adicionar multiplicadores e ajustes
        self.current_targets['position_multiplier'] = regime_config['position_multiplier']
        self.current_targets['confidence_adjustment'] = regime_config['confidence_adjustment']
        
        # Adicionar recomendações do regime
        recommendations = regime_data.get('recommendations', {})
        if recommendations:
            self.current_targets.update(recommendations)
        
        return self.current_targets
    
    def calculate_position_targets(self, 
                                 entry_price: float,
                                 direction: str,
                                 regime_data: Dict = None) -> Dict:
        """
        Calcula stops e alvos para uma nova posição
        
        Args:
            entry_price: Preço de entrada
            direction: 'BUY' ou 'SELL'
            regime_data: Dados do regime atual (opcional)
            
        Returns:
            Dict com todos os níveis calculados
        """
        # Atualizar targets se regime fornecido
        if regime_data:
            self.update_regime(regime_data)
        
        # Calcular níveis baseado na direção
        if direction == 'BUY':
            stop_loss = entry_price - self.current_targets['stop_loss'] * 0.5  # 0.5 = tick WDO
            take_profit = entry_price + self.current_targets['take_profit'] * 0.5
            partial_1 = entry_price + self.current_targets['partial_exit_1'] * 0.5
            partial_2 = entry_price + self.current_targets['partial_exit_2'] * 0.5
            breakeven = entry_price + self.current_targets['breakeven_trigger'] * 0.5
            
        else:  # SELL
            stop_loss = entry_price + self.current_targets['stop_loss'] * 0.5
            take_profit = entry_price - self.current_targets['take_profit'] * 0.5
            partial_1 = entry_price - self.current_targets['partial_exit_1'] * 0.5
            partial_2 = entry_price - self.current_targets['partial_exit_2'] * 0.5
            breakeven = entry_price - self.current_targets['breakeven_trigger'] * 0.5
        
        position_targets = {
            'entry_price': entry_price,
            'direction': direction,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'partial_exit_1': partial_1,
            'partial_exit_2': partial_2,
            'breakeven_trigger': breakeven,
            'trailing_stop_distance': self.current_targets['trailing_stop'] * 0.5,
            'position_multiplier': self.current_targets.get('position_multiplier', 1.0),
            'regime': self.current_regime,
            'created_at': datetime.now()
        }
        
        # Logar níveis calculados
        logger.info(
            f"[TARGETS] Nova posição {direction} @ {entry_price:.1f} | "
            f"Stop: {stop_loss:.1f} | TP: {take_profit:.1f} | "
            f"Regime: {self.current_regime}"
        )
        
        return position_targets
    
    def update_position_trailing(self, 
                                position_id: str,
                                current_price: float,
                                position_targets: Dict) -> Tuple[float, str]:
        """
        Atualiza trailing stop de uma posição
        
        Args:
            position_id: ID da posição
            current_price: Preço atual do mercado
            position_targets: Targets da posição
            
        Returns:
            Tuple (novo_stop_loss, ação_recomendada)
        """
        direction = position_targets['direction']
        entry_price = position_targets['entry_price']
        current_stop = position_targets.get('current_stop', position_targets['stop_loss'])
        trailing_distance = position_targets['trailing_stop_distance']
        
        new_stop = current_stop
        action = 'HOLD'
        
        if direction == 'BUY':
            # Verificar se atingiu breakeven trigger
            if current_price >= position_targets['breakeven_trigger'] and current_stop < entry_price:
                new_stop = entry_price
                action = 'MOVE_TO_BREAKEVEN'
                logger.info(f"[TRAILING] Posição {position_id} movida para breakeven")
            
            # Aplicar trailing stop
            elif current_price - trailing_distance > current_stop:
                new_stop = current_price - trailing_distance
                action = 'UPDATE_TRAILING'
                logger.debug(f"[TRAILING] Posição {position_id} stop atualizado: {new_stop:.1f}")
            
            # Verificar saídas parciais
            if current_price >= position_targets['partial_exit_2'] and not position_targets.get('partial_2_done'):
                action = 'PARTIAL_EXIT_2'
            elif current_price >= position_targets['partial_exit_1'] and not position_targets.get('partial_1_done'):
                action = 'PARTIAL_EXIT_1'
                
        else:  # SELL
            # Verificar se atingiu breakeven trigger
            if current_price <= position_targets['breakeven_trigger'] and current_stop > entry_price:
                new_stop = entry_price
                action = 'MOVE_TO_BREAKEVEN'
                logger.info(f"[TRAILING] Posição {position_id} movida para breakeven")
            
            # Aplicar trailing stop
            elif current_price + trailing_distance < current_stop:
                new_stop = current_price + trailing_distance
                action = 'UPDATE_TRAILING'
                logger.debug(f"[TRAILING] Posição {position_id} stop atualizado: {new_stop:.1f}")
            
            # Verificar saídas parciais
            if current_price <= position_targets['partial_exit_2'] and not position_targets.get('partial_2_done'):
                action = 'PARTIAL_EXIT_2'
            elif current_price <= position_targets['partial_exit_1'] and not position_targets.get('partial_1_done'):
                action = 'PARTIAL_EXIT_1'
        
        # Atualizar stop na estrutura
        position_targets['current_stop'] = new_stop
        
        return new_stop, action
    
    def should_exit_position(self, 
                            position_targets: Dict,
                            current_price: float,
                            current_regime: str = None) -> Tuple[bool, str]:
        """
        Verifica se deve sair da posição
        
        Args:
            position_targets: Targets da posição
            current_price: Preço atual
            current_regime: Regime atual (opcional)
            
        Returns:
            Tuple (deve_sair, motivo)
        """
        direction = position_targets['direction']
        
        # Verificar stop loss
        if direction == 'BUY':
            if current_price <= position_targets.get('current_stop', position_targets['stop_loss']):
                return True, 'STOP_LOSS'
            if current_price >= position_targets['take_profit']:
                return True, 'TAKE_PROFIT'
        else:  # SELL
            if current_price >= position_targets.get('current_stop', position_targets['stop_loss']):
                return True, 'STOP_LOSS'
            if current_price <= position_targets['take_profit']:
                return True, 'TAKE_PROFIT'
        
        # Verificar mudança de regime (opcional)
        if current_regime and current_regime != position_targets['regime']:
            # Se mudou de tendência para lateralização ou volatilidade, considerar saída
            if current_regime in ['RANGING', 'VOLATILE'] and position_targets['regime'].startswith('TRENDING'):
                # Calcular P&L atual
                if direction == 'BUY':
                    pnl_points = (current_price - position_targets['entry_price']) / 0.5
                else:
                    pnl_points = (position_targets['entry_price'] - current_price) / 0.5
                
                # Se positivo, sair na mudança de regime
                if pnl_points > 2:  # Mais de 2 pontos de lucro
                    return True, 'REGIME_CHANGE'
        
        return False, 'HOLD'
    
    def get_confidence_threshold(self, base_confidence: float = 0.6) -> float:
        """
        Retorna o threshold de confiança ajustado para o regime atual
        
        Args:
            base_confidence: Confiança base (padrão 60%)
            
        Returns:
            Confiança ajustada
        """
        adjustment = self.current_targets.get('confidence_adjustment', 0)
        adjusted = base_confidence + adjustment
        
        # Limitar entre 0.5 e 0.8
        return max(0.5, min(0.8, adjusted))
    
    def get_position_size_multiplier(self) -> float:
        """
        Retorna o multiplicador de tamanho de posição para o regime atual
        
        Returns:
            Multiplicador (0.5 a 1.5)
        """
        return self.current_targets.get('position_multiplier', 1.0)
    
    def format_targets_message(self, position_targets: Dict) -> str:
        """
        Formata mensagem com os targets para log/display
        
        Args:
            position_targets: Targets calculados
            
        Returns:
            String formatada
        """
        direction = position_targets['direction']
        entry = position_targets['entry_price']
        stop = position_targets['stop_loss']
        tp = position_targets['take_profit']
        
        # Calcular riscos e retornos em pontos
        if direction == 'BUY':
            risk_points = (entry - stop) / 0.5
            reward_points = (tp - entry) / 0.5
        else:
            risk_points = (stop - entry) / 0.5
            reward_points = (entry - tp) / 0.5
        
        rr_ratio = reward_points / risk_points if risk_points > 0 else 0
        
        return (
            f"[TARGETS] {direction} @ {entry:.1f}\n"
            f"  Stop Loss: {stop:.1f} (-{risk_points:.0f} pts)\n"
            f"  Take Profit: {tp:.1f} (+{reward_points:.0f} pts)\n"
            f"  Parcial 1: {position_targets['partial_exit_1']:.1f}\n"
            f"  Parcial 2: {position_targets['partial_exit_2']:.1f}\n"
            f"  R:R Ratio: 1:{rr_ratio:.1f}\n"
            f"  Regime: {self.current_regime}"
        )