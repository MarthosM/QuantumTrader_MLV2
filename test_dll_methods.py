"""
Test script to check available DLL methods for Times & Trades
"""

import ctypes
import os

def test_dll_methods():
    """Test which methods are available in ProfitDLL"""
    
    # Try to load DLL
    dll_path = os.path.abspath("ProfitDLL64.dll")
    if not os.path.exists(dll_path):
        dll_path = os.path.abspath("dll/ProfitDLL64.dll")
    
    if not os.path.exists(dll_path):
        print(f"[ERROR] DLL not found at {dll_path}")
        # Try current directory
        dll_path = os.path.join(os.getcwd(), "ProfitDLL64.dll")
        if not os.path.exists(dll_path):
            print(f"[ERROR] DLL not found in current directory either")
            return
        
    try:
        dll = ctypes.CDLL(dll_path)
        print(f"[OK] DLL loaded from {dll_path}")
    except Exception as e:
        print(f"[ERROR] Failed to load DLL: {e}")
        return
    
    # List of methods to test
    methods_to_test = [
        # Trade callbacks
        "SetTradeCallbackV2",
        "SetNewTradeCallback", 
        "SetHistoryTradeCallbackV2",
        
        # Subscription methods
        "SubscribeAggregatedBook",
        "SubscribeTimesAndTrades",
        "SubscribeTrades",
        "SubscribeMarketData",
        "SubscribeAggregatedTrade",
        
        # Book subscriptions (should exist)
        "SubscribeTicker",
        "SubscribeOfferBook", 
        "SubscribePriceBook",
        
        # Get methods
        "GetAggregatedBook",
        "GetTimesAndTrades",
        "GetLastTrade",
        "GetTradeVolume"
    ]
    
    print("\n" + "="*60)
    print("CHECKING DLL METHODS")
    print("="*60)
    
    available = []
    not_available = []
    
    for method in methods_to_test:
        if hasattr(dll, method):
            available.append(method)
            print(f"[OK] {method} - AVAILABLE")
        else:
            not_available.append(method)
            print(f"[X] {method} - NOT FOUND")
    
    print("\n" + "="*60)
    print(f"SUMMARY: {len(available)} available, {len(not_available)} not found")
    print("="*60)
    
    if available:
        print("\nAvailable methods for volume data:")
        for m in available:
            if "trade" in m.lower() or "aggregat" in m.lower():
                print(f"  - {m}")
    
    # Try to get all exported functions
    print("\n" + "="*60)
    print("SEARCHING FOR ALL TRADE/VOLUME RELATED FUNCTIONS")
    print("="*60)
    
    # Use dumpbin or similar to get exports
    import subprocess
    try:
        result = subprocess.run(
            ["dumpbin", "/exports", dll_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                lower_line = line.lower()
                if 'trade' in lower_line or 'volume' in lower_line or 'aggregat' in lower_line:
                    print(line.strip())
    except:
        # Dumpbin not available, try alternative
        print("Note: Could not enumerate all DLL exports (dumpbin not available)")
        print("Trying alternative method...")
        
        # List common variants
        variants = [
            "GetTrades", "GetTradeData", "GetTradeHistory",
            "SetTradeCallback", "SetTradesCallback",
            "SubscribeTradeData", "SubscribeTradeFlow",
            "GetVolume", "GetTradeVolume", "GetAccumulatedVolume",
            "GetMarketVolume", "GetSessionVolume"
        ]
        
        for variant in variants:
            if hasattr(dll, variant):
                print(f"  Found: {variant}")

if __name__ == "__main__":
    test_dll_methods()