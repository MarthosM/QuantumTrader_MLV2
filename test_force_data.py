"""
Teste para forçar recepção de dados do book
"""
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from ctypes import c_wchar_p, c_int, c_double

# Carregar variáveis de ambiente
load_dotenv('.env.production')

# Adicionar diretório ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from src.connection_manager_v4 import ConnectionManagerV4

print("="*60)
print("TESTE FORÇADO DE RECEPÇÃO DE DADOS")
print("="*60)

# Criar conexão
dll_path = os.getenv('PROFIT_DLL_PATH')
conn = ConnectionManagerV4(dll_path=dll_path)

# Contadores
offer_count = 0
price_count = 0
trade_count = 0

# Callbacks
def on_offer_book(data):
    global offer_count
    offer_count += 1
    print(f"\n[OFFER BOOK #{offer_count}]")
    print(f"  Ticker: {data.get('ticker')}")
    print(f"  Position: {data.get('position')}")
    print(f"  Side: {data.get('side')} (0=Bid, 1=Ask)")
    print(f"  Price: {data.get('price')}")
    print(f"  Quantity: {data.get('quantity')}")
    
def on_price_book(data):
    global price_count
    price_count += 1
    if price_count <= 3:
        print(f"\n[PRICE BOOK #{price_count}]")
        print(f"  Price: {data.get('price')}")

def on_trade(data):
    global trade_count
    trade_count += 1
    if trade_count <= 3:
        print(f"\n[TRADE #{trade_count}]")
        print(f"  Price: {data.get('price')}")
        print(f"  Volume: {data.get('volume')}")

# Registrar callbacks
print("\n[1] Registrando callbacks...")
conn.register_offer_book_callback(on_offer_book)
conn.register_price_book_callback(on_price_book)
conn.register_trade_callback(on_trade)

# Inicializar
print("\n[2] Inicializando conexão...")
key = os.getenv('PROFIT_KEY')
username = os.getenv('PROFIT_USERNAME')
password = os.getenv('PROFIT_PASSWORD')

if not conn.initialize(key=key, username=username, password=password):
    print("  [ERRO] Falha ao inicializar")
    sys.exit(1)

print("  [OK] Conexão inicializada")

# Aguardar market data
print("\n[3] Aguardando Market Data...")
for i in range(10):
    if conn.market_state == conn.MARKET_CONNECTED:
        print(f"  [OK] Market Data conectado após {i}s")
        break
    time.sleep(1)

# Subscrever
symbol = "WDOU25"
print(f"\n[4] Subscrevendo {symbol}...")

# Tentar diferentes métodos de subscrição
if hasattr(conn, 'subscribe_ticker'):
    result = conn.subscribe_ticker(symbol)
    print(f"  subscribe_ticker: {'OK' if result else 'FALHOU'}")

if hasattr(conn, 'subscribe_offer_book'):
    result = conn.subscribe_offer_book(symbol)
    print(f"  subscribe_offer_book: {'OK' if result else 'FALHOU'}")
    
if hasattr(conn, 'subscribe_price_book'):
    result = conn.subscribe_price_book(symbol)
    print(f"  subscribe_price_book: {'OK' if result else 'FALHOU'}")

# Tentar buscar último preço diretamente
print(f"\n[5] Tentando buscar dados diretamente...")

# Verificar se há métodos para buscar dados
if hasattr(conn.dll, 'GetLastPrice'):
    try:
        conn.dll.GetLastPrice.restype = c_double
        price = conn.dll.GetLastPrice(c_wchar_p(symbol), c_wchar_p("F"))
        print(f"  GetLastPrice: {price}")
    except Exception as e:
        print(f"  GetLastPrice erro: {e}")

if hasattr(conn.dll, 'GetTicker'):
    try:
        # Estrutura para receber dados do ticker
        print("  GetTicker: Método existe")
    except Exception as e:
        print(f"  GetTicker erro: {e}")

# Aguardar dados
print(f"\n[6] Aguardando dados por 30 segundos...")
print("  (Se não receber nada, verifique o ProfitChart)")

for i in range(30):
    time.sleep(1)
    if i % 5 == 0:
        total = offer_count + price_count + trade_count
        print(f"  {i}s - Total msgs: {total} (Offer: {offer_count}, Price: {price_count}, Trade: {trade_count})")
        
        # Tentar processar eventos pendentes da DLL
        if hasattr(conn.dll, 'ProcessEvents'):
            try:
                conn.dll.ProcessEvents()
            except:
                pass

# Resultado
print("\n" + "="*60)
print("RESULTADO")
print("="*60)
print(f"Offer Book: {offer_count} mensagens")
print(f"Price Book: {price_count} mensagens")
print(f"Trades: {trade_count} mensagens")

if offer_count + price_count + trade_count == 0:
    print("\n[PROBLEMA] Nenhum dado recebido!")
    print("\nPossíveis causas:")
    print("1. ProfitChart não está aberto")
    print("2. Gráfico do WDOU25 não está aberto no ProfitChart")
    print("3. Mercado sem negociação no momento")
    print("4. Problema de permissão para dados de mercado")
    print("\n[AÇÃO] Abra o ProfitChart, conecte e abra um gráfico do WDOU25")
else:
    print(f"\n[OK] Recebendo dados!")

# Desconectar
print("\n[7] Desconectando...")
conn.disconnect()
print("  [OK] Desconectado")