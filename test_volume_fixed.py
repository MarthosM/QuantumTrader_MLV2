#!/usr/bin/env python3
"""
Teste do Sistema de Captura de Volume Corrigido
Baseado na análise dos arquivos analises_claude
"""

import os
import sys
import time
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_volume_capture():
    """Testa o novo sistema de captura de volume"""
    
    print("\n" + "=" * 60)
    print("TESTE DE CAPTURA DE VOLUME - SISTEMA CORRIGIDO")
    print("=" * 60)
    print()
    
    from src.connection_manager_volume_fixed import ConnectionManagerVolumeFixed
    import os
    
    # Criar connection manager com caminho completo
    logger.info("Criando Connection Manager com volume fix...")
    dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ProfitDLL64.dll")
    conn_manager = ConnectionManagerVolumeFixed(dll_path)
    
    # Inicializar
    logger.info("Inicializando conexão...")
    if conn_manager.initialize():
        logger.info("✅ Sistema inicializado com sucesso!")
        
        # Aguardar estabilização
        logger.info("Aguardando 3 segundos para estabilização...")
        time.sleep(3)
        
        # Monitorar por 60 segundos
        logger.info("\n" + "=" * 60)
        logger.info("MONITORANDO VOLUME POR 60 SEGUNDOS")
        logger.info("=" * 60)
        
        start_time = time.time()
        last_log = 0
        
        while time.time() - start_time < 60:
            current_time = time.time() - start_time
            
            # Log a cada 5 segundos
            if current_time - last_log >= 5:
                last_log = current_time
                
                # Obter estatísticas
                stats = conn_manager.get_volume_stats()
                book = conn_manager.get_current_book()
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Status após {int(current_time)}s:")
                print("-" * 40)
                
                # Book
                print(f"📊 BOOK:")
                print(f"   Bid: R$ {book.get('bid', 0):.2f} x {book.get('bid_qtd', 0)}")
                print(f"   Ask: R$ {book.get('ask', 0):.2f} x {book.get('ask_qtd', 0)}")
                print(f"   Spread: {book.get('spread', 0):.2f}")
                
                # Volume
                print(f"\n📈 VOLUME:")
                print(f"   Volume Atual: {stats['current_volume']} contratos")
                print(f"   Volume Total: {stats['cumulative_volume']} contratos")
                print(f"   Buy Volume: {stats['buy_volume']} contratos")
                print(f"   Sell Volume: {stats['sell_volume']} contratos")
                print(f"   Delta: {stats['delta_volume']} (Buy - Sell)")
                
                if stats['cumulative_volume'] > 0:
                    ratio = stats['buy_volume'] / stats['sell_volume'] if stats['sell_volume'] > 0 else 0
                    print(f"   Ratio B/S: {ratio:.2f}")
                    
                    # Análise de fluxo
                    if stats['delta_volume'] > 50:
                        print("   🟢 Pressão COMPRADORA detectada!")
                    elif stats['delta_volume'] < -50:
                        print("   🔴 Pressão VENDEDORA detectada!")
                    else:
                        print("   ⚪ Mercado equilibrado")
                
                # Debug
                print(f"\n📊 DEBUG:")
                print(f"   Callbacks recebidos: {stats['callbacks_received']}")
                print(f"   Volumes capturados: {stats['volumes_captured']}")
                
                if stats['last_trade']:
                    trade = stats['last_trade']
                    print(f"   Último trade: {trade['volume']} @ R$ {trade['price']:.2f}")
            
            time.sleep(0.5)
        
        # Resultado final
        print("\n" + "=" * 60)
        print("RESULTADO FINAL DO TESTE")
        print("=" * 60)
        
        final_stats = conn_manager.get_volume_stats()
        
        if final_stats['cumulative_volume'] > 0:
            print("✅ SUCESSO! Volume capturado corretamente!")
            print(f"\nEstatísticas Finais:")
            print(f"  Total de Contratos: {final_stats['cumulative_volume']}")
            print(f"  Compras: {final_stats['buy_volume']}")
            print(f"  Vendas: {final_stats['sell_volume']}")
            print(f"  Delta: {final_stats['delta_volume']}")
            print(f"  Trades processados: {final_stats['volumes_captured']}")
            
            # Análise de mercado
            if final_stats['delta_volume'] > 0:
                print(f"\n📊 Análise: Mercado com viés COMPRADOR (+{final_stats['delta_volume']} contratos)")
            else:
                print(f"\n📊 Análise: Mercado com viés VENDEDOR ({final_stats['delta_volume']} contratos)")
                
        else:
            print("⚠️ ATENÇÃO: Nenhum volume capturado!")
            print("\nPossíveis causas:")
            print("  1. Mercado fechado (horário: 9h-18h)")
            print("  2. Sem negócios no momento")
            print("  3. Problema na estrutura do callback")
            print(f"\nCallbacks recebidos: {final_stats['callbacks_received']}")
            
            if final_stats['callbacks_received'] > 0:
                print("  ⚠️ Callbacks estão sendo recebidos mas volume não está sendo decodificado")
                print("  Verificar estrutura TNewTradeCallback")
        
        # Finalizar
        conn_manager.finalize()
        
    else:
        logger.error("❌ Falha ao inicializar sistema")

def monitor_continuous():
    """Monitoramento contínuo de volume"""
    
    print("\nMONITORAMENTO CONTÍNUO DE VOLUME")
    print("Pressione Ctrl+C para parar")
    print("-" * 40)
    
    from src.connection_manager_volume_fixed import ConnectionManagerVolumeFixed
    import os
    
    dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ProfitDLL64.dll")
    conn_manager = ConnectionManagerVolumeFixed(dll_path)
    
    if conn_manager.initialize():
        try:
            last_volume = 0
            
            while True:
                stats = conn_manager.get_volume_stats()
                
                # Só mostra quando há mudança
                if stats['cumulative_volume'] != last_volume:
                    last_volume = stats['cumulative_volume']
                    
                    print(f"\n[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]", end=" ")
                    
                    if stats['last_trade']:
                        trade = stats['last_trade']
                        trade_type = "BUY " if trade['trade_type'] == 2 else "SELL"
                        
                        print(f"{trade_type} {trade['volume']:3d} @ R$ {trade['price']:7.2f}", end=" | ")
                        print(f"Total: {stats['cumulative_volume']:5d} | Delta: {stats['delta_volume']:+4d}")
                
                time.sleep(0.01)  # Check rápido
                
        except KeyboardInterrupt:
            print("\n\nMonitoramento encerrado")
            final = conn_manager.get_volume_stats()
            print(f"Volume Total Capturado: {final['cumulative_volume']} contratos")
            
        finally:
            conn_manager.finalize()

if __name__ == "__main__":
    print("\nTESTE DO SISTEMA DE CAPTURA DE VOLUME")
    print("Baseado na solução encontrada em analises_claude")
    print()
    print("Escolha uma opção:")
    print("1. Teste de 60 segundos")
    print("2. Monitoramento contínuo")
    print("3. Sair")
    
    choice = input("\nOpção: ")
    
    if choice == "1":
        test_volume_capture()
    elif choice == "2":
        monitor_continuous()
    else:
        print("Saindo...")
        
    print("\nTeste concluído!")