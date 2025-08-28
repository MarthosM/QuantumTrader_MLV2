"""
Debug específico dos callbacks V2
Testa diferentes assinaturas e implementações
"""

import os
import sys
import time
import logging
import faulthandler
import traceback
from ctypes import *
from dotenv import load_dotenv

# Habilitar faulthandler para capturar segfaults
faulthandler.enable()

# Logging detalhado
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv('.env.production')

# Estruturas necessárias
class TAssetID(Structure):
    _fields_ = [
        ("pwcTicker", c_wchar_p),
        ("pwcBolsa", c_wchar_p),
        ("nFeed", c_int)
    ]

def test_callback_v2_versions():
    """Testa diferentes versões dos callbacks V2"""
    
    print("\n" + "=" * 80)
    print("DEBUG DE CALLBACKS V2")
    print("=" * 80)
    
    dll_path = r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
    
    try:
        # Carregar DLL
        print("\n[1] Carregando DLL...")
        dll = WinDLL(dll_path)
        print("[OK] DLL carregada")
        
        # Verificar funções disponíveis
        print("\n[2] Verificando funcoes V2 disponiveis...")
        
        v2_functions = [
            'SetOfferBookCallbackV2',
            'SetPriceBookCallbackV2',
            'SetTradeCallbackV2',
            'SetHistoryTradeCallbackV2',
            'SetOrderCallbackV2',
            'SetHistoryCallbackV2'
        ]
        
        available_v2 = []
        for func_name in v2_functions:
            if hasattr(dll, func_name):
                print(f"  [OK] {func_name} disponivel")
                available_v2.append(func_name)
            else:
                print(f"  [--] {func_name} NAO encontrada")
        
        # Testar SetOfferBookCallbackV2 com diferentes assinaturas
        if 'SetOfferBookCallbackV2' in available_v2:
            print("\n[3] Testando SetOfferBookCallbackV2...")
            
            # Versão 1: Assinatura conforme manual
            print("\n  Teste 1: Assinatura do manual")
            try:
                @WINFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
                           c_longlong, c_double, c_char, c_char, c_char, c_char, 
                           c_char, c_wchar_p, c_void_p, c_void_p)
                def offer_book_v2_test1(asset_id, action, position, side, qtd, agent,
                                       offer_id, price, has_price, has_qtd, has_date,
                                       has_offer_id, has_agent, date_ptr, array_sell, array_buy):
                    print(f"    [CALLBACK V2.1] Chamado!")
                    return 0
                
                dll.SetOfferBookCallbackV2.restype = c_int
                result = dll.SetOfferBookCallbackV2(offer_book_v2_test1)
                print(f"    Resultado: {result}")
                
                if result == 0:
                    print("    [OK] Callback V2.1 registrado com sucesso!")
                else:
                    print(f"    [ERRO] Falha ao registrar V2.1: {result}")
                    
            except Exception as e:
                print(f"    [ERRO] Excecao em V2.1: {e}")
            
            # Versão 2: Com POINTER(TAssetID)
            print("\n  Teste 2: Com POINTER(TAssetID)")
            try:
                @WINFUNCTYPE(c_int, POINTER(TAssetID), c_int, c_int, c_int, c_longlong, 
                           c_int, c_longlong, c_double, c_char, c_char, c_char, 
                           c_char, c_char, c_wchar_p, c_void_p, c_void_p)
                def offer_book_v2_test2(asset_id_ptr, action, position, side, qtd, agent,
                                       offer_id, price, has_price, has_qtd, has_date,
                                       has_offer_id, has_agent, date_ptr, array_sell, array_buy):
                    print(f"    [CALLBACK V2.2] Chamado!")
                    return 0
                
                result = dll.SetOfferBookCallbackV2(offer_book_v2_test2)
                print(f"    Resultado: {result}")
                
                if result == 0:
                    print("    [OK] Callback V2.2 registrado com sucesso!")
                else:
                    print(f"    [ERRO] Falha ao registrar V2.2: {result}")
                    
            except Exception as e:
                print(f"    [ERRO] Excecao em V2.2: {e}")
            
            # Versão 3: Sem retorno (void)
            print("\n  Teste 3: Sem retorno (void)")
            try:
                @WINFUNCTYPE(None, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
                           c_longlong, c_double, c_char, c_char, c_char, c_char, 
                           c_char, c_wchar_p, c_void_p, c_void_p)
                def offer_book_v2_test3(asset_id, action, position, side, qtd, agent,
                                       offer_id, price, has_price, has_qtd, has_date,
                                       has_offer_id, has_agent, date_ptr, array_sell, array_buy):
                    print(f"    [CALLBACK V2.3] Chamado!")
                
                result = dll.SetOfferBookCallbackV2(offer_book_v2_test3)
                print(f"    Resultado: {result}")
                
                if result == 0:
                    print("    [OK] Callback V2.3 registrado com sucesso!")
                else:
                    print(f"    [ERRO] Falha ao registrar V2.3: {result}")
                    
            except Exception as e:
                print(f"    [ERRO] Excecao em V2.3: {e}")
        
        # Agora testar com inicialização completa
        print("\n[4] Testando com inicializacao completa...")
        
        # Configurar servidor
        dll.SetServerAndPort(c_wchar_p("producao.nelogica.com.br"), c_wchar_p("8184"))
        
        # Callback de estado
        @WINFUNCTYPE(None, c_int, c_int)
        def state_callback(conn_type, result):
            if conn_type == 2 and result == 4:
                print("  [STATE] Market Data conectado")
        
        # Callback V2 final para teste
        callback_called = [False]
        
        @WINFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
                   c_longlong, c_double, c_char, c_char, c_char, c_char, 
                   c_char, c_wchar_p, c_void_p, c_void_p)
        def offer_book_v2_final(asset_id, action, position, side, qtd, agent,
                               offer_id, price, has_price, has_qtd, has_date,
                               has_offer_id, has_agent, date_ptr, array_sell, array_buy):
            callback_called[0] = True
            try:
                ticker = asset_id.pwcTicker if hasattr(asset_id, 'pwcTicker') else 'N/A'
                print(f"  [BOOK V2] {ticker} - Side: {side}, Price: {price}, Qty: {qtd}")
            except:
                print(f"  [BOOK V2] Callback chamado!")
            return 0
        
        # Registrar callback V2 antes da inicialização
        if 'SetOfferBookCallbackV2' in available_v2:
            print("\n  Registrando callback V2...")
            result = dll.SetOfferBookCallbackV2(offer_book_v2_final)
            print(f"  SetOfferBookCallbackV2 resultado: {result}")
        
        # Callbacks vazios
        empty_callback = WINFUNCTYPE(None)()
        
        # Inicializar
        print("\n  Inicializando DLL...")
        username = os.getenv('PROFIT_USERNAME', '')
        password = os.getenv('PROFIT_PASSWORD', '')
        key = os.getenv('PROFIT_KEY', '')
        
        result = dll.DLLInitializeLogin(
            c_wchar_p(key), c_wchar_p(username), c_wchar_p(password),
            state_callback, empty_callback, empty_callback, empty_callback,
            empty_callback, empty_callback, empty_callback, empty_callback,
            empty_callback, empty_callback, empty_callback
        )
        print(f"  DLL inicializada: {result}")
        
        # Aguardar conexão
        print("\n  Aguardando conexao...")
        time.sleep(3)
        
        # Subscrever ao book
        print("\n  Subscrevendo ao book...")
        dll.SubscribeOfferBook(c_wchar_p("WDOU25"), c_wchar_p("F"))
        
        # Aguardar callbacks
        print("\n  Aguardando callbacks por 10 segundos...")
        for i in range(10):
            time.sleep(1)
            print(f"    {i+1}/10... Callback chamado: {callback_called[0]}")
            if callback_called[0]:
                print("    [OK] Callback V2 funcionando!")
                break
        
        if not callback_called[0]:
            print("    [AVISO] Callback V2 nao foi chamado (normal com mercado fechado)")
        
        # Finalizar
        print("\n[5] Finalizando...")
        if hasattr(dll, 'DLLFinalize'):
            dll.DLLFinalize()
        
        print("\n[OK] TESTE CONCLUIDO!")
        
    except Exception as e:
        print(f"\n[ERRO CRITICO]: {e}")
        traceback.print_exc()
        
        # Informações adicionais
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print(f"\nTipo: {exc_type}")
        print(f"Valor: {exc_value}")

if __name__ == "__main__":
    try:
        test_callback_v2_versions()
    except Exception as e:
        print(f"\n[ERRO]: {e}")
        traceback.print_exc()
    finally:
        print("\n" + "=" * 80)
        print("FIM DO DEBUG")