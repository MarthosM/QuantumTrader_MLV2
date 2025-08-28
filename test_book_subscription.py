"""
Script para testar subscrição e recepção de dados de book
"""
import os
import sys
import time
from datetime import datetime
from ctypes import c_wchar_p, c_int

# Adicionar diretório ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Importar módulos
from src.connection_manager_oco import ConnectionManagerOCO

def test_book_subscription():
    """Testa se estamos recebendo dados do book"""
    
    print("\n" + "="*60)
    print("TESTE DE SUBSCRIÇÃO DE BOOK DATA")
    print("="*60)
    
    # Criar conexão
    print("\n[1] Criando conexão...")
    conn = ConnectionManagerOCO()
    
    # Dados de autenticação
    KEY = os.getenv('PROFIT_KEY', '')
    USERNAME = os.getenv('PROFIT_USERNAME', '')
    PASSWORD = os.getenv('PROFIT_PASSWORD', '')
    
    if not KEY:
        print("[ERRO] PROFIT_KEY não configurada no .env")
        return
    
    # Contadores para os callbacks
    offer_book_count = 0
    price_book_count = 0
    last_book_data = None
    
    # Definir callbacks
    def on_offer_book(data):
        nonlocal offer_book_count, last_book_data
        offer_book_count += 1
        last_book_data = data
        if offer_book_count <= 5:
            print(f"\n[OFFER BOOK #{offer_book_count}]")
            print(f"  Position: {data.get('position')}")
            print(f"  Side: {data.get('side')} (0=Bid, 1=Ask)")
            print(f"  Price: {data.get('price')}")
            print(f"  Quantity: {data.get('quantity')}")
    
    def on_price_book(data):
        nonlocal price_book_count
        price_book_count += 1
        if price_book_count <= 5:
            print(f"\n[PRICE BOOK #{price_book_count}]")
            print(f"  Position: {data.get('position')}")
            print(f"  Side: {data.get('side')}")
            print(f"  Price: {data.get('price')}")
            print(f"  Quantity: {data.get('quantity')}")
    
    # Registrar callbacks
    print("\n[2] Registrando callbacks...")
    conn.register_offer_book_callback(on_offer_book)
    conn.register_price_book_callback(on_price_book)
    print("  [OK] Callbacks registrados")
    
    # Inicializar conexão
    print("\n[3] Inicializando conexão...")
    if not conn.initialize(key=KEY, username=USERNAME, password=PASSWORD):
        print("  [ERRO] Falha ao inicializar")
        return
    print("  [OK] Conexão inicializada")
    
    # Verificar estados da conexão
    print("\n[4] Estados da conexão:")
    print(f"  Connected: {conn.connected}")
    print(f"  Login State: {conn.login_state}")
    print(f"  Market State: {conn.market_state}")
    print(f"  Routing State: {conn.routing_state}")
    
    # Aguardar market data
    print("\n[5] Aguardando Market Data...")
    for i in range(10):
        if hasattr(conn, 'MARKET_CONNECTED') and conn.market_state == conn.MARKET_CONNECTED:
            print(f"  [OK] Market Data conectado após {i}s")
            break
        time.sleep(1)
    else:
        print(f"  [AVISO] Market Data não conectou (estado: {conn.market_state})")
    
    # Subscrever ao ticker
    symbol = "WDOU25"
    print(f"\n[6] Subscrevendo ao símbolo {symbol}...")
    
    # Subscrever ticker
    if hasattr(conn, 'subscribe_ticker'):
        result = conn.subscribe_ticker(symbol)
        print(f"  subscribe_ticker: {'OK' if result else 'FALHOU'}")
    
    # Subscrever offer book
    if hasattr(conn, 'subscribe_offer_book'):
        result = conn.subscribe_offer_book(symbol)
        print(f"  subscribe_offer_book: {'OK' if result else 'FALHOU'}")
    else:
        print("  subscribe_offer_book: NÃO DISPONÍVEL")
    
    # Subscrever price book
    if hasattr(conn, 'subscribe_price_book'):
        result = conn.subscribe_price_book(symbol)
        print(f"  subscribe_price_book: {'OK' if result else 'FALHOU'}")
    else:
        print("  subscribe_price_book: NÃO DISPONÍVEL")
    
    # Aguardar dados
    print(f"\n[7] Aguardando dados por 30 segundos...")
    print("    (Se não receber nada, o mercado pode estar fechado)")
    
    for i in range(30):
        time.sleep(1)
        if i % 5 == 0:
            print(f"  {i}s - Offer book: {offer_book_count} msgs, Price book: {price_book_count} msgs")
    
    # Resultado final
    print("\n" + "="*60)
    print("RESULTADO DO TESTE")
    print("="*60)
    print(f"Total de mensagens offer book: {offer_book_count}")
    print(f"Total de mensagens price book: {price_book_count}")
    
    if offer_book_count > 0:
        print(f"\n[OK] RECEBENDO DADOS DO BOOK!")
        if last_book_data:
            print(f"Último dado recebido: {last_book_data}")
    else:
        print(f"\n[PROBLEMA] Não recebeu dados do book")
        print("Possíveis causas:")
        print("  1. Mercado fechado (horário: 9h-18h)")
        print("  2. Símbolo incorreto")
        print("  3. Falta de permissão para dados de mercado")
        print("  4. Problema de conexão com a B3")
    
    # Desconectar
    print("\n[8] Desconectando...")
    conn.disconnect()
    print("  [OK] Desconectado")

if __name__ == "__main__":
    test_book_subscription()