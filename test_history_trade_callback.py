"""
Teste do callback de histórico de trades para capturar volume
"""
from ctypes import *
import time
import os
import sys
from datetime import datetime

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from dotenv import load_dotenv
load_dotenv('.env.production')

# Importar estruturas
from src.profit_trade_structures import TConnectorTrade, decode_trade_v2

# Configurar DLL
dll_path = os.path.abspath("ProfitDLL64.dll")
print(f"[OK] DLL encontrada: {dll_path}")    
dll = CDLL(dll_path)

# Dados globais
trades_received = []
last_log_time = time.time()

# Testar SetHistoryTradeCallbackV2
if hasattr(dll, 'SetHistoryTradeCallbackV2'):
    print("[OK] SetHistoryTradeCallbackV2 encontrado")
    
    @WINFUNCTYPE(None, POINTER(c_byte))
    def history_trade_callback(trade_ptr):
        """Callback para histórico de trades V2"""
        global trades_received, last_log_time
        
        try:
            # Decodificar estrutura
            trade_data = decode_trade_v2(trade_ptr)
            
            # Extrair dados
            price = trade_data.get('price', 0)
            volume = trade_data.get('quantity', 0)
            timestamp = trade_data.get('timestamp', '')
            aggressor = trade_data.get('aggressor', 'UNKNOWN')
            
            # Salvar trade
            trades_received.append({
                'timestamp': timestamp,
                'price': price,
                'volume': volume,
                'aggressor': aggressor
            })
            
            # Log periódico
            current_time = time.time()
            if len(trades_received) <= 5 or current_time - last_log_time >= 5:
                print(f"[HISTORY TRADE #{len(trades_received)}] Price: {price:.2f} | Volume: {volume} | Aggressor: {aggressor}")
                last_log_time = current_time
                
        except Exception as e:
            print(f"[ERRO] Callback: {e}")
    
    # Registrar callback
    ret = dll.SetHistoryTradeCallbackV2(history_trade_callback)
    print(f"SetHistoryTradeCallbackV2 registrado: {ret}")
else:
    print("[AVISO] SetHistoryTradeCallbackV2 não encontrado")

# Testar GetHistoryTrades
if hasattr(dll, 'GetHistoryTrades'):
    print("[OK] GetHistoryTrades encontrado")
    
    # Inicializar
    key = os.getenv('PROFIT_KEY', '')
    if key:
        dll.DLLInitializeLogin(0, key.encode('cp1252'), None)
        
        symbol = b"WDOU25"
        ret = dll.SubscribeTicker(0, symbol)
        print(f"Subscribe WDOU25: {ret}")
        
        # Solicitar histórico de trades
        print("\nSolicitando histórico de trades...")
        
        # Tentar obter trades do dia
        today = datetime.now()
        start_date = c_wchar_p(today.strftime("%Y%m%d"))
        end_date = c_wchar_p(today.strftime("%Y%m%d")) 
        
        ret = dll.GetHistoryTrades(0, symbol, start_date, end_date)
        print(f"GetHistoryTrades retornou: {ret}")
        
        # Aguardar dados
        print("\nAguardando trades históricos... (30 segundos)")
        for i in range(30):
            time.sleep(1)
            if i % 5 == 0:
                print(f"  {i}s - Total trades: {len(trades_received)}")
                
                # Se tiver dados, mostrar últimos
                if trades_received and i >= 10:
                    last_trade = trades_received[-1]
                    print(f"    Último: Price={last_trade['price']:.2f} Volume={last_trade['volume']}")
        
        # Análise final
        print(f"\n[RESULTADO] Total de trades históricos: {len(trades_received)}")
        
        if trades_received:
            volumes = [t['volume'] for t in trades_received]
            volumes_positivos = [v for v in volumes if v > 0]
            
            print(f"Trades com volume > 0: {len(volumes_positivos)}/{len(trades_received)}")
            
            if volumes_positivos:
                print(f"Volume mínimo: {min(volumes_positivos)}")
                print(f"Volume máximo: {max(volumes_positivos)}")
                print(f"Volume médio: {sum(volumes_positivos)/len(volumes_positivos):.2f}")
                
                # Mostrar primeiros trades
                print("\nPrimeiros 5 trades:")
                for i, trade in enumerate(trades_received[:5]):
                    print(f"  #{i+1} Price: {trade['price']:.2f} | Volume: {trade['volume']} | Aggressor: {trade['aggressor']}")
        
        # Desconectar
        dll.UnsubscribeTicker(0, symbol)
        dll.DLLFinalize(0)
        
else:
    print("[ERRO] GetHistoryTrades não encontrado")

print("\nTeste concluído!")