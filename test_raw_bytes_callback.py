"""
Test to capture raw bytes from trade callbacks
This will help us understand the actual structure being sent
"""
from ctypes import *
import time
import os
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('.env.production')

# Configure DLL
dll_path = os.path.abspath("ProfitDLL64.dll")
print(f"[OK] DLL found: {dll_path}")    
dll = CDLL(dll_path)

# Global counter
trade_count = 0
raw_captures = []

print("=" * 60)
print("RAW BYTES CAPTURE TEST")
print("=" * 60)

# Test 1: SetTradeCallbackV2 with raw pointer
if hasattr(dll, 'SetTradeCallbackV2'):
    print("\n[TEST 1] SetTradeCallbackV2 - Raw bytes capture")
    
    @WINFUNCTYPE(None, c_void_p)
    def raw_trade_callback(raw_ptr):
        """Capture raw pointer value"""
        global trade_count, raw_captures
        trade_count += 1
        
        if raw_ptr:
            # Try to read first few bytes
            try:
                # Cast to byte pointer
                byte_ptr = cast(raw_ptr, POINTER(c_ubyte))
                
                # Read first 200 bytes
                raw_bytes = []
                for i in range(200):
                    try:
                        raw_bytes.append(byte_ptr[i])
                    except:
                        break
                
                if raw_bytes:
                    raw_captures.append(bytes(raw_bytes))
                    print(f"\n[TRADE {trade_count}] Captured {len(raw_bytes)} bytes")
                    
                    # Print first 32 bytes as hex
                    hex_str = ' '.join(f'{b:02x}' for b in raw_bytes[:32])
                    print(f"  First 32 bytes: {hex_str}")
                    
                    # Try to find price pattern (double around 5400)
                    import struct
                    for offset in range(0, min(len(raw_bytes)-7, 100), 4):
                        try:
                            # Try as double
                            val = struct.unpack_from('<d', bytes(raw_bytes), offset)[0]
                            if 5000 < val < 6000:
                                print(f"  Possible price at offset {offset}: {val:.2f}")
                        except:
                            pass
            except Exception as e:
                print(f"  Error reading bytes: {e}")
        else:
            print(f"[TRADE {trade_count}] NULL pointer received")
    
    # Register callback
    ret = dll.SetTradeCallbackV2(raw_trade_callback)
    print(f"  SetTradeCallbackV2 result: {ret}")
    
    # Alternative: Try with c_byte pointer
    @WINFUNCTYPE(None, POINTER(c_byte))
    def byte_trade_callback(byte_ptr):
        """Alternative with c_byte pointer"""
        global trade_count
        trade_count += 1
        
        if byte_ptr:
            print(f"[ALT TRADE {trade_count}] Byte pointer received")
            try:
                # Read some bytes
                vals = [byte_ptr[i] for i in range(32)]
                hex_str = ' '.join(f'{b&0xFF:02x}' for b in vals)
                print(f"  Bytes: {hex_str}")
            except Exception as e:
                print(f"  Error: {e}")

# Initialize and connect
print("\n[INIT] Initializing connection...")
key = os.getenv('PROFIT_KEY', '')
if not key:
    print("[ERROR] PROFIT_KEY not found")
    sys.exit(1)

# Try different initialization sequences
print("\n[INIT] Testing different initialization methods:")

# Method 1: Just DLLInitializeLogin
ret1 = dll.DLLInitializeLogin(0, key.encode('cp1252'), None)
print(f"  DLLInitializeLogin: {ret1}")

# Method 2: Try with server address if available
if hasattr(dll, 'SetServerAddress'):
    server = b"producao.nelogica.com.br:8184"
    ret2 = dll.SetServerAddress(server)
    print(f"  SetServerAddress: {ret2}")

# Method 3: Check for InitializeMarket
if hasattr(dll, 'DLLInitializeMarket'):
    ret3 = dll.DLLInitializeMarket(0)
    print(f"  DLLInitializeMarket: {ret3}")

# Subscribe to ticker
print("\n[SUBSCRIBE] Subscribing to tickers...")
symbols = [b"WDOU25", b"WDOQ25", b"WDOZ24"]  # Try multiple symbols
for symbol in symbols:
    ret = dll.SubscribeTicker(0, symbol)
    print(f"  Subscribe {symbol.decode()}: {ret}")
    time.sleep(0.5)

# Also try SubscribeBBO if available (Best Bid/Offer)
if hasattr(dll, 'SubscribeBBO'):
    for symbol in symbols:
        ret = dll.SubscribeBBO(0, symbol)
        print(f"  SubscribeBBO {symbol.decode()}: {ret}")

# Wait for trades
print("\n[MONITOR] Waiting for trades (60 seconds)...")
print("  Note: If no trades, market might be in auction or low activity")

start_time = time.time()
last_report = start_time

while time.time() - start_time < 60:
    current = time.time()
    
    if current - last_report >= 10:
        elapsed = int(current - start_time)
        print(f"\n  [{elapsed}s] Trade count: {trade_count}")
        
        if raw_captures:
            # Analyze captured data
            print(f"  Captured {len(raw_captures)} trade(s)")
            
            # Compare first bytes across captures
            if len(raw_captures) > 1:
                print("  Comparing first bytes:")
                for i, capture in enumerate(raw_captures[-3:]):  # Last 3
                    hex_str = ' '.join(f'{b:02x}' for b in capture[:16])
                    print(f"    Trade {i}: {hex_str}")
        
        last_report = current
    
    time.sleep(0.1)

# Final analysis
print("\n" + "=" * 60)
print("FINAL ANALYSIS")
print("=" * 60)

print(f"\nTotal trades received: {trade_count}")

if raw_captures:
    print(f"Successfully captured: {len(raw_captures)}")
    
    # Analyze structure
    print("\n[STRUCTURE ANALYSIS]")
    for i, capture in enumerate(raw_captures[:3]):  # First 3
        print(f"\nTrade {i+1} - {len(capture)} bytes:")
        
        # Show in 16-byte rows
        for offset in range(0, min(len(capture), 64), 16):
            hex_part = ' '.join(f'{b:02x}' for b in capture[offset:offset+16])
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in capture[offset:offset+16])
            print(f"  {offset:04x}: {hex_part:<48} | {ascii_part}")
else:
    print("\n[NO DATA] No trades captured")
    print("\nPossible reasons:")
    print("  1. Market in auction (no trades)")
    print("  2. Wrong symbol subscribed")
    print("  3. Callback registration failed")
    print("  4. Need different API initialization")
    
    # Try to check connection status
    if hasattr(dll, 'IsConnected'):
        connected = dll.IsConnected(0)
        print(f"\n  IsConnected: {connected}")
    
    if hasattr(dll, 'GetLastError'):
        error = dll.GetLastError()
        print(f"  GetLastError: {error}")

# Cleanup
print("\n[CLEANUP]")
for symbol in symbols:
    dll.UnsubscribeTicker(0, symbol)
dll.DLLFinalize(0)
print("Test complete!")