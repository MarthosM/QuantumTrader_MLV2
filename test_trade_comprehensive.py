"""
Comprehensive test for trade data capture - testing all methods
"""
from ctypes import *
import time
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from dotenv import load_dotenv
load_dotenv('.env.production')

# Import structures
from src.profit_trade_structures import TConnectorTrade, decode_trade_v2, decode_trade_simple

# Configure DLL
dll_path = os.path.abspath("ProfitDLL64.dll")
print(f"[OK] DLL found: {dll_path}")    
dll = CDLL(dll_path)

# Global data
trades_v1 = []
trades_v2 = []
history_trades = []

print("=" * 60)
print("COMPREHENSIVE TRADE DATA TEST")
print("=" * 60)

# 1. Test DLL methods availability
print("\n1. CHECKING AVAILABLE DLL METHODS:")
methods = [
    'DLLInitializeLogin',
    'DLLInitializeMarket', 
    'SubscribeTicker',
    'SetTradeCallback',
    'SetTradeCallbackV2',
    'SetHistoryTradeCallbackV2',
    'GetHistoryTrades',
    'GetTicker',
    'GetAggressorTrades'
]

available_methods = []
for method in methods:
    if hasattr(dll, method):
        print(f"  [OK] {method} - Available")
        available_methods.append(method)
    else:
        print(f"  [X] {method} - Not found")

# 2. Initialize connection
print("\n2. INITIALIZING CONNECTION:")
key = os.getenv('PROFIT_KEY', '')
if not key:
    print("[ERROR] PROFIT_KEY not found in .env.production")
    sys.exit(1)

# Initialize login
ret = dll.DLLInitializeLogin(0, key.encode('cp1252'), None)
print(f"  DLLInitializeLogin: {ret}")

# Try DLLInitializeMarket if available
if 'DLLInitializeMarket' in available_methods:
    ret = dll.DLLInitializeMarket(0)
    print(f"  DLLInitializeMarket: {ret}")

# 3. Register callbacks
print("\n3. REGISTERING CALLBACKS:")

# SetTradeCallback V1 (simple)
if 'SetTradeCallback' in available_methods:
    @WINFUNCTYPE(None, c_wchar_p, c_double, c_int32, c_int32, c_int32)
    def trade_callback_v1(ticker, price, qty, buyer, seller):
        global trades_v1
        trade = decode_trade_simple(ticker, price, qty, buyer, seller)
        trades_v1.append(trade)
        if len(trades_v1) <= 5:
            print(f"  [V1 Trade] Price: {trade['price']:.2f} | Volume: {trade['quantity']}")
    
    ret = dll.SetTradeCallback(trade_callback_v1)
    print(f"  SetTradeCallback (V1): {ret}")

# SetTradeCallbackV2
if 'SetTradeCallbackV2' in available_methods:
    @WINFUNCTYPE(None, POINTER(c_byte))
    def trade_callback_v2(trade_ptr):
        global trades_v2
        try:
            trade = decode_trade_v2(trade_ptr)
            trades_v2.append(trade)
            if len(trades_v2) <= 5:
                print(f"  [V2 Trade] Price: {trade['price']:.2f} | Volume: {trade['quantity']} | Aggressor: {trade.get('aggressor', '?')}")
        except Exception as e:
            print(f"  [V2 Error] {e}")
    
    ret = dll.SetTradeCallbackV2(trade_callback_v2)
    print(f"  SetTradeCallbackV2: {ret}")

# SetHistoryTradeCallbackV2
if 'SetHistoryTradeCallbackV2' in available_methods:
    @WINFUNCTYPE(None, POINTER(c_byte))
    def history_callback(trade_ptr):
        global history_trades
        try:
            trade = decode_trade_v2(trade_ptr)
            history_trades.append(trade)
            if len(history_trades) <= 5:
                print(f"  [History] Price: {trade['price']:.2f} | Volume: {trade['quantity']}")
        except Exception as e:
            print(f"  [History Error] {e}")
    
    ret = dll.SetHistoryTradeCallbackV2(history_callback)
    print(f"  SetHistoryTradeCallbackV2: {ret}")

# 4. Subscribe to ticker
print("\n4. SUBSCRIBING TO TICKER:")
symbol = b"WDOU25"
ret = dll.SubscribeTicker(0, symbol)
print(f"  SubscribeTicker(WDOU25): {ret}")

