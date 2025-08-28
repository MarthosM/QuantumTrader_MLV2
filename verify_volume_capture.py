#!/usr/bin/env python3
"""
Script para verificar se o volume está sendo capturado corretamente
"""

import os
import sys
import time
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("\n" + "=" * 60)
    print("VERIFICAÇÃO DE CAPTURA DE VOLUME")
    print("=" * 60)
    print()
    
    # Importar connection manager
    from src.connection_manager_working import ConnectionManagerWorking
    
    # Criar conexão
    print("[1/4] Conectando...")
    dll_path = "ProfitDLL64.dll"
    if not Path(dll_path).exists():
        dll_path = "C:/Users/marth/OneDrive/Programacao/Python/QuantumTrader_Production/ProfitDLL64.dll"
    
    conn = ConnectionManagerWorking(dll_path)
    
    if not conn.connect():
        print("[X] Falha ao conectar")
        return False
    
    print("[OK] Conectado!")
    time.sleep(3)
    
    # Subscribe
    print("\n[2/4] Subscrevendo ao WDOU25...")
    conn.subscribe_symbol("WDOU25")
    time.sleep(2)
    
    # Verificar volume por 30 segundos
    print("\n[3/4] Monitorando volume por 30 segundos...")
    print("-" * 40)
    
    start_time = time.time()
    last_volume = 0
    trades_detected = 0
    
    while time.time() - start_time < 30:
        stats = conn.get_volume_stats()
        current_vol = stats['cumulative_volume']
        
        if current_vol != last_volume:
            trades_detected += 1
            print(f"\n[TRADE #{trades_detected}] Volume mudou!")
            print(f"  Total: {current_vol} contratos")
            print(f"  Último: {stats['current_volume']} contratos")
            print(f"  Buy: {stats['buy_volume']} | Sell: {stats['sell_volume']}")
            print(f"  Delta: {stats['delta_volume']}")
            
            if stats.get('last_trade'):
                trade = stats['last_trade']
                trade_type = 'BUY' if trade.get('trade_type') == 2 else 'SELL'
                print(f"  Tipo: {trade_type} @ R$ {trade['price']:.2f}")
            
            last_volume = current_vol
        
        # Mostrar . para indicar que está rodando
        print(".", end="", flush=True)
        time.sleep(1)
    
    # Resultado final
    print("\n\n[4/4] RESULTADO DA VERIFICAÇÃO")
    print("=" * 60)
    
    final_stats = conn.get_volume_stats()
    
    if final_stats['cumulative_volume'] > 0:
        print(f"✅ SUCESSO! Volume capturado: {final_stats['cumulative_volume']} contratos")
        print(f"   Buy: {final_stats['buy_volume']} contratos")
        print(f"   Sell: {final_stats['sell_volume']} contratos")
        print(f"   Delta: {final_stats['delta_volume']}")
        success = True
    else:
        print("❌ PROBLEMA: Nenhum volume capturado")
        print("   Possíveis causas:")
        print("   1. Mercado sem negociação no momento")
        print("   2. Callback não está funcionando")
        print("   3. ConnectionManager não usa connection_manager_working.py")
        success = False
    
    # Desconectar
    conn.disconnect()
    print("\nVerificação concluída!")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)