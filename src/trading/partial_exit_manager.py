"""
Gerenciador de Saídas Parciais - Sistema para escalonar saídas de posições
Otimizado para WDO (Mini Índice Bovespa)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging
from enum import Enum

logger = logging.getLogger(__name__)

class ExitLevel(Enum):
    """Níveis de saída parcial"""
    LEVEL_1 = "partial_1"  # Primeira saída (33%)
    LEVEL_2 = "partial_2"  # Segunda saída (33%)
    LEVEL_3 = "final"      # Saída final (34%)
    BREAKEVEN = "breakeven"
    TRAILING = "trailing"

class PartialExitManager:
    """Gerencia saídas parciais e escalonadas de posições"""
    
    def __init__(self, config: Dict = None):
        """
        Inicializa o gerenciador de saídas parciais
        
        Args:
            config: Configuração das saídas
        """
        self.config = config or {
            'exit_levels': {
                'partial_1': {
                    'points': 5,      # Saída em 5 pontos
                    'percentage': 33,  # Sair 33% da posição
                    'move_stop_to_breakeven': True
                },
                'partial_2': {
                    'points': 10,     # Saída em 10 pontos
                    'percentage': 33,  # Sair mais 33%
                    'activate_trailing': True
                },
                'final': {
                    'points': 20,     # Alvo final
                    'percentage': 34  # Resto da posição
                }
            },
            'regime_adjustments': {
                'RANGING': {
                    'partial_1': {'points': 3, 'percentage': 50},
                    'partial_2': {'points': 5, 'percentage': 30},
                    'final': {'points': 8, 'percentage': 20}
                },
                'TRENDING_UP': {
                    'partial_1': {'points': 8, 'percentage': 25},
                    'partial_2': {'points': 15, 'percentage': 25},
                    'final': {'points': 25, 'percentage': 50}
                },
                'TRENDING_DOWN': {
                    'partial_1': {'points': 8, 'percentage': 25},
                    'partial_2': {'points': 15, 'percentage': 25},
                    'final': {'points': 25, 'percentage': 50}
                },
                'VOLATILE': {
                    'partial_1': {'points': 10, 'percentage': 40},
                    'partial_2': {'points': 18, 'percentage': 40},
                    'final': {'points': 30, 'percentage': 20}
                }
            },
            'min_profit_for_partial': 3,  # Mínimo de pontos para começar saídas
            'protect_profits_after': 15,  # Proteger lucros após X pontos
        }
        
        # Posições sendo gerenciadas
        self.active_positions = {}
        
        # Estatísticas
        self.stats = {
            'total_exits': 0,
            'partial_exits': 0,
            'full_exits': 0,
            'exits_by_level': {
                'partial_1': 0,
                'partial_2': 0,
                'final': 0
            },
            'average_exit_points': []
        }
        
        logger.info("PartialExitManager inicializado")
    
    def register_position(self, 
                         position_id: str,
                         entry_price: float,
                         direction: str,
                         quantity: int,
                         regime: str = 'UNDEFINED') -> Dict:
        """
        Registra uma nova posição para gerenciamento
        
        Args:
            position_id: ID único da posição
            entry_price: Preço de entrada
            direction: 'BUY' ou 'SELL'
            quantity: Quantidade total
            regime: Regime de mercado atual
            
        Returns:
            Estrutura de gerenciamento da posição
        """
        # Obter configuração baseada no regime
        exit_config = self._get_regime_config(regime)
        
        # Calcular níveis de saída
        exit_levels = self._calculate_exit_levels(entry_price, direction, exit_config)
        
        # Estrutura da posição
        position = {
            'id': position_id,
            'entry_price': entry_price,
            'direction': direction,
            'original_quantity': quantity,
            'remaining_quantity': quantity,
            'regime': regime,
            'exit_levels': exit_levels,
            'executed_exits': [],
            'current_stop': None,
            'is_breakeven': False,
            'is_trailing': False,
            'created_at': datetime.now(),
            'last_update': datetime.now(),
            'total_profit_points': 0,
            'status': 'ACTIVE'
        }
        
        self.active_positions[position_id] = position
        
        logger.info(
            f"[PARTIAL] Posição registrada: {position_id} | "
            f"{direction} {quantity} @ {entry_price:.1f} | "
            f"Regime: {regime}"
        )
        
        return position
    
    def check_exit_conditions(self,
                            position_id: str,
                            current_price: float,
                            current_volume: float = None) -> List[Dict]:
        """
        Verifica condições de saída para uma posição
        
        Args:
            position_id: ID da posição
            current_price: Preço atual
            current_volume: Volume atual (opcional)
            
        Returns:
            Lista de ações de saída recomendadas
        """
        if position_id not in self.active_positions:
            return []
        
        position = self.active_positions[position_id]
        
        if position['status'] != 'ACTIVE':
            return []
        
        actions = []
        direction = position['direction']
        entry_price = position['entry_price']
        
        # Calcular lucro atual em pontos
        if direction == 'BUY':
            profit_points = (current_price - entry_price) / 0.5
        else:  # SELL
            profit_points = (entry_price - current_price) / 0.5
        
        position['total_profit_points'] = profit_points
        
        # Verificar cada nível de saída
        for level_name, level_data in position['exit_levels'].items():
            if level_name in [e['level'] for e in position['executed_exits']]:
                continue  # Já executado
            
            level_reached = False
            
            if direction == 'BUY':
                level_reached = current_price >= level_data['price']
            else:  # SELL
                level_reached = current_price <= level_data['price']
            
            if level_reached:
                # Calcular quantidade para sair
                exit_quantity = int(position['original_quantity'] * level_data['percentage'] / 100)
                
                if exit_quantity > 0 and exit_quantity <= position['remaining_quantity']:
                    action = {
                        'type': 'PARTIAL_EXIT',
                        'position_id': position_id,
                        'level': level_name,
                        'price': current_price,
                        'quantity': exit_quantity,
                        'profit_points': profit_points,
                        'reason': f"Atingiu {level_name}: {level_data['points']} pontos"
                    }
                    
                    # Verificar ações adicionais
                    if level_data.get('move_stop_to_breakeven'):
                        action['additional_action'] = 'MOVE_STOP_TO_BREAKEVEN'
                    elif level_data.get('activate_trailing'):
                        action['additional_action'] = 'ACTIVATE_TRAILING'
                    
                    actions.append(action)
                    
                    logger.info(
                        f"[PARTIAL] Saída parcial recomendada: {position_id} | "
                        f"Nível: {level_name} | Qtd: {exit_quantity} | "
                        f"Lucro: {profit_points:.1f} pts"
                    )
        
        # Proteção de lucros
        if profit_points >= self.config['protect_profits_after'] and not position['is_trailing']:
            actions.append({
                'type': 'PROTECT_PROFITS',
                'position_id': position_id,
                'action': 'TIGHTEN_STOP',
                'new_stop_distance': 5,  # Apertar stop para 5 pontos
                'reason': f"Proteção de lucros: {profit_points:.1f} pontos"
            })
        
        position['last_update'] = datetime.now()
        
        return actions
    
    def execute_partial_exit(self, 
                           position_id: str,
                           level: str,
                           quantity: int,
                           exit_price: float) -> bool:
        """
        Registra execução de uma saída parcial
        
        Args:
            position_id: ID da posição
            level: Nível de saída executado
            quantity: Quantidade saída
            exit_price: Preço de saída
            
        Returns:
            True se executado com sucesso
        """
        if position_id not in self.active_positions:
            return False
        
        position = self.active_positions[position_id]
        
        # Registrar saída
        exit_record = {
            'level': level,
            'quantity': quantity,
            'price': exit_price,
            'timestamp': datetime.now(),
            'profit_points': (exit_price - position['entry_price']) / 0.5 
                           if position['direction'] == 'BUY' 
                           else (position['entry_price'] - exit_price) / 0.5
        }
        
        position['executed_exits'].append(exit_record)
        position['remaining_quantity'] -= quantity
        
        # Atualizar estatísticas
        self.stats['partial_exits'] += 1
        self.stats['exits_by_level'][level] = self.stats['exits_by_level'].get(level, 0) + 1
        self.stats['average_exit_points'].append(exit_record['profit_points'])
        
        # Verificar se posição foi totalmente fechada
        if position['remaining_quantity'] <= 0:
            position['status'] = 'CLOSED'
            self.stats['full_exits'] += 1
            logger.info(f"[PARTIAL] Posição {position_id} totalmente fechada")
        
        # Aplicar ações adicionais
        level_config = position['exit_levels'].get(level, {})
        if level_config.get('move_stop_to_breakeven'):
            position['is_breakeven'] = True
            position['current_stop'] = position['entry_price']
            logger.info(f"[PARTIAL] Stop movido para breakeven: {position_id}")
        
        if level_config.get('activate_trailing'):
            position['is_trailing'] = True
            logger.info(f"[PARTIAL] Trailing stop ativado: {position_id}")
        
        self.stats['total_exits'] += 1
        
        return True
    
    def _get_regime_config(self, regime: str) -> Dict:
        """Obtém configuração específica do regime"""
        if regime in self.config['regime_adjustments']:
            return self.config['regime_adjustments'][regime]
        return self.config['exit_levels']
    
    def _calculate_exit_levels(self, 
                              entry_price: float,
                              direction: str,
                              config: Dict) -> Dict:
        """
        Calcula níveis de preço para saídas parciais
        
        Args:
            entry_price: Preço de entrada
            direction: Direção da posição
            config: Configuração dos níveis
            
        Returns:
            Dict com níveis calculados
        """
        levels = {}
        
        for level_name, level_config in config.items():
            points = level_config['points']
            percentage = level_config['percentage']
            
            if direction == 'BUY':
                exit_price = entry_price + (points * 0.5)
            else:  # SELL
                exit_price = entry_price - (points * 0.5)
            
            levels[level_name] = {
                'price': exit_price,
                'points': points,
                'percentage': percentage,
                'move_stop_to_breakeven': level_config.get('move_stop_to_breakeven', False),
                'activate_trailing': level_config.get('activate_trailing', False)
            }
        
        return levels
    
    def get_position_status(self, position_id: str) -> Dict:
        """
        Retorna status detalhado de uma posição
        
        Args:
            position_id: ID da posição
            
        Returns:
            Status da posição
        """
        if position_id not in self.active_positions:
            return {'error': 'Position not found'}
        
        position = self.active_positions[position_id]
        
        # Calcular resumo
        total_exits = len(position['executed_exits'])
        total_profit = sum(e['profit_points'] for e in position['executed_exits'])
        
        return {
            'id': position_id,
            'status': position['status'],
            'direction': position['direction'],
            'entry_price': position['entry_price'],
            'original_quantity': position['original_quantity'],
            'remaining_quantity': position['remaining_quantity'],
            'percentage_closed': (1 - position['remaining_quantity']/position['original_quantity']) * 100,
            'total_exits': total_exits,
            'executed_levels': [e['level'] for e in position['executed_exits']],
            'pending_levels': [
                level for level in position['exit_levels'].keys()
                if level not in [e['level'] for e in position['executed_exits']]
            ],
            'total_profit_points': position['total_profit_points'],
            'realized_profit_points': total_profit,
            'is_breakeven': position['is_breakeven'],
            'is_trailing': position['is_trailing'],
            'regime': position['regime']
        }
    
    def optimize_exit_strategy(self,
                              position_id: str,
                              market_conditions: Dict) -> Dict:
        """
        Otimiza estratégia de saída baseada em condições atuais
        
        Args:
            position_id: ID da posição
            market_conditions: Condições atuais do mercado
            
        Returns:
            Recomendações de ajuste
        """
        if position_id not in self.active_positions:
            return {}
        
        position = self.active_positions[position_id]
        recommendations = {
            'adjust_levels': False,
            'new_levels': {},
            'reasoning': []
        }
        
        # Analisar volatilidade
        volatility = market_conditions.get('volatility', 0)
        if volatility > 0.02:  # Alta volatilidade
            recommendations['reasoning'].append("Alta volatilidade detectada")
            recommendations['adjust_levels'] = True
            
            # Aumentar distância dos alvos
            for level_name in position['exit_levels']:
                current_points = position['exit_levels'][level_name]['points']
                new_points = int(current_points * 1.3)  # 30% mais longe
                recommendations['new_levels'][level_name] = new_points
        
        # Analisar momentum
        momentum = market_conditions.get('momentum', 0)
        if abs(momentum) > 0.5:  # Forte momentum
            recommendations['reasoning'].append(f"Forte momentum: {momentum:.2f}")
            
            # Se momentum favorável, aumentar último alvo
            if (position['direction'] == 'BUY' and momentum > 0) or \
               (position['direction'] == 'SELL' and momentum < 0):
                recommendations['new_levels']['final'] = \
                    position['exit_levels']['final']['points'] * 1.5
        
        # Analisar tempo na posição
        time_in_position = (datetime.now() - position['created_at']).total_seconds() / 60
        if time_in_position > 30 and position['total_profit_points'] < 5:
            recommendations['reasoning'].append("Posição estagnada há muito tempo")
            recommendations['tighten_targets'] = True
        
        return recommendations
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas do gerenciador"""
        avg_exit_points = np.mean(self.stats['average_exit_points']) \
                         if self.stats['average_exit_points'] else 0
        
        return {
            'total_positions': len(self.active_positions),
            'active_positions': sum(1 for p in self.active_positions.values() 
                                  if p['status'] == 'ACTIVE'),
            'closed_positions': sum(1 for p in self.active_positions.values() 
                                  if p['status'] == 'CLOSED'),
            'total_exits': self.stats['total_exits'],
            'partial_exits': self.stats['partial_exits'],
            'full_exits': self.stats['full_exits'],
            'exits_by_level': self.stats['exits_by_level'],
            'average_profit_per_exit': avg_exit_points,
            'best_exit': max(self.stats['average_exit_points']) 
                        if self.stats['average_exit_points'] else 0,
            'worst_exit': min(self.stats['average_exit_points']) 
                         if self.stats['average_exit_points'] else 0
        }
    
    def cleanup_old_positions(self, hours: int = 24):
        """Remove posições antigas fechadas"""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        
        positions_to_remove = []
        for pos_id, position in self.active_positions.items():
            if position['status'] == 'CLOSED':
                if position['last_update'].timestamp() < cutoff_time:
                    positions_to_remove.append(pos_id)
        
        for pos_id in positions_to_remove:
            del self.active_positions[pos_id]
            logger.debug(f"[PARTIAL] Posição antiga removida: {pos_id}")
        
        if positions_to_remove:
            logger.info(f"[PARTIAL] {len(positions_to_remove)} posições antigas removidas")