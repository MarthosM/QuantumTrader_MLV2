"""
Sistema Mínimo com Callbacks V2 Funcionais
Baseado no test_callback_final.py que funcionou
"""

import os
import time
import logging
from ctypes import *
from datetime import datetime
from dotenv import load_dotenv
import threading
from collections import deque

load_dotenv('.env.production')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Estruturas
class TAssetID(Structure):
    _fields_ = [
        ("pwcTicker", c_wchar_p),
        ("pwcBolsa", c_wchar_p),
        ("nFeed", c_int)
    ]

# Buffers para armazenar dados
book_buffer = deque(maxlen=200)
book_lock = threading.RLock()

# Manter referência global aos callbacks
callbacks_refs = []

def main():
    print("\n" + "=" * 80)
    print("SISTEMA MINIMO V2 - COM CALLBACKS FUNCIONAIS")
    print("=" * 80)
    
    # Carregar DLL
    dll_path = r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
    dll = WinDLL(dll_path)
    
    # Configurar servidor
    dll.SetServerAndPort(c_wchar_p("producao.nelogica.com.br"), c_wchar_p("8184"))
    
    # Estado de conexão
    states = {'market_connected': False, 'book_count': 0}
    
    # Callback de estado
    @WINFUNCTYPE(None, c_int, c_int)
    def state_callback(conn_type, result):
        if conn_type == 2 and result == 4:
            states['market_connected'] = True
            print("  [STATE] Market Data conectado")
    
    # Callback V2 para book de ofertas (usando CFUNCTYPE!)
    @CFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
              c_longlong, c_double, c_char, c_char, c_char, c_char,
              c_char, c_wchar_p, c_void_p, c_void_p)
    def offer_book_v2(asset_id, action, position, side, qtd, agent,
                     offer_id, price, has_price, has_qtd, has_date,
                     has_offer_id, has_agent, date_ptr, array_sell, array_buy):
        try:
            # Acessar campos com segurança
            ticker = "N/A"
            if asset_id and hasattr(asset_id, 'pwcTicker') and asset_id.pwcTicker:
                ticker = asset_id.pwcTicker
            
            # Processar apenas dados com preço válido
            if has_price and price > 0:
                book_data = {
                    'timestamp': datetime.now(),
                    'ticker': ticker,
                    'side': 'BUY' if side == 0 else 'SELL',
                    'price': price,
                    'quantity': qtd,
                    'action': action  # 0=Add, 1=Update, 2=Remove
                }
                
                # Adicionar ao buffer
                with book_lock:
                    book_buffer.append(book_data)
                    states['book_count'] += 1
                
                # Log apenas primeiras mensagens
                if states['book_count'] <= 10:
                    print(f"  [BOOK] {ticker} - {book_data['side']}: {price:.2f} x {qtd}")
                elif states['book_count'] % 100 == 0:
                    print(f"  [BOOK] {states['book_count']} mensagens recebidas")
            
            return 0
        except Exception as e:
            logger.error(f"Erro no callback: {e}")
            return 0
    
    # Manter referências
    callbacks_refs.append(state_callback)
    callbacks_refs.append(offer_book_v2)
    
    # Callbacks vazios
    empty = WINFUNCTYPE(None)()
    
    # Inicializar DLL
    print("\n[1] Inicializando DLL...")
    username = os.getenv('PROFIT_USERNAME', '')
    password = os.getenv('PROFIT_PASSWORD', '')
    key = os.getenv('PROFIT_KEY', '')
    
    result = dll.DLLInitializeLogin(
        c_wchar_p(key), c_wchar_p(username), c_wchar_p(password),
        state_callback, empty, empty, empty,
        empty, empty, empty, empty,
        empty, empty, empty
    )
    print(f"  Resultado inicialização: {result}")
    
    # Aguardar conexão
    print("\n[2] Aguardando conexão...")
    for i in range(10):
        if states['market_connected']:
            print("  [OK] Conectado ao Market Data!")
            break
        time.sleep(1)
        if i % 3 == 0:
            print(f"  Aguardando... ({i}/10s)")
    
    # Registrar callback V2
    print("\n[3] Registrando SetOfferBookCallbackV2...")
    dll.SetOfferBookCallbackV2.restype = c_int
    result = dll.SetOfferBookCallbackV2(offer_book_v2)
    print(f"  Resultado: {result}")
    
    if result == 0:
        print("  [OK] Callback V2 registrado com sucesso!")
        
        # Subscrever ao book
        print("\n[4] Subscrevendo ao book...")
        dll.SubscribeOfferBook(c_wchar_p("WDOU25"), c_wchar_p("F"))
        print("  [OK] Subscrito a WDOU25")
        
        # Loop principal
        print("\n[5] Sistema rodando...")
        print("  Pressione Ctrl+C para parar")
        print("\n" + "-" * 40)
        
        try:
            last_log_time = time.time()
            while True:
                # Log periódico
                if time.time() - last_log_time > 10:
                    with book_lock:
                        buffer_size = len(book_buffer)
                        total_msgs = states['book_count']
                    
                    print(f"\n[STATUS] Buffer: {buffer_size}/200 | Total msgs: {total_msgs}")
                    
                    # Mostrar últimas 3 mensagens do buffer
                    if buffer_size > 0:
                        print("  Últimas mensagens:")
                        with book_lock:
                            for msg in list(book_buffer)[-3:]:
                                print(f"    {msg['timestamp'].strftime('%H:%M:%S')} - "
                                     f"{msg['side']}: {msg['price']:.2f} x {msg['quantity']}")
                    
                    last_log_time = time.time()
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\n[INFO] Parando sistema...")
    else:
        print(f"  [ERRO] Falha ao registrar callback: {result}")
    
    # Finalizar
    print("\n[6] Finalizando...")
    dll.DLLFinalize()
    
    print("\n" + "=" * 80)
    print("SISTEMA FINALIZADO")
    print(f"Total de mensagens recebidas: {states['book_count']}")
    print("=" * 80)

if __name__ == "__main__":
    main()