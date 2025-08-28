"""
Teste completo para descobrir TODOS os métodos da DLL relacionados a trades e volume
"""
from ctypes import *
import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('.env.production')

# Configure DLL
dll_path = os.path.abspath("ProfitDLL64.dll")
print(f"[OK] DLL encontrada: {dll_path}")    
dll = CDLL(dll_path)

print("=" * 60)
print("ANÁLISE COMPLETA DA PROFITDLL")
print("=" * 60)

# Lista de todos os possíveis métodos relacionados a trades/volume
possible_methods = [
    # Callbacks de Trade
    'SetTradeCallback',
    'SetTradeCallbackV2', 
    'SetNewTradeCallback',
    'SetHistoryTradeCallback',
    'SetHistoryTradeCallbackV2',
    'SetAggTradeCallback',
    'SetTimesTradesCallback',
    'SetTradeHistoryCallback',
    'SetTradeEventCallback',
    
    # Métodos Get para trades
    'GetTrade',
    'GetTrades', 
    'GetLastTrade',
    'GetHistoryTrades',
    'GetAggressorTrades',
    'GetTradeHistory',
    'GetTimesAndTrades',
    'GetTradeVolume',
    'GetDayTrades',
    'GetTodayTrades',
    
    # Métodos de Ticker/Symbol
    'GetTicker',
    'GetTickerInfo',
    'GetSymbol',
    'GetSymbolInfo',
    'GetQuote',
    'GetQuoteEx',
    
    # Métodos de Book/Offer
    'GetOfferBook',
    'GetPriceBook', 
    'GetBookInfo',
    'GetBBO',  # Best Bid Offer
    
    # Subscribe methods
    'SubscribeTicker',
    'SubscribeBBO',
    'SubscribeAggTrade',
    'SubscribeTimesAndTrades',
    'SubscribeTrade',
    'SubscribeMarketData',
    
    # Métodos de State/Status
    'GetConnectionState',
    'GetMarketState',
    'IsConnected',
    'IsMarketOpen',
    
    # Inicialização
    'DLLInitialize',
    'DLLInitializeLogin',
    'DLLInitializeMarket',
    'Initialize',
    'InitializeMarket',
    'Connect',
    'ConnectMarket',
    
    # Outros potenciais
    'SetServerAddress',
    'SetAssetInfo',
    'GetAssetInfo',
    'TranslateTrade',
    'GetLastError',
    'GetErrorMessage'
]

# Categorizar métodos encontrados
categories = {
    'Callbacks': [],
    'Get Methods': [],
    'Subscribe': [],
    'Initialize': [],
    'Other': []
}

print("\n[SCANNING] Verificando métodos disponíveis...")
print("-" * 60)

for method in possible_methods:
    if hasattr(dll, method):
        # Categorizar
        if 'Callback' in method:
            categories['Callbacks'].append(method)
        elif method.startswith('Get'):
            categories['Get Methods'].append(method)
        elif method.startswith('Subscribe'):
            categories['Subscribe'].append(method)
        elif 'Initialize' in method or 'Connect' in method:
            categories['Initialize'].append(method)
        else:
            categories['Other'].append(method)
        
        print(f"  [OK] {method}")

# Mostrar métodos por categoria
print("\n" + "=" * 60)
print("MÉTODOS ENCONTRADOS POR CATEGORIA")
print("=" * 60)

for category, methods in categories.items():
    if methods:
        print(f"\n{category} ({len(methods)} métodos):")
        for method in methods:
            print(f"  - {method}")

# Tentar descobrir assinatura dos métodos importantes
print("\n" + "=" * 60)
print("TESTANDO MÉTODOS IMPORTANTES")
print("=" * 60)

# Inicializar
key = os.getenv('PROFIT_KEY', '')
if key:
    print("\n[INIT] Inicializando...")
    ret = dll.DLLInitializeLogin(0, key.encode('cp1252'), None)
    print(f"  DLLInitializeLogin: {ret}")
    
    # Tentar GetTicker se existir
    if hasattr(dll, 'GetTicker'):
        print("\n[TEST] Tentando GetTicker...")
        # Testar diferentes estruturas
        
        # Opção 1: Estrutura simples
        class TickerInfo(Structure):
            _fields_ = [
                ("Last", c_double),
                ("Bid", c_double),
                ("Ask", c_double),
                ("Volume", c_int64),
                ("Trades", c_int32)
            ]
        
        ticker = TickerInfo()
        symbol = b"WDOU25"
        
        try:
            ret = dll.GetTicker(0, symbol, byref(ticker))
            if ret == 0:
                print(f"  Last: {ticker.Last}")
                print(f"  Volume: {ticker.Volume}")
                print(f"  Trades: {ticker.Trades}")
            else:
                print(f"  GetTicker retornou erro: {ret}")
        except Exception as e:
            print(f"  Erro ao chamar GetTicker: {e}")
    
    # Tentar GetQuote se existir
    if hasattr(dll, 'GetQuote') or hasattr(dll, 'GetQuoteEx'):
        print("\n[TEST] Tentando GetQuote...")
        
        class Quote(Structure):
            _fields_ = [
                ("Symbol", c_char * 20),
                ("Last", c_double),
                ("Bid", c_double),
                ("Ask", c_double),
                ("Volume", c_int64),
                ("TotalVolume", c_int64),
                ("Trades", c_int32)
            ]
        
        quote = Quote()
        symbol = b"WDOU25"
        
        if hasattr(dll, 'GetQuote'):
            try:
                ret = dll.GetQuote(0, symbol, byref(quote))
                if ret == 0:
                    print(f"  Volume: {quote.Volume}")
                    print(f"  TotalVolume: {quote.TotalVolume}")
            except Exception as e:
                print(f"  Erro: {e}")
    
    # Tentar GetLastTrade
    if hasattr(dll, 'GetLastTrade'):
        print("\n[TEST] Tentando GetLastTrade...")
        
        class LastTrade(Structure):
            _fields_ = [
                ("Price", c_double),
                ("Volume", c_int64),
                ("Aggressor", c_int32)
            ]
        
        trade = LastTrade()
        symbol = b"WDOU25"
        
        try:
            ret = dll.GetLastTrade(0, symbol, byref(trade))
            if ret == 0:
                print(f"  Price: {trade.Price}")
                print(f"  Volume: {trade.Volume} contratos")
                print(f"  Aggressor: {trade.Aggressor}")
        except Exception as e:
            print(f"  Erro: {e}")
    
    # Cleanup
    dll.DLLFinalize(0)

# Análise final
print("\n" + "=" * 60)
print("ANÁLISE FINAL")
print("=" * 60)

total_methods = sum(len(methods) for methods in categories.values())
print(f"\nTotal de métodos relacionados encontrados: {total_methods}")

if categories['Get Methods']:
    print(f"\n[IMPORTANTE] Encontrados {len(categories['Get Methods'])} métodos Get")
    print("Estes métodos podem fornecer dados de volume diretamente!")
    
if categories['Callbacks']:
    print(f"\n[CALLBACKS] {len(categories['Callbacks'])} callbacks disponíveis")
    print("Precisamos descobrir qual está funcionando corretamente")

print("\n[PRÓXIMOS PASSOS]")
print("1. Testar cada método Get para obter volume")
print("2. Verificar estrutura correta para cada callback")
print("3. Usar Wireshark/monitor de rede para ver dados recebidos")
print("4. Verificar se precisa chamar alguma função de ativação")