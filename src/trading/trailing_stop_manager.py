"""
Gerenciador de Trailing Stop Adaptativo
Sistema inteligente que ajusta stops dinamicamente baseado no comportamento do mercado
"""

import numpy as np
from typing import Dict, Tuple, Optional, List
from datetime import datetime, timedelta
from collections import deque
import logging

logger = logging.getLogger(__name__)

class TrailingStopManager:
    """Gerencia trailing stops adaptativos para posições abertas"""
    
    def __init__(self, config: Dict = None):
        """
        Inicializa o gerenciador de trailing stop
        
        Args:
            config: Configuração do trailing stop
        """
        self.config = config or {
            'default_distance': 5,         # Distância padrão em pontos
            'min_distance': 3,             # Distância mínima
            'max_distance': 15,            # Distância máxima
            'activation_profit': 5,        # Pontos de lucro para ativar
            'step_size': 0.5,              # Tamanho do passo (tick do WDO)
            'adaptive_modes': {
                'AGGRESSIVE': {
                    'distance': 3,
                    'activation': 3,
                    'tightening_rate': 0.8,   # Aperta 20% a cada atualização
                    'suitable_for': ['RANGING']
                },
                'MODERATE': {
                    'distance': 5,
                    'activation': 5,
                    'tightening_rate': 0.9,   # Aperta 10%
                    'suitable_for': ['UNDEFINED']
                },
                'CONSERVATIVE': {
                    'distance': 8,
                    'activation': 8,
                    'tightening_rate': 0.95,  # Aperta 5%
                    'suitable_for': ['TRENDING_UP', 'TRENDING_DOWN']
                },
                'PROTECTIVE': {
                    'distance': 12,
                    'activation': 10,
                    'tightening_rate': 1.0,   # Não aperta
                    'suitable_for': ['VOLATILE']
                }
            },
            'volatility_adjustment': True,     # Ajustar por volatilidade
            'momentum_adjustment': True,       # Ajustar por momentum
            'time_decay': True,                # Apertar com o tempo
            'breakeven_first': True,           # Sempre mover para breakeven primeiro
        }
        
        # Posições com trailing stop ativo
        self.active_trails = {}
        
        # Buffer de preços para cálculos
        self.price_buffer = deque(maxlen=50)
        
        # Estatísticas
        self.stats = {
            'trails_activated': 0,
            'trails_triggered': 0,
            'total_adjustments': 0,
            'profit_protected': [],
            'modes_used': {
                'AGGRESSIVE': 0,
                'MODERATE': 0,
                'CONSERVATIVE': 0,
                'PROTECTIVE': 0
            }
        }
        
        logger.info("TrailingStopManager inicializado")
    
    def activate_trailing(self,
                         position_id: str,
                         entry_price: float,
                         current_price: float,
                         direction: str,
                         regime: str = 'UNDEFINED',
                         initial_stop: float = None) -> Dict:
        """
        Ativa trailing stop para uma posição
        
        Args:
            position_id: ID da posição
            entry_price: Preço de entrada
            current_price: Preço atual
            direction: 'BUY' ou 'SELL'
            regime: Regime de mercado atual
            initial_stop: Stop loss inicial (opcional)
            
        Returns:
            Configuração do trailing stop
        """
        # Calcular lucro atual
        if direction == 'BUY':
            profit_points = (current_price - entry_price) / 0.5
        else:
            profit_points = (entry_price - current_price) / 0.5
        
        # Selecionar modo baseado no regime
        mode = self._select_mode(regime, profit_points)
        mode_config = self.config['adaptive_modes'][mode]
        
        # Verificar se pode ativar
        if profit_points < mode_config['activation']:
            logger.debug(
                f"[TRAILING] Não ativado para {position_id}: "
                f"lucro insuficiente ({profit_points:.1f} < {mode_config['activation']})"
            )
            return {'activated': False, 'reason': 'insufficient_profit'}
        
        # Calcular distância inicial
        distance = self._calculate_initial_distance(
            current_price, 
            mode_config['distance'],
            regime
        )
        
        # Calcular stop inicial
        if direction == 'BUY':
            trailing_stop = current_price - distance
            # Garantir que não piora o stop atual
            if initial_stop and trailing_stop < initial_stop:
                trailing_stop = initial_stop
        else:
            trailing_stop = current_price + distance
            if initial_stop and trailing_stop > initial_stop:
                trailing_stop = initial_stop
        
        # Registrar trailing
        trail_config = {
            'position_id': position_id,
            'entry_price': entry_price,
            'direction': direction,
            'mode': mode,
            'current_stop': trailing_stop,
            'distance': distance,
            'high_water_mark': current_price if direction == 'BUY' else None,
            'low_water_mark': current_price if direction == 'SELL' else None,
            'profit_locked': profit_points,
            'adjustments': 0,
            'tightening_rate': mode_config['tightening_rate'],
            'activated_at': datetime.now(),
            'last_update': datetime.now(),
            'regime': regime,
            'status': 'ACTIVE'
        }
        
        self.active_trails[position_id] = trail_config
        
        # Atualizar estatísticas
        self.stats['trails_activated'] += 1
        self.stats['modes_used'][mode] += 1
        
        logger.info(
            f"[TRAILING] Ativado para {position_id} | "
            f"Modo: {mode} | Stop: {trailing_stop:.1f} | "
            f"Distância: {distance:.1f} pts"
        )
        
        return {
            'activated': True,
            'mode': mode,
            'stop': trailing_stop,
            'distance': distance,
            'profit_locked': profit_points
        }
    
    def update_trailing_stop(self,
                            position_id: str,
                            current_price: float,
                            market_data: Dict = None) -> Tuple[float, bool, str]:
        """
        Atualiza trailing stop de uma posição
        
        Args:
            position_id: ID da posição
            current_price: Preço atual
            market_data: Dados adicionais do mercado
            
        Returns:
            Tuple (novo_stop, foi_alterado, ação)
        """
        if position_id not in self.active_trails:
            return None, False, 'not_active'
        
        trail = self.active_trails[position_id]
        
        if trail['status'] != 'ACTIVE':
            return trail['current_stop'], False, 'inactive'
        
        # Atualizar buffer de preços
        self.price_buffer.append(current_price)
        
        direction = trail['direction']
        old_stop = trail['current_stop']
        new_stop = old_stop
        action = 'hold'
        
        if direction == 'BUY':
            # Atualizar high water mark
            if current_price > trail.get('high_water_mark', 0):
                trail['high_water_mark'] = current_price
                
                # Calcular novo stop
                distance = self._adjust_distance(trail, market_data)
                new_stop = current_price - distance
                
                # Só atualiza se melhorar
                if new_stop > old_stop:
                    trail['current_stop'] = new_stop
                    trail['distance'] = distance
                    trail['adjustments'] += 1
                    action = 'tightened'
                    
                    # Calcular lucro protegido
                    trail['profit_locked'] = (new_stop - trail['entry_price']) / 0.5
            
            # Verificar se stop foi atingido
            if current_price <= trail['current_stop']:
                action = 'triggered'
                trail['status'] = 'TRIGGERED'
                self.stats['trails_triggered'] += 1
                
        else:  # SELL
            # Atualizar low water mark
            if current_price < trail.get('low_water_mark', float('inf')):
                trail['low_water_mark'] = current_price
                
                # Calcular novo stop
                distance = self._adjust_distance(trail, market_data)
                new_stop = current_price + distance
                
                # Só atualiza se melhorar
                if new_stop < old_stop:
                    trail['current_stop'] = new_stop
                    trail['distance'] = distance
                    trail['adjustments'] += 1
                    action = 'tightened'
                    
                    # Calcular lucro protegido
                    trail['profit_locked'] = (trail['entry_price'] - new_stop) / 0.5
            
            # Verificar se stop foi atingido
            if current_price >= trail['current_stop']:
                action = 'triggered'
                trail['status'] = 'TRIGGERED'
                self.stats['trails_triggered'] += 1
        
        # Aplicar time decay se configurado
        if self.config['time_decay'] and action != 'triggered':
            new_stop = self._apply_time_decay(trail, new_stop)
        
        trail['last_update'] = datetime.now()
        
        # Log se houve mudança
        if new_stop != old_stop:
            self.stats['total_adjustments'] += 1
            logger.debug(
                f"[TRAILING] Ajustado {position_id}: "
                f"{old_stop:.1f} → {new_stop:.1f} | "
                f"Lucro protegido: {trail['profit_locked']:.1f} pts"
            )
        
        return new_stop, new_stop != old_stop, action
    
    def _select_mode(self, regime: str, profit_points: float) -> str:
        """Seleciona modo de trailing baseado no regime e lucro"""
        
        # Encontrar modo adequado para o regime
        for mode_name, mode_config in self.config['adaptive_modes'].items():
            if regime in mode_config.get('suitable_for', []):
                # Ajustar por lucro
                if profit_points > 20:
                    return 'AGGRESSIVE'  # Muito lucro, proteger agressivamente
                elif profit_points > 10:
                    return mode_name
                else:
                    # Pouco lucro, ser mais conservador
                    if mode_name == 'AGGRESSIVE':
                        return 'MODERATE'
                    return mode_name
        
        return 'MODERATE'  # Padrão
    
    def _calculate_initial_distance(self, 
                                   current_price: float,
                                   base_distance: float,
                                   regime: str) -> float:
        """Calcula distância inicial do trailing stop"""
        
        distance = base_distance * 0.5  # Converter para valor monetário
        
        # Ajustar por volatilidade se tiver dados
        if len(self.price_buffer) >= 20:
            prices = list(self.price_buffer)
            volatility = np.std(prices) / np.mean(prices)
            
            if self.config['volatility_adjustment']:
                # Aumentar distância com volatilidade
                vol_factor = 1 + (volatility * 10)  # 10% por 1% de volatilidade
                distance *= vol_factor
        
        # Limitar distância
        distance = max(self.config['min_distance'] * 0.5, 
                      min(self.config['max_distance'] * 0.5, distance))
        
        return distance
    
    def _adjust_distance(self, trail: Dict, market_data: Dict = None) -> float:
        """Ajusta distância do trailing stop dinamicamente"""
        
        current_distance = trail['distance']
        new_distance = current_distance
        
        # Aplicar tightening rate
        new_distance *= trail['tightening_rate']
        
        # Ajustar por volatilidade
        if self.config['volatility_adjustment'] and market_data:
            volatility = market_data.get('volatility', 0)
            if volatility > 0.02:  # Alta volatilidade
                new_distance *= 1.2  # Aumentar 20%
            elif volatility < 0.01:  # Baixa volatilidade
                new_distance *= 0.9  # Reduzir 10%
        
        # Ajustar por momentum
        if self.config['momentum_adjustment'] and market_data:
            momentum = market_data.get('momentum', 0)
            direction = trail['direction']
            
            # Se momentum contrário, apertar stop
            if (direction == 'BUY' and momentum < -0.3) or \
               (direction == 'SELL' and momentum > 0.3):
                new_distance *= 0.7  # Apertar 30%
        
        # Limitar distância
        new_distance = max(self.config['min_distance'] * 0.5,
                          min(self.config['max_distance'] * 0.5, new_distance))
        
        return new_distance
    
    def _apply_time_decay(self, trail: Dict, current_stop: float) -> float:
        """Aplica decaimento temporal ao stop"""
        
        # Calcular tempo desde ativação
        time_active = (datetime.now() - trail['activated_at']).total_seconds() / 60
        
        # Apertar 1% a cada 10 minutos
        if time_active > 10:
            decay_factor = 0.99 ** (time_active / 10)
            
            direction = trail['direction']
            entry = trail['entry_price']
            
            if direction == 'BUY':
                # Mover stop para cima
                distance_from_entry = current_stop - entry
                new_distance = distance_from_entry * decay_factor
                new_stop = entry + new_distance
                
                # Garantir que não piora
                return max(current_stop, new_stop)
            else:
                # Mover stop para baixo
                distance_from_entry = entry - current_stop
                new_distance = distance_from_entry * decay_factor
                new_stop = entry - new_distance
                
                return min(current_stop, new_stop)
        
        return current_stop
    
    def get_trail_status(self, position_id: str) -> Dict:
        """Retorna status do trailing stop de uma posição"""
        
        if position_id not in self.active_trails:
            return {'active': False}
        
        trail = self.active_trails[position_id]
        
        return {
            'active': True,
            'mode': trail['mode'],
            'current_stop': trail['current_stop'],
            'distance': trail['distance'],
            'profit_locked': trail['profit_locked'],
            'adjustments': trail['adjustments'],
            'time_active': (datetime.now() - trail['activated_at']).total_seconds() / 60,
            'status': trail['status']
        }
    
    def should_convert_to_trailing(self,
                                  position_data: Dict,
                                  current_price: float) -> bool:
        """
        Verifica se deve converter stop fixo para trailing
        
        Args:
            position_data: Dados da posição
            current_price: Preço atual
            
        Returns:
            True se deve converter
        """
        direction = position_data['direction']
        entry_price = position_data['entry_price']
        
        # Calcular lucro
        if direction == 'BUY':
            profit_points = (current_price - entry_price) / 0.5
        else:
            profit_points = (entry_price - current_price) / 0.5
        
        # Verificar condições
        min_profit = self.config.get('activation_profit', 5)
        
        if profit_points >= min_profit:
            # Verificar se já tem trailing ativo
            position_id = position_data.get('id')
            if position_id and position_id not in self.active_trails:
                return True
        
        return False
    
    def get_recommended_action(self,
                              position_id: str,
                              current_price: float,
                              market_conditions: Dict) -> Dict:
        """
        Retorna ação recomendada para o trailing stop
        
        Args:
            position_id: ID da posição
            current_price: Preço atual
            market_conditions: Condições do mercado
            
        Returns:
            Recomendação de ação
        """
        if position_id not in self.active_trails:
            return {'action': 'none', 'reason': 'no_trailing_active'}
        
        trail = self.active_trails[position_id]
        
        # Analisar situação
        recommendation = {
            'action': 'maintain',
            'current_stop': trail['current_stop'],
            'suggestions': []
        }
        
        # Verificar se está muito próximo do preço
        distance_to_price = abs(current_price - trail['current_stop'])
        if distance_to_price < 2 * 0.5:  # Menos de 2 pontos
            recommendation['suggestions'].append('stop_very_close')
            recommendation['action'] = 'monitor_closely'
        
        # Verificar se deveria mudar modo
        current_mode = trail['mode']
        suggested_mode = self._select_mode(
            market_conditions.get('regime', 'UNDEFINED'),
            trail['profit_locked']
        )
        
        if suggested_mode != current_mode:
            recommendation['suggestions'].append(f'change_mode_to_{suggested_mode}')
            recommendation['new_mode'] = suggested_mode
        
        # Verificar se lucro justifica apertar mais
        if trail['profit_locked'] > 15:
            recommendation['suggestions'].append('tighten_aggressively')
            recommendation['action'] = 'tighten'
        
        return recommendation
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas do gerenciador"""
        
        avg_profit_protected = np.mean(self.stats['profit_protected']) \
                              if self.stats['profit_protected'] else 0
        
        active_count = sum(1 for t in self.active_trails.values() 
                          if t['status'] == 'ACTIVE')
        
        return {
            'total_trails_activated': self.stats['trails_activated'],
            'active_trails': active_count,
            'trails_triggered': self.stats['trails_triggered'],
            'total_adjustments': self.stats['total_adjustments'],
            'average_profit_protected': avg_profit_protected,
            'modes_distribution': self.stats['modes_used'],
            'trigger_rate': self.stats['trails_triggered'] / self.stats['trails_activated']
                          if self.stats['trails_activated'] > 0 else 0
        }
    
    def cleanup_old_trails(self, hours: int = 24):
        """Remove trails antigos inativos"""
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        trails_to_remove = []
        for pos_id, trail in self.active_trails.items():
            if trail['status'] != 'ACTIVE':
                if trail['last_update'] < cutoff_time:
                    trails_to_remove.append(pos_id)
        
        for pos_id in trails_to_remove:
            # Salvar lucro protegido antes de remover
            if self.active_trails[pos_id]['profit_locked'] > 0:
                self.stats['profit_protected'].append(
                    self.active_trails[pos_id]['profit_locked']
                )
            del self.active_trails[pos_id]
        
        if trails_to_remove:
            logger.info(f"[TRAILING] {len(trails_to_remove)} trails antigos removidos")