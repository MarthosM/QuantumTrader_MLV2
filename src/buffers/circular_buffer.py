"""
CircularBuffer - Buffer circular otimizado para dados de mercado
Mantém histórico limitado com acesso eficiente para cálculo de features
"""

import numpy as np
import pandas as pd
from collections import deque
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import threading
import logging

class CircularBuffer:
    """
    Buffer circular thread-safe para armazenamento eficiente de dados de mercado
    """
    
    def __init__(self, max_size: int = 1000, name: str = "buffer"):
        """
        Inicializa o buffer circular
        
        Args:
            max_size: Tamanho máximo do buffer
            name: Nome identificador do buffer
        """
        self.max_size = max_size
        self.name = name
        self.data = deque(maxlen=max_size)
        self.lock = threading.RLock()
        self.logger = logging.getLogger(f"CircularBuffer.{name}")
        
        # Estatísticas
        self.stats = {
            "total_added": 0,
            "total_dropped": 0,
            "last_update": None
        }
        
    def add(self, item: Any) -> bool:
        """
        Adiciona item ao buffer
        
        Args:
            item: Item a ser adicionado
            
        Returns:
            True se adicionado com sucesso
        """
        try:
            with self.lock:
                # Se buffer está cheio, o item mais antigo é removido automaticamente
                if len(self.data) == self.max_size:
                    self.stats["total_dropped"] += 1
                    
                self.data.append(item)
                self.stats["total_added"] += 1
                self.stats["last_update"] = datetime.now()
                
                return True
                
        except Exception as e:
            self.logger.error(f"Erro ao adicionar item: {e}")
            return False
    
    def add_batch(self, items: List[Any]) -> int:
        """
        Adiciona múltiplos itens de uma vez
        
        Args:
            items: Lista de itens
            
        Returns:
            Número de itens adicionados
        """
        added = 0
        with self.lock:
            for item in items:
                if self.add(item):
                    added += 1
        return added
    
    def get_last_n(self, n: int) -> List[Any]:
        """
        Retorna os últimos N itens
        
        Args:
            n: Número de itens
            
        Returns:
            Lista com os últimos N itens
        """
        with self.lock:
            if n >= len(self.data):
                return list(self.data)
            return list(self.data)[-n:]
    
    def get_dataframe(self, columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Converte buffer para DataFrame
        
        Args:
            columns: Nomes das colunas (opcional)
            
        Returns:
            DataFrame com os dados do buffer
        """
        with self.lock:
            if not self.data:
                return pd.DataFrame()
            
            # Se os itens são dicts
            if isinstance(self.data[0], dict):
                df = pd.DataFrame(list(self.data))
                if columns:
                    # Reordenar/filtrar colunas se especificado
                    available_cols = [col for col in columns if col in df.columns]
                    df = df[available_cols]
                return df
            
            # Se os itens são listas/tuplas
            elif isinstance(self.data[0], (list, tuple)):
                return pd.DataFrame(list(self.data), columns=columns)
            
            # Outros tipos
            else:
                return pd.DataFrame(list(self.data), columns=['value'])
    
    def clear(self):
        """Limpa o buffer"""
        with self.lock:
            self.data.clear()
            self.logger.info(f"Buffer '{self.name}' limpo")
    
    def size(self) -> int:
        """Retorna tamanho atual do buffer"""
        with self.lock:
            return len(self.data)
    
    def is_full(self) -> bool:
        """Verifica se buffer está cheio"""
        with self.lock:
            return len(self.data) == self.max_size
    
    def is_empty(self) -> bool:
        """Verifica se buffer está vazio"""
        with self.lock:
            return len(self.data) == 0
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do buffer"""
        with self.lock:
            return {
                "name": self.name,
                "current_size": len(self.data),
                "max_size": self.max_size,
                "utilization": len(self.data) / self.max_size * 100,
                **self.stats
            }
    
    def __len__(self) -> int:
        """Retorna tamanho do buffer"""
        return self.size()
    
    def __repr__(self) -> str:
        """Representação string do buffer"""
        return f"CircularBuffer(name='{self.name}', size={self.size()}/{self.max_size})"


class CandleBuffer(CircularBuffer):
    """
    Buffer especializado para candles OHLCV
    """
    
    def __init__(self, max_size: int = 200):
        super().__init__(max_size, name="candles")
        
    def add_candle(self, timestamp: datetime, open: float, high: float, 
                   low: float, close: float, volume: float) -> bool:
        """
        Adiciona um candle ao buffer
        
        Args:
            timestamp: Timestamp do candle
            open: Preço de abertura
            high: Preço máximo
            low: Preço mínimo
            close: Preço de fechamento
            volume: Volume negociado
        """
        candle = {
            "timestamp": timestamp,
            "open": open,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume
        }
        return self.add(candle)
    
    def calculate_returns(self, periods: int = 1) -> np.ndarray:
        """
        Calcula retornos para N períodos
        
        Args:
            periods: Número de períodos
            
        Returns:
            Array com retornos
        """
        with self.lock:
            df = self.get_dataframe()
            if df.empty or len(df) < periods + 1:
                return np.array([])
            
            closes = df['close'].values
            returns = (closes[periods:] - closes[:-periods]) / closes[:-periods]
            return returns
    
    def calculate_volatility(self, periods: int = 20) -> float:
        """
        Calcula volatilidade (desvio padrão dos retornos)
        
        Args:
            periods: Número de períodos
            
        Returns:
            Volatilidade
        """
        returns = self.calculate_returns(1)
        if len(returns) < periods:
            return 0.0
        
        return np.std(returns[-periods:])
    
    def get_ohlc_stats(self) -> Dict:
        """
        Retorna estatísticas OHLC
        
        Returns:
            Dict com estatísticas
        """
        with self.lock:
            df = self.get_dataframe()
            if df.empty:
                return {}
            
            return {
                "last_close": df['close'].iloc[-1],
                "avg_volume": df['volume'].mean(),
                "high_period": df['high'].max(),
                "low_period": df['low'].min(),
                "total_volume": df['volume'].sum()
            }


class BookBuffer(CircularBuffer):
    """
    Buffer especializado para dados de book (bid/ask)
    """
    
    def __init__(self, max_size: int = 100, levels: int = 5):
        super().__init__(max_size, name="book")
        self.levels = levels
        
    def add_snapshot(self, timestamp: datetime, 
                    bid_prices: List[float], bid_volumes: List[float],
                    ask_prices: List[float], ask_volumes: List[float],
                    bid_traders: Optional[List[str]] = None,
                    ask_traders: Optional[List[str]] = None) -> bool:
        """
        Adiciona snapshot do book
        
        Args:
            timestamp: Timestamp do snapshot
            bid_prices: Lista de preços bid
            bid_volumes: Lista de volumes bid
            ask_prices: Lista de preços ask
            ask_volumes: Lista de volumes ask
            bid_traders: IDs dos traders bid (opcional)
            ask_traders: IDs dos traders ask (opcional)
        """
        snapshot = {
            "timestamp": timestamp,
            "bid_prices": bid_prices[:self.levels],
            "bid_volumes": bid_volumes[:self.levels],
            "ask_prices": ask_prices[:self.levels],
            "ask_volumes": ask_volumes[:self.levels]
        }
        
        if bid_traders:
            snapshot["bid_traders"] = bid_traders[:self.levels]
        if ask_traders:
            snapshot["ask_traders"] = ask_traders[:self.levels]
            
        return self.add(snapshot)
    
    def calculate_spread(self) -> float:
        """
        Calcula spread atual (ask - bid)
        
        Returns:
            Spread
        """
        with self.lock:
            if not self.data:
                return 0.0
            
            last = self.data[-1]
            if last["bid_prices"] and last["ask_prices"]:
                return last["ask_prices"][0] - last["bid_prices"][0]
            return 0.0
    
    def calculate_imbalance(self, periods: int = 10) -> float:
        """
        Calcula order flow imbalance
        
        Args:
            periods: Número de períodos para análise
            
        Returns:
            Imbalance ratio (-1 a 1)
        """
        with self.lock:
            snapshots = self.get_last_n(periods)
            if not snapshots:
                return 0.0
            
            total_bid_volume = 0
            total_ask_volume = 0
            
            for snapshot in snapshots:
                total_bid_volume += sum(snapshot.get("bid_volumes", []))
                total_ask_volume += sum(snapshot.get("ask_volumes", []))
            
            total_volume = total_bid_volume + total_ask_volume
            if total_volume == 0:
                return 0.0
            
            return (total_bid_volume - total_ask_volume) / total_volume
    
    def get_book_depth(self) -> Dict:
        """
        Retorna profundidade atual do book
        
        Returns:
            Dict com informações de profundidade
        """
        with self.lock:
            if not self.data:
                return {}
            
            last = self.data[-1]
            return {
                "bid_depth": sum(last.get("bid_volumes", [])),
                "ask_depth": sum(last.get("ask_volumes", [])),
                "total_depth": sum(last.get("bid_volumes", [])) + sum(last.get("ask_volumes", [])),
                "spread": self.calculate_spread(),
                "mid_price": (last["bid_prices"][0] + last["ask_prices"][0]) / 2 if last["bid_prices"] and last["ask_prices"] else 0
            }


class TradeBuffer(CircularBuffer):
    """
    Buffer especializado para trades executados
    """
    
    def __init__(self, max_size: int = 1000):
        super().__init__(max_size, name="trades")
        
    def add_trade(self, timestamp: datetime, price: float, volume: float,
                  side: str, aggressor: str, trader_id: Optional[str] = None) -> bool:
        """
        Adiciona trade ao buffer
        
        Args:
            timestamp: Timestamp do trade
            price: Preço executado
            volume: Volume negociado
            side: Lado ('buy' ou 'sell')
            aggressor: Quem foi o agressor ('buyer' ou 'seller')
            trader_id: ID do trader (opcional)
        """
        trade = {
            "timestamp": timestamp,
            "price": price,
            "volume": volume,
            "side": side,
            "aggressor": aggressor
        }
        
        if trader_id:
            trade["trader_id"] = trader_id
            
        return self.add(trade)
    
    def calculate_vwap(self, periods: int = 100) -> float:
        """
        Calcula VWAP (Volume Weighted Average Price)
        
        Args:
            periods: Número de trades para considerar
            
        Returns:
            VWAP
        """
        with self.lock:
            trades = self.get_last_n(periods)
            if not trades:
                return 0.0
            
            total_value = sum(t["price"] * t["volume"] for t in trades)
            total_volume = sum(t["volume"] for t in trades)
            
            if total_volume == 0:
                return 0.0
            
            return total_value / total_volume
    
    def calculate_trade_intensity(self, time_window_seconds: int = 60) -> float:
        """
        Calcula intensidade de negociação (trades por segundo)
        
        Args:
            time_window_seconds: Janela de tempo em segundos
            
        Returns:
            Trades por segundo
        """
        with self.lock:
            if len(self.data) < 2:
                return 0.0
            
            # Pegar trades na janela de tempo
            current_time = self.data[-1]["timestamp"]
            trades_in_window = [
                t for t in self.data 
                if (current_time - t["timestamp"]).total_seconds() <= time_window_seconds
            ]
            
            if not trades_in_window:
                return 0.0
            
            time_span = (trades_in_window[-1]["timestamp"] - trades_in_window[0]["timestamp"]).total_seconds()
            if time_span == 0:
                return len(trades_in_window)
            
            return len(trades_in_window) / time_span
    
    def get_aggressor_ratio(self) -> Dict:
        """
        Retorna proporção de agressores
        
        Returns:
            Dict com estatísticas de agressores
        """
        with self.lock:
            if not self.data:
                return {}
            
            buyer_aggressor = sum(1 for t in self.data if t["aggressor"] == "buyer")
            seller_aggressor = sum(1 for t in self.data if t["aggressor"] == "seller")
            total = len(self.data)
            
            return {
                "buyer_aggressor_count": buyer_aggressor,
                "seller_aggressor_count": seller_aggressor,
                "buyer_aggressor_ratio": buyer_aggressor / total if total > 0 else 0,
                "seller_aggressor_ratio": seller_aggressor / total if total > 0 else 0
            }