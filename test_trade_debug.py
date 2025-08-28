"""
Teste rápido para capturar bytes raw do trade callback
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

print("=" * 60)
print("DEBUG ESTRUTURA TRADE - CAPTURA DE BYTES RAW")
print("=" * 60)

# SetTradeCallbackV2
if hasattr(dll, 'SetTradeCallbackV2'):
    print("\n[OK] SetTradeCallbackV2 disponível")
    
    @WINFUNCTYPE(None, POINTER(c_byte))
    def trade_callback_v2(trade_ptr):
        global trades_captured
        trades_captured += 1
        
        if trade_ptr and trades_captured <= 5:  # Primeiros 5 trades
            try:
                # Capturar 150 bytes
                raw_bytes = cast(trade_ptr, POINTER(c_byte * 150))
                raw_data = bytes(raw_bytes.contents[:150])
                
                print(f"\n[TRADE #{trades_captured}] {len(raw_data)} bytes capturados")
                print("=" * 60)
                
                # Hex dump
                print("HEX DUMP:")
                for offset in range(0, min(len(raw_data), 96), 16):
                    hex_str = ' '.join(f'{b:02x}' for b in raw_data[offset:offset+16])
                    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in raw_data[offset:offset+16])
                    print(f"  {offset:04x}: {hex_str:<48} | {ascii_str}")
                
                # Análise de padrões
                print("\nANÁLISE DE PADRÕES:")
                
                # Procurar preço (double ~5400)
                for offset in range(0, min(len(raw_data)-7, 100), 4):
                    try:
                        val_double = struct.unpack_from('<d', raw_data, offset)[0]
                        if 5000 < val_double < 6000:
                            print(f"  [PREÇO] Offset {offset}: {val_double:.2f}")
                    except:
                        pass
                
                # Procurar volume (int32/int64)
                volume_found = False
                for offset in range(0, min(len(raw_data)-3, 100), 4):
                    try:
                        # int32
                        val32 = struct.unpack_from('<i', raw_data, offset)[0]
                        if 1 <= val32 <= 500:
                            print(f"  [VOLUME int32] Offset {offset}: {val32} contratos")
                            volume_found = True
                        
                        # int64
                        if offset <= len(raw_data)-8:
                            val64 = struct.unpack_from('<q', raw_data, offset)[0]
                            if 1 <= val64 <= 500:
                                print(f"  [VOLUME int64] Offset {offset}: {val64} contratos")
                                volume_found = True
                    except:
                        pass
                
                if not volume_found:
                    print("  [!] Volume não encontrado no range esperado (1-500)")
                
                # Procurar timestamp (ano 2025 = 0x07E9)
                for i in range(len(raw_data)-1):
                    if raw_data[i] == 0xE9 and raw_data[i+1] == 0x07:
                        print(f"  [TIMESTAMP] Ano 2025 encontrado no offset {i}")
                
                print("=" * 60)
                
            except Exception as e:
                print(f"[ERRO] {e}")
    
    # Registrar callback
    ret = dll.SetTradeCallbackV2(trade_callback_v2)
    print(f"SetTradeCallbackV2 registrado: {ret}")

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
    
    # Aguardar trades
    print(f"\n[AGUARDANDO] Capturando primeiros 5 trades...")
    print(f"Horário: {datetime.now().strftime('%H:%M:%S')} - Mercado deve estar aberto")
    
    timeout = 60
    start = time.time()
    
    while time.time() - start < timeout and trades_captured < 5:
        time.sleep(0.5)
        if trades_captured > 0 and trades_captured % 1 == 0:
            print(f"  [{int(time.time()-start)}s] Trades capturados: {trades_captured}")
    
    if trades_captured == 0:
        print("\n[AVISO] Nenhum trade capturado!")
        print("Possíveis causas:")
        print("  - Mercado em leilão")
        print("  - Baixa liquidez no momento")
        print("  - Callback não está sendo chamado")
    
    # Cleanup
    dll.UnsubscribeTicker(0, symbol)
    dll.DLLFinalize(0)

print(f"\n[FIM] Total de trades capturados: {trades_captured}")
print("\nPRÓXIMOS PASSOS:")
if trades_captured > 0:
    print("1. Analisar offsets de preço e volume")
    print("2. Atualizar TConnectorTrade com layout correto")
    print("3. Testar decodificação com nova estrutura")
else:
    print("1. Verificar se mercado está ativo")
    print("2. Testar em outro horário com mais liquidez")