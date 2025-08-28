"""
Debug das convenções de chamada dos callbacks
Testa stdcall vs cdecl
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

def test_conventions():
    """Testa diferentes convenções de chamada"""
    
    print("\n" + "=" * 80)
    print("TESTE DE CONVENCOES DE CHAMADA")
    print("=" * 80)
    
    dll_path = r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
    dll = WinDLL(dll_path)  # WinDLL = stdcall
    
    # Configurar
    dll.SetServerAndPort(c_wchar_p("producao.nelogica.com.br"), c_wchar_p("8184"))
    
    # Callbacks básicos
    @WINFUNCTYPE(None, c_int, c_int)
    def state_callback(conn_type, result):
        if conn_type == 2 and result == 4:
            print("  [STATE] Market Data conectado")
    
    empty_callback = WINFUNCTYPE(None)()
    
    # Inicializar
    username = os.getenv('PROFIT_USERNAME', '')
    password = os.getenv('PROFIT_PASSWORD', '')
    key = os.getenv('PROFIT_KEY', '')
    
    result = dll.DLLInitializeLogin(
        c_wchar_p(key), c_wchar_p(username), c_wchar_p(password),
        state_callback, empty_callback, empty_callback, empty_callback,
        empty_callback, empty_callback, empty_callback, empty_callback,
        empty_callback, empty_callback, empty_callback
    )
    print(f"DLL inicializada: {result}")
    
    time.sleep(3)
    
    # TESTE 1: WINFUNCTYPE (stdcall) - já testado e falha
    print("\n[TESTE 1] WINFUNCTYPE (stdcall)")
    print("-" * 40)
    
    # TESTE 2: CFUNCTYPE (cdecl)
    print("\n[TESTE 2] CFUNCTYPE (cdecl)")
    print("-" * 40)
    
    try:
        @CFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
                  c_longlong, c_double, c_char, c_char, c_char, c_char,
                  c_char, c_wchar_p, c_void_p, c_void_p)
        def offer_book_cdecl(asset_id, action, position, side, qtd, agent,
                            offer_id, price, has_price, has_qtd, has_date,
                            has_offer_id, has_agent, date_ptr, array_sell, array_buy):
            print(f"  [BOOK CDECL] Callback chamado!")
            return 0
        
        dll.SetOfferBookCallbackV2.restype = c_int
        result = dll.SetOfferBookCallbackV2(offer_book_cdecl)
        print(f"  SetOfferBookCallbackV2 resultado: {result}")
        
        if result == 0:
            print("  [OK] Registrado com CFUNCTYPE")
            
            # Testar subscrição
            print("  Subscrevendo...")
            dll.SubscribeOfferBook(c_wchar_p("WDOU25"), c_wchar_p("F"))
            print("  Aguardando 3 segundos...")
            time.sleep(3)
            print("  [OK] Sem crash com CFUNCTYPE")
        
    except Exception as e:
        print(f"  [ERRO] Com CFUNCTYPE: {e}")
    
    # TESTE 3: Diferentes números de parâmetros
    print("\n[TESTE 3] Menos parametros (pode ser V1 vs V2)")
    print("-" * 40)
    
    try:
        # Tentar com menos parâmetros (versão antiga?)
        @WINFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_int, c_int,
                    c_longlong, c_double, c_void_p, c_void_p)
        def offer_book_simple(asset_id, action, position, side, quantity, agent,
                             offer_id, price, array_sell, array_buy):
            print(f"  [BOOK SIMPLE] Callback chamado!")
            return 0
        
        result = dll.SetOfferBookCallbackV2(offer_book_simple)
        print(f"  SetOfferBookCallbackV2 resultado: {result}")
        
        if result == 0:
            print("  [OK] Registrado com menos parametros")
            time.sleep(2)
            
    except Exception as e:
        print(f"  [ERRO] Com menos parametros: {e}")
    
    # TESTE 4: Verificar se precisa ser persistente
    print("\n[TESTE 4] Callback persistente (manter referencia)")
    print("-" * 40)
    
    # Criar callback como variável global para não ser coletado
    global persistent_callback
    
    @WINFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
                c_longlong, c_double, c_char, c_char, c_char, c_char,
                c_char, c_wchar_p, c_void_p, c_void_p)
    def persistent_offer_book(asset_id, action, position, side, qtd, agent,
                             offer_id, price, has_price, has_qtd, has_date,
                             has_offer_id, has_agent, date_ptr, array_sell, array_buy):
        print(f"  [BOOK PERSISTENT] Callback chamado!")
        return 0
    
    persistent_callback = persistent_offer_book
    
    result = dll.SetOfferBookCallbackV2(persistent_callback)
    print(f"  SetOfferBookCallbackV2 resultado: {result}")
    
    if result == 0:
        print("  [OK] Registrado com referencia persistente")
        dll.SubscribeOfferBook(c_wchar_p("WDOU25"), c_wchar_p("F"))
        print("  Aguardando 5 segundos...")
        time.sleep(5)
        print("  [OK] Teste concluido")
    
    # Finalizar
    dll.DLLFinalize()
    
    print("\n" + "=" * 80)
    print("RESUMO")
    print("=" * 80)
    print("O problema parece ser com a assinatura ou convencao de chamada")
    print("Pode ser necessario verificar a documentacao da DLL v4.0.0.30")

if __name__ == "__main__":
    try:
        test_conventions()
    except Exception as e:
        print(f"\n[ERRO]: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n" + "=" * 80)