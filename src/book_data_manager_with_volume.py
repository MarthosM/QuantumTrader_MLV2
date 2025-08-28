"""
Enhanced BookDataManager with Volume Estimation
Integrates volume estimator to provide volume data from book dynamics
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

# Add project path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from buffers.circular_buffer import BookBuffer, TradeBuffer
from features.volume_estimator import VolumeEstimator


class BookDataManagerWithVolume:
    """
    Enhanced book manager with integrated volume estimation
    Provides both book data and estimated volume from microstructure
    """
    
    def __init__(self, max_book_snapshots: int = 100, max_trades: int = 1000, levels: int = 5):
        """
        Initialize enhanced book manager with volume estimation
        
        Args:
            max_book_snapshots: Maximum book snapshots to maintain
            max_trades: Maximum trades to maintain
            levels: Number of book levels to process
        """
        self.levels = levels
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Specialized buffers
        self.book_buffer = BookBuffer(max_size=max_book_snapshots, levels=levels)
        self.trade_buffer = TradeBuffer(max_size=max_trades)
        
        # Volume estimator
        self.volume_estimator = VolumeEstimator(window_size=100)
        
        # Current book state with volume
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
            "total_ask_volume": 0,
            "estimated_volume": 0,  # NEW: Estimated trade volume
            "volume_intensity": 0.0,  # NEW: Volume intensity metric
            "volume_trend": 0.0       # NEW: Volume trend indicator
        }
        
        # Statistics
        self.stats = {
            "total_snapshots": 0,
            "total_trades": 0,
            "last_update": None,
            "price_book_callbacks": 0,
            "offer_book_callbacks": 0,
            "trades_callbacks": 0,
            "errors": 0,
            "avg_estimated_volume": 0.0
        }
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Cache
        self._cache = {}
        self._cache_timestamp = None
        
        self.logger.info(f"BookDataManagerWithVolume initialized: {levels} levels, volume estimation enabled")
    
    def on_price_book_callback(self, data: Dict) -> bool:
        """
        Process price book callback with volume estimation
        
        Args:
            data: Price book data from callback
            
        Returns:
            Success status
        """
        try:
            with self.lock:
                # Update statistics
                self.stats["price_book_callbacks"] += 1
                self.stats["last_update"] = datetime.now()
                
                # Extract book data
                timestamp = data.get("timestamp", datetime.now())
                bid_prices = data.get("bid_prices", [])[:self.levels]
                bid_volumes = data.get("bid_volumes", [])[:self.levels]
                ask_prices = data.get("ask_prices", [])[:self.levels]
                ask_volumes = data.get("ask_volumes", [])[:self.levels]
                
                # Calculate key metrics
                if bid_prices and ask_prices:
                    best_bid = bid_prices[0] if bid_prices else 0
                    best_ask = ask_prices[0] if ask_prices else 0
                    mid_price = (best_bid + best_ask) / 2
                    spread = best_ask - best_bid
                    
                    # Calculate imbalance
                    total_bid_vol = sum(bid_volumes) if bid_volumes else 0
                    total_ask_vol = sum(ask_volumes) if ask_volumes else 0
                    imbalance = (total_bid_vol - total_ask_vol) / max(total_bid_vol + total_ask_vol, 1)
                    
                    # ESTIMATE VOLUME from book dynamics
                    estimated_volume = self.volume_estimator.update(
                        price=mid_price,
                        bid=best_bid,
                        ask=best_ask,
                        spread=spread,
                        imbalance=imbalance
                    )
                    
                    # Get volume profile
                    volume_profile = self.volume_estimator.get_volume_profile()
                    
                    # Update current book with volume
                    self.current_book.update({
                        "timestamp": timestamp,
                        "bid_prices": bid_prices,
                        "bid_volumes": bid_volumes,
                        "ask_prices": ask_prices,
                        "ask_volumes": ask_volumes,
                        "mid_price": mid_price,
                        "spread": spread,
                        "total_bid_volume": total_bid_vol,
                        "total_ask_volume": total_ask_vol,
                        "estimated_volume": estimated_volume,
                        "volume_intensity": volume_profile.get('intensity', 0),
                        "volume_trend": volume_profile.get('trend', 0)
                    })
                    
                    # Update average volume
                    self.stats["avg_estimated_volume"] = self.volume_estimator.get_average_volume()
                    
                    # Store in buffer
                    self.book_buffer.add({
                        **self.current_book,
                        "imbalance": imbalance
                    })
                    
                    self.stats["total_snapshots"] += 1
                    
                    # Clear cache
                    self._cache = {}
                    
                    # Log significant volume events
                    if self.volume_estimator.detect_volume_spike():
                        self.logger.info(f"Volume spike detected: {estimated_volume} (avg: {self.stats['avg_estimated_volume']:.0f})")
                    
                    return True
                
                return False
                
        except Exception as e:
            self.logger.error(f"Error processing price book: {e}")
            self.stats["errors"] += 1
            return False
    
    def get_current_state(self) -> Dict:
        """
        Get current book state with volume data
        
        Returns:
            Complete book state including estimated volume
        """
        with self.lock:
            return self.current_book.copy()
    
    def get_volume_data(self) -> Dict:
        """
        Get detailed volume data and statistics
        
        Returns:
            Volume metrics and analysis
        """
        with self.lock:
            return {
                "current_volume": self.current_book.get("estimated_volume", 0),
                "average_volume": self.stats.get("avg_estimated_volume", 0),
                "volume_intensity": self.current_book.get("volume_intensity", 0),
                "volume_trend": self.current_book.get("volume_trend", 0),
                "volume_momentum": self.volume_estimator.get_volume_momentum(),
                "has_volume_spike": self.volume_estimator.detect_volume_spike()
            }
    
    def get_microstructure_features(self) -> Dict:
        """
        Get comprehensive microstructure features including volume
        
        Returns:
            Dictionary of microstructure features
        """
        with self.lock:
            if not self.current_book["bid_prices"] or not self.current_book["ask_prices"]:
                return {}
            
            features = {
                # Price features
                "mid_price": self.current_book["mid_price"],
                "spread": self.current_book["spread"],
                "spread_pct": self.current_book["spread"] / max(self.current_book["mid_price"], 1) * 100,
                
                # Volume features (NEW)
                "estimated_volume": self.current_book["estimated_volume"],
                "volume_intensity": self.current_book["volume_intensity"],
                "volume_trend": self.current_book["volume_trend"],
                "avg_volume": self.stats["avg_estimated_volume"],
                "volume_ratio": self.current_book["estimated_volume"] / max(self.stats["avg_estimated_volume"], 1),
                
                # Book imbalance
                "book_imbalance": (self.current_book["total_bid_volume"] - self.current_book["total_ask_volume"]) / 
                                 max(self.current_book["total_bid_volume"] + self.current_book["total_ask_volume"], 1),
                
                # Depth features
                "bid_depth": self.current_book["total_bid_volume"],
                "ask_depth": self.current_book["total_ask_volume"],
                "depth_imbalance": (self.current_book["total_bid_volume"] - self.current_book["total_ask_volume"]) /
                                  max(self.current_book["total_bid_volume"] + self.current_book["total_ask_volume"], 1)
            }
            
            # Add level-specific features
            for i in range(min(3, self.levels)):
                if i < len(self.current_book["bid_prices"]):
                    features[f"bid_price_{i}"] = self.current_book["bid_prices"][i]
                    features[f"bid_vol_{i}"] = self.current_book["bid_volumes"][i]
                if i < len(self.current_book["ask_prices"]):
                    features[f"ask_price_{i}"] = self.current_book["ask_prices"][i]
                    features[f"ask_vol_{i}"] = self.current_book["ask_volumes"][i]
            
            return features
    
    def get_trading_signals(self) -> Dict:
        """
        Generate trading signals based on book and volume
        
        Returns:
            Trading signal indicators
        """
        with self.lock:
            signals = {
                "timestamp": datetime.now(),
                "volume_signal": 0,
                "book_signal": 0,
                "combined_signal": 0
            }
            
            # Volume-based signals
            volume_data = self.get_volume_data()
            if volume_data["has_volume_spike"]:
                # Volume spike suggests potential move
                if volume_data["volume_trend"] > 0:
                    signals["volume_signal"] = 1  # Bullish volume
                else:
                    signals["volume_signal"] = -1  # Bearish volume
            
            # Book-based signals
            if self.current_book["bid_prices"] and self.current_book["ask_prices"]:
                book_imbalance = (self.current_book["total_bid_volume"] - self.current_book["total_ask_volume"]) / \
                                max(self.current_book["total_bid_volume"] + self.current_book["total_ask_volume"], 1)
                
                if book_imbalance > 0.2:
                    signals["book_signal"] = 1  # Bullish book
                elif book_imbalance < -0.2:
                    signals["book_signal"] = -1  # Bearish book
            
            # Combined signal (weighted average)
            if signals["volume_signal"] != 0 and signals["book_signal"] != 0:
                # Both signals agree
                if signals["volume_signal"] == signals["book_signal"]:
                    signals["combined_signal"] = signals["volume_signal"] * 1.5  # Strong signal
                else:
                    # Conflicting signals
                    signals["combined_signal"] = (signals["volume_signal"] * 0.4 + signals["book_signal"] * 0.6)
            else:
                # Single signal
                signals["combined_signal"] = signals["volume_signal"] * 0.5 + signals["book_signal"] * 0.5
            
            return signals
    
    def reset(self):
        """Reset all buffers and state"""
        with self.lock:
            self.book_buffer.clear()
            self.trade_buffer.clear()
            self.volume_estimator = VolumeEstimator(window_size=100)
            self._cache = {}
            self.logger.info("BookDataManagerWithVolume reset")