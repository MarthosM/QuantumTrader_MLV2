"""
Feature Mapping - Mapeamento entre features calculadas e esperadas pelos agentes
"""

from typing import Dict, List, Optional
import numpy as np


class FeatureMapper:
    """
    Mapeia features calculadas para os nomes esperados pelos agentes HMARL
    """
    
    def __init__(self):
        # Mapeamento de features calculadas -> esperadas pelos agentes
        self.feature_mapping = {
            # Order Flow mappings
            "order_flow_imbalance_5": "order_flow_imbalance_10",  # Usar período mais próximo
            "signed_volume_5": "signed_volume",
            "signed_volume_10": "signed_volume",
            
            # Book features (criar sintéticas)
            "bid_volume_total": "volume_ratio_20",  # Proxy para volume total bid
            "ask_volume_total": "volume_ratio_50",  # Proxy para volume total ask
            "book_imbalance": "order_flow_imbalance_10",
            "book_pressure": "order_flow_imbalance_20",
            "micro_price": "vwap",  # Usar VWAP como proxy
            "weighted_mid_price": "vwap",
            
            # Liquidity features
            "bid_levels_active": "top_buyers_count",
            "ask_levels_active": "top_sellers_count", 
            "book_depth_imbalance": "order_flow_imbalance_20",
            "volume_depth_ratio": "volume_ratio_20",
            "spread": "volatility_10",  # Usar volatilidade como proxy para spread
            "spread_ma": "volatility_20",
            "spread_std": "volatility_50",
            "volume_20": "volume_ratio_20",
            "volume_50": "volume_ratio_50",
            
            # Tape reading features
            "trade_flow_5": "order_flow_imbalance_10",
            "trade_flow_10": "order_flow_imbalance_20",
            "buy_intensity": "is_buyer_aggressor",
            "sell_intensity": "is_buyer_aggressor",  # Inverso
            "large_trade_ratio": "volume_ratio_20",
            "trade_velocity": "trade_intensity",
            "vwap": "volume_weighted_return",
            "vwap_distance": "volume_weighted_return",
            "aggressive_buy_ratio": "is_buyer_aggressor",
            "aggressive_sell_ratio": "is_buyer_aggressor",
            
            # Footprint features
            "volume_profile_skew": "cumulative_signed_volume",
            "volume_concentration": "trade_intensity",
            "top_trader_ratio": "agent_turnover",
            "top_trader_side_bias": "is_buyer_aggressor",
            "volatility_5": "volatility_10"  # Usar período mais próximo
        }
        
        # Features sintéticas que precisam ser calculadas
        self.synthetic_features = {
            "sell_intensity": lambda features: 1.0 - features.get("is_buyer_aggressor", 0.5),
            "aggressive_sell_ratio": lambda features: 1.0 - features.get("is_buyer_aggressor", 0.5),
            "vwap_distance": lambda features: abs(features.get("volume_weighted_return", 0.0))
        }
    
    def map_features(self, calculated_features: Dict) -> Dict:
        """
        Mapeia features calculadas para incluir os nomes esperados pelos agentes
        
        Args:
            calculated_features: Features calculadas pelo sistema
            
        Returns:
            Dict com features originais + mapeadas
        """
        # Começar com todas as features calculadas
        mapped_features = calculated_features.copy()
        
        # Adicionar features mapeadas
        for expected_name, calculated_name in self.feature_mapping.items():
            if calculated_name in calculated_features:
                mapped_features[expected_name] = calculated_features[calculated_name]
            else:
                # Se não existir, usar valor padrão
                mapped_features[expected_name] = 0.0
        
        # Calcular features sintéticas
        for feature_name, calc_func in self.synthetic_features.items():
            try:
                mapped_features[feature_name] = calc_func(mapped_features)
            except:
                mapped_features[feature_name] = 0.0
        
        return mapped_features
    
    def get_required_agent_features(self) -> Dict[str, List[str]]:
        """
        Retorna as features requeridas por cada agente
        """
        return {
            "OrderFlowSpecialist": [
                "order_flow_imbalance_5", "signed_volume_5", "signed_volume_10",
                "bid_volume_total", "ask_volume_total", "book_imbalance",
                "book_pressure", "micro_price", "weighted_mid_price"
            ],
            "LiquidityAgent": [
                "bid_volume_total", "ask_volume_total", "bid_levels_active",
                "ask_levels_active", "book_depth_imbalance", "volume_depth_ratio",
                "spread", "spread_ma", "spread_std", "volume_20", "volume_50"
            ],
            "TapeReadingAgent": [
                "trade_flow_5", "trade_flow_10", "buy_intensity", "sell_intensity",
                "large_trade_ratio", "trade_velocity", "vwap", "vwap_distance",
                "aggressive_buy_ratio", "aggressive_sell_ratio"
            ],
            "FootprintPatternAgent": [
                "volume_profile_skew", "volume_concentration", "top_trader_ratio",
                "top_trader_side_bias", "micro_price", "weighted_mid_price", "volatility_5"
            ]
        }
    
    def validate_agent_features(self, features: Dict, agent_name: str) -> tuple[bool, List[str]]:
        """
        Valida se as features necessárias para um agente estão presentes
        
        Args:
            features: Features disponíveis
            agent_name: Nome do agente
            
        Returns:
            (is_valid, missing_features)
        """
        required = self.get_required_agent_features().get(agent_name, [])
        missing = [f for f in required if f not in features or features[f] is None]
        
        return len(missing) == 0, missing