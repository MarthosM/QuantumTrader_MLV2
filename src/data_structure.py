"""
Data Structure - Estrutura centralizada de dados do sistema
Baseado em enhanced_historical.py e market_data_processor.py
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional, List, Any
import logging

class TradingDataStructure:
    """
    Estrutura centralizada de dados do sistema
    Mantém dataframes separados para melhor organização e performance
    """
    
    def __init__(self):
        # DataFrames principais (baseado em enhanced_historical.py)
        self.candles = pd.DataFrame()
        self.microstructure = pd.DataFrame()
        self.orderbook = pd.DataFrame()
        self.indicators = pd.DataFrame()
        self.features = pd.DataFrame()
        
        # Metadados
        self.last_update = None
        self.ticker = None
        self.exchange = "F"
        
        # Controle de qualidade de dados
        self.data_quality = {
            'missing_candles': 0,
            'data_gaps': [],
            'last_check': None,
            'total_candles': 0,
            'data_range': None
        }
        
        # Cache de últimos valores
        self.last_price = None
        self.last_volume = None
        
        # Logger
        self.logger = logging.getLogger('TradingDataStructure')
        
    def initialize_structure(self) -> None:
        """
        Inicializa estrutura dos DataFrames
        Baseado no mapeamento de fluxo de dados
        """
        # Estrutura de candles (OHLCV)
        self.candles = pd.DataFrame(columns=[
            'open', 'high', 'low', 'close', 'volume', 'quantidade'
        ])
        
        # Estrutura de microestrutura
        self.microstructure = pd.DataFrame(columns=[
            'buy_volume', 'sell_volume',
            'buy_trades', 'sell_trades',
            'buy_pressure', 'sell_pressure',
            'volume_imbalance', 'trade_imbalance',
            'buy_ratio'
        ])
        
        # Estrutura de orderbook
        self.orderbook = pd.DataFrame(columns=[
            'bid', 'ask', 'spread',
            'bid_volume', 'ask_volume',
            'bid_count', 'ask_count',
            'depth_imbalance'
        ])
        
        # Estrutura de indicadores técnicos
        self.indicators = pd.DataFrame(columns=[
            # EMAs
            'ema_5', 'ema_9', 'ema_20', 'ema_50', 'ema_200',
            # RSI
            'rsi',
            # MACD
            'macd', 'macd_signal', 'macd_hist',
            # Bollinger Bands
            'bb_upper_20', 'bb_middle_20', 'bb_lower_20', 'bb_width_20',
            'bb_upper_50', 'bb_middle_50', 'bb_lower_50', 'bb_width_50',
            # ATR
            'atr', 'true_range',
            # Stochastic
            'stoch_k', 'stoch_d', 'slow_k', 'slow_d'
        ])
        
        # Estrutura de features ML
        self.features = pd.DataFrame(columns=[
            # Momentum
            'momentum_1', 'momentum_3', 'momentum_5', 'momentum_10', 'momentum_15', 'momentum_20',
            'momentum_pct_1', 'momentum_pct_3', 'momentum_pct_5', 'momentum_pct_10', 'momentum_pct_15', 'momentum_pct_20',
            # Volatilidade
            'volatility_5', 'volatility_10', 'volatility_20', 'volatility_50',
            'high_low_range_5', 'high_low_range_10', 'high_low_range_20',
            # Retornos
            'return_5', 'return_10', 'return_20', 'return_50',
            # Volume
            'volume_ratio_5', 'volume_ratio_10', 'volume_ratio_20',
            # Compostas
            'regime_strength', 'trend_strength', 'price_position_bb'
        ])
        
        self.logger.info("Estrutura de dados inicializada")
    
    def update_candles(self, new_candles: pd.DataFrame) -> bool:
        """Atualiza DataFrame de candles"""
        try:
            if new_candles.empty:
                return False
                
            if self.candles.empty:
                self.candles = new_candles.copy()
            else:
                # Concatenar e remover duplicatas
                self.candles = pd.concat([self.candles, new_candles])
                self.candles = self.candles[~self.candles.index.duplicated(keep='last')]
                self.candles = self.candles.sort_index()
                
            # Atualizar metadados
            self._update_metadata()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro atualizando candles: {e}")
            return False
    
    def update_microstructure(self, new_micro: pd.DataFrame) -> bool:
        """Atualiza DataFrame de microestrutura"""
        try:
            if new_micro.empty:
                return False
                
            if self.microstructure.empty:
                self.microstructure = new_micro.copy()
            else:
                # Concatenar e remover duplicatas
                self.microstructure = pd.concat([self.microstructure, new_micro])
                self.microstructure = self.microstructure[~self.microstructure.index.duplicated(keep='last')]
                self.microstructure = self.microstructure.sort_index()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Erro atualizando microestrutura: {e}")
            return False
    
    def update_orderbook(self, new_orderbook: pd.DataFrame) -> bool:
        """Atualiza DataFrame de orderbook"""
        try:
            if new_orderbook.empty:
                return False
                
            if self.orderbook.empty:
                self.orderbook = new_orderbook.copy()
            else:
                # Concatenar e remover duplicatas
                self.orderbook = pd.concat([self.orderbook, new_orderbook])
                self.orderbook = self.orderbook[~self.orderbook.index.duplicated(keep='last')]
                self.orderbook = self.orderbook.sort_index()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Erro atualizando orderbook: {e}")
            return False
    
    def update_indicators(self, new_indicators: pd.DataFrame) -> bool:
        """Atualiza DataFrame de indicadores"""
        try:
            if new_indicators.empty:
                return False
                
            if self.indicators.empty:
                self.indicators = new_indicators.copy()
            else:
                # Concatenar e remover duplicatas
                self.indicators = pd.concat([self.indicators, new_indicators])
                self.indicators = self.indicators[~self.indicators.index.duplicated(keep='last')]
                self.indicators = self.indicators.sort_index()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Erro atualizando indicadores: {e}")
            return False
    
    def update_features(self, new_features: pd.DataFrame) -> bool:
        """Atualiza DataFrame de features"""
        try:
            if new_features.empty:
                return False
                
            if self.features.empty:
                self.features = new_features.copy()
            else:
                # Concatenar e remover duplicatas
                self.features = pd.concat([self.features, new_features])
                self.features = self.features[~self.features.index.duplicated(keep='last')]
                self.features = self.features.sort_index()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Erro atualizando features: {e}")
            return False
    
    def _update_metadata(self):
        """Atualiza metadados e cache"""
        if not self.candles.empty:
            self.last_update = datetime.now()
            self.last_price = self.candles['close'].iloc[-1]
            self.last_volume = self.candles['volume'].iloc[-1]
            
            # Atualizar qualidade de dados
            self.data_quality['total_candles'] = len(self.candles)
            self.data_quality['data_range'] = {
                'start': self.candles.index[0],
                'end': self.candles.index[-1]
            }
    
    def get_candles(self) -> pd.DataFrame:
        """Retorna DataFrame de candles"""
        return self.candles.copy() if not self.candles.empty else pd.DataFrame()
    
    def get_indicators(self) -> pd.DataFrame:
        """Retorna DataFrame de indicadores"""
        return self.indicators.copy() if not self.indicators.empty else pd.DataFrame()
    
    def get_features(self) -> pd.DataFrame:
        """Retorna DataFrame de features"""
        return self.features.copy() if not self.features.empty else pd.DataFrame()
    
    def get_latest_candle(self) -> Optional[pd.Series]:
        """Retorna o candle mais recente"""
        if not self.candles.empty:
            return self.candles.iloc[-1]
        return None
    
    def get_candles_window(self, periods: int) -> pd.DataFrame:
        """Retorna janela de N candles mais recentes"""
        if not self.candles.empty:
            return self.candles.tail(periods)
        return pd.DataFrame()
    
    def check_data_quality(self) -> Dict[str, Any]:
        """
        Verifica qualidade dos dados
        Baseado em enhanced_historical.py _validate_separated_data()
        """
        issues = []
        
        # Verificar dados vazios
        if self.candles.empty:
            issues.append("DataFrame de candles vazio")
            
        # Verificar alinhamento temporal
        if not self.candles.empty and not self.microstructure.empty:
            missing_micro = set(self.candles.index) - set(self.microstructure.index)
            if missing_micro:
                issues.append(f"{len(missing_micro)} candles sem microestrutura")
                
        # Verificar gaps temporais
        if not self.candles.empty and len(self.candles) > 1:
            time_diffs = pd.Series(self.candles.index).diff()
            gaps = time_diffs[time_diffs > pd.Timedelta(minutes=1)]
            if len(gaps) > 0:
                issues.append(f"{len(gaps)} gaps temporais detectados")
                self.data_quality['data_gaps'] = gaps.tolist()
                
        # Verificar valores OHLC consistentes
        if not self.candles.empty:
            invalid_ohlc = (
                (self.candles['high'] < self.candles['low']) |
                (self.candles['high'] < self.candles['open']) |
                (self.candles['high'] < self.candles['close']) |
                (self.candles['low'] > self.candles['open']) |
                (self.candles['low'] > self.candles['close'])
            ).any()
            
            if invalid_ohlc:
                issues.append("Valores OHLC inconsistentes")
                
        # Verificar NaN
        for name, df in self.get_all_dataframes().items():
            if not df.empty:
                nan_count = df.isna().sum().sum()
                if nan_count > 0:
                    issues.append(f"{name}: {nan_count} valores NaN")
                    
        self.data_quality['issues'] = issues
        self.data_quality['last_check'] = datetime.now()
        
        return {
            'has_issues': len(issues) > 0,
            'issues': issues,
            'quality_score': max(0, 100 - len(issues) * 10),
            'details': self.data_quality
        }
    
    def get_all_dataframes(self) -> Dict[str, pd.DataFrame]:
        """Retorna todos os dataframes"""
        return {
            'candles': self.candles,
            'microstructure': self.microstructure,
            'orderbook': self.orderbook,
            'indicators': self.indicators,
            'features': self.features
        }
    
    def get_unified_dataframe(self) -> pd.DataFrame:
        """
        Retorna DataFrame unificado para compatibilidade
        Similar ao enhanced_historical.py _create_unified_dataframe()
        """
        dfs_to_concat = []
        
        # Adicionar DataFrames não vazios
        for name, df in self.get_all_dataframes().items():
            if not df.empty:
                # Adicionar prefixo às colunas (exceto candles)
                if name != 'candles':
                    df = df.add_prefix(f'{name}_')
                dfs_to_concat.append(df)
                
        # Unificar se houver dados
        if dfs_to_concat:
            unified = pd.concat(dfs_to_concat, axis=1)
            unified = unified.sort_index()
            return unified
            
        return pd.DataFrame()
    
    def clear(self):
        """Limpa todos os dados"""
        self.candles = pd.DataFrame()
        self.microstructure = pd.DataFrame()
        self.orderbook = pd.DataFrame()
        self.indicators = pd.DataFrame()
        self.features = pd.DataFrame()
        
        self.last_update = None
        self.last_price = None
        self.last_volume = None
        
        self.logger.info("Estrutura de dados limpa")
    
    def get_summary(self) -> Dict[str, Any]:
        """Retorna resumo do estado atual dos dados"""
        summary = {
            'ticker': self.ticker,
            'last_update': self.last_update,
            'last_price': self.last_price,
            'last_volume': self.last_volume,
            'dataframes': {}
        }
        
        for name, df in self.get_all_dataframes().items():
            summary['dataframes'][name] = {
                'rows': len(df),
                'columns': len(df.columns),
                'memory_usage': df.memory_usage(deep=True).sum() / 1024 / 1024,  # MB
                'has_data': not df.empty
            }
            
        return summary