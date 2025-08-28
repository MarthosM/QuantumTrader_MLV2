"""
Debug detalhado da conexão com ProfitDLL
Captura informações sobre o erro "Illegal instruction"
"""

import os
import sys
import time
import logging
import faulthandler
import traceback
import platform
from ctypes import *
from dotenv import load_dotenv

# Habilitar faulthandler para capturar segfaults
faulthandler.enable()

# Configurar logging detalhado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Carregar variáveis
load_dotenv()

def print_system_info():
    """Imprime informações do sistema"""
    print("=" * 80)
    print("INFORMAÇÕES DO SISTEMA")
    print("=" * 80)
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Machine: {platform.machine()}")
    print(f"Processor: {platform.processor()}")
    print(f"Architecture: {platform.architecture()}")
    print(f"Python build: {platform.python_build()}")
    print(f"Python compiler: {platform.python_compiler()}")
    print("=" * 80)

def test_dll_loading():
    """Testa carregamento da DLL diretamente"""
    print("\n[1] Testando carregamento direto da DLL...")
    
    dll_path = r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
    
    if not os.path.exists(dll_path):
        print(f"[ERRO] DLL nao encontrada em: {dll_path}")
        return None
    
    print(f"[OK] DLL encontrada: {dll_path}")
    print(f"   Tamanho: {os.path.getsize(dll_path):,} bytes")
    
    try:
        # Tentar carregar com WinDLL (stdcall)
        print("\n[2] Carregando DLL com WinDLL (stdcall)...")
        dll = WinDLL(dll_path)
        print("[OK] DLL carregada com sucesso!")
        return dll
    except Exception as e:
        print(f"[ERRO] Erro ao carregar DLL: {e}")
        traceback.print_exc()
        return None

def test_dll_functions(dll):
    """Testa funções básicas da DLL"""
    if not dll:
        return
    
    print("\n[3] Testando funções da DLL...")
    
    try:
        # Testar GetDLLVersion se existir
        if hasattr(dll, 'GetDLLVersion'):
            print("   Testando GetDLLVersion...")
            dll.GetDLLVersion.restype = c_int
            version = dll.GetDLLVersion()
            print(f"   [OK] Versão da DLL: {version}")
    except Exception as e:
        print(f"   [ERRO] Erro em GetDLLVersion: {e}")
    
    try:
        # Testar SetServerAndPort
        if hasattr(dll, 'SetServerAndPort'):
            print("   Testando SetServerAndPort...")
            dll.SetServerAndPort.argtypes = [c_wchar_p, c_wchar_p]
            dll.SetServerAndPort.restype = c_int
            result = dll.SetServerAndPort(
                c_wchar_p("producao.nelogica.com.br"),
                c_wchar_p("8184")
            )
            print(f"   [OK] SetServerAndPort retornou: {result}")
    except Exception as e:
        print(f"   [ERRO] Erro em SetServerAndPort: {e}")
        traceback.print_exc()

def test_initialization(dll):
    """Testa inicialização básica"""
    if not dll:
        return
    
    print("\n[4] Testando inicialização...")
    
    username = os.getenv('PROFIT_USERNAME', '')
    password = os.getenv('PROFIT_PASSWORD', '')
    key = os.getenv('PROFIT_KEY', '')
    
    print(f"   Username: {username}")
    print(f"   Key length: {len(key)}")
    
    try:
        # Definir tipos de retorno
        dll.DLLInitializeLogin.restype = c_int
        
        # Criar callbacks vazios para teste
        @WINFUNCTYPE(None, c_int, c_int)
        def empty_state_callback(type, result):
            print(f"   [STATE] Type={type}, Result={result}")
            return
        
        # Outros callbacks vazios
        empty_callback = WINFUNCTYPE(None)()
        
        print("   Chamando DLLInitializeLogin...")
        result = dll.DLLInitializeLogin(
            c_wchar_p(key),
            c_wchar_p(username),
            c_wchar_p(password),
            empty_state_callback,  # StateCallback
            empty_callback,        # HistoryCallback
            empty_callback,        # OrderChangeCallback  
            empty_callback,        # AccountCallback
            empty_callback,        # NewTradeCallback
            empty_callback,        # NewDailyCallback
            empty_callback,        # PriceBookCallback
            empty_callback,        # OfferBookCallback
            empty_callback,        # HistoryTradeCallback
            empty_callback,        # ProgressCallback
            empty_callback         # TinyBookCallback
        )
        
        print(f"   [OK] DLLInitializeLogin retornou: {result}")
        
        # Aguardar um pouco
        print("   Aguardando 5 segundos...")
        for i in range(5):
            time.sleep(1)
            print(f"   {i+1}/5...")
        
        print("   [OK] Teste de inicialização concluído!")
        
    except Exception as e:
        print(f"   [ERRO] Erro na inicialização: {e}")
        traceback.print_exc()

def main():
    """Função principal de debug"""
    print("\n" + "=" * 80)
    print("DEBUG DA CONEXÃO COM PROFITDLL")
    print("=" * 80)
    
    # Informações do sistema
    print_system_info()
    
    try:
        # Testar carregamento da DLL
        dll = test_dll_loading()
        
        if dll:
            # Testar funções básicas
            test_dll_functions(dll)
            
            # Testar inicialização
            test_initialization(dll)
            
            print("\n" + "=" * 80)
            print("[OK] TODOS OS TESTES CONCLUÍDOS!")
            print("=" * 80)
        else:
            print("\n[ERRO] Falha no carregamento da DLL")
            
    except Exception as e:
        print(f"\n[ERRO] ERRO CRÍTICO: {e}")
        traceback.print_exc()
        
        # Tentar obter mais informações
        import sys
        exc_type, exc_value, exc_traceback = sys.exc_info()
        print("\nInformações adicionais do erro:")
        print(f"Tipo: {exc_type}")
        print(f"Valor: {exc_value}")
        print(f"Traceback:")
        traceback.print_tb(exc_traceback)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERRO NA EXECUÇÃO: {e}")
        traceback.print_exc()
    finally:
        print("\nPressione Enter para sair...")
        input()