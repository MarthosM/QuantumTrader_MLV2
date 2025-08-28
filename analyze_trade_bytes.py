"""
Análise dos bytes recebidos no trade callback
"""
from ctypes import *
import time
import os
import sys
import struct
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('.env.production')

# Configure DLL
dll_path = os.path.abspath("ProfitDLL64.dll")
print(f"[OK] DLL encontrada: {dll_path}")    
dll = CDLL(dll_path)

# Global
trades_captured = 0
byte_patterns = {}

print("=" * 60)
print("ANÁLISE DETALHADA DE BYTES DOS TRADES")
print("=" * 60)

# SetTradeCallbackV2
if hasattr(dll, 'SetTradeCallbackV2'):
    print("\n[OK] SetTradeCallbackV2 disponível")
    
    @WINFUNCTYPE(None, POINTER(c_byte))
    def trade_callback_v2(trade_ptr):
        global trades_captured, byte_patterns
        trades_captured += 1
        
        if trade_ptr and trades_captured <= 5:  # Primeiros 5 trades
            try:
                # Capturar 200 bytes
                raw_bytes = cast(trade_ptr, POINTER(c_byte * 200))
                raw_data = bytes(raw_bytes.contents[:200])
                
                print(f"\n{'='*60}")
                print(f"TRADE #{trades_captured} - {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
                print(f"{'='*60}")
                
                # Hex dump completo
                print("\nHEX DUMP COMPLETO (200 bytes):")
                for offset in range(0, min(len(raw_data), 200), 16):
                    hex_str = ' '.join(f'{b:02x}' for b in raw_data[offset:offset+16])
                    print(f"  {offset:04x}: {hex_str}")
                
                print("\nANÁLISE DE VALORES:")
                
                # Procurar por todos os valores possíveis
                found_prices = []
                found_volumes = []
                
                # Análise byte a byte para volumes
                for offset in range(len(raw_data)):
                    # int8
                    if offset < len(raw_data):
                        val = raw_data[offset]
                        if 1 <= val <= 100:
                            print(f"  [BYTE] Offset {offset:3d}: {val} (possível volume int8)")
                    
                    # int16
                    if offset <= len(raw_data)-2:
                        try:
                            val = struct.unpack_from('<h', raw_data, offset)[0]
                            if 1 <= val <= 500:
                                print(f"  [INT16] Offset {offset:3d}: {val} (possível volume)")
                        except:
                            pass
                    
                    # int32
                    if offset <= len(raw_data)-4:
                        try:
                            val = struct.unpack_from('<i', raw_data, offset)[0]
                            if 1 <= val <= 500:
                                found_volumes.append((offset, val, 'int32'))
                                print(f"  [INT32] Offset {offset:3d}: {val} contratos")
                        except:
                            pass
                    
                    # float32
                    if offset <= len(raw_data)-4:
                        try:
                            val = struct.unpack_from('<f', raw_data, offset)[0]
                            if 5000 < val < 6000:
                                print(f"  [FLOAT32] Offset {offset:3d}: {val:.2f} (possível preço)")
                        except:
                            pass
                    
                    # double
                    if offset <= len(raw_data)-8:
                        try:
                            val = struct.unpack_from('<d', raw_data, offset)[0]
                            if 5000 < val < 6000:
                                found_prices.append((offset, val))
                                print(f"  [DOUBLE] Offset {offset:3d}: {val:.2f} (preço)")
                        except:
                            pass
                
                # Salvar padrões
                byte_patterns[trades_captured] = {
                    'prices': found_prices,
                    'volumes': found_volumes,
                    'raw_sample': raw_data[:64].hex()
                }
                
                # Verificar timestamp (ano 2025 = 0xE9 0x07)
                for i in range(len(raw_data)-1):
                    if raw_data[i] == 0xE9 and raw_data[i+1] == 0x07:
                        print(f"\n  [TIMESTAMP] Ano 2025 em offset {i}")
                        # Tentar ler SYSTEMTIME completo
                        if i >= 0 and i <= len(raw_data)-16:
                            try:
                                year = struct.unpack_from('<H', raw_data, i)[0]
                                month = struct.unpack_from('<H', raw_data, i+2)[0]
                                day = struct.unpack_from('<H', raw_data, i+6)[0]
                                print(f"    Data: {day:02d}/{month:02d}/{year}")
                            except:
                                pass
                                
            except Exception as e:
                print(f"[ERRO] {e}")
    
    # Registrar callback
    ret = dll.SetTradeCallbackV2(trade_callback_v2)
    print(f"Callback registrado: {ret}")

# Inicializar
print("\n[INIT] Conectando...")
key = os.getenv('PROFIT_KEY', '')
if key:
    ret = dll.DLLInitializeLogin(0, key.encode('cp1252'), None)
    print(f"  DLLInitializeLogin: {ret}")
    
    # Subscribe
    symbol = b"WDOU25"
    ret = dll.SubscribeTicker(0, symbol)
    print(f"  SubscribeTicker: {ret}")
    
    print(f"\n[AGUARDANDO] Capturando primeiros 5 trades...")
    print(f"Horário: {datetime.now().strftime('%H:%M:%S')}")
    
    timeout = 60
    start = time.time()
    
    while time.time() - start < timeout and trades_captured < 5:
        time.sleep(0.5)
    
    # Análise final
    if byte_patterns:
        print(f"\n{'='*60}")
        print("PADRÕES ENCONTRADOS")
        print(f"{'='*60}")
        
        all_price_offsets = []
        all_volume_offsets = []
        
        for trade_num, data in byte_patterns.items():
            for offset, price in data['prices']:
                all_price_offsets.append(offset)
            for offset, vol, tipo in data['volumes']:
                all_volume_offsets.append((offset, tipo))
        
        from collections import Counter
        
        if all_price_offsets:
            price_counter = Counter(all_price_offsets)
            print(f"\n[PREÇO] Offsets mais frequentes:")
            for offset, count in price_counter.most_common(3):
                print(f"  Offset {offset}: apareceu {count}x")
        
        if all_volume_offsets:
            volume_counter = Counter(all_volume_offsets)
            print(f"\n[VOLUME] Offsets mais frequentes:")
            for (offset, tipo), count in volume_counter.most_common(5):
                print(f"  Offset {offset} ({tipo}): apareceu {count}x")
        
        # Recomendação de estrutura
        if price_counter and volume_counter:
            price_offset = price_counter.most_common(1)[0][0]
            volume_offset, volume_type = volume_counter.most_common(1)[0][0]
            
            print(f"\n[ESTRUTURA RECOMENDADA]")
            print(f"  Preço em offset {price_offset} (double)")
            print(f"  Volume em offset {volume_offset} ({volume_type})")
    else:
        print("\n[AVISO] Nenhum trade capturado")
        print("Possíveis causas: Mercado em leilão ou baixa liquidez")
    
    # Cleanup
    dll.UnsubscribeTicker(0, symbol)
    dll.DLLFinalize(0)

print(f"\n[FIM] Análise concluída - {trades_captured} trades analisados")