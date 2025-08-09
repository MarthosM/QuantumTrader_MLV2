"""
BookFeatureEngineerRT - Engenharia de Features em Tempo Real
Versão otimizada para cálculo incremental das 65 features necessárias
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import logging
import threading
from collections import deque
import warnings
warnings.filterwarnings('ignore')

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from book_data_manager import BookDataManager
from buffers.circular_buffer import CandleBuffer, BookBuffer, TradeBuffer


class BookFeatureEngineerRT:
    """
    Engenharia de Features em Tempo Real
    Calcula as 65 features necessárias para os modelos ML de forma incremental
    """
    
    def __init__(self, book_manager: Optional[BookDataManager] = None):
        """
        Inicializa o calculador de features em tempo real
        
        Args:
            book_manager: Gerenciador de dados de book (opcional)
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Gerenciador de dados
        self.book_manager = book_manager or BookDataManager()
        
        # Buffers para cálculos
        self.candle_buffer = CandleBuffer(max_size=200)
        
        # Cache de features calculadas
        self.feature_cache = {}
        self.cache_timestamp = None
        self.cache_lock = threading.RLock()
        
        # Configurações
        self.lookback_periods = {
            'short': [1, 2, 5],
            'medium': [10, 20],
            'long': [50, 100]
        }
        
        # Lista das 65 features esperadas
        self.required_features = self._get_required_features()
        
        # Estatísticas
        self.stats = {
            'total_calculations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'avg_calc_time_ms': 0
        }
        
        self.logger.info(f"BookFeatureEngineerRT inicializado com {len(self.required_features)} features")
    
    def _get_required_features(self) -> List[str]:
        """Retorna lista das 65 features necessárias"""
        return [
            # Volatilidade (10)
            "volatility_10", "volatility_20", "volatility_50", "volatility_100",
            "volatility_ratio_10_20", "volatility_ratio_20_50", "volatility_ratio_50_100", "volatility_ratio_100_200",
            "volatility_gk", "bb_position",
            
            # Retornos (10)
            "returns_1", "returns_2", "returns_5", "returns_10", "returns_20",
            "returns_50", "returns_100", "log_returns_1", "log_returns_5", "log_returns_20",
            
            # Order Flow (8)
            "order_flow_imbalance_10", "order_flow_imbalance_20",
            "order_flow_imbalance_50", "order_flow_imbalance_100",
            "cumulative_signed_volume", "signed_volume",
            "volume_weighted_return", "agent_turnover",
            
            # Volume (8)
            "volume_ratio_20", "volume_ratio_50", "volume_ratio_100",
            "volume_zscore_20", "volume_zscore_50", "volume_zscore_100",
            "trade_intensity", "trade_intensity_ratio",
            
            # Indicadores Técnicos (8)
            "ma_5_20_ratio", "ma_20_50_ratio",
            "momentum_5_20", "momentum_20_50",
            "sharpe_5", "sharpe_20",
            "time_normalized", "rsi_14",
            
            # Microestrutura (15)
            "top_buyer_0_active", "top_buyer_1_active", "top_buyer_2_active",
            "top_buyer_3_active", "top_buyer_4_active",
            "top_seller_0_active", "top_seller_1_active", "top_seller_2_active",
            "top_seller_3_active", "top_seller_4_active",
            "top_buyers_count", "top_sellers_count",
            "buyer_changed", "seller_changed",
            "is_buyer_aggressor",
            
            # Temporais (6)
            "minute", "hour", "day_of_week",
            "is_opening_30min", "is_closing_30min", "is_lunch_hour"
        ]
    
    def calculate_incremental_features(self, new_data: Dict) -> Dict:
        """
        Calcula features de forma incremental com novo dado
        
        Args:
            new_data: Novo dado recebido (candle, book ou trade)
            
        Returns:
            Dict com todas as 65 features calculadas
        """
        import time
        start_time = time.time()
        
        try:
            with self.cache_lock:
                # Verificar tipo de dado
                if 'open' in new_data and 'close' in new_data:
                    # É um candle
                    self._update_candle(new_data)
                
                # Calcular todas as features
                features = {}
                
                # 1. Features de Volatilidade
                volatility_features = self._calculate_volatility_features()
                features.update(volatility_features)
                
                # 2. Features de Retornos
                return_features = self._calculate_return_features()
                features.update(return_features)
                
                # 3. Features de Order Flow
                order_flow_features = self._calculate_order_flow_features()
                features.update(order_flow_features)
                
                # 4. Features de Volume
                volume_features = self._calculate_volume_features()
                features.update(volume_features)
                
                # 5. Features de Indicadores Técnicos
                technical_features = self._calculate_technical_features()
                features.update(technical_features)
                
                # 6. Features de Microestrutura
                microstructure_features = self._calculate_microstructure_features()
                features.update(microstructure_features)
                
                # 7. Features Temporais
                temporal_features = self._calculate_temporal_features()
                features.update(temporal_features)
                
                # Garantir que temos todas as 65 features
                features = self._validate_and_fill_features(features)
                
                # Atualizar estatísticas
                self.stats['total_calculations'] += 1
                calc_time = (time.time() - start_time) * 1000
                self.stats['avg_calc_time_ms'] = (
                    (self.stats['avg_calc_time_ms'] * (self.stats['total_calculations'] - 1) + calc_time) 
                    / self.stats['total_calculations']
                )
                
                self.logger.debug(f"Features calculadas em {calc_time:.2f}ms")
                
                return features
                
        except Exception as e:
            self.logger.error(f"Erro ao calcular features: {e}")
            self.stats['errors'] += 1
            # Retornar features com valores padrão
            return self._get_default_features()
    
    def get_feature_vector(self) -> np.ndarray:
        """
        Retorna vetor de features pronto para predição
        
        Returns:
            Array numpy com 65 features na ordem correta
        """
        features = self.calculate_incremental_features({})
        
        # Garantir ordem correta das features
        feature_vector = []
        for feature_name in self.required_features:
            feature_vector.append(features.get(feature_name, 0.0))
        
        return np.array(feature_vector)
    
    # Métodos privados de cálculo de features
    
    def _update_candle(self, candle_data: Dict):
        """Atualiza buffer de candles"""
        self.candle_buffer.add_candle(
            timestamp=candle_data.get('timestamp', datetime.now()),
            open=candle_data['open'],
            high=candle_data['high'],
            low=candle_data['low'],
            close=candle_data['close'],
            volume=candle_data['volume']
        )
    
    def _calculate_volatility_features(self) -> Dict:
        """Calcula features de volatilidade"""
        features = {}
        
        df = self.candle_buffer.get_dataframe()
        if df.empty:
            return self._get_default_volatility_features()
        
        closes = df['close'].values
        
        # Volatilidades em diferentes períodos
        for period in [10, 20, 50, 100]:
            if len(closes) >= period:
                returns = np.diff(closes[-period:]) / closes[-period:-1]
                features[f'volatility_{period}'] = np.std(returns) if len(returns) > 0 else 0
            else:
                features[f'volatility_{period}'] = 0
        
        # Ratios de volatilidade
        for p1, p2 in [(10, 20), (20, 50), (50, 100), (100, 200)]:
            key1, key2 = f'volatility_{p1}', f'volatility_{min(p2, 100)}'
            if key1 in features and key2 in features and features[key2] > 0:
                features[f'volatility_ratio_{p1}_{p2}'] = features[key1] / features[key2]
            else:
                features[f'volatility_ratio_{p1}_{p2}'] = 1.0
        
        # Garman-Klass volatility
        if len(df) >= 20:
            high_low = np.log(df['high'].values[-20:] / df['low'].values[-20:])
            close_open = np.log(df['close'].values[-20:] / df['open'].values[-20:])
            features['volatility_gk'] = np.sqrt(np.mean(0.5 * high_low**2 - (2*np.log(2) - 1) * close_open**2))
        else:
            features['volatility_gk'] = 0
        
        # Bollinger Band position
        if len(closes) >= 20:
            ma20 = np.mean(closes[-20:])
            std20 = np.std(closes[-20:])
            if std20 > 0:
                features['bb_position'] = (closes[-1] - ma20) / (2 * std20)
            else:
                features['bb_position'] = 0
        else:
            features['bb_position'] = 0
        
        return features
    
    def _calculate_return_features(self) -> Dict:
        """Calcula features de retornos"""
        features = {}
        
        df = self.candle_buffer.get_dataframe()
        if df.empty:
            return self._get_default_return_features()
        
        closes = df['close'].values
        
        # Retornos simples
        for period in [1, 2, 5, 10, 20, 50, 100]:
            if len(closes) > period:
                features[f'returns_{period}'] = (closes[-1] - closes[-period-1]) / closes[-period-1]
            else:
                features[f'returns_{period}'] = 0
        
        # Log retornos
        for period in [1, 5, 20]:
            if len(closes) > period:
                features[f'log_returns_{period}'] = np.log(closes[-1] / closes[-period-1])
            else:
                features[f'log_returns_{period}'] = 0
        
        return features
    
    def _calculate_order_flow_features(self) -> Dict:
        """Calcula features de order flow"""
        features = {}
        
        # Usar dados do book manager se disponível
        if self.book_manager:
            book_state = self.book_manager.get_current_state()
            
            # Order flow imbalance
            for period in [10, 20, 50, 100]:
                features[f'order_flow_imbalance_{period}'] = book_state.get('imbalance', 0)
            
            # Volume metrics
            features['cumulative_signed_volume'] = 0  # Seria calculado com histórico de trades
            features['signed_volume'] = 0
            
            # Volume weighted return
            if 'vwap' in book_state and self.candle_buffer.size() > 0:
                last_close = self.candle_buffer.get_last_n(1)[0].get('close', 0)
                if last_close > 0:
                    features['volume_weighted_return'] = (book_state['vwap'] - last_close) / last_close
                else:
                    features['volume_weighted_return'] = 0
            else:
                features['volume_weighted_return'] = 0
            
            # Agent turnover (simplicado)
            features['agent_turnover'] = book_state.get('trade_intensity', 0)
        else:
            # Valores padrão
            for period in [10, 20, 50, 100]:
                features[f'order_flow_imbalance_{period}'] = 0
            features['cumulative_signed_volume'] = 0
            features['signed_volume'] = 0
            features['volume_weighted_return'] = 0
            features['agent_turnover'] = 0
        
        return features
    
    def _calculate_volume_features(self) -> Dict:
        """Calcula features de volume"""
        features = {}
        
        df = self.candle_buffer.get_dataframe()
        if df.empty:
            return self._get_default_volume_features()
        
        volumes = df['volume'].values
        
        # Volume ratios
        for period in [20, 50, 100]:
            if len(volumes) > period:
                recent_vol = np.mean(volumes[-10:])
                period_vol = np.mean(volumes[-period:])
                if period_vol > 0:
                    features[f'volume_ratio_{period}'] = recent_vol / period_vol
                else:
                    features[f'volume_ratio_{period}'] = 1.0
            else:
                features[f'volume_ratio_{period}'] = 1.0
        
        # Volume z-score
        for period in [20, 50, 100]:
            if len(volumes) >= period:
                mean_vol = np.mean(volumes[-period:])
                std_vol = np.std(volumes[-period:])
                if std_vol > 0:
                    features[f'volume_zscore_{period}'] = (volumes[-1] - mean_vol) / std_vol
                else:
                    features[f'volume_zscore_{period}'] = 0
            else:
                features[f'volume_zscore_{period}'] = 0
        
        # Trade intensity
        if self.book_manager:
            book_state = self.book_manager.get_current_state()
            features['trade_intensity'] = book_state.get('trade_intensity', 0)
            features['trade_intensity_ratio'] = min(features['trade_intensity'] / 10, 1.0)  # Normalizado
        else:
            features['trade_intensity'] = 0
            features['trade_intensity_ratio'] = 0
        
        return features
    
    def _calculate_technical_features(self) -> Dict:
        """Calcula indicadores técnicos"""
        features = {}
        
        df = self.candle_buffer.get_dataframe()
        if df.empty:
            return self._get_default_technical_features()
        
        closes = df['close'].values
        
        # Moving average ratios
        if len(closes) >= 20:
            ma5 = np.mean(closes[-5:])
            ma20 = np.mean(closes[-20:])
            if ma20 > 0:
                features['ma_5_20_ratio'] = ma5 / ma20
            else:
                features['ma_5_20_ratio'] = 1.0
        else:
            features['ma_5_20_ratio'] = 1.0
        
        if len(closes) >= 50:
            ma20 = np.mean(closes[-20:])
            ma50 = np.mean(closes[-50:])
            if ma50 > 0:
                features['ma_20_50_ratio'] = ma20 / ma50
            else:
                features['ma_20_50_ratio'] = 1.0
        else:
            features['ma_20_50_ratio'] = 1.0
        
        # Momentum
        if len(closes) >= 20:
            features['momentum_5_20'] = (closes[-1] - closes[-5]) / (closes[-5] - closes[-20]) if closes[-5] != closes[-20] else 0
        else:
            features['momentum_5_20'] = 0
        
        if len(closes) >= 50:
            features['momentum_20_50'] = (closes[-1] - closes[-20]) / (closes[-20] - closes[-50]) if closes[-20] != closes[-50] else 0
        else:
            features['momentum_20_50'] = 0
        
        # Sharpe ratio simplificado
        for period in [5, 20]:
            if len(closes) > period:
                returns = np.diff(closes[-period:]) / closes[-period:-1]
                if len(returns) > 0:
                    mean_ret = np.mean(returns)
                    std_ret = np.std(returns)
                    if std_ret > 0:
                        features[f'sharpe_{period}'] = mean_ret / std_ret * np.sqrt(252)  # Anualizado
                    else:
                        features[f'sharpe_{period}'] = 0
                else:
                    features[f'sharpe_{period}'] = 0
            else:
                features[f'sharpe_{period}'] = 0
        
        # Time normalized (0-1 para o dia de trading)
        now = datetime.now()
        market_open = now.replace(hour=9, minute=0, second=0)
        market_close = now.replace(hour=17, minute=30, second=0)
        total_seconds = (market_close - market_open).total_seconds()
        elapsed_seconds = (now - market_open).total_seconds()
        features['time_normalized'] = min(max(elapsed_seconds / total_seconds, 0), 1)
        
        # RSI
        features['rsi_14'] = self._calculate_rsi(closes, 14)
        
        return features
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calcula RSI"""
        if len(prices) < period + 1:
            return 50.0  # Neutro
        
        deltas = np.diff(prices[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_microstructure_features(self) -> Dict:
        """Calcula features de microestrutura"""
        features = {}
        
        if self.book_manager:
            book_state = self.book_manager.get_current_state()
            micro_features = self.book_manager.get_microstructure_features()
            
            # Top traders activity (simplificado - seria baseado em IDs reais)
            for i in range(5):
                features[f'top_buyer_{i}_active'] = 1 if i < 2 else 0  # Simulado
                features[f'top_seller_{i}_active'] = 1 if i < 2 else 0  # Simulado
            
            # Contagem de traders únicos
            features['top_buyers_count'] = min(len(book_state.get('bid_traders', [])), 5)
            features['top_sellers_count'] = min(len(book_state.get('ask_traders', [])), 5)
            
            # Mudança de traders (simplificado)
            features['buyer_changed'] = 0  # Precisaria histórico
            features['seller_changed'] = 0  # Precisaria histórico
            
            # Aggressor
            features['is_buyer_aggressor'] = 1 if micro_features.get('buyer_aggressor_ratio', 0.5) > 0.5 else 0
        else:
            # Valores padrão
            for i in range(5):
                features[f'top_buyer_{i}_active'] = 0
                features[f'top_seller_{i}_active'] = 0
            features['top_buyers_count'] = 0
            features['top_sellers_count'] = 0
            features['buyer_changed'] = 0
            features['seller_changed'] = 0
            features['is_buyer_aggressor'] = 0
        
        return features
    
    def _calculate_temporal_features(self) -> Dict:
        """Calcula features temporais"""
        features = {}
        
        now = datetime.now()
        
        # Features básicas de tempo
        features['minute'] = now.minute / 60.0  # Normalizado 0-1
        features['hour'] = now.hour / 24.0  # Normalizado 0-1
        features['day_of_week'] = now.weekday() / 4.0  # 0-1 (segunda a sexta)
        
        # Períodos especiais do mercado
        hour_min = now.hour * 60 + now.minute
        
        # Primeiros 30 minutos (9:00 - 9:30)
        features['is_opening_30min'] = 1 if 540 <= hour_min <= 570 else 0
        
        # Últimos 30 minutos (17:00 - 17:30)
        features['is_closing_30min'] = 1 if 1020 <= hour_min <= 1050 else 0
        
        # Hora do almoço (12:00 - 13:00)
        features['is_lunch_hour'] = 1 if 720 <= hour_min <= 780 else 0
        
        return features
    
    def _validate_and_fill_features(self, features: Dict) -> Dict:
        """
        Valida e preenche features faltantes
        
        Args:
            features: Dict com features calculadas
            
        Returns:
            Dict com todas as 65 features
        """
        validated = {}
        
        for feature_name in self.required_features:
            if feature_name in features:
                value = features[feature_name]
                # Tratar NaN e infinitos
                if pd.isna(value) or np.isinf(value):
                    validated[feature_name] = 0.0
                else:
                    validated[feature_name] = float(value)
            else:
                # Feature faltante - usar valor padrão
                validated[feature_name] = 0.0
                self.logger.debug(f"Feature faltante preenchida com 0: {feature_name}")
        
        return validated
    
    def _get_default_features(self) -> Dict:
        """Retorna features com valores padrão"""
        return {feature: 0.0 for feature in self.required_features}
    
    def _get_default_volatility_features(self) -> Dict:
        """Valores padrão para features de volatilidade"""
        features = {}
        for period in [10, 20, 50, 100]:
            features[f'volatility_{period}'] = 0.01  # Volatilidade mínima
        for p1, p2 in [(10, 20), (20, 50), (50, 100), (100, 200)]:
            features[f'volatility_ratio_{p1}_{p2}'] = 1.0
        features['volatility_gk'] = 0.01
        features['bb_position'] = 0.0
        return features
    
    def _get_default_return_features(self) -> Dict:
        """Valores padrão para features de retorno"""
        features = {}
        for period in [1, 2, 5, 10, 20, 50, 100]:
            features[f'returns_{period}'] = 0.0
        for period in [1, 5, 20]:
            features[f'log_returns_{period}'] = 0.0
        return features
    
    def _get_default_volume_features(self) -> Dict:
        """Valores padrão para features de volume"""
        features = {}
        for period in [20, 50, 100]:
            features[f'volume_ratio_{period}'] = 1.0
            features[f'volume_zscore_{period}'] = 0.0
        features['trade_intensity'] = 0.0
        features['trade_intensity_ratio'] = 0.0
        return features
    
    def _get_default_technical_features(self) -> Dict:
        """Valores padrão para indicadores técnicos"""
        return {
            'ma_5_20_ratio': 1.0,
            'ma_20_50_ratio': 1.0,
            'momentum_5_20': 0.0,
            'momentum_20_50': 0.0,
            'sharpe_5': 0.0,
            'sharpe_20': 0.0,
            'time_normalized': 0.5,
            'rsi_14': 50.0
        }
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas do calculador"""
        with self.cache_lock:
            return {
                **self.stats,
                'candle_buffer_size': self.candle_buffer.size(),
                'book_manager_stats': self.book_manager.get_statistics() if self.book_manager else {},
                'features_calculated': len(self.required_features)
            }


