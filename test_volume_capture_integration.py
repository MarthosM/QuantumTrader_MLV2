#!/usr/bin/env python3
"""
Teste de integração do sistema de captura de volume
Baseado nas análises da pasta analises_claude
"""

import os
import sys
import time
import ctypes
from ctypes import c_char_p, c_void_p, c_int
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_volume_capture():
    """Testa captura de volume usando o novo sistema"""
    
    logger.info("=" * 60)
    logger.info("TESTE DE CAPTURA DE VOLUME - WDO")
    logger.info("=" * 60)
    
    # Importar novo sistema
    from src.market_data.volume_capture_system import WDOVolumeCapture, initialize_volume_capture
    
    # Inicializar captura
    logger.info("Inicializando sistema de captura de volume...")
    volume_system = initialize_volume_capture("ProfitDLL64.dll")
    
    if not volume_system:
        logger.error("Falha ao inicializar sistema de captura")
        return
    
    # Tentar integrar com DLL existente
    try:
        logger.info("Carregando ProfitDLL...")
        dll = ctypes.CDLL("ProfitDLL64.dll")
        
        # Configurar tipos de retorno
        dll.DLLInitialize.argtypes = [c_char_p, c_char_p, c_char_p]
        dll.DLLInitialize.restype = c_int
        
        # Credenciais
        activation_key = os.getenv('PROFIT_KEY', '')
        
        # Login básico
        logger.info("Fazendo login na ProfitDLL...")
        result = dll.DLLInitialize(
            activation_key.encode('utf-16-le'),
            b'',  # Username vazio
            b''   # Password vazio
        )
        
        if result == 0:
            logger.info("Login bem-sucedido!")
            
            # Registrar callback de volume
            logger.info("Registrando callback de volume...")
            if volume_system.register_callback(dll):
                logger.info("Callback registrado com sucesso!")
                
                # Subscribe no WDO
                if hasattr(dll, 'SubscribeTicker'):
                    dll.SubscribeTicker.argtypes = [c_char_p, c_char_p]
                    dll.SubscribeTicker.restype = c_int
                    
                    # Determinar contrato atual
                    contract = "WDOU25"  # Agosto 2025
                    logger.info(f"Subscribing no contrato: {contract}")
                    
                    result = dll.SubscribeTicker(
                        contract.encode('utf-16-le'),
                        b'F\x00'  # Bolsa F
                    )
                    
                    if result == 0:
                        logger.info("Subscribe bem-sucedido!")
                    else:
                        logger.warning(f"Erro no subscribe: {result}")
                
                # Monitorar por 30 segundos
                logger.info("\nMonitorando volume por 30 segundos...")
                logger.info("=" * 60)
                
                for i in range(30):
                    time.sleep(1)
                    
                    # Obter estatísticas
                    stats = volume_system.get_volume_stats()
                    
                    # Exibir a cada 5 segundos
                    if i % 5 == 0:
                        logger.info(f"\n[{datetime.now().strftime('%H:%M:%S')}] Status de Volume:")
                        logger.info(f"  Volume Atual: {stats['current_volume']} contratos")
                        logger.info(f"  Volume Total: {stats['cumulative_volume']} contratos")
                        logger.info(f"  Buy Volume: {stats['buy_volume']}")
                        logger.info(f"  Sell Volume: {stats['sell_volume']}")
                        logger.info(f"  Delta: {stats['delta_volume']}")
                        logger.info(f"  Callbacks: {volume_system.callbacks_received}")
                        logger.info(f"  Volumes Capturados: {volume_system.volumes_captured}")
                        
                        if stats['last_trade']:
                            logger.info(f"  Último Trade: {stats['last_trade']['volume']} @ {stats['last_trade']['price']}")
                
                # Resultado final
                logger.info("\n" + "=" * 60)
                logger.info("RESULTADO FINAL:")
                final_stats = volume_system.get_volume_stats()
                
                if final_stats['cumulative_volume'] > 0:
                    logger.info("✅ SUCESSO! Volume capturado corretamente!")
                    logger.info(f"Total capturado: {final_stats['cumulative_volume']} contratos")
                    
                    # Exibir volume profile
                    profile = volume_system.get_volume_profile()
                    if profile:
                        logger.info("\nVolume por Preço:")
                        for price, vol in sorted(profile.items())[:10]:
                            logger.info(f"  R$ {price:.2f}: {vol['total']} contratos (Buy: {vol['buy']}, Sell: {vol['sell']})")
                else:
                    logger.warning("⚠️ Nenhum volume capturado")
                    logger.info("Possíveis causas:")
                    logger.info("  1. Mercado fechado (horário: 9h-18h)")
                    logger.info("  2. Callback não está sendo chamado")
                    logger.info("  3. Estrutura de decodificação incorreta")
                    
            else:
                logger.error("Falha ao registrar callback")
                
        else:
            logger.error(f"Falha no login: {result}")
            
    except Exception as e:
        logger.error(f"Erro no teste: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if hasattr(dll, 'DLLFinalize'):
            dll.DLLFinalize()
            logger.info("DLL finalizada")

def test_alternative_callback():
    """Testa método alternativo usando callback no login"""
    
    logger.info("\n" + "=" * 60)
    logger.info("TESTE ALTERNATIVO - CALLBACK NO LOGIN")
    logger.info("=" * 60)
    
    from src.market_data.volume_capture_system import WDOVolumeCapture
    
    # Criar sistema
    volume_system = WDOVolumeCapture("ProfitDLL64.dll")
    volume_system.initialize()
    
    try:
        dll = ctypes.CDLL("ProfitDLL64.dll")
        
        # DLLInitializeLogin com callbacks
        dll.DLLInitializeLogin.argtypes = [
            c_char_p,  # Key
            c_char_p,  # User
            c_char_p,  # Pass
            c_void_p,  # StateCallback
            c_void_p,  # HistoryCallback
            c_void_p,  # OrderChangeCallback
            c_void_p,  # AccountCallback
            c_void_p,  # NewTradeCallback <- AQUI!
            c_void_p,  # NewDailyCallback
            c_void_p,  # PriceBookCallback
            c_void_p,  # OfferBookCallback
            c_void_p,  # HistoryTradeCallback
            c_void_p,  # ProgressCallback
            c_void_p   # TinyBookCallback
        ]
        dll.DLLInitializeLogin.restype = c_int
        
        activation_key = os.getenv('PROFIT_KEY', '')
        
        logger.info("Fazendo login com callback de trade...")
        result = dll.DLLInitializeLogin(
            activation_key.encode('utf-16-le'),
            b'',  # User
            b'',  # Pass
            None,  # StateCallback
            None,  # HistoryCallback
            None,  # OrderChangeCallback
            None,  # AccountCallback
            volume_system.trade_callback,  # NewTradeCallback
            None,  # NewDailyCallback
            None,  # PriceBookCallback
            None,  # OfferBookCallback
            None,  # HistoryTradeCallback
            None,  # ProgressCallback
            None   # TinyBookCallback
        )
        
        if result == 0:
            logger.info("Login com callback bem-sucedido!")
            volume_system.is_connected = True
            
            # Aguardar dados
            logger.info("Aguardando dados de volume...")
            time.sleep(10)
            
            stats = volume_system.get_volume_stats()
            logger.info(f"Volume capturado: {stats['cumulative_volume']} contratos")
            
        else:
            logger.error(f"Falha no login: {result}")
            
    except Exception as e:
        logger.error(f"Erro no teste alternativo: {e}")

if __name__ == "__main__":
    print("\nTESTE DE CAPTURA DE VOLUME DO WDO")
    print("Baseado nas análises da pasta analises_claude")
    print("-" * 60)
    
    # Teste principal
    test_volume_capture()
    
    # Se não funcionar, tentar alternativa
    print("\nDeseja testar método alternativo? (s/n): ", end="")
    if input().lower() == 's':
        test_alternative_callback()
    
    print("\nTeste concluído!")