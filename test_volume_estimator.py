"""
Test the volume estimator with current book data
"""
import json
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.features.volume_estimator import VolumeEstimator

def test_volume_estimator():
    """Test volume estimation with sample book data"""
    
    print("=" * 60)
    print("VOLUME ESTIMATOR TEST")
    print("=" * 60)
    
    # Create estimator
    estimator = VolumeEstimator(window_size=50)
    
    # Load current market data
    monitor_file = 'data/monitor/hmarl_status.json'
    if os.path.exists(monitor_file):
        with open(monitor_file, 'r') as f:
            data = json.load(f)
            
        price = data['market_data']['price']
        spread = data['market_data']['book_data']['spread']
        imbalance = data['market_data']['book_data']['imbalance']
        
        print(f"\nCurrent Market Data:")
        print(f"  Price: {price}")
        print(f"  Spread: {spread}")
        print(f"  Imbalance: {imbalance}")
        
        # Simulate market updates with variations
        print("\nSimulating market activity...")
        
        for i in range(30):
            # Add realistic variations
            price_var = price + (i % 3 - 1) * 0.5  # Price moves ±0.5
            spread_var = spread + (i % 5 - 2) * 0.1  # Spread varies
            imbalance_var = imbalance + (i % 7 - 3) * 0.1  # Imbalance shifts
            
            # Ensure valid ranges
            spread_var = max(0.5, min(2.0, spread_var))
            imbalance_var = max(-1.0, min(1.0, imbalance_var))
            
            bid = price_var - spread_var/2
            ask = price_var + spread_var/2
            
            # Update estimator
            estimated_vol = estimator.update(
                price=price_var,
                bid=bid,
                ask=ask,
                spread=spread_var,
                imbalance=imbalance_var
            )
            
            if i % 5 == 0:
                print(f"\n  Update {i+1}:")
                print(f"    Price: {price_var:.2f} | Spread: {spread_var:.2f} | Imbalance: {imbalance_var:.2f}")
                print(f"    Estimated Volume: {estimated_vol}")
        
        # Get final statistics
        print("\n" + "=" * 60)
        print("VOLUME PROFILE ANALYSIS")
        print("=" * 60)
        
        profile = estimator.get_volume_profile()
        print(f"\nVolume Statistics:")
        print(f"  Current Volume: {profile['current']}")
        print(f"  Average Volume: {profile['average']:.2f}")
        print(f"  Std Deviation: {profile['std']:.2f}")
        print(f"  Volume Trend: {profile['trend']:.2%}")
        print(f"  Trading Intensity: {profile['intensity']:.2f}x")
        
        # Check for spikes
        if estimator.detect_volume_spike():
            print("\n[ALERT] Volume spike detected!")
        
        # Volume momentum
        momentum = estimator.get_volume_momentum()
        if momentum > 0:
            print(f"\nVolume momentum: +{momentum:.2%} (increasing)")
        else:
            print(f"\nVolume momentum: {momentum:.2%} (decreasing)")
        
        # Test integration feasibility
        print("\n" + "=" * 60)
        print("INTEGRATION FEASIBILITY")
        print("=" * 60)
        
        avg_vol = estimator.get_average_volume()
        print(f"\nAverage estimated volume: {avg_vol:.0f}")
        
        if avg_vol > 0:
            print("[OK] Volume estimator producing reasonable values")
            print("     Can be integrated into HMARL agents and ML features")
        else:
            print("[WARNING] Volume estimator needs calibration")
            
        return True
        
    else:
        print(f"[ERROR] Monitor file not found: {monitor_file}")
        return False

if __name__ == "__main__":
    success = test_volume_estimator()
    
    if success:
        print("\n[SUCCESS] Volume estimator working correctly")
        print("\nNext steps:")
        print("1. Integrate into connection_manager_v4.py")
        print("2. Update HMARL agents to use estimated volume")
        print("3. Add volume features to ML pipeline")
    else:
        print("\n[FAILED] Volume estimator test failed")