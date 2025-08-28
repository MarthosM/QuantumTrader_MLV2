"""
Teste rápido do fix de volume
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

# Import smart decoder
from src.profit_trade_structures import decode_trade_v2

# Configure DLL
dll_path = os.path.abspath("ProfitDLL64.dll")
print(f"[OK] DLL encontrada: {dll_path}")    
dll = CDLL(dll_path)

# Global counters
trades_captured = 0
volumes_found = []

print("=" * 60)
print("TESTE DO FIX DE VOLUME - SMART DECODER")
print("=" * 60)

# SetTradeCallbackV2
if hasattr(dll, 'SetTradeCallbackV2'):
    print("\n[OK] SetTradeCallbackV2 disponível")
    
    @WINFUNCTYPE(None, POINTER(c_byte))
    def trade_callback_v2(trade_ptr):
        global trades_captured, volumes_found
        trades_captured += 1
        
        if trade_ptr and trades_captured <= 10:
            try:
                # Usar nosso decoder inteligente
                trade_data = decode_trade_v2(trade_ptr)
                
                price = trade_data.get('price', 0)
                volume = trade_data.get('quantity', 0)
                method = trade_data.get('decoded_method', 'unknown')
                
                print(f"\n[TRADE #{trades_captured}]")
                print(f"  Preço: R$ {price:.2f}")
                print(f"  Volume: {volume} contratos")
                print(f"  Método: {method}")
                
                if volume > 0 and volume < 1000:
                    volumes_found.append(volume)
                    print(f"  ✅ VOLUME VÁLIDO ENCONTRADO!")
                elif volume == 0:
                    print(f"  ⚠️ Volume zero - mercado parado?")
                else:
                    print(f"  ❌ Volume inválido: {volume}")
                    
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
    
    print(f"\n[AGUARDANDO] Capturando primeiros 10 trades...")
    print(f"Horário: {datetime.now().strftime('%H:%M:%S')}")
    
    timeout = 30
    start = time.time()
    
    while time.time() - start < timeout and trades_captured < 10:
        time.sleep(0.5)
        if trades_captured > 0 and trades_captured % 5 == 0:
            print(f"\n  [{int(time.time()-start)}s] {trades_captured} trades capturados")
    
    # Análise final
    print(f"\n{'='*60}")
    print("RESULTADO DO TESTE")
    print(f"{'='*60}")
    print(f"Total de trades: {trades_captured}")
    
    if volumes_found:
        print(f"\n✅ SUCESSO! Volumes válidos encontrados:")
        print(f"  Volumes: {volumes_found}")
        print(f"  Média: {sum(volumes_found)/len(volumes_found):.1f} contratos")
        print(f"  Range: {min(volumes_found)}-{max(volumes_found)} contratos")
    else:
        print(f"\n❌ NENHUM VOLUME VÁLIDO ENCONTRADO")
        if trades_captured == 0:
            print("  Possível causa: Mercado em leilão ou baixa liquidez")
        else:
            print("  Possível causa: Estrutura ainda incorreta")
    
    # Cleanup
    dll.UnsubscribeTicker(0, symbol)
    dll.DLLFinalize(0)

print("\n[FIM] Teste concluído")