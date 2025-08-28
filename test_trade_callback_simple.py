"""
Teste do callback de trades - versão simplificada
"""
from ctypes import *
import time
import os
import sys

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from dotenv import load_dotenv
load_dotenv('.env.production')

# Configurar DLL - usar caminho absoluto
dll_path = os.path.abspath("ProfitDLL64.dll")
if not os.path.exists(dll_path):
    print(f"[ERRO] DLL não encontrada em: {dll_path}")
    sys.exit(1)
    
print(f"[OK] DLL encontrada: {dll_path}")    
dll = CDLL(dll_path)

# Dados globais para testes
trades_received = []

# Testar SetTradeCallback (V1 - simples)
if hasattr(dll, 'SetTradeCallback'):
    print("[OK] SetTradeCallback encontrado - testando versão simples")
    
    # Callback simples com 5 parâmetros
    @WINFUNCTYPE(None, c_wchar_p, c_double, c_int32, c_int32, c_int32)
    def trade_callback_simple(ticker, price, qty, buyer, seller):
        """Callback simples V1"""
        global trades_received
        
        # Converter para valores Python
        symbol = ticker if ticker else "UNKNOWN"
        price_val = float(price) if price else 0
        volume = int(qty) if qty else 0
        
        trade = {
            'symbol': symbol,
            'price': price_val,
            'volume': volume,
            'buyer': int(buyer) if buyer else 0,
            'seller': int(seller) if seller else 0
        }
        
        trades_received.append(trade)
        
        # Log apenas os primeiros trades
        if len(trades_received) <= 10:
            print(f"[TRADE #{len(trades_received)}] Symbol: {symbol} | Price: {price_val:.2f} | Volume: {volume}")
        elif len(trades_received) % 100 == 0:
            print(f"[MILESTONE] {len(trades_received)} trades recebidos - último volume: {volume}")
    
    # Registrar callback
    ret = dll.SetTradeCallback(trade_callback_simple)
    print(f"SetTradeCallback registrado: {ret}")

# Inicializar e conectar
print("\nInicializando conexão...")
key = os.getenv('PROFIT_KEY', '')
if key:
    dll.DLLInitializeLogin(0, key.encode('cp1252'), None)
    # DLLInitializeMarket não existe na versão atual
    
    symbol = b"WDOU25"
    ret = dll.SubscribeTicker(0, symbol)
    print(f"Subscribe WDOU25: {ret}")
    
    # Aguardar trades
    print("\nAguardando trades... (30 segundos)")
    for i in range(30):
        time.sleep(1)
        if i % 5 == 0:
            print(f"  {i}s - Total trades: {len(trades_received)}")
    
    # Análise dos dados
    print(f"\n[RESULTADO] Total de trades recebidos: {len(trades_received)}")
    
    if trades_received:
        # Estatísticas de volume
        volumes = [t['volume'] for t in trades_received]
        volumes_nao_zero = [v for v in volumes if v > 0]
        
        print(f"Trades com volume > 0: {len(volumes_nao_zero)}/{len(trades_received)}")
        
        if volumes_nao_zero:
            print(f"Volume mínimo: {min(volumes_nao_zero)}")
            print(f"Volume máximo: {max(volumes_nao_zero)}")
            print(f"Volume médio: {sum(volumes_nao_zero)/len(volumes_nao_zero):.2f}")
            
            # Últimos 5 trades
            print("\nÚltimos 5 trades:")
            for trade in trades_received[-5:]:
                print(f"  Price: {trade['price']:.2f} | Volume: {trade['volume']}")
    
    # Desconectar
    dll.UnsubscribeTicker(0, symbol)
    dll.DLLFinalize(0)
    
else:
    print("[ERRO] SetTradeCallback não encontrado na DLL")

print("\nTeste concluído!")