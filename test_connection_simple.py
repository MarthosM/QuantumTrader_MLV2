"""
Teste simples de conexão com ProfitDLL
Sem callbacks V2 problemáticos
"""

import os
import time
import logging
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carregar variáveis
load_dotenv()

def test_connection():
    """Testa conexão básica com Profit"""
    try:
        from src.connection_manager_v4 import ConnectionManagerV4
        
        # Criar connection manager
        dll_path = r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
        connection = ConnectionManagerV4(dll_path)
        
        # Inicializar
        username = os.getenv('PROFIT_USERNAME', '')
        password = os.getenv('PROFIT_PASSWORD', '')
        key = os.getenv('PROFIT_KEY', '')
        
        logger.info(f"Conectando com usuário: {username}")
        
        if connection.initialize(username=username, password=password, key=key):
            logger.info("✅ Conexão estabelecida com sucesso!")
            
            # Aguardar um pouco
            logger.info("Aguardando 10 segundos...")
            time.sleep(10)
            
            # Verificar estados
            logger.info(f"Login conectado: {connection.login_state == 0}")
            logger.info(f"Routing conectado: {connection.routing_connected}")
            logger.info(f"Market conectado: {connection.market_connected}")
            
            # Tentar subscrever ao book
            symbol = "WDOU25"
            logger.info(f"Tentando subscrever ao book de {symbol}...")
            
            if hasattr(connection, 'subscribe_offer_book'):
                if connection.subscribe_offer_book(symbol):
                    logger.info(f"✅ Subscrito ao offer book de {symbol}")
                else:
                    logger.warning(f"❌ Falha ao subscrever offer book")
            
            # Manter rodando por 30 segundos
            logger.info("Sistema rodando por 30 segundos...")
            for i in range(30):
                time.sleep(1)
                if i % 5 == 0:
                    logger.info(f"Rodando... {i}/30s")
            
            logger.info("✅ Teste concluído com sucesso!")
            return True
            
        else:
            logger.error("❌ Falha na conexão")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("=== TESTE DE CONEXÃO SIMPLES ===")
    success = test_connection()
    
    if success:
        logger.info("✅ TESTE PASSOU!")
    else:
        logger.error("❌ TESTE FALHOU!")