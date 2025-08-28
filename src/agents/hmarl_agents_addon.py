"""
Adiciona métodos e classes auxiliares para o HMARL
"""

import numpy as np
from typing import Dict

class SimpleAgent:
    """Agente simples para compatibilidade com monitor"""
    def __init__(self, name):
        self.name = name
    
    def get_action(self, features: Dict) -> float:
        """Retorna ação do agente baseada nas features"""
        try:
            if self.name == 'orderflow':
                imbalance = features.get('order_flow_imbalance', 0)
                if imbalance > 0.3:
                    return 1.0
                elif imbalance < -0.3:
                    return -1.0
                return imbalance
                
            elif self.name == 'liquidity':
                spread = features.get('bid_ask_spread', 0.001)
                imbalance = features.get('liquidity_imbalance', 0)
                if spread < 0.002:  # Alta liquidez
                    return imbalance
                return 0.0
                
            elif self.name == 'tapereading':
                momentum = features.get('price_momentum', 0)
                if abs(momentum) > 0.5:
                    return np.sign(momentum)
                return momentum * 2  # Amplificar sinal
                
            elif self.name == 'footprint':
                delta = features.get('delta_profile', 0)
                absorption = features.get('absorption_ratio', 0.5)
                if delta > 50 and absorption > 0.7:
                    return 1.0
                elif delta < -50 and absorption > 0.7:
                    return -1.0
                return delta / 100
                
            return 0.0
            
        except Exception as e:
            return 0.0