"""
Teste final para callbacks V2 com CFUNCTYPE
"""

import os
import time
import logging
from ctypes import *
from dotenv import load_dotenv

load_dotenv('.env.production')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Estrutura
class TAssetID(Structure):
    _fields_ = [
        ("pwcTicker", c_wchar_p),
        ("pwcBolsa", c_wchar_p),
        ("nFeed", c_int)
    ]

# Manter referência global aos callbacks
callbacks_refs = []

def test_callbacks():
    print("\n" + "=" * 80)
    print("TESTE FINAL DE CALLBACKS V2 COM CFUNCTYPE")
    print("=" * 80)
    
    dll = WinDLL(r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll")
    dll.SetServerAndPort(c_wchar_p("producao.nelogica.com.br"), c_wchar_p("8184"))
    
    # Callback de estado
    @WINFUNCTYPE(None, c_int, c_int)
    def state_callback(conn_type, result):
        if conn_type == 2 and result == 4:
            print("  [STATE] Market Data conectado")
    
    # Callback V2 com CFUNCTYPE
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
            
            print(f"  [BOOK V2] {ticker} - Side: {side}, Price: {price:.2f}, Qty: {qtd}")
            return 0
        except Exception as e:
            print(f"  [ERRO] No callback: {e}")
            return 0
    
    # Manter referência
    callbacks_refs.append(offer_book_v2)
    callbacks_refs.append(state_callback)
    
    # Callbacks vazios
    empty = WINFUNCTYPE(None)()
    
    # Inicializar
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
    print(f"  Inicializado: {result}")
    
    # Aguardar conexão
    print("\n[2] Aguardando conexao...")
    time.sleep(3)
    
    # Registrar callback V2
    print("\n[3] Registrando SetOfferBookCallbackV2...")
    dll.SetOfferBookCallbackV2.restype = c_int
    result = dll.SetOfferBookCallbackV2(offer_book_v2)
    print(f"  Resultado: {result}")
    
    if result == 0:
        print("  [OK] Callback V2 registrado com sucesso!")
        
        # Subscrever
        print("\n[4] Subscrevendo ao book...")
        dll.SubscribeOfferBook(c_wchar_p("WDOU25"), c_wchar_p("F"))
        
        print("\n[5] Sistema rodando por 20 segundos...")
        for i in range(20):
            time.sleep(1)
            if i % 5 == 0:
                print(f"  {i}/20 segundos...")
        
        print("\n[OK] TESTE CONCLUIDO SEM ERROS!")
    else:
        print(f"  [ERRO] Falha ao registrar callback: {result}")
    
    # Finalizar
    print("\n[6] Finalizando...")
    dll.DLLFinalize()
    
    print("\n" + "=" * 80)
    print("FIM DO TESTE")
    print("=" * 80)

if __name__ == "__main__":
    test_callbacks()