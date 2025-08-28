"""
Sistema mínimo de trading - versão simplificada e estável
Sem callbacks V2 e componentes problemáticos
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime
from ctypes import *
from dotenv import load_dotenv
from collections import deque

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MinimalSystem')

# Carregar configurações
load_dotenv('.env.production')

class MinimalTradingSystem:
    """Sistema mínimo de trading com ProfitDLL"""
    
    def __init__(self):
        self.dll = None
        self.running = False
        self.symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
        self.dll_path = r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
        
        # Buffers simples
        self.price_buffer = deque(maxlen=100)
        self.trade_count = 0
        
        # Estados de conexão
        self.market_connected = False
        self.routing_connected = False
        
        logger.info("Sistema Minimo inicializado")
        
    def initialize(self):
        """Inicializa conexão com Profit"""
        try:
            print("\n" + "=" * 80)
            print(" SISTEMA MINIMO DE TRADING v1.0")
            print("=" * 80)
            print(f"Simbolo: {self.symbol}")
            print(f"Horario: {datetime.now()}")
            print("=" * 80)
            
            # Carregar DLL
            print("\n[1/4] Carregando DLL...")
            self.dll = WinDLL(self.dll_path)
            print("  [OK] DLL carregada")
            
            # Configurar servidor
            print("\n[2/4] Configurando servidor...")
            self.dll.SetServerAndPort.argtypes = [c_wchar_p, c_wchar_p]
            self.dll.SetServerAndPort.restype = c_int
            self.dll.SetServerAndPort(
                c_wchar_p("producao.nelogica.com.br"),
                c_wchar_p("8184")
            )
            print("  [OK] Servidor configurado")
            
            # Preparar callbacks básicos
            print("\n[3/4] Preparando callbacks...")
            
            @WINFUNCTYPE(None, c_int, c_int)
            def state_callback(conn_type, result):
                try:
                    if conn_type == 2 and result == 4:  # Market Data
                        self.market_connected = True
                        logger.info("[OK] Market Data conectado")
                    elif conn_type == 1 and result == 5:  # Routing
                        self.routing_connected = True
                        logger.info("[OK] Roteamento conectado")
                except:
                    pass
            
            # Callback para trades (simplificado)
            from ctypes import Structure, POINTER
            
            class TAssetID(Structure):
                _fields_ = [
                    ("pwcTicker", c_wchar_p),
                    ("pwcBolsa", c_wchar_p),
                    ("nFeed", c_int)
                ]
            
            @WINFUNCTYPE(None, TAssetID, c_wchar_p, c_int, c_double, c_double, 
                        c_int, c_int, c_int, c_int)
            def trade_callback(asset_id, date, trade_number, price, vol, 
                             qtd, buy_agent, sell_agent, trade_type):
                try:
                    if price > 0:
                        self.price_buffer.append(price)
                        self.trade_count += 1
                        if self.trade_count % 100 == 0:
                            logger.info(f"[TRADE] {self.trade_count} trades recebidos")
                except:
                    pass
            
            # Callbacks vazios
            empty_callback = WINFUNCTYPE(None)()
            
            # Inicializar DLL
            print("\n[4/4] Conectando ao Profit...")
            username = os.getenv('PROFIT_USERNAME', '')
            password = os.getenv('PROFIT_PASSWORD', '')
            key = os.getenv('PROFIT_KEY', '')
            
            self.dll.DLLInitializeLogin.restype = c_int
            result = self.dll.DLLInitializeLogin(
                c_wchar_p(key),
                c_wchar_p(username),
                c_wchar_p(password),
                state_callback,      # StateCallback
                empty_callback,      # HistoryCallback
                empty_callback,      # OrderChangeCallback
                empty_callback,      # AccountCallback
                trade_callback,      # NewTradeCallback
                empty_callback,      # NewDailyCallback
                empty_callback,      # PriceBookCallback
                empty_callback,      # OfferBookCallback
                empty_callback,      # HistoryTradeCallback
                empty_callback,      # ProgressCallback
                empty_callback       # TinyBookCallback
            )
            
            if result == 0:
                print("  [OK] Conectado com sucesso!")
                
                # Aguardar conexões
                print("\n  Aguardando Market Data...")
                for i in range(5):
                    time.sleep(1)
                    if self.market_connected:
                        print("  [OK] Market Data conectado!")
                        break
                
                # Subscrever ao ticker
                print(f"\n  Subscrevendo ao {self.symbol}...")
                if hasattr(self.dll, 'SubscribeTicker'):
                    self.dll.SubscribeTicker.argtypes = [c_wchar_p, c_wchar_p]
                    self.dll.SubscribeTicker.restype = c_int
                    result = self.dll.SubscribeTicker(
                        c_wchar_p(self.symbol),
                        c_wchar_p("F")
                    )
                    if result == 0:
                        print(f"  [OK] Subscrito aos ticks de {self.symbol}")
                
                return True
            else:
                print(f"  [ERRO] Falha na conexao: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Erro na inicializacao: {e}")
            return False
    
    def run(self):
        """Loop principal do sistema"""
        self.running = True
        
        print("\n" + "=" * 80)
        print(" SISTEMA RODANDO")
        print("=" * 80)
        print("Pressione Ctrl+C para parar")
        print("")
        
        iteration = 0
        
        while self.running:
            try:
                iteration += 1
                
                # Log a cada 10 iterações
                if iteration % 10 == 0:
                    buffer_size = len(self.price_buffer)
                    if buffer_size > 0:
                        last_price = self.price_buffer[-1]
                        logger.info(f"[STATUS] Iteracao: {iteration} | Buffer: {buffer_size} | Ultimo preco: {last_price:.2f}")
                    else:
                        logger.info(f"[STATUS] Iteracao: {iteration} | Aguardando dados...")
                
                # Verificar se temos dados suficientes
                if len(self.price_buffer) >= 20:
                    # Aqui poderia fazer alguma análise simples
                    pass
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Parando sistema...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Erro no loop: {e}")
                time.sleep(5)
    
    def stop(self):
        """Para o sistema"""
        self.running = False
        
        if self.dll and hasattr(self.dll, 'DLLFinalize'):
            logger.info("Finalizando DLL...")
            self.dll.DLLFinalize()
        
        logger.info("Sistema parado")

def main():
    """Função principal"""
    system = MinimalTradingSystem()
    
    try:
        if system.initialize():
            system.run()
        else:
            logger.error("Falha na inicializacao")
    except KeyboardInterrupt:
        logger.info("\nParando...")
    except Exception as e:
        logger.error(f"Erro critico: {e}")
    finally:
        system.stop()

if __name__ == "__main__":
    main()