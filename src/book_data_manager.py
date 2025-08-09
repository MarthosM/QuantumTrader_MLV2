"""
BookDataManager - Gerenciador de dados de Book (Bid/Ask)
Recebe callbacks de price_book e offer_book, mantém estado atualizado
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import threading
import logging
from collections import defaultdict
import sys
import os

# Adicionar path do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from buffers.circular_buffer import BookBuffer, TradeBuffer


class BookDataManager:
    """
    Gerenciador centralizado de dados de book
    Mantém estado atual e histórico do order book
    """
    
    def __init__(self, max_book_snapshots: int = 100, max_trades: int = 1000, levels: int = 5):
        """
        Inicializa o gerenciador de book
        
        Args:
            max_book_snapshots: Máximo de snapshots do book a manter
            max_trades: Máximo de trades a manter
            levels: Número de níveis do book a processar
        """
        self.levels = levels
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Buffers especializados
        self.book_buffer = BookBuffer(max_size=max_book_snapshots, levels=levels)
        self.trade_buffer = TradeBuffer(max_size=max_trades)
        
        # Estado atual do book
        self.current_book = {
            "timestamp": None,
            "bid_prices": [],
            "bid_volumes": [],
            "bid_traders": [],
            "ask_prices": [],
            "ask_volumes": [],
            "ask_traders": [],
            "mid_price": 0.0,
            "spread": 0.0,
            "total_bid_volume": 0,
            "total_ask_volume": 0
        }
        
        # Estatísticas acumuladas
        self.stats = {
            "total_snapshots": 0,
            "total_trades": 0,
            "last_update": None,
            "price_book_callbacks": 0,
            "offer_book_callbacks": 0,
            "trades_callbacks": 0,
            "errors": 0
        }
        
        # Lock para thread-safety
        self.lock = threading.RLock()
        
        # Cache de cálculos
        self._cache = {}
        self._cache_timestamp = None
        
        self.logger.info(f"BookDataManager inicializado: {levels} níveis, {max_book_snapshots} snapshots")
    
    def on_price_book_callback(self, data: Dict) -> bool:
        """
        Processa callback de price_book (bid side)
        
        Args:
            data: Dados do callback com estrutura:
                {
                    'timestamp': datetime,
                    'symbol': str,
                    'bids': [
                        {'price': float, 'volume': int, 'trader_id': str},
                        ...
                    ]
                }
        
        Returns:
            True se processado com sucesso
        """
        try:
            with self.lock:
                self.stats["price_book_callbacks"] += 1
                
                # Extrair dados do bid
                timestamp = data.get('timestamp', datetime.now())
                bids = data.get('bids', [])
                
                # Atualizar estado atual - lado bid
                self.current_book["timestamp"] = timestamp
                self.current_book["bid_prices"] = [b['price'] for b in bids[:self.levels]]
                self.current_book["bid_volumes"] = [b['volume'] for b in bids[:self.levels]]
                self.current_book["bid_traders"] = [b.get('trader_id', '') for b in bids[:self.levels]]
                self.current_book["total_bid_volume"] = sum(self.current_book["bid_volumes"])
                
                # Atualizar mid_price e spread se ask disponível
                self._update_derived_metrics()
                
                # Limpar cache
                self._invalidate_cache()
                
                self.stats["last_update"] = timestamp
                
                self.logger.debug(f"Price book atualizado: {len(bids)} bids")
                return True
                
        except Exception as e:
            self.logger.error(f"Erro em price_book_callback: {e}")
            self.stats["errors"] += 1
            return False
    
    def on_offer_book_callback(self, data: Dict) -> bool:
        """
        Processa callback de offer_book (ask side)
        
        Args:
            data: Dados do callback com estrutura:
                {
                    'timestamp': datetime,
                    'symbol': str,
                    'asks': [
                        {'price': float, 'volume': int, 'trader_id': str},
                        ...
                    ]
                }
        
        Returns:
            True se processado com sucesso
        """
        try:
            with self.lock:
                self.stats["offer_book_callbacks"] += 1
                
                # Extrair dados do ask
                timestamp = data.get('timestamp', datetime.now())
                asks = data.get('asks', [])
                
                # Atualizar estado atual - lado ask
                self.current_book["timestamp"] = timestamp
                self.current_book["ask_prices"] = [a['price'] for a in asks[:self.levels]]
                self.current_book["ask_volumes"] = [a['volume'] for a in asks[:self.levels]]
                self.current_book["ask_traders"] = [a.get('trader_id', '') for a in asks[:self.levels]]
                self.current_book["total_ask_volume"] = sum(self.current_book["ask_volumes"])
                
                # Atualizar mid_price e spread
                self._update_derived_metrics()
                
                # Se temos bid e ask completos, adicionar snapshot ao buffer
                if self._is_book_complete():
                    self._add_snapshot_to_buffer()
                
                # Limpar cache
                self._invalidate_cache()
                
                self.stats["last_update"] = timestamp
                
                self.logger.debug(f"Offer book atualizado: {len(asks)} asks")
                return True
                
        except Exception as e:
            self.logger.error(f"Erro em offer_book_callback: {e}")
            self.stats["errors"] += 1
            return False
    
    def on_trade_callback(self, data: Dict) -> bool:
        """
        Processa callback de trade executado
        
        Args:
            data: Dados do trade:
                {
                    'timestamp': datetime,
                    'symbol': str,
                    'price': float,
                    'volume': int,
                    'side': str ('buy' ou 'sell'),
                    'aggressor': str ('buyer' ou 'seller'),
                    'trader_id': str (opcional)
                }
        
        Returns:
            True se processado com sucesso
        """
        try:
            with self.lock:
                self.stats["trades_callbacks"] += 1
                
                # Adicionar trade ao buffer
                success = self.trade_buffer.add_trade(
                    timestamp=data.get('timestamp', datetime.now()),
                    price=data['price'],
                    volume=data['volume'],
                    side=data.get('side', 'unknown'),
                    aggressor=data.get('aggressor', 'unknown'),
                    trader_id=data.get('trader_id')
                )
                
                if success:
                    self.stats["total_trades"] += 1
                
                # Limpar cache
                self._invalidate_cache()
                
                return success
                
        except Exception as e:
            self.logger.error(f"Erro em trade_callback: {e}")
            self.stats["errors"] += 1
            return False
    
    def get_current_state(self) -> Dict:
        """
        Retorna estado atual completo do book
        
        Returns:
            Dict com estado atual incluindo métricas derivadas
        """
        with self.lock:
            state = self.current_book.copy()
            
            # Adicionar métricas do buffer
            state["book_depth"] = self.book_buffer.get_book_depth()
            state["imbalance"] = self.book_buffer.calculate_imbalance(periods=10)
            
            # Adicionar métricas de trades se disponível
            if self.trade_buffer.size() > 0:
                state["vwap"] = self.trade_buffer.calculate_vwap(periods=100)
                state["trade_intensity"] = self.trade_buffer.calculate_trade_intensity(60)
                state["aggressor_ratio"] = self.trade_buffer.get_aggressor_ratio()
            
            return state
    
    def get_microstructure_features(self) -> Dict:
        """
        Calcula features de microestrutura do mercado
        
        Returns:
            Dict com features de microestrutura
        """
        # Verificar cache
        if self._cache_timestamp == self.current_book["timestamp"] and "microstructure" in self._cache:
            return self._cache["microstructure"]
        
        with self.lock:
            features = {}
            
            # 1. Spread metrics
            features["spread"] = self.current_book["spread"]
            features["spread_relative"] = (
                self.current_book["spread"] / self.current_book["mid_price"] 
                if self.current_book["mid_price"] > 0 else 0
            )
            
            # 2. Depth imbalance
            total_volume = self.current_book["total_bid_volume"] + self.current_book["total_ask_volume"]
            if total_volume > 0:
                features["bid_volume_ratio"] = self.current_book["total_bid_volume"] / total_volume
                features["ask_volume_ratio"] = self.current_book["total_ask_volume"] / total_volume
            else:
                features["bid_volume_ratio"] = 0.5
                features["ask_volume_ratio"] = 0.5
            
            # 3. Order flow imbalance
            features["order_flow_imbalance"] = self.book_buffer.calculate_imbalance(periods=20)
            
            # 4. Price levels
            if self.current_book["bid_prices"]:
                features["best_bid"] = self.current_book["bid_prices"][0]
                features["bid_depth_weighted_price"] = self._calculate_weighted_price("bid")
            else:
                features["best_bid"] = 0
                features["bid_depth_weighted_price"] = 0
            
            if self.current_book["ask_prices"]:
                features["best_ask"] = self.current_book["ask_prices"][0]
                features["ask_depth_weighted_price"] = self._calculate_weighted_price("ask")
            else:
                features["best_ask"] = 0
                features["ask_depth_weighted_price"] = 0
            
            # 5. Level analysis
            features["bid_levels_active"] = len([v for v in self.current_book["bid_volumes"] if v > 0])
            features["ask_levels_active"] = len([v for v in self.current_book["ask_volumes"] if v > 0])
            
            # 6. Trader concentration (se disponível)
            if self.current_book["bid_traders"]:
                unique_bid_traders = len(set(t for t in self.current_book["bid_traders"] if t))
                features["bid_trader_concentration"] = 1 / unique_bid_traders if unique_bid_traders > 0 else 0
            else:
                features["bid_trader_concentration"] = 0
            
            if self.current_book["ask_traders"]:
                unique_ask_traders = len(set(t for t in self.current_book["ask_traders"] if t))
                features["ask_trader_concentration"] = 1 / unique_ask_traders if unique_ask_traders > 0 else 0
            else:
                features["ask_trader_concentration"] = 0
            
            # 7. Trade-based features
            if self.trade_buffer.size() > 0:
                features["vwap"] = self.trade_buffer.calculate_vwap(periods=100)
                features["trade_intensity"] = self.trade_buffer.calculate_trade_intensity(60)
                
                aggressor_ratio = self.trade_buffer.get_aggressor_ratio()
                features["buyer_aggressor_ratio"] = aggressor_ratio.get("buyer_aggressor_ratio", 0.5)
                features["seller_aggressor_ratio"] = aggressor_ratio.get("seller_aggressor_ratio", 0.5)
            
            # Cachear resultado
            self._cache["microstructure"] = features
            self._cache_timestamp = self.current_book["timestamp"]
            
            return features
    
    def get_book_dataframe(self, last_n: int = 100) -> pd.DataFrame:
        """
        Retorna DataFrame com histórico do book
        
        Args:
            last_n: Número de snapshots a retornar
            
        Returns:
            DataFrame com dados do book
        """
        return self.book_buffer.get_dataframe()
    
    def get_trades_dataframe(self, last_n: int = 1000) -> pd.DataFrame:
        """
        Retorna DataFrame com histórico de trades
        
        Args:
            last_n: Número de trades a retornar
            
        Returns:
            DataFrame com dados de trades
        """
        return self.trade_buffer.get_dataframe()
    
    def get_statistics(self) -> Dict:
        """
        Retorna estatísticas do gerenciador
        
        Returns:
            Dict com estatísticas completas
        """
        with self.lock:
            stats = self.stats.copy()
            stats["book_buffer_stats"] = self.book_buffer.get_stats()
            stats["trade_buffer_stats"] = self.trade_buffer.get_stats()
            stats["current_spread"] = self.current_book["spread"]
            stats["current_mid_price"] = self.current_book["mid_price"]
            return stats
    
    def reset(self):
        """Reseta todos os buffers e estado"""
        with self.lock:
            self.book_buffer.clear()
            self.trade_buffer.clear()
            
            # Resetar estado atual
            for key in self.current_book:
                if isinstance(self.current_book[key], list):
                    self.current_book[key] = []
                elif isinstance(self.current_book[key], (int, float)):
                    self.current_book[key] = 0
                else:
                    self.current_book[key] = None
            
            # Resetar estatísticas
            for key in self.stats:
                if key != "errors":
                    self.stats[key] = 0
            
            # Limpar cache
            self._invalidate_cache()
            
            self.logger.info("BookDataManager resetado")
    
    # Métodos privados auxiliares
    
    def _update_derived_metrics(self):
        """Atualiza métricas derivadas (mid_price, spread)"""
        if self.current_book["bid_prices"] and self.current_book["ask_prices"]:
            best_bid = self.current_book["bid_prices"][0]
            best_ask = self.current_book["ask_prices"][0]
            
            self.current_book["mid_price"] = (best_bid + best_ask) / 2
            self.current_book["spread"] = best_ask - best_bid
    
    def _is_book_complete(self) -> bool:
        """Verifica se temos dados completos de bid e ask"""
        return (
            len(self.current_book["bid_prices"]) > 0 and
            len(self.current_book["ask_prices"]) > 0
        )
    
    def _add_snapshot_to_buffer(self):
        """Adiciona snapshot atual ao buffer histórico"""
        if self._is_book_complete():
            self.book_buffer.add_snapshot(
                timestamp=self.current_book["timestamp"],
                bid_prices=self.current_book["bid_prices"],
                bid_volumes=self.current_book["bid_volumes"],
                ask_prices=self.current_book["ask_prices"],
                ask_volumes=self.current_book["ask_volumes"],
                bid_traders=self.current_book["bid_traders"] if self.current_book["bid_traders"] else None,
                ask_traders=self.current_book["ask_traders"] if self.current_book["ask_traders"] else None
            )
            self.stats["total_snapshots"] += 1
    
    def _calculate_weighted_price(self, side: str) -> float:
        """
        Calcula preço ponderado por volume
        
        Args:
            side: 'bid' ou 'ask'
            
        Returns:
            Preço ponderado por volume
        """
        if side == "bid":
            prices = self.current_book["bid_prices"]
            volumes = self.current_book["bid_volumes"]
        else:
            prices = self.current_book["ask_prices"]
            volumes = self.current_book["ask_volumes"]
        
        if not prices or not volumes:
            return 0.0
        
        total_value = sum(p * v for p, v in zip(prices, volumes))
        total_volume = sum(volumes)
        
        if total_volume == 0:
            return 0.0
        
        return total_value / total_volume
    
    def _invalidate_cache(self):
        """Invalida cache de cálculos"""
        self._cache.clear()
        self._cache_timestamp = None


# Exemplo de uso e teste rápido
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Criar gerenciador
    manager = BookDataManager(max_book_snapshots=50, max_trades=500, levels=5)
    
    # Simular callbacks
    print("Testando BookDataManager...")
    
    # Callback de price_book (bid)
    price_data = {
        'timestamp': datetime.now(),
        'symbol': 'WDOU25',
        'bids': [
            {'price': 5450.0, 'volume': 100, 'trader_id': 'T1'},
            {'price': 5449.5, 'volume': 150, 'trader_id': 'T2'},
            {'price': 5449.0, 'volume': 200, 'trader_id': 'T3'},
            {'price': 5448.5, 'volume': 120, 'trader_id': 'T1'},
            {'price': 5448.0, 'volume': 180, 'trader_id': 'T4'},
        ]
    }
    manager.on_price_book_callback(price_data)
    
    # Callback de offer_book (ask)
    offer_data = {
        'timestamp': datetime.now(),
        'symbol': 'WDOU25',
        'asks': [
            {'price': 5451.0, 'volume': 110, 'trader_id': 'T5'},
            {'price': 5451.5, 'volume': 160, 'trader_id': 'T6'},
            {'price': 5452.0, 'volume': 190, 'trader_id': 'T7'},
            {'price': 5452.5, 'volume': 130, 'trader_id': 'T5'},
            {'price': 5453.0, 'volume': 170, 'trader_id': 'T8'},
        ]
    }
    manager.on_offer_book_callback(offer_data)
    
    # Callback de trade
    trade_data = {
        'timestamp': datetime.now(),
        'symbol': 'WDOU25',
        'price': 5450.5,
        'volume': 50,
        'side': 'buy',
        'aggressor': 'buyer',
        'trader_id': 'T1'
    }
    manager.on_trade_callback(trade_data)
    
    # Verificar estado
    state = manager.get_current_state()
    print(f"\nEstado atual do book:")
    print(f"  Mid price: {state['mid_price']:.2f}")
    print(f"  Spread: {state['spread']:.2f}")
    print(f"  Total bid volume: {state['total_bid_volume']}")
    print(f"  Total ask volume: {state['total_ask_volume']}")
    
    # Verificar features de microestrutura
    features = manager.get_microstructure_features()
    print(f"\nFeatures de microestrutura:")
    for key, value in features.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
    
    # Estatísticas
    stats = manager.get_statistics()
    print(f"\nEstatísticas:")
    print(f"  Price book callbacks: {stats['price_book_callbacks']}")
    print(f"  Offer book callbacks: {stats['offer_book_callbacks']}")
    print(f"  Trade callbacks: {stats['trades_callbacks']}")
    print(f"  Total snapshots: {stats['total_snapshots']}")
    print(f"  Total trades: {stats['total_trades']}")
    
    print("\n[OK] BookDataManager testado com sucesso!")