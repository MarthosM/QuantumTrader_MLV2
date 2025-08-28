"""
Debug específico para subscription de book
Testa onde ocorre o erro "Illegal instruction"
"""

import os
import sys
import time
import logging
import faulthandler
import traceback
from ctypes import *
from dotenv import load_dotenv

# Habilitar faulthandler
faulthandler.enable()

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

def test_subscription():
    """Testa subscrição ao book"""
    print("\n" + "=" * 80)
    print("TESTE DE SUBSCRIPTION")
    print("=" * 80)
    
    dll_path = r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
    
    try:
        # Carregar DLL
        print("\n[1] Carregando DLL...")
        dll = WinDLL(dll_path)
        print("[OK] DLL carregada")
        
        # Configurar servidor
        print("\n[2] Configurando servidor...")
        dll.SetServerAndPort.argtypes = [c_wchar_p, c_wchar_p]
        dll.SetServerAndPort.restype = c_int
        dll.SetServerAndPort(c_wchar_p("producao.nelogica.com.br"), c_wchar_p("8184"))
        print("[OK] Servidor configurado")
        
        # Preparar callbacks
        print("\n[3] Preparando callbacks...")
        
        state_events = []
        
        @WINFUNCTYPE(None, c_int, c_int)
        def state_callback(type, result):
            state_events.append((type, result))
            if len(state_events) <= 20:
                print(f"   [STATE] Type={type}, Result={result}")
        
        # Callback vazio para outros
        empty_callback = WINFUNCTYPE(None)()
        
        # Inicializar
        print("\n[4] Inicializando DLL...")
        username = os.getenv('PROFIT_USERNAME', '')
        password = os.getenv('PROFIT_PASSWORD', '')
        key = os.getenv('PROFIT_KEY', '')
        
        dll.DLLInitializeLogin.restype = c_int
        result = dll.DLLInitializeLogin(
            c_wchar_p(key),
            c_wchar_p(username),
            c_wchar_p(password),
            state_callback,
            empty_callback, empty_callback, empty_callback,
            empty_callback, empty_callback, empty_callback,
            empty_callback, empty_callback, empty_callback,
            empty_callback
        )
        print(f"[OK] DLL inicializada: {result}")
        
        # Aguardar conexão
        print("\n[5] Aguardando conexão...")
        time.sleep(3)
        
        # Verificar se Market Data conectou (Type=2, Result=4)
        market_connected = any(t == 2 and r == 4 for t, r in state_events)
        if market_connected:
            print("[OK] Market Data conectado!")
        else:
            print("[AVISO] Market Data pode não estar conectado")
        
        # Tentar subscrever ao book
        print("\n[6] Tentando subscrever ao book...")
        symbol = "WDOU25"
        
        if hasattr(dll, 'SubscribeOfferBook'):
            print(f"   Subscrevendo ao offer book de {symbol}...")
            dll.SubscribeOfferBook.argtypes = [c_wchar_p, c_wchar_p]
            dll.SubscribeOfferBook.restype = c_int
            
            result = dll.SubscribeOfferBook(
                c_wchar_p(symbol),
                c_wchar_p("F")  # F = Futuros
            )
            print(f"   [RESULTADO] SubscribeOfferBook retornou: {result}")
            
            # Aguardar um pouco
            print("\n[7] Aguardando 10 segundos para testar estabilidade...")
            for i in range(10):
                time.sleep(1)
                print(f"   {i+1}/10...")
                
        print("\n[OK] TESTE CONCLUIDO SEM ERROS!")
        
        # Finalizar
        if hasattr(dll, 'DLLFinalize'):
            print("\n[8] Finalizando DLL...")
            dll.DLLFinalize()
            print("[OK] DLL finalizada")
            
    except Exception as e:
        print(f"\n[ERRO] Excecao capturada: {e}")
        traceback.print_exc()
        
        # Informações adicionais
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print(f"\nTipo do erro: {exc_type}")
        print(f"Valor: {exc_value}")

if __name__ == "__main__":
    try:
        test_subscription()
    except Exception as e:
        print(f"\n[ERRO CRITICO]: {e}")
        traceback.print_exc()
    finally:
        print("\n" + "=" * 80)
        print("FIM DO TESTE")