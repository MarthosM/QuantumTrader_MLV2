#!/usr/bin/env python3
"""
Script para limpar as ordens órfãs ATUAIS do sistema
Específico para a situação atual onde há grupos OCO mas sem posição real
"""

import os
import sys
from pathlib import Path
from ctypes import WinDLL, c_char_p, c_int, c_longlong
from dotenv import load_dotenv
import json
from datetime import datetime

# Carregar configurações
load_dotenv('.env.production')

def cleanup_current_orphans():
    """Limpa as ordens órfãs atuais"""
    
    print("\n" + "="*70)
    print("LIMPEZA DE ORDENS ÓRFÃS ATUAIS")
    print("="*70)
    
    # IDs conhecidos das últimas ordens (baseado no log)
    # Última posição: POS_20250822_125637
    # Stop: 25082212555332
    # Take: 25082212555333
    
    known_orphan_orders = [
        25082212555332,  # Stop da última posição
        25082212555333,  # Take da última posição
    ]
    
    print("\n[INFO] Ordens órfãs conhecidas:")
    for order_id in known_orphan_orders:
        print(f"  - {order_id}")
    
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
            print(f"\n[OK] DLL encontrada: {dll_path}")
            break
    
    if not dll_path:
        print("\n[ERRO] ProfitDLL64.dll não encontrada!")
        return False
    
    try:
        # Carregar DLL
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
            print("[ERRO] Credenciais não configuradas")
            return False
        
        result = dll.Initialize(key, username, password)
        if result != 0:
            print(f"[OK] Login realizado")
        else:
            print("[ERRO] Falha no login")
            return False
        
        # Configurar CancelOrder
        dll.CancelOrder.argtypes = [c_longlong]
        dll.CancelOrder.restype = c_int
        
        # Cancelar ordens conhecidas
        print("\n3. Cancelando ordens órfãs...")
        
        for order_id in known_orphan_orders:
            print(f"\n  Cancelando ordem {order_id}...")
            try:
                result = dll.CancelOrder(c_longlong(order_id))
                if result == 0:
                    print(f"  [OK] Ordem {order_id} cancelada com sucesso")
                elif result == -2147483645:
                    print(f"  [INFO] Ordem {order_id} já não existe ou já foi executada")
                else:
                    print(f"  [AVISO] Retorno ao cancelar {order_id}: {result}")
            except Exception as e:
                print(f"  [ERRO] Falha ao cancelar {order_id}: {e}")
        
        # Tentar limpar arquivo de grupos OCO também
        print("\n4. Limpando arquivos de estado OCO...")
        
        # Limpar arquivo de status do OCO Monitor se existir
        oco_files = [
            'oco_groups.json',
            'data/monitor/oco_status.json',
            'data/oco_monitor_state.json'
        ]
        
        for file in oco_files:
            if Path(file).exists():
                try:
                    # Fazer backup
                    backup = f"{file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    Path(file).rename(backup)
                    print(f"  [OK] {file} -> {backup}")
                except Exception as e:
                    print(f"  [AVISO] Erro ao mover {file}: {e}")
        
        # Criar arquivo vazio de grupos OCO
        empty_oco = {
            "oco_groups": {},
            "last_update": datetime.now().isoformat()
        }
        
        try:
            with open('oco_groups.json', 'w') as f:
                json.dump(empty_oco, f, indent=2)
            print("  [OK] Arquivo oco_groups.json resetado")
        except:
            pass
        
        # Finalizar
        print("\n5. Finalizando...")
        try:
            dll.Finalize.argtypes = []
            dll.Finalize.restype = None
            dll.Finalize()
            print("[OK] Conexão finalizada")
        except:
            pass
        
        print("\n" + "="*70)
        print("LIMPEZA CONCLUÍDA")
        print("="*70)
        print("\nAções realizadas:")
        print("1. Ordens órfãs canceladas (ou já não existem)")
        print("2. Arquivos de estado OCO limpos")
        print("\nPróximos passos:")
        print("1. Reinicie o sistema de trading")
        print("2. O sistema deve estar limpo para novos trades")
        
        return True
        
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*80)
    print(" LIMPEZA DE ORDENS ÓRFÃS ESPECÍFICAS")
    print("="*80)
    print("\nEste script cancela as ordens órfãs conhecidas:")
    print("- Stop: 25082212555332")
    print("- Take: 25082212555333")
    print("\n[AVISO] Certifique-se que a posição já foi fechada!")
    
    print("\nDeseja continuar? (S/N)")
    if input("> ").strip().upper() == 'S':
        success = cleanup_current_orphans()
        sys.exit(0 if success else 1)
    else:
        print("\nOperação cancelada.")
        sys.exit(0)