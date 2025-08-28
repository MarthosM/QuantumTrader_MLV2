#!/usr/bin/env python3
"""
Teste isolado para identificar crash nas subscrições
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TestSubscription')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_connection_only():
    """Testa apenas conexão sem subscrições"""
    print("\n" + "="*80)
    print(" TESTE 1: Conexão Básica (sem subscrições)")
    print("="*80)
    
    from src.connection_manager_v4 import ConnectionManagerV4
    
    conn = ConnectionManagerV4(dll_path=None)
    
    if conn.initialize(
        key="16168135121806338936",
        username="29936354842",
        password="Ultra3376!"
    ):
        print("[OK] Conexão estabelecida")
        time.sleep(5)
        print("[OK] Sistema estável por 5 segundos")
        conn.disconnect()
        print("[OK] Desconectado com sucesso")
        return True
    else:
        print("[ERRO] Falha na conexão")
        return False

def test_with_subscription():
    """Testa conexão com subscrições"""
    print("\n" + "="*80)
    print(" TESTE 2: Conexão com Subscrições")
    print("="*80)
    
    from src.connection_manager_v4 import ConnectionManagerV4
    
    conn = ConnectionManagerV4(dll_path=None)
    
    if not conn.initialize(
        key="16168135121806338936",
        username="29936354842",
        password="Ultra3376!"
    ):
        print("[ERRO] Falha na conexão")
        return False
    
    print("[OK] Conexão estabelecida")
    
    # Aguardar market data
    print("\n[*] Aguardando Market Data...")
    start = time.time()
    while time.time() - start < 10:
        if conn.market_connected:
            print("[OK] Market Data conectado")
            break
        time.sleep(0.5)
    
    if not conn.market_connected:
        print("[AVISO] Market Data não conectado - continuando teste")
    
    # Testar subscrições uma por vez
    symbol = "WDOU25"
    
    print(f"\n[*] Testando subscribe_offer_book({symbol})...")
    try:
        if hasattr(conn, 'subscribe_offer_book'):
            result = conn.subscribe_offer_book(symbol)
            print(f"  Resultado: {result}")
            
            if result:
                print("  [OK] Subscrição bem-sucedida")
                print("  Aguardando 5 segundos para verificar estabilidade...")
                time.sleep(5)
                print("  [OK] Sistema estável após subscrição")
            else:
                print("  [AVISO] Subscrição falhou")
    except Exception as e:
        print(f"  [ERRO] Exception: {e}")
    
    print("\nDesconectando...")
    conn.disconnect()
    print("[OK] Teste concluído")
    return True

def test_callback_isolation():
    """Testa callbacks isoladamente"""
    print("\n" + "="*80)
    print(" TESTE 3: Callbacks Isolados")
    print("="*80)
    
    from ctypes import CFUNCTYPE, WINFUNCTYPE, c_int, c_double, c_longlong, c_char, c_void_p, c_wchar_p
    from src.profit_dll_structures import TAssetID, TOfferBookCallbackV2
    
    print("\n[*] Testando criação de callback com CFUNCTYPE...")
    try:
        @CFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
                  c_longlong, c_double, c_char, c_char, c_char, c_char,
                  c_char, c_wchar_p, c_void_p, c_void_p)
        def test_callback_cfunc(asset_id, action, position, side, qtd, agent,
                                offer_id, price, has_price, has_qtd, has_date,
                                has_offer_id, has_agent, date_ptr, array_sell, array_buy):
            print("  Callback CFUNCTYPE chamado!")
            return 0
        
        print("  [OK] Callback CFUNCTYPE criado com sucesso")
    except Exception as e:
        print(f"  [ERRO] Falha ao criar CFUNCTYPE: {e}")
    
    print("\n[*] Testando criação de callback com WINFUNCTYPE...")
    try:
        @WINFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
                    c_longlong, c_double, c_char, c_char, c_char, c_char,
                    c_char, c_wchar_p, c_void_p, c_void_p)
        def test_callback_winfunc(asset_id, action, position, side, qtd, agent,
                                  offer_id, price, has_price, has_qtd, has_date,
                                  has_offer_id, has_agent, date_ptr, array_sell, array_buy):
            print("  Callback WINFUNCTYPE chamado!")
            return 0
        
        print("  [OK] Callback WINFUNCTYPE criado com sucesso")
    except Exception as e:
        print(f"  [ERRO] Falha ao criar WINFUNCTYPE: {e}")
    
    print("\n[*] Verificando tipo correto para callbacks V2...")
    print(f"  TOfferBookCallbackV2 é baseado em: {TOfferBookCallbackV2.__name__}")
    
    return True

def main():
    """Executa testes sequencialmente"""
    print("\n" + "="*80)
    print(" DIAGNÓSTICO DE CRASH NAS SUBSCRIÇÕES")
    print("="*80)
    print(f" Horário: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("="*80)
    
    tests = [
        ("Conexão Básica", test_connection_only),
        ("Callbacks Isolados", test_callback_isolation),
        ("Conexão com Subscrições", test_with_subscription)
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            print(f"\nExecutando: {name}")
            result = test_func()
            results.append((name, "OK" if result else "FALHOU"))
            
            if not result:
                print(f"\n[!] Teste '{name}' falhou - parando testes")
                break
                
        except Exception as e:
            print(f"\n[ERRO] Teste '{name}' gerou exception: {e}")
            results.append((name, "ERRO"))
            break
        
        print("\nAguardando 2 segundos antes do próximo teste...")
        time.sleep(2)
    
    print("\n" + "="*80)
    print(" RESUMO DOS TESTES")
    print("="*80)
    
    for name, status in results:
        print(f"  {name}: {status}")
    
    print("="*80)
    
    if all(status == "OK" for _, status in results):
        print("\n[OK] Todos os testes passaram!")
    else:
        print("\n[!] Alguns testes falharam - verificar logs acima")
        print("\nPossíveis causas do crash:")
        print("  1. Incompatibilidade entre CFUNCTYPE e WINFUNCTYPE")
        print("  2. Estrutura TAssetID incorreta")
        print("  3. Callback sendo chamado após garbage collection")
        print("  4. DLL esperando convenção diferente da implementada")

if __name__ == "__main__":
    main()