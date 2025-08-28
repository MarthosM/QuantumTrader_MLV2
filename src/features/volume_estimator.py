"""
Volume Estimator - Estimates volume from book dynamics
Since trade callbacks aren't providing volume, we estimate it from:
1. Book imbalance changes
2. Spread tightness  
3. Price movements
4. Order book depth changes
"""

import numpy as np
from collections import deque
from typing import Dict, Optional, Tuple
import time

class VolumeEstimator:
    """Estimates volume from book microstructure dynamics"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        
        # Historical data for estimation
        self.price_history = deque(maxlen=window_size)
        self.spread_history = deque(maxlen=window_size)
        self.imbalance_history = deque(maxlen=window_size)
        self.bid_history = deque(maxlen=window_size)
        self.ask_history = deque(maxlen=window_size)
        
        # Volume estimation components
        self.estimated_volumes = deque(maxlen=window_size)
        self.last_update_time = time.time()
        
        # Calibration parameters (tuned for WDO)
        self.price_impact_factor = 100.0  # Volume per point move
        self.imbalance_factor = 50.0      # Volume per imbalance unit
        self.spread_factor = 200.0        # Volume inversely proportional to spread
        
    def update(self, price: float, bid: float, ask: float, 
               spread: float, imbalance: float) -> float:
        """
        Update estimator with new book data and return estimated volume
        
        Args:
            price: Current mid price
            bid: Best bid price
            ask: Best ask price
            spread: Current spread
            imbalance: Book imbalance ratio
            
        Returns:
            Estimated volume for this update
        """
        current_time = time.time()
        
        # Store current values
        self.price_history.append(price)
        self.spread_history.append(spread)
        self.imbalance_history.append(imbalance)
        self.bid_history.append(bid)
        self.ask_history.append(ask)
        
        # Calculate volume estimate
        estimated_vol = self._estimate_volume()
        self.estimated_volumes.append(estimated_vol)
        
        self.last_update_time = current_time
        return estimated_vol
    
    def _estimate_volume(self) -> float:
        """
        Core volume estimation logic based on microstructure
        """
        if len(self.price_history) < 2:
            return 0.0
        
        volume_components = []
        
        # 1. Price movement component (larger moves = more volume)
        if len(self.price_history) >= 2:
            price_change = abs(self.price_history[-1] - self.price_history[-2])
            # Normalize: typical tick is 0.5, big move is 5+ points
            price_volume = price_change * self.price_impact_factor
            volume_components.append(price_volume)
        
        # 2. Imbalance change component (imbalance shifts = trading)
        if len(self.imbalance_history) >= 2:
            imbalance_change = abs(self.imbalance_history[-1] - self.imbalance_history[-2])
            # Large imbalance changes suggest aggressive trading
            imbalance_volume = imbalance_change * self.imbalance_factor
            volume_components.append(imbalance_volume)
        
        # 3. Spread tightness component (tight spread = active market)
        current_spread = self.spread_history[-1] if self.spread_history else 0.5
        if current_spread > 0:
            # Inverse relationship: tighter spread = more volume
            # Normalize: 0.5 is tight, 2.0+ is wide
            spread_volume = self.spread_factor / max(current_spread, 0.5)
            volume_components.append(spread_volume)
        
        # 4. Bid/Ask pressure component
        if len(self.bid_history) >= 10 and len(self.ask_history) >= 10:
            # Calculate recent bid/ask movement intensity
            bid_volatility = np.std(list(self.bid_history)[-10:])
            ask_volatility = np.std(list(self.ask_history)[-10:])
            pressure_volume = (bid_volatility + ask_volatility) * 100
            volume_components.append(pressure_volume)
        
        # Combine components with weights
        if volume_components:
            # Weighted average with emphasis on price and imbalance
            weights = [0.35, 0.35, 0.20, 0.10][:len(volume_components)]
            estimated_volume = np.average(volume_components, weights=weights)
            
            # Add noise factor for realism (markets are never perfectly predictable)
            noise = np.random.normal(0, estimated_volume * 0.1)
            estimated_volume = max(0, estimated_volume + noise)
            
            # Round to integer (contracts are discrete)
            return int(estimated_volume)
        
        return 0
    
    def get_average_volume(self, periods: int = 20) -> float:
        """Get average estimated volume over recent periods"""
        if not self.estimated_volumes:
            return 0.0
        
        recent_vols = list(self.estimated_volumes)[-periods:]
        return np.mean(recent_vols) if recent_vols else 0.0
    
    def get_volume_profile(self) -> Dict[str, float]:
        """
        Get detailed volume profile statistics
        """
        if not self.estimated_volumes:
            return {
                'current': 0,
                'average': 0,
                'std': 0,
                'trend': 0,
                'intensity': 0
            }
        
        volumes = list(self.estimated_volumes)
        current = volumes[-1] if volumes else 0
        
        # Calculate statistics
        avg_volume = np.mean(volumes) if volumes else 0
        std_volume = np.std(volumes) if len(volumes) > 1 else 0
        
        # Volume trend (increasing/decreasing)
        if len(volumes) >= 10:
            recent = np.mean(volumes[-5:])
            older = np.mean(volumes[-10:-5])
            trend = (recent - older) / max(older, 1)
        else:
            trend = 0
        
        # Trading intensity (normalized)
        intensity = current / max(avg_volume, 1) if avg_volume > 0 else 0
        
        return {
            'current': current,
            'average': avg_volume,
            'std': std_volume,
            'trend': trend,
            'intensity': intensity
        }
    
    def detect_volume_spike(self, threshold: float = 2.0) -> bool:
        """
        Detect if current volume is spiking
        
        Args:
            threshold: Number of standard deviations for spike detection
            
        Returns:
            True if volume spike detected
        """
        if len(self.estimated_volumes) < 20:
            return False
        
        volumes = list(self.estimated_volumes)
        current = volumes[-1]
        mean = np.mean(volumes[:-1])
        std = np.std(volumes[:-1])
        
        if std > 0:
            z_score = (current - mean) / std
            return z_score > threshold
        
        return False
    
    def get_volume_momentum(self) -> float:
        """
        Calculate volume momentum (rate of change)
        """
        if len(self.estimated_volumes) < 10:
            return 0.0
        
        volumes = list(self.estimated_volumes)
        
        # Compare recent vs older average
        recent_avg = np.mean(volumes[-5:])
        older_avg = np.mean(volumes[-10:-5])
        
        if older_avg > 0:
            momentum = (recent_avg - older_avg) / older_avg
            return momentum
        
        return 0.0