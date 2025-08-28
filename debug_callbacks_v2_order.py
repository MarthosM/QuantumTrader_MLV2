"""
Debug da ordem de registro dos callbacks V2
Testa registrar antes vs depois da inicialização
"""

import os
import sys
import time
import logging
import faulthandler
from ctypes import *
from dotenv import load_dotenv

faulthandler.enable()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv('.env.production')

# Estruturas
class TAssetID(Structure):
    _fields_ = [
        ("pwcTicker", c_wchar_p),
        ("pwcBolsa", c_wchar_p),
        ("nFeed", c_int)
    ]

def test_callback_order():
    """Testa ordem de registro dos callbacks"""
    
    print("\n" + "=" * 80)
    print("TESTE DE ORDEM DE REGISTRO DOS CALLBACKS V2")
    print("=" * 80)
    
    dll_path = r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
    dll = WinDLL(dll_path)
    
    # Configurar servidor
    dll.SetServerAndPort(c_wchar_p("producao.nelogica.com.br"), c_wchar_p("8184"))
    
    # Estados
    states = {'market_connected': False, 'callback_count': 0}
    
    # Callbacks
    @WINFUNCTYPE(None, c_int, c_int)
    def state_callback(conn_type, result):
        if conn_type == 2 and result == 4:
            states['market_connected'] = True
            print("  [STATE] Market Data conectado")
    
    # Callback V1 original para comparação
    @WINFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
               c_longlong, c_double, c_char, c_char, c_char, c_char,
               c_char, c_wchar_p, c_void_p, c_void_p)
    def offer_book_v1(asset_id, broker_id, position, side, volume, quantity,
                     offer_id, price, has_price, has_quantity, has_date,
                     has_offer_id, is_edit, date, book_array, reserved):
        states['callback_count'] += 1
        print(f"  [BOOK V1] Callback #{states['callback_count']}")
        return 0
    
    empty_callback = WINFUNCTYPE(None)()
    
    print("\n[TESTE 1] Callback V1 no DLLInitializeLogin")
    print("-" * 40)
    
    # Inicializar com callback V1
    username = os.getenv('PROFIT_USERNAME', '')
    password = os.getenv('PROFIT_PASSWORD', '')
    key = os.getenv('PROFIT_KEY', '')
    
    result = dll.DLLInitializeLogin(
        c_wchar_p(key), c_wchar_p(username), c_wchar_p(password),
        state_callback,     # StateCallback
        empty_callback,     # HistoryCallback
        empty_callback,     # OrderChangeCallback
        empty_callback,     # AccountCallback
        empty_callback,     # NewTradeCallback
        empty_callback,     # NewDailyCallback
        empty_callback,     # PriceBookCallback
        offer_book_v1,      # OfferBookCallback V1
        empty_callback,     # HistoryTradeCallback
        empty_callback,     # ProgressCallback
        empty_callback      # TinyBookCallback
    )
    print(f"  Inicializado: {result}")
    
    # Aguardar e subscrever
    time.sleep(3)
    print("  Subscrevendo ao book...")
    dll.SubscribeOfferBook(c_wchar_p("WDOU25"), c_wchar_p("F"))
    
    print("  Aguardando 5 segundos...")
    time.sleep(5)
    print(f"  Callbacks V1 recebidos: {states['callback_count']}")
    
    # Finalizar para próximo teste
    dll.DLLFinalize()
    time.sleep(1)
    
    # TESTE 2: Registrar V2 APÓS inicialização
    print("\n[TESTE 2] SetOfferBookCallbackV2 APOS inicializacao")
    print("-" * 40)
    
    states['callback_count'] = 0
    
    # Callback V2
    @WINFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
               c_longlong, c_double, c_char, c_char, c_char, c_char, 
               c_char, c_wchar_p, c_void_p, c_void_p)
    def offer_book_v2(asset_id, action, position, side, qtd, agent,
                     offer_id, price, has_price, has_qtd, has_date,
                     has_offer_id, has_agent, date_ptr, array_sell, array_buy):
        states['callback_count'] += 1
        print(f"  [BOOK V2] Callback #{states['callback_count']}")
        return 0
    
    # Inicializar primeiro SEM callback de book
    result = dll.DLLInitializeLogin(
        c_wchar_p(key), c_wchar_p(username), c_wchar_p(password),
        state_callback,     # StateCallback
        empty_callback,     # HistoryCallback
        empty_callback,     # OrderChangeCallback
        empty_callback,     # AccountCallback
        empty_callback,     # NewTradeCallback
        empty_callback,     # NewDailyCallback
        empty_callback,     # PriceBookCallback
        empty_callback,     # OfferBookCallback (vazio!)
        empty_callback,     # HistoryTradeCallback
        empty_callback,     # ProgressCallback
        empty_callback      # TinyBookCallback
    )
    print(f"  Inicializado: {result}")
    
    # Aguardar conexão
    time.sleep(3)
    
    # AGORA registrar callback V2
    print("  Registrando SetOfferBookCallbackV2...")
    if hasattr(dll, 'SetOfferBookCallbackV2'):
        dll.SetOfferBookCallbackV2.restype = c_int
        result = dll.SetOfferBookCallbackV2(offer_book_v2)
        print(f"  SetOfferBookCallbackV2 resultado: {result}")
        
        if result == 0:
            print("  [OK] Callback V2 registrado com sucesso!")
        else:
            print(f"  [ERRO] Falha ao registrar: {result}")
    
    # Subscrever
    print("  Subscrevendo ao book...")
    dll.SubscribeOfferBook(c_wchar_p("WDOU25"), c_wchar_p("F"))
    
    print("  Aguardando 5 segundos...")
    time.sleep(5)
    print(f"  Callbacks V2 recebidos: {states['callback_count']}")
    
    # Finalizar
    dll.DLLFinalize()
    
    print("\n" + "=" * 80)
    print("RESUMO DOS TESTES")
    print("=" * 80)
    print("Teste 1 (V1 no init): Funciona")
    print("Teste 2 (V2 apos init): A verificar")
    
if __name__ == "__main__":
    try:
        test_callback_order()
    except Exception as e:
        print(f"\n[ERRO]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n" + "=" * 80)