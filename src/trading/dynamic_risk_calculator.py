"""
Dynamic Risk Calculator
Calcula stop loss e take profit dinâmicos baseados em:
- Tipo de análise (scalping vs swing)
- Volatilidade atual
- Força do sinal
"""

import numpy as np
from typing import Dict, Tuple
from collections import deque
import logging

logger = logging.getLogger('DynamicRisk')

class DynamicRiskCalculator:
    """Calcula stops e takes dinâmicos baseados no contexto do mercado"""
    
    def __init__(self):
        # Histórico de preços para volatilidade
        self.price_history = deque(maxlen=100)
        self.volatility_window = 20
        
        # Configurações base (em pontos do WDO) - AJUSTADO
        self.config = {
            'scalping': {
                'base_stop': 5,      # 5 pontos base
                'base_take': 7,      # 7 pontos base (5-10)
                'max_stop': 10,      # Máximo 10 pontos
                'max_take': 10,      # Máximo 10 pontos
                'volatility_mult': 1.2  # Multiplicador de volatilidade menor
            },
            'swing': {
                'base_stop': 10,     # 10 pontos base
                'base_take': 25,     # 25 pontos base (20-30)
                'max_stop': 20,      # Máximo 20 pontos
                'max_take': 30,      # Máximo 30 pontos
                'volatility_mult': 1.5  # Multiplicador de volatilidade
            },
            'hybrid': {
                'base_stop': 7,      # 7 pontos base
                'base_take': 15,     # 15 pontos base (10-20)
                'max_stop': 15,      # Máximo 15 pontos
                'max_take': 20,      # Máximo 20 pontos
                'volatility_mult': 1.3  # Multiplicador de volatilidade
            }
        }
        
        # ATR (Average True Range) para volatilidade
        self.atr_period = 14
        self.atr_values = deque(maxlen=self.atr_period)
        
    def update_price(self, price: float):
        """Atualiza histórico de preços"""
        self.price_history.append(price)
        
    def calculate_volatility(self) -> float:
        """Calcula volatilidade atual em pontos"""
        if len(self.price_history) < 10:
            return 10.0  # Volatilidade padrão
            
        prices = list(self.price_history)[-20:]  # Últimos 20 preços
        returns = np.diff(prices)
        
        # Desvio padrão dos retornos (volatilidade)
        if len(returns) > 0:
            volatility = np.std(returns)
            # Converter para pontos do WDO (arredondar para múltiplo de 0.5)
            volatility_points = round(volatility * 2) / 2
            return max(5.0, min(50.0, volatility_points))  # Entre 5 e 50 pontos
        
        return 10.0
    
    def get_trade_type(self, signal_source: Dict) -> str:
        """
        Determina tipo de trade baseado na fonte do sinal
        
        Args:
            signal_source: Dict com informações do sinal
                - 'ml_confidence': confiança do ML
                - 'hmarl_confidence': confiança do HMARL
                - 'microstructure_weight': peso da microestrutura (0-1)
                - 'context_weight': peso do contexto (0-1)
        
        Returns:
            'scalping', 'swing' ou 'hybrid'
        """
        # Se sinal vem principalmente de microestrutura/book = scalping
        micro_weight = signal_source.get('microstructure_weight', 0.5)
        context_weight = signal_source.get('context_weight', 0.5)
        
        if micro_weight > 0.7:
            return 'scalping'
        elif context_weight > 0.7:
            return 'swing'
        else:
            return 'hybrid'
    
    def calculate_dynamic_levels(self, 
                                 current_price: float,
                                 signal: int,
                                 confidence: float,
                                 signal_source: Dict = None) -> Dict:
        """
        Calcula stop loss e take profit dinâmicos
        
        Args:
            current_price: Preço atual
            signal: 1 (BUY) ou -1 (SELL)
            confidence: Confiança do sinal (0-1)
            signal_source: Informações sobre origem do sinal
            
        Returns:
            Dict com stop_price, take_price e informações
        """
        # Atualizar preço
        self.update_price(current_price)
        
        # Determinar tipo de trade
        if signal_source:
            trade_type = self.get_trade_type(signal_source)
        else:
            # Fallback: usar confiança para determinar
            if confidence > 0.75:
                trade_type = 'swing'
            elif confidence > 0.65:
                trade_type = 'hybrid'
            else:
                trade_type = 'scalping'
        
        # Obter configuração base
        config = self.config[trade_type]
        
        # Calcular volatilidade
        volatility = self.calculate_volatility()
        
        # Ajustar stops/takes pela volatilidade
        volatility_factor = min(2.0, volatility / 10.0)  # Normalizar volatilidade
        
        # Base + ajuste por volatilidade
        stop_points = config['base_stop'] * (1 + (volatility_factor - 1) * 0.5)
        take_points = config['base_take'] * (1 + (volatility_factor - 1) * 0.5)
        
        # Ajustar pela confiança (maior confiança = pode arriscar mais)
        confidence_factor = 0.7 + (confidence * 0.6)  # Entre 0.7 e 1.3
        stop_points = stop_points * (2 - confidence_factor)  # Inverso para stop
        take_points = take_points * confidence_factor
        
        # Aplicar limites
        stop_points = min(config['max_stop'], max(config['base_stop'], stop_points))
        take_points = min(config['max_take'], max(config['base_take'], take_points))
        
        # Arredondar para múltiplos de 5 (tick do WDO)
        stop_points = round(stop_points / 5) * 5
        take_points = round(take_points / 5) * 5
        
        # Calcular preços finais
        if signal > 0:  # BUY
            stop_price = current_price - stop_points
            take_price = current_price + take_points
        else:  # SELL
            stop_price = current_price + stop_points
            take_price = current_price - take_points
        
        # Garantir múltiplos de 5
        stop_price = round(stop_price / 5) * 5
        take_price = round(take_price / 5) * 5
        
        # Log da decisão
        logger.info(f"[RISK] Tipo: {trade_type.upper()}")
        logger.info(f"  Volatilidade: {volatility:.1f} pontos")
        logger.info(f"  Confiança: {confidence:.1%}")
        logger.info(f"  Stop: {stop_points:.0f} pontos")
        logger.info(f"  Take: {take_points:.0f} pontos")
        
        return {
            'stop_price': stop_price,
            'take_price': take_price,
            'stop_points': stop_points,
            'take_points': take_points,
            'trade_type': trade_type,
            'volatility': volatility,
            'risk_reward_ratio': take_points / stop_points if stop_points > 0 else 2.0
        }
    
    def calculate_position_size(self, 
                               stop_points: float,
                               max_risk_brl: float = 500.0) -> int:
        """
        Calcula tamanho da posição baseado no risco máximo
        
        Args:
            stop_points: Distância do stop em pontos
            max_risk_brl: Risco máximo em R$
            
        Returns:
            Quantidade de contratos
        """
        # WDO: 1 ponto = R$ 10 por contrato
        point_value = 10.0
        
        # Calcular contratos
        risk_per_contract = stop_points * point_value
        
        if risk_per_contract > 0:
            contracts = int(max_risk_brl / risk_per_contract)
            return max(1, min(5, contracts))  # Entre 1 e 5 contratos
        
        return 1
    
    def get_market_regime(self) -> str:
        """
        Identifica regime do mercado baseado em volatilidade
        
        Returns:
            'low_vol', 'normal' ou 'high_vol'
        """
        volatility = self.calculate_volatility()
        
        if volatility < 8:
            return 'low_vol'
        elif volatility < 15:
            return 'normal'
        else:
            return 'high_vol'
    
    def adjust_for_time_of_day(self, stop_points: float, take_points: float) -> Tuple[float, float]:
        """
        Ajusta stops/takes baseado no horário do pregão
        
        Args:
            stop_points: Stop loss em pontos
            take_points: Take profit em pontos
            
        Returns:
            (stop_ajustado, take_ajustado)
        """
        from datetime import datetime
        
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        # Abertura (9:00-10:00) - mais volatilidade
        if 9 <= hour < 10:
            stop_points *= 1.2
            take_points *= 1.2
        
        # Almoço (12:00-13:00) - menos liquidez
        elif 12 <= hour < 13:
            stop_points *= 0.8
            take_points *= 0.8
        
        # Fechamento (17:00-18:00) - mais volatilidade
        elif hour >= 17:
            stop_points *= 1.3
            take_points *= 1.3
        
        return stop_points, take_points