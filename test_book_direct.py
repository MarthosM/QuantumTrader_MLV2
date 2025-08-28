#!/usr/bin/env python3
"""
Test direct book data reception
"""

import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# Setup paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Load environment
load_dotenv('.env.production')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TestBookDirect')

# Import connection manager
from src.connection_manager_oco import ConnectionManagerOCO

def test_book_data():
    """Test book data reception directly"""
    print("\n" + "="*60)
    print("TESTE DIRETO DE BOOK DATA")
    print("="*60)
    
    # Setup connection
    dll_path = Path(os.getcwd()) / 'ProfitDLL64.dll'
    if not dll_path.exists():
        dll_path = Path('ProfitDLL64.dll')
    
    print(f"\n[1] Criando conexão com DLL: {dll_path}")
    connection = ConnectionManagerOCO(str(dll_path))
    
    # Track book updates
    book_count = 0
    last_book = {}
    
    def on_book_update(book_data):
        nonlocal book_count, last_book
        book_count += 1
        last_book = book_data
        
        if book_count <= 5 or book_count % 100 == 0:
            print(f"\n[BOOK #{book_count}]")
            print(f"  Bid: {book_data.get('bid_price_1', 0):.2f} x {book_data.get('bid_quantity_1', 0)}")
            print(f"  Ask: {book_data.get('ask_price_1', 0):.2f} x {book_data.get('ask_quantity_1', 0)}")
    
    # Set callback
    connection.book_update_callback = on_book_update
    print("[OK] Callback configurado")
    
    # Initialize connection
    print("\n[2] Inicializando conexão...")
    USERNAME = os.getenv('PROFIT_USERNAME', '')
    PASSWORD = os.getenv('PROFIT_PASSWORD', '')
    KEY = os.getenv('PROFIT_KEY', '')
    
    if connection.initialize(username=USERNAME, password=PASSWORD, key=KEY):
        print("[OK] Conexão inicializada")
        
        # Subscribe to symbol
        symbol = "WDOU25"
        print(f"\n[3] Subscrevendo ao símbolo {symbol}...")
        
        if hasattr(connection, 'subscribe_offer_book'):
            if connection.subscribe_offer_book(symbol):
                print(f"[OK] Offer book de {symbol} subscrito")
        
        if hasattr(connection, 'subscribe_price_book'):  
            if connection.subscribe_price_book(symbol):
                print(f"[OK] Price book de {symbol} subscrito")
        
        # Wait for data
        print("\n[4] Aguardando dados de book por 30 segundos...")
        print("    Se não receber dados, verifique o ProfitChart!")
        
        for i in range(30):
            time.sleep(1)
            if i % 5 == 0:
                print(f"    {i}s - Total de books recebidos: {book_count}")
        
        print(f"\n[5] RESULTADO FINAL:")
        print(f"    Total de books recebidos: {book_count}")
        
        if book_count > 0:
            print(f"    Último book:")
            print(f"      Bid: {last_book.get('bid_price_1', 0):.2f}")
            print(f"      Ask: {last_book.get('ask_price_1', 0):.2f}")
            print("\n✅ SUCESSO! Sistema está recebendo dados de book!")
        else:
            print("\n❌ PROBLEMA: Nenhum dado de book recebido!")
            print("\nVerifique no ProfitChart:")
            print("1. Gráfico WDOU25 está aberto?")
            print("2. Book de ofertas está ativo?")
            print("3. Dados estão sendo atualizados?")
            
    else:
        print("[ERRO] Falha ao inicializar conexão")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    test_book_data()