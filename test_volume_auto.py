#!/usr/bin/env python3
"""
Teste Automático do Sistema de Captura de Volume
Executa sem necessitar input do usuário
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

def main():
    """Teste automático de 30 segundos"""
    
    print("\n" + "=" * 60)
    print("TESTE AUTOMÁTICO DE CAPTURA DE VOLUME")
    print("Duração: 30 segundos")
    print("=" * 60)
    print()
    
    from src.connection_manager_volume_fixed import ConnectionManagerVolumeFixed
    
    # Caminho completo da DLL
    dll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ProfitDLL64.dll")
    logger.info(f"Usando DLL: {dll_path}")
    
    # Criar connection manager
    logger.info("Criando Connection Manager com volume fix...")
    conn_manager = ConnectionManagerVolumeFixed(dll_path)
    
    # Inicializar
    logger.info("Inicializando conexão...")
    if not conn_manager.initialize():
        logger.error("[X] Falha ao inicializar sistema")
        logger.error("Possiveis causas:")
        logger.error("  1. Credenciais nao configuradas (PROFIT_KEY)")
        logger.error("  2. DLL nao encontrada ou incompativel")
        logger.error("  3. Mercado fechado")
        return False
    
    logger.info("[OK] Sistema inicializado com sucesso!")
    
    # Aguardar estabilização
    logger.info("Aguardando 3 segundos para estabilização...")
    time.sleep(3)
    
    # Monitorar por 30 segundos
    logger.info("\n" + "=" * 60)
    logger.info("MONITORANDO VOLUME POR 30 SEGUNDOS")
    logger.info("=" * 60)
    
    start_time = time.time()
    last_log = 0
    volumes_detected = []
    
    while time.time() - start_time < 30:
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
            if book.get('bid', 0) > 0:
                print(f"BOOK:")
                print(f"   Bid: R$ {book.get('bid', 0):.2f} x {book.get('bid_qtd', 0)}")
                print(f"   Ask: R$ {book.get('ask', 0):.2f} x {book.get('ask_qtd', 0)}")
                print(f"   Spread: {book.get('spread', 0):.2f} pts")
            else:
                print("BOOK: Aguardando dados...")
            
            # Volume
            print(f"\nVOLUME:")
            current_vol = stats.get('current_volume', 0)
            cumulative_vol = stats.get('cumulative_volume', 0)
            
            if cumulative_vol > 0:
                volumes_detected.append(current_vol)
                print(f"   [OK] Volume Atual: {current_vol} contratos")
                print(f"   [OK] Volume Total: {cumulative_vol} contratos")
                print(f"   Buy: {stats['buy_volume']} | Sell: {stats['sell_volume']}")
                print(f"   Delta: {stats['delta_volume']} (Buy - Sell)")
                
                # Análise
                if stats['delta_volume'] > 50:
                    print("   >>> Pressao COMPRADORA detectada!")
                elif stats['delta_volume'] < -50:
                    print("   >>> Pressao VENDEDORA detectada!")
            else:
                print(f"   [!] Volume ainda nao capturado")
                print(f"   Callbacks recebidos: {stats.get('callbacks_received', 0)}")
        
        time.sleep(0.5)
    
    # Resultado final
    print("\n" + "=" * 60)
    print("RESULTADO FINAL DO TESTE AUTOMÁTICO")
    print("=" * 60)
    
    final_stats = conn_manager.get_volume_stats()
    
    success = final_stats['cumulative_volume'] > 0
    
    if success:
        print("[OK] SUCESSO! Volume capturado corretamente!")
        print(f"\nEstatisticas Finais:")
        print(f"  Total de Contratos: {final_stats['cumulative_volume']}")
        print(f"  Compras: {final_stats['buy_volume']}")
        print(f"  Vendas: {final_stats['sell_volume']}")
        print(f"  Delta: {final_stats['delta_volume']}")
        print(f"  Trades processados: {final_stats['volumes_captured']}")
        
        if volumes_detected:
            avg_vol = sum(volumes_detected) / len(volumes_detected)
            print(f"  Volume medio por trade: {avg_vol:.1f} contratos")
    else:
        print("[!] ATENCAO: Nenhum volume capturado!")
        print(f"\nCallbacks recebidos: {final_stats.get('callbacks_received', 0)}")
        
        if final_stats.get('callbacks_received', 0) > 0:
            print("\n[!] Callbacks estao sendo recebidos mas volume nao esta sendo decodificado")
            print("Verificar:")
            print("  1. Estrutura TNewTradeCallback")
            print("  2. Parametro nQtd (6o parametro)")
            print("  3. Validacao de volume (1-10000 contratos)")
        else:
            print("\n[X] Nenhum callback de trade recebido")
            print("Possíveis causas:")
            print("  1. Mercado fechado (horário: 9h-18h)")
            print("  2. Sem negócios no momento")
            print("  3. Callback não registrado corretamente")
    
    # Finalizar
    logger.info("Finalizando conexão...")
    conn_manager.finalize()
    
    print("\n" + "=" * 60)
    print("TESTE CONCLUÍDO")
    print("=" * 60)
    
    return success

if __name__ == "__main__":
    success = main()
    
    # Retornar código de saída apropriado
    sys.exit(0 if success else 1)