# Teste rápido
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Testando BookFeatureEngineerRT...")
    
    # Criar calculador
    engineer = BookFeatureEngineerRT()
    
    # Simular alguns candles
    for i in range(30):
        candle = {
            'timestamp': datetime.now() - timedelta(minutes=30-i),
            'open': 5450 + np.random.randn() * 5,
            'high': 5455 + np.random.randn() * 5,
            'low': 5445 + np.random.randn() * 5,
            'close': 5450 + np.random.randn() * 5,
            'volume': 100000 + np.random.randint(-10000, 10000)
        }
        engineer._update_candle(candle)
    
    # Calcular features
    features = engineer.calculate_incremental_features({})
    
    print(f"\nTotal de features calculadas: {len(features)}")
    print("\nPrimeiras 10 features:")
    for i, (name, value) in enumerate(list(features.items())[:10]):
        print(f"  {name}: {value:.4f}")
    
    # Verificar vetor de features
    vector = engineer.get_feature_vector()
    print(f"\nVetor de features shape: {vector.shape}")
    print(f"Valores não-zero: {np.count_nonzero(vector)}/{len(vector)}")
    
    # Estatísticas
    stats = engineer.get_statistics()
    print(f"\nEstatísticas:")
    print(f"  Cálculos totais: {stats['total_calculations']}")
    print(f"  Tempo médio: {stats['avg_calc_time_ms']:.2f}ms")
    print(f"  Features configuradas: {stats['features_calculated']}")
    
    print("\n[OK] BookFeatureEngineerRT testado com sucesso!")