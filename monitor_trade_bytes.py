"""
Monitor de bytes do trade callback - Executa em paralelo ao sistema
"""
from ctypes import *
import time
import os
import sys
import struct
from datetime import datetime
import json

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('.env.production')

# Configure DLL
dll_path = os.path.abspath("ProfitDLL64.dll")
print(f"[OK] DLL encontrada: {dll_path}")    
dll = CDLL(dll_path)

# Verificar se já existe sistema rodando
monitor_file = "data/monitor/ml_status.json"
if os.path.exists(monitor_file):
    with open(monitor_file, 'r') as f:
        data = json.load(f)
        last_update = data.get('timestamp', '')
        print(f"[INFO] Sistema já rodando - última atualização: {last_update}")
        print(f"[INFO] Este monitor irá capturar trades em paralelo")
else:
    print(f"[AVISO] Sistema principal pode não estar rodando")

# Global
trades_captured = 0
analysis_results = {}

print("=" * 60)
print("MONITOR DE ESTRUTURA DE TRADES - ANÁLISE EM TEMPO REAL")
print("=" * 60)

# SetTradeCallbackV2
if hasattr(dll, 'SetTradeCallbackV2'):
    print("[OK] SetTradeCallbackV2 disponível")
    
    @WINFUNCTYPE(None, POINTER(c_byte))
    def trade_callback_v2_monitor(trade_ptr):
        global trades_captured, analysis_results
        trades_captured += 1
        
        if trade_ptr and trades_captured <= 10:  # Analisar primeiros 10
            try:
                # Capturar bytes
                raw_bytes = cast(trade_ptr, POINTER(c_byte * 200))
                raw_data = bytes(raw_bytes.contents[:150])
                
                print(f"\n{'='*60}")
                print(f"TRADE #{trades_captured} - {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
                print(f"{'='*60}")
                
                # Análise detalhada
                volume_candidates = []
                price_candidates = []
                
                # Procurar preço
                for offset in range(0, min(len(raw_data)-7, 120), 4):
                    try:
                        val_double = struct.unpack_from('<d', raw_data, offset)[0]
                        if 5400 <= val_double <= 5500:  # Range atual do WDO
                            price_candidates.append((offset, val_double))
                            print(f"[PREÇO] Offset {offset:3d}: {val_double:8.2f}")
                    except:
                        pass
                
                # Procurar volume
                for offset in range(0, min(len(raw_data)-3, 120), 1):  # Byte a byte
                    try:
                        # int32
                        if offset <= len(raw_data)-4:
                            val32 = struct.unpack_from('<i', raw_data, offset)[0]
                            if 1 <= val32 <= 200:  # Volume típico
                                volume_candidates.append((offset, val32, 'int32'))
                                print(f"[VOL32] Offset {offset:3d}: {val32:4d} contratos")
                        
                        # int64
                        if offset <= len(raw_data)-8:
                            val64 = struct.unpack_from('<q', raw_data, offset)[0]
                            if 1 <= val64 <= 200:
                                volume_candidates.append((offset, val64, 'int64'))
                                print(f"[VOL64] Offset {offset:3d}: {val64:4d} contratos")
                    except:
                        pass
                
                # Salvar análise
                if trades_captured not in analysis_results:
                    analysis_results[trades_captured] = {
                        'price_offsets': price_candidates,
                        'volume_offsets': volume_candidates
                    }
                
                # Hex dump parcial
                print(f"\nHEX DUMP (primeiros 64 bytes):")
                for i in range(0, min(64, len(raw_data)), 16):
                    hex_str = ' '.join(f'{b:02x}' for b in raw_data[i:i+16])
                    print(f"  {i:04x}: {hex_str}")
                
            except Exception as e:
                print(f"[ERRO] {e}")
    
    # Registrar callback
    ret = dll.SetTradeCallbackV2(trade_callback_v2_monitor)
    print(f"Monitor callback registrado: {ret}")
else:
    print("[ERRO] SetTradeCallbackV2 não encontrado")
    sys.exit(1)

# Inicializar
print("\n[INIT] Conectando monitor...")
key = os.getenv('PROFIT_KEY', '')
if key:
    ret = dll.DLLInitializeLogin(0, key.encode('cp1252'), None)
    print(f"  DLLInitializeLogin: {ret}")
    
    # Subscribe
    symbol = b"WDOU25"
    ret = dll.SubscribeTicker(0, symbol)
    print(f"  SubscribeTicker: {ret}")
    
    print(f"\n[MONITOR] Capturando trades...")
    print(f"Pressione Ctrl+C para parar\n")
    
    try:
        while trades_captured < 10:
            time.sleep(1)
            if trades_captured > 0 and trades_captured % 5 == 0:
                print(f"\n[STATUS] {trades_captured} trades analisados")
    except KeyboardInterrupt:
        print("\n[INTERROMPIDO]")
    
    # Análise final
    if analysis_results:
        print(f"\n{'='*60}")
        print("ANÁLISE CONSOLIDADA")
        print(f"{'='*60}")
        
        # Encontrar offsets mais comuns
        all_price_offsets = []
        all_volume_offsets = []
        
        for trade_num, data in analysis_results.items():
            for offset, price in data['price_offsets']:
                all_price_offsets.append(offset)
            for offset, vol, tipo in data['volume_offsets']:
                all_volume_offsets.append((offset, tipo))
        
        # Offsets mais frequentes
        from collections import Counter
        
        if all_price_offsets:
            price_counter = Counter(all_price_offsets)
            print(f"\n[PREÇO] Offsets mais prováveis:")
            for offset, count in price_counter.most_common(3):
                print(f"  Offset {offset}: apareceu {count}x")
        
        if all_volume_offsets:
            volume_counter = Counter(all_volume_offsets)
            print(f"\n[VOLUME] Offsets mais prováveis:")
            for (offset, tipo), count in volume_counter.most_common(5):
                print(f"  Offset {offset} ({tipo}): apareceu {count}x")
        
        # Sugestão de estrutura
        print(f"\n[SUGESTÃO DE ESTRUTURA]")
        if price_counter and volume_counter:
            price_offset = price_counter.most_common(1)[0][0]
            volume_offset, volume_type = volume_counter.most_common(1)[0][0]
            
            print(f"  Preço (double) provavelmente em: offset {price_offset}")
            print(f"  Volume ({volume_type}) provavelmente em: offset {volume_offset}")
            
            # Estimar estrutura
            print(f"\n  Possível layout TConnectorTrade:")
            if volume_offset < price_offset:
                print(f"    - Bytes 0-{volume_offset-1}: Headers/timestamp")
                print(f"    - Bytes {volume_offset}-{volume_offset+3}: Volume ({volume_type})")
                print(f"    - Bytes {price_offset}-{price_offset+7}: Preço (double)")
            else:
                print(f"    - Bytes 0-{price_offset-1}: Headers/timestamp")
                print(f"    - Bytes {price_offset}-{price_offset+7}: Preço (double)")
                print(f"    - Bytes {volume_offset}-{volume_offset+3}: Volume ({volume_type})")
    
    # Cleanup
    dll.UnsubscribeTicker(0, symbol)
    dll.DLLFinalize(0)

print(f"\n[FIM] Monitor encerrado - {trades_captured} trades analisados")