# 5. Check current ticker price (verify connection)
if 'GetTicker' in available_methods:
    print("\n5. CHECKING CURRENT TICKER:")
    # Create structure for ticker data (simplified)
    class TickerData(Structure):
        _fields_ = [
            ("Symbol", c_char * 20),
            ("Last", c_double),
            ("Bid", c_double),
            ("Ask", c_double),
            ("Volume", c_int64)
        ]
    
    ticker = TickerData()
    ret = dll.GetTicker(0, symbol, byref(ticker))
    if ret == 0:
        print(f"  Symbol: WDOU25")
        print(f"  Last: {ticker.Last:.2f}")
        print(f"  Bid: {ticker.Bid:.2f}")
        print(f"  Ask: {ticker.Ask:.2f}")
        print(f"  Volume: {ticker.Volume}")
    else:
        print(f"  GetTicker failed: {ret}")

# 6. Request history trades if available
if 'GetHistoryTrades' in available_methods:
    print("\n6. REQUESTING HISTORY TRADES:")
    today = datetime.now().strftime("%Y%m%d")
    ret = dll.GetHistoryTrades(0, symbol, c_wchar_p(today), c_wchar_p(today))
    print(f"  GetHistoryTrades({today}): {ret}")

# 7. Try GetAggressorTrades if available
if 'GetAggressorTrades' in available_methods:
    print("\n7. REQUESTING AGGRESSOR TRADES:")
    ret = dll.GetAggressorTrades(0, symbol, 100)  # Last 100 trades
    print(f"  GetAggressorTrades(100): {ret}")

# 8. Wait and monitor
print("\n8. MONITORING TRADES (30 seconds):")
print("  Waiting for real-time trade data...")

start_time = time.time()
last_report = start_time

while time.time() - start_time < 30:
    current_time = time.time()
    
    # Report every 5 seconds
    if current_time - last_report >= 5:
        elapsed = int(current_time - start_time)
        print(f"\n  [{elapsed}s] Status:")
        print(f"    V1 Trades: {len(trades_v1)}")
        print(f"    V2 Trades: {len(trades_v2)}")
        print(f"    History: {len(history_trades)}")
        
        # Show last trade if any
        if trades_v2:
            last = trades_v2[-1]
            print(f"    Last V2: Price={last['price']:.2f} Vol={last['quantity']}")
        elif trades_v1:
            last = trades_v1[-1]
            print(f"    Last V1: Price={last['price']:.2f} Vol={last['quantity']}")
        
        last_report = current_time
    
    time.sleep(0.1)

# 9. Final analysis
print("\n" + "=" * 60)
print("FINAL RESULTS:")
print("=" * 60)

total_trades = len(trades_v1) + len(trades_v2) + len(history_trades)
print(f"\nTotal trades captured: {total_trades}")
print(f"  - V1 Callback: {len(trades_v1)}")
print(f"  - V2 Callback: {len(trades_v2)}")
print(f"  - History Callback: {len(history_trades)}")

# Analyze volumes
all_trades = trades_v1 + trades_v2 + history_trades
if all_trades:
    volumes = [t['quantity'] for t in all_trades if t.get('quantity')]
    volumes_positive = [v for v in volumes if v > 0]
    
    if volumes_positive:
        print(f"\nVolume Analysis:")
        print(f"  Trades with volume > 0: {len(volumes_positive)}/{len(volumes)}")
        print(f"  Min volume: {min(volumes_positive)}")
        print(f"  Max volume: {max(volumes_positive)}")
        print(f"  Avg volume: {sum(volumes_positive)/len(volumes_positive):.2f}")
        
        # Show sample trades
        print(f"\nSample trades (first 5):")
        for i, trade in enumerate(all_trades[:5]):
            print(f"  #{i+1} Price: {trade.get('price', 0):.2f} | Volume: {trade.get('quantity', 0)}")
    else:
        print("\n[WARNING] All volumes are 0 or invalid")
else:
    print("\n[WARNING] No trades captured!")
    print("\nPossible issues:")
    print("  1. Market might be in auction/pre-market")
    print("  2. Symbol WDOU25 might not be active")
    print("  3. Connection might need additional initialization")
    print("  4. Callbacks might need different registration sequence")

# 10. Cleanup
print("\n10. CLEANING UP:")
dll.UnsubscribeTicker(0, symbol)
print("  Unsubscribed from ticker")

dll.DLLFinalize(0)
print("  DLL finalized")

print("\nTest complete!")