"""
Debug script to analyze TConnectorTrade structure raw bytes
"""
from ctypes import *
import time
import os
import sys
import struct

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from dotenv import load_dotenv
load_dotenv('.env.production')

# Configure DLL
dll_path = os.path.abspath("ProfitDLL64.dll")
if not os.path.exists(dll_path):
    print(f"[ERRO] DLL não encontrada em: {dll_path}")
    sys.exit(1)
    
print(f"[OK] DLL encontrada: {dll_path}")    
dll = CDLL(dll_path)

# Global to store raw bytes
raw_captures = []

# Test SetTradeCallbackV2 with raw byte analysis
if hasattr(dll, 'SetTradeCallbackV2'):
    print("[OK] SetTradeCallbackV2 encontrado")
    
    @WINFUNCTYPE(None, POINTER(c_byte))
    def trade_callback_debug(trade_ptr):
        """Callback to capture raw bytes"""
        global raw_captures
        
        try:
            # Capture first 100 bytes
            raw_bytes = bytes([trade_ptr[i] for i in range(min(100, 200))])
            raw_captures.append(raw_bytes)
            
            # Print hex dump
            print(f"\n[RAW BYTES {len(raw_captures)}] Total: {len(raw_bytes)} bytes")
            
            # Format as hex dump with offset
            for offset in range(0, min(len(raw_bytes), 64), 16):
                hex_part = ' '.join(f'{b:02x}' for b in raw_bytes[offset:offset+16])
                print(f"  {offset:04x}: {hex_part}")
            
            # Try to identify patterns
            print("\n[ANALYSIS]")
            
            # Check for version byte (should be 1 or 2)
            print(f"  Byte 0 (Version?): 0x{raw_bytes[0]:02x} = {raw_bytes[0]}")
            
            # Look for date/time structure (SYSTEMTIME is 16 bytes)
            # Year should be 2025 (0x07E9 in little endian)
            for i in range(len(raw_bytes)-1):
                if raw_bytes[i] == 0xE9 and raw_bytes[i+1] == 0x07:
                    print(f"  Found year 2025 at offset {i} (0x07E9)")
                    
            # Look for price (double) - should be around 5400
            # 5400.0 in double = 0x40B5180000000000 (big endian) or reversed for little
            for i in range(len(raw_bytes)-7):
                double_bytes = raw_bytes[i:i+8]
                try:
                    # Try little endian double
                    value = struct.unpack('<d', double_bytes)[0]
                    if 5000 < value < 6000:
                        print(f"  Possible price at offset {i}: {value:.2f}")
                except:
                    pass
                    
            # Look for reasonable quantities (int32 or int64)
            for i in range(len(raw_bytes)-3):
                try:
                    # Try int32
                    val32 = struct.unpack('<i', raw_bytes[i:i+4])[0]
                    if 1 <= val32 <= 10000:  # Reasonable volume range
                        print(f"  Possible volume (int32) at offset {i}: {val32}")
                        
                    # Try int64
                    if i <= len(raw_bytes)-8:
                        val64 = struct.unpack('<q', raw_bytes[i:i+8])[0]
                        if 1 <= val64 <= 10000:
                            print(f"  Possible volume (int64) at offset {i}: {val64}")
                except:
                    pass
                    
            # Stop after 5 captures for analysis
            if len(raw_captures) >= 5:
                print("\n[CAPTURED 5 SAMPLES - Analyzing patterns...]")
                
                # Compare first bytes across samples
                print("\nFirst 20 bytes of each sample:")
                for idx, sample in enumerate(raw_captures):
                    hex_str = ' '.join(f'{b:02x}' for b in sample[:20])
                    print(f"  Sample {idx+1}: {hex_str}")
                    
                return
                
        except Exception as e:
            print(f"[ERRO] Callback: {e}")
    
    # Register callback
    ret = dll.SetTradeCallbackV2(trade_callback_debug)
    print(f"SetTradeCallbackV2 registrado: {ret}")
    
    # Initialize and connect
    print("\nInicializando conexão...")
    key = os.getenv('PROFIT_KEY', '')
    if key:
        dll.DLLInitializeLogin(0, key.encode('cp1252'), None)
        
        symbol = b"WDOU25"
        ret = dll.SubscribeTicker(0, symbol)
        print(f"Subscribe WDOU25: {ret}")
        
        # Wait for trades
        print("\nAguardando trades para análise... (30 segundos)")
        for i in range(30):
            time.sleep(1)
            if len(raw_captures) >= 5:
                print(f"\nColetadas {len(raw_captures)} amostras. Análise completa!")
                break
            elif i % 5 == 0:
                print(f"  {i}s - Amostras coletadas: {len(raw_captures)}")
        
        # Final analysis
        if raw_captures:
            print(f"\n[RESULTADO] Coletadas {len(raw_captures)} amostras de trades")
            
            # Try different structure interpretations
            print("\n[TESTING STRUCTURE LAYOUTS]")
            
            for sample in raw_captures[:1]:  # Test on first sample
                print("\nOption 1: Version(1) + SYSTEMTIME(16) + TradeNumber(4) + Price(8) + Quantity(8)")
                if len(sample) >= 37:
                    version = sample[0]
                    # Skip SYSTEMTIME (16 bytes)
                    trade_num = struct.unpack('<I', sample[17:21])[0]
                    price = struct.unpack('<d', sample[21:29])[0]
                    quantity = struct.unpack('<q', sample[29:37])[0]
                    print(f"  Version: {version}, TradeNum: {trade_num}, Price: {price:.2f}, Volume: {quantity}")
                    
                print("\nOption 2: Version(1) + TradeNumber(4) + Price(8) + Quantity(8)")
                if len(sample) >= 21:
                    version = sample[0]
                    trade_num = struct.unpack('<I', sample[1:5])[0]
                    price = struct.unpack('<d', sample[5:13])[0]
                    quantity = struct.unpack('<q', sample[13:21])[0]
                    print(f"  Version: {version}, TradeNum: {trade_num}, Price: {price:.2f}, Volume: {quantity}")
                    
                print("\nOption 3: No version, starts with SYSTEMTIME")
                if len(sample) >= 36:
                    # Skip SYSTEMTIME (16 bytes)
                    trade_num = struct.unpack('<I', sample[16:20])[0]
                    price = struct.unpack('<d', sample[20:28])[0]
                    quantity = struct.unpack('<q', sample[28:36])[0]
                    print(f"  TradeNum: {trade_num}, Price: {price:.2f}, Volume: {quantity}")
                    
        else:
            print("\n[AVISO] Nenhum trade capturado")
        
        # Disconnect
        dll.UnsubscribeTicker(0, symbol)
        dll.DLLFinalize(0)
        
else:
    print("[ERRO] SetTradeCallbackV2 não encontrado")

print("\nAnálise concluída!")