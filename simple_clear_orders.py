#!/usr/bin/env python3
"""
Script simplificado para cancelar ordens pendentes
Usa diretamente a DLL sem dependências complexas
"""

import os
import sys
from pathlib import Path
from ctypes import WinDLL, c_char_p, c_int, c_longlong
from dotenv import load_dotenv

# Carregar configurações
load_dotenv('.env.production')

def clear_orders_simple():
    """Cancela ordens pendentes de forma simplificada"""
    
    print("\n" + "="*60)
    print("LIMPEZA SIMPLIFICADA DE ORDENS")
    print("="*60)
    
    # Encontrar DLL
    dll_path = None
    possible_paths = [
        Path("C:/Users/marth/OneDrive/Programacao/Python/QuantumTrader_Production/ProfitDLL64.dll"),
        Path.cwd() / "ProfitDLL64.dll",
        Path("ProfitDLL64.dll")
    ]
    
    for path in possible_paths:
        if path.exists():
            dll_path = str(path.absolute())
            print(f"[OK] DLL encontrada: {dll_path}")
            break
    
    if not dll_path:
        print("[ERRO] ProfitDLL64.dll não encontrada!")
        print("Certifique-se que o arquivo está no diretório do projeto")
        return False
    
    try:
        # Carregar DLL diretamente
        print("\n1. Carregando DLL...")
        dll = WinDLL(dll_path)
        print("[OK] DLL carregada")
        
        # Configurar Initialize
        dll.Initialize.argtypes = [c_char_p, c_char_p, c_char_p]
        dll.Initialize.restype = c_int
        
        # Fazer login
        print("\n2. Fazendo login...")
        key = os.getenv('PROFIT_KEY', '').encode('utf-8')
        username = os.getenv('PROFIT_USERNAME', '').encode('utf-8')
        password = os.getenv('PROFIT_PASSWORD', '').encode('utf-8')
        
        if not all([key, username, password]):
            print("[ERRO] Credenciais não configuradas no .env.production")
            return False
        
        result = dll.Initialize(key, username, password)
        if result != 0:
            print(f"[OK] Login realizado: {result}")
        else:
            print("[ERRO] Falha no login")
            return False
        
        # Cancelar ordens específicas se conhecidas
        print("\n3. Digite os IDs das ordens a cancelar (separados por vírgula)")
        print("   Exemplo: 25082211182827,25082211182828")
        print("   Ou pressione ENTER para pular:")
        
        order_ids_input = input("> ").strip()
        
        if order_ids_input:
            # Configurar CancelOrder
            dll.CancelOrder.argtypes = [c_longlong]
            dll.CancelOrder.restype = c_int
            
            order_ids = [int(oid.strip()) for oid in order_ids_input.split(",")]
            
            for order_id in order_ids:
                print(f"\nCancelando ordem {order_id}...")
                try:
                    result = dll.CancelOrder(c_longlong(order_id))
                    if result == 0:
                        print(f"[OK] Ordem {order_id} cancelada com sucesso")
                    else:
                        print(f"[AVISO] Retorno ao cancelar {order_id}: {result}")
                except Exception as e:
                    print(f"[ERRO] Falha ao cancelar {order_id}: {e}")
        
        # Tentar cancelar todas as ordens pendentes
        print("\n4. Deseja tentar cancelar TODAS as ordens pendentes? (S/N)")
        resposta = input("> ").strip().upper()
        
        if resposta == 'S':
            symbol = os.getenv('TRADING_SYMBOL', 'WDOU25').encode('utf-8')
            
            # Tentar CancelAllOrders se existir
            try:
                dll.CancelAllOrders.argtypes = [c_char_p]
                dll.CancelAllOrders.restype = c_int
                
                result = dll.CancelAllOrders(symbol)
                if result == 0:
                    print(f"[OK] Todas as ordens de {symbol.decode()} canceladas")
                else:
                    print(f"[AVISO] Retorno: {result}")
            except:
                print("[INFO] CancelAllOrders não disponível")
                
                # Alternativa: cancelar uma faixa de IDs
                print("\n   Digite o ID inicial e final para cancelar em lote")
                print("   Exemplo: 25082211182820,25082211182830")
                range_input = input("> ").strip()
                
                if range_input and ',' in range_input:
                    start_id, end_id = map(int, range_input.split(','))
                    
                    for order_id in range(start_id, end_id + 1):
                        try:
                            result = dll.CancelOrder(c_longlong(order_id))
                            if result == 0:
                                print(f"[OK] Ordem {order_id} cancelada")
                        except:
                            pass  # Ignorar erros para IDs inexistentes
        
        # Finalizar
        print("\n5. Finalizando...")
        try:
            dll.Finalize.argtypes = []
            dll.Finalize.restype = None
            dll.Finalize()
            print("[OK] Conexão finalizada")
        except:
            pass
        
        print("\n" + "="*60)
        print("LIMPEZA CONCLUÍDA")
        print("="*60)
        print("\nVerifique no ProfitChart se as ordens foram canceladas.")
        print("Se ainda houver ordens pendentes, cancele manualmente.")
        
        return True
        
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*80)
    print(" LIMPEZA SIMPLIFICADA DE ORDENS PENDENTES")
    print("="*80)
    print("\nEste script cancela ordens pendentes órfãs diretamente via DLL.")
    print("\n[AVISO] Use com cuidado - pode cancelar ordens importantes!")
    
    print("\nDeseja continuar? (S/N)")
    if input("> ").strip().upper() == 'S':
        success = clear_orders_simple()
        sys.exit(0 if success else 1)
    else:
        print("\nOperação cancelada.")
        sys.exit(0)