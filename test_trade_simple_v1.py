"""
Teste focado no callback V1 simples e TranslateTrade
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
print(f"[OK] DLL encontrada: {dll_path}")    
dll = CDLL(dll_path)

# Global para trades
trades_received = []

print("=" * 60)
print("TESTE CALLBACK V1 SIMPLES + TRANSLATETRADE")
print("=" * 60)

# 1. Testar SetTradeCallback V1 (versão simples)
if hasattr(dll, 'SetTradeCallback'):
    print("\n[TEST 1] SetTradeCallback V1 - Callback simples")
    
    # V1 tem 5 parâmetros: ticker, price, qty, buyer, seller
    @WINFUNCTYPE(None, c_wchar_p, c_double, c_int32, c_int32, c_int32)
    def trade_callback_v1(ticker, price, qty, buyer, seller):
        """Callback V1 simples - Volume em qty (quantidade)"""
        global trades_received
        
        try:
            symbol = ticker if ticker else "UNKNOWN"
            price_val = float(price) if price else 0
            volume = int(qty) if qty else 0  # VOLUME EM CONTRATOS!
            
            trades_received.append({
                'type': 'V1',
                'symbol': symbol,
                'price': price_val,
                'volume': volume,  # Quantidade em contratos
                'buyer': buyer,
                'seller': seller,
                'timestamp': datetime.now().isoformat()
            })
            
            # Log primeiros trades
            if len(trades_received) <= 10:
                print(f"  [V1 TRADE] Price: {price_val:.2f} | Volume: {volume} contratos | Buyer: {buyer} | Seller: {seller}")
        except Exception as e:
            print(f"  [V1 ERROR] {e}")
    
    # Registrar callback
    ret = dll.SetTradeCallback(trade_callback_v1)
    print(f"  Registro SetTradeCallback: {ret}")
    if ret == 0:
        print("  [OK] Callback V1 registrado com sucesso!")
    else:
        print(f"  [WARN] Retorno não esperado: {ret}")

# 2. Testar TranslateTrade se disponível
if hasattr(dll, 'TranslateTrade'):
    print("\n[TEST 2] TranslateTrade - Função de tradução")
    print("  TranslateTrade encontrado - pode converter dados de trade")
    print("  Esta função pode ser necessária para decodificar trades do V2")
    
    # Definir possível assinatura
    # TranslateTrade pode converter de formato interno para formato legível
    dll.TranslateTrade.argtypes = [c_void_p, c_void_p]  # Input pointer, output pointer
    dll.TranslateTrade.restype = c_int
    
    print("  Assinatura configurada para TranslateTrade")

# 3. Inicializar e conectar
print("\n[INIT] Inicializando conexão...")
key = os.getenv('PROFIT_KEY', '')
if not key:
    print("[ERROR] PROFIT_KEY não encontrada")
    sys.exit(1)

ret = dll.DLLInitializeLogin(0, key.encode('cp1252'), None)
print(f"  DLLInitializeLogin: {ret}")

# 4. Subscribe para múltiplos símbolos
print("\n[SUBSCRIBE] Inscrevendo em símbolos...")

symbols = [
    b"WDOU25",  # WDO Agosto 2025
    b"WDOQ25",  # WDO Setembro 2025  
    b"WDOG25",  # WDO Julho 2025
]

for symbol in symbols:
    ret = dll.SubscribeTicker(0, symbol)
    print(f"  Subscribe {symbol.decode()}: {ret}")
    time.sleep(0.2)  # Pequeno delay entre inscrições

# 5. Tentar forçar atualização de trades
print("\n[FORCE UPDATE] Tentando forçar recebimento de trades...")

# Tentar GetHistoryTrades para "acordar" o sistema
if hasattr(dll, 'GetHistoryTrades'):
    today = datetime.now().strftime("%Y%m%d")
    for symbol in symbols:
        ret = dll.GetHistoryTrades(0, symbol, c_wchar_p(today), c_wchar_p(today))
        print(f"  GetHistoryTrades {symbol.decode()}: {ret}")

# 6. Monitorar trades
print("\n[MONITOR] Aguardando trades (60 segundos)...")
print("  Mercado WDO - Volume em CONTRATOS")
print("  Observando múltiplos vencimentos...")

start_time = time.time()
last_report = start_time

while time.time() - start_time < 60:
    current = time.time()
    
    if current - last_report >= 10:
        elapsed = int(current - start_time)
        print(f"\n  [{elapsed}s] Total trades capturados: {len(trades_received)}")
        
        if trades_received:
            # Estatísticas
            volumes = [t['volume'] for t in trades_received if t['volume'] > 0]
            if volumes:
                print(f"    Volume MIN: {min(volumes)} contratos")
                print(f"    Volume MAX: {max(volumes)} contratos")
                print(f"    Volume MÉDIO: {sum(volumes)/len(volumes):.1f} contratos")
                
                # Últimos 3 trades
                print("    Últimos trades:")
                for trade in trades_received[-3:]:
                    print(f"      Price: {trade['price']:.2f} | Vol: {trade['volume']} | {trade['symbol']}")
        
        last_report = current
    
    time.sleep(0.1)

# 7. Análise final
print("\n" + "=" * 60)
print("ANÁLISE FINAL")
print("=" * 60)

if trades_received:
    print(f"\n[SUCESSO] {len(trades_received)} trades capturados!")
    
    # Análise por tipo
    v1_trades = [t for t in trades_received if t['type'] == 'V1']
    print(f"  Trades V1: {len(v1_trades)}")
    
    # Análise de volume
    all_volumes = [t['volume'] for t in trades_received]
    valid_volumes = [v for v in all_volumes if v > 0]
    
    if valid_volumes:
        print(f"\n[VOLUME EM CONTRATOS]")
        print(f"  Total de trades com volume: {len(valid_volumes)}/{len(trades_received)}")
        print(f"  Volume mínimo: {min(valid_volumes)} contratos")
        print(f"  Volume máximo: {max(valid_volumes)} contratos")
        print(f"  Volume médio: {sum(valid_volumes)/len(valid_volumes):.1f} contratos")
        print(f"  Volume total negociado: {sum(valid_volumes)} contratos")
        
        # Distribuição
        print(f"\n[DISTRIBUIÇÃO DE VOLUME]")
        vol_1_10 = len([v for v in valid_volumes if 1 <= v <= 10])
        vol_11_50 = len([v for v in valid_volumes if 11 <= v <= 50])
        vol_51_100 = len([v for v in valid_volumes if 51 <= v <= 100])
        vol_100_plus = len([v for v in valid_volumes if v > 100])
        
        print(f"  1-10 contratos: {vol_1_10} trades")
        print(f"  11-50 contratos: {vol_11_50} trades")
        print(f"  51-100 contratos: {vol_51_100} trades")
        print(f"  100+ contratos: {vol_100_plus} trades")
    else:
        print(f"\n[PROBLEMA] Trades capturados mas volume = 0")
        print("  Possível problema na decodificação do campo volume")
else:
    print("\n[SEM DADOS] Nenhum trade capturado")
    print("\nPossíveis causas:")
    print("  1. Mercado em leilão (sem trades normais)")
    print("  2. Símbolos inativos no momento")
    print("  3. Callback precisa de configuração adicional")
    print("  4. Firewall/antivírus bloqueando dados")
    
    # Verificar estado da conexão
    if hasattr(dll, 'IsConnected'):
        connected = dll.IsConnected(0)
        print(f"\n  IsConnected: {connected}")

# Cleanup
print("\n[CLEANUP] Finalizando...")
for symbol in symbols:
    dll.UnsubscribeTicker(0, symbol)
dll.DLLFinalize(0)

print("\nTeste concluído!")