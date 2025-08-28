#!/usr/bin/env python3
"""
Testa conexão e recebimento de dados do ProfitChart
"""
import sys
import time
import os
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent))

from src.connection_manager_v4 import ConnectionManagerV4
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv('.env.production')

def test_connection():
    """Testa conexão com ProfitChart"""
    print("[TEST] Iniciando teste de conexão...")
    
    # Configurações
    symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
    print(f"[CONFIG] Símbolo: {symbol}")
    
    # Criar conexão
    dll_path = Path('dll/ProfitDLL64.dll')
    if not dll_path.exists():
        print(f"[ERRO] DLL não encontrada em {dll_path}")
        return
    
    connection = ConnectionManagerV4(str(dll_path))
    
    # Contador de updates
    update_count = 0
    last_bid = 0
    last_ask = 0
    
    def book_callback(symbol_str, book_data):
        """Callback para receber dados do book"""
        nonlocal update_count, last_bid, last_ask
        update_count += 1
        
        bid = book_data.get('bid_price_1', 0)
        ask = book_data.get('ask_price_1', 0)
        
        # Só mostrar se valores mudaram
        if bid != last_bid or ask != last_ask:
            print(f"[UPDATE #{update_count}] {symbol_str} - Bid: {bid:.2f} Ask: {ask:.2f}")
            print(f"  Bid Vol: {book_data.get('bid_volume_1', 0)}")
            print(f"  Ask Vol: {book_data.get('ask_volume_1', 0)}")
            last_bid = bid
            last_ask = ask
            
            if bid > 0 and ask > 0:
                print("[SUCCESS] ✅ Recebendo dados REAIS do mercado!")
                return True
        
        return False
    
    # Registrar callback
    connection.set_offer_book_callback(book_callback)
    
    # Conectar
    print("[CONNECTING] Conectando ao ProfitChart...")
    if connection.connect():
        print("[OK] Conectado com sucesso!")
        
        # Subscrever ao símbolo
        print(f"[SUBSCRIBE] Subscrevendo ao {symbol}...")
        if connection.subscribe_symbol(symbol):
            print("[OK] Subscrito com sucesso!")
            
            # Aguardar dados
            print("[WAITING] Aguardando dados do mercado...")
            print("(Se não receber dados em 10 segundos, verifique se o ProfitChart está com o símbolo aberto)")
            
            start_time = time.time()
            timeout = 30  # 30 segundos de timeout
            
            while time.time() - start_time < timeout:
                time.sleep(0.1)
                
                if update_count > 0 and update_count % 100 == 0:
                    print(f"[INFO] {update_count} updates recebidos...")
                    if last_bid > 0 and last_ask > 0:
                        print(f"[DATA OK] Último Bid: {last_bid:.2f} Ask: {last_ask:.2f}")
                        break
            
            if last_bid == 0 and last_ask == 0:
                print("\n" + "="*60)
                print("[ERRO] ❌ NÃO está recebendo dados reais!")
                print("\nPossíveis causas:")
                print("1. ProfitChart não está com o símbolo WDOU25 aberto")
                print("2. Mercado está fechado (horário: 9h-18h)")
                print("3. Símbolo incorreto ou expirado")
                print("\nSOLUÇÕES:")
                print("1. Abra o ProfitChart")
                print("2. Adicione um gráfico de WDOU25") 
                print("3. Verifique se está conectado à corretora")
                print("="*60)
            else:
                print("\n" + "="*60)
                print("[SUCCESS] ✅ Sistema recebendo dados REAIS!")
                print(f"Último Bid: {last_bid:.2f}")
                print(f"Último Ask: {last_ask:.2f}")
                print(f"Total updates: {update_count}")
                print("="*60)
        else:
            print("[ERRO] Falha ao subscrever ao símbolo")
    else:
        print("[ERRO] Falha ao conectar")
    
    # Desconectar
    connection.disconnect()
    print("\n[FIM] Teste concluído")

if __name__ == "__main__":
    test_connection()