#!/usr/bin/env python3
"""
SCRIPT DE EMERGÊNCIA - Proteger posição aberta sem ordens de proteção
Verifica se há posição aberta e recria stop/take se necessário
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Carregar configurações
load_dotenv('.env.production')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.connection_manager_oco import ConnectionManagerOCO

def emergency_protect_position():
    """Verifica posição e adiciona proteção se necessário"""
    
    print("\n" + "="*60)
    print("PROTEÇÃO DE EMERGÊNCIA - POSIÇÃO ABERTA")
    print("="*60)
    
    # Configurações
    dll_path = Path("ProfitDLL64.dll")
    
    if not dll_path.exists():
        print(f"[ERRO] DLL não encontrada: {dll_path}")
        return False
    
    # Criar conexão
    print("\n1. Conectando ao sistema...")
    connection = ConnectionManagerOCO(str(dll_path))
    
    # Inicializar
    key = os.getenv('PROFIT_KEY', '')
    username = os.getenv('PROFIT_USERNAME', '')
    password = os.getenv('PROFIT_PASSWORD', '')
    
    if not all([key, username, password]):
        print("[ERRO] Credenciais não configuradas no .env.production")
        return False
    
    print("2. Fazendo login...")
    if not connection.initialize(key, username, password):
        print("[ERRO] Falha no login")
        return False
    
    print("[OK] Login realizado com sucesso")
    
    # Aguardar conexão
    print("\n3. Aguardando conexão com mercado...")
    for i in range(10):
        if connection.bMarketConnected:
            print("[OK] Conectado ao mercado")
            break
        time.sleep(1)
    
    # Verificar posição atual
    print("\n4. Verificando posição atual...")
    symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
    
    has_position = False
    quantity = 0
    side = None
    
    try:
        has_position, quantity, side = connection.check_position_exists(symbol)
        
        if has_position:
            print(f"\n[ALERTA] POSIÇÃO DETECTADA!")
            print(f"  Symbol: {symbol}")
            print(f"  Side: {side}")
            print(f"  Quantity: {quantity}")
            
            # Verificar se há ordens pendentes
            print("\n5. Verificando ordens pendentes...")
            
            has_pending_orders = False
            if hasattr(connection, 'oco_monitor'):
                oco_monitor = connection.oco_monitor
                if hasattr(oco_monitor, 'oco_groups'):
                    for group_id, group in oco_monitor.oco_groups.items():
                        if group.get('active', False):
                            stop_id = group.get('stop_order_id')
                            take_id = group.get('take_order_id')
                            
                            if stop_id or take_id:
                                has_pending_orders = True
                                print(f"[OK] Ordens de proteção encontradas:")
                                print(f"  Stop ID: {stop_id}")
                                print(f"  Take ID: {take_id}")
                                break
            
            if not has_pending_orders:
                print("\n[PERIGO] POSIÇÃO SEM PROTEÇÃO!")
                print("=" * 60)
                
                # Pegar preço atual
                last_price = 0
                if hasattr(connection.dll, 'GetLastPrice'):
                    last_price = connection.dll.GetLastPrice(symbol)
                    print(f"\nPreço atual: {last_price}")
                
                if last_price > 0:
                    # Calcular stop e take baseado no lado da posição
                    if side == "BUY":
                        stop_price = last_price - 5  # 5 pontos abaixo
                        take_price = last_price + 10  # 10 pontos acima
                        print(f"\n[PROTEÇÃO] Criando ordens para posição COMPRADA:")
                    else:  # SELL
                        stop_price = last_price + 5  # 5 pontos acima
                        take_price = last_price - 10  # 10 pontos abaixo
                        print(f"\n[PROTEÇÃO] Criando ordens para posição VENDIDA:")
                    
                    print(f"  Stop Loss: {stop_price:.2f}")
                    print(f"  Take Profit: {take_price:.2f}")
                    
                    # Perguntar confirmação
                    print("\n" + "="*60)
                    print("ATENÇÃO: Deseja criar estas ordens de proteção?")
                    print("Digite 'SIM' para confirmar ou 'NAO' para cancelar:")
                    
                    resposta = input("> ").strip().upper()
                    
                    if resposta == "SIM":
                        print("\n[EXECUTANDO] Criando ordens de proteção...")
                        
                        # Criar ordens OCO
                        try:
                            if side == "BUY":
                                # Para posição comprada: stop é venda, take é venda
                                result = connection.send_oco_order(
                                    symbol=symbol,
                                    side="SELL",
                                    quantity=quantity,
                                    stop_price=stop_price,
                                    take_price=take_price
                                )
                            else:
                                # Para posição vendida: stop é compra, take é compra
                                result = connection.send_oco_order(
                                    symbol=symbol,
                                    side="BUY",
                                    quantity=quantity,
                                    stop_price=stop_price,
                                    take_price=take_price
                                )
                            
                            if result:
                                print("[SUCESSO] Ordens de proteção criadas!")
                                print(f"  Stop Order: {result.get('stop_order')}")
                                print(f"  Take Order: {result.get('take_order')}")
                            else:
                                print("[ERRO] Falha ao criar ordens de proteção")
                        
                        except Exception as e:
                            print(f"[ERRO] Exceção ao criar ordens: {e}")
                    else:
                        print("\n[CANCELADO] Operação cancelada pelo usuário")
                else:
                    print("[ERRO] Não foi possível obter preço atual")
            else:
                print("\n[OK] Posição já está protegida com ordens pendentes")
        else:
            print("\n[INFO] Nenhuma posição aberta detectada")
            
            # Verificar se há ordens órfãs
            print("\n6. Verificando ordens órfãs...")
            orphan_orders = False
            
            if hasattr(connection, 'oco_monitor'):
                oco_monitor = connection.oco_monitor
                if hasattr(oco_monitor, 'oco_groups'):
                    for group_id, group in oco_monitor.oco_groups.items():
                        if group.get('active', False):
                            orphan_orders = True
                            print(f"[AVISO] Grupo OCO órfão encontrado: {group_id}")
                            
                            # Oferecer cancelar
                            print("\nDeseja cancelar estas ordens órfãs? (SIM/NAO):")
                            resposta = input("> ").strip().upper()
                            
                            if resposta == "SIM":
                                try:
                                    connection.cancel_all_pending_orders(symbol)
                                    print("[OK] Ordens órfãs canceladas")
                                except:
                                    print("[ERRO] Falha ao cancelar ordens")
                            break
            
            if not orphan_orders:
                print("[OK] Nenhuma ordem órfã encontrada")
    
    except Exception as e:
        print(f"[ERRO] Falha ao verificar posição: {e}")
        import traceback
        traceback.print_exc()
    
    # Desconectar
    print("\n7. Finalizando...")
    if connection.dll:
        try:
            connection.dll.Finalize()
            print("[OK] Conexão finalizada")
        except:
            pass
    
    print("\n" + "="*60)
    print("VERIFICAÇÃO CONCLUÍDA")
    print("="*60)
    
    return True

if __name__ == "__main__":
    try:
        print("\n" + "="*80)
        print(" SISTEMA DE PROTEÇÃO DE EMERGÊNCIA")
        print("="*80)
        print("\nEste script verifica se há posição aberta sem proteção")
        print("e oferece criar ordens de stop/take se necessário.")
        print("\n[AVISO] Use com cuidado - confirme os valores antes de executar!")
        
        success = emergency_protect_position()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n[CANCELADO] Operação interrompida pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERRO FATAL] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)