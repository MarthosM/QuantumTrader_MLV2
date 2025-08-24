#!/usr/bin/env python3
"""
Sistema Híbrido com OCO e Controle de Posição
Baseado no START_HYBRID_COMPLETE.py com melhorias de controle
"""

import os
import sys
import time
import json
import logging
import threading
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from collections import deque
import warnings
warnings.filterwarnings('ignore')

# Carregar configurações
load_dotenv('.env.production')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/hybrid_oco_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('HybridOCO')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Importar componentes
from src.connection_manager_oco import ConnectionManagerOCO

class HybridSystemOCO:
    """Sistema híbrido com OCO e controle de posição única"""
    
    def __init__(self):
        self.running = False
        self.connection = None
        
        # Configurações
        self.enable_trading = os.getenv('ENABLE_TRADING', 'false').lower() == 'true'
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE', '0.60'))
        self.symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
        self.stop_loss = float(os.getenv('STOP_LOSS', '0.005'))
        self.take_profit = float(os.getenv('TAKE_PROFIT', '0.010'))
        self.max_daily_trades = int(os.getenv('MAX_DAILY_TRADES', '50'))
        
        # Controle de posição
        self.has_open_position = False
        self.current_position = 0
        self.current_position_side = None
        self.active_orders = {}
        self.last_position_check = datetime.now()
        self.position_check_interval = 5  # segundos
        self.use_internal_tracking = False  # Fallback se GetPosition falhar
        
        # Métricas
        self.metrics = {
            'trades_today': 0,
            'wins': 0,
            'losses': 0,
            'blocked_signals': 0
        }
        
        # Dados de mercado
        self.current_price = 0
        self.last_book = None
        
        logger.info("Sistema OCO inicializado")
        
    def initialize(self):
        """Inicializa sistema"""
        try:
            print("\n" + "=" * 80)
            print(" INICIANDO SISTEMA HÍBRIDO COM OCO")
            print("=" * 80)
            print(f"Horário: {datetime.now():%Y-%m-%d %H:%M:%S}")
            print()
            
            # 1. Configurações
            print("[1/4] Configurações:")
            print(f"  Trading: {'REAL' if self.enable_trading else 'SIMULADO'}")
            print(f"  Símbolo: {self.symbol}")
            print(f"  Confiança mínima: {self.min_confidence:.0%}")
            print(f"  Stop Loss: {self.stop_loss:.1%}")
            print(f"  Take Profit: {self.take_profit:.1%}")
            print(f"  Max trades/dia: {self.max_daily_trades}")
            
            # 2. Conexão
            print("\n[2/4] Conectando ao ProfitChart...")
            
            # Obter caminho da DLL
            dll_path = Path(os.getcwd()) / 'ProfitDLL64.dll'
            if not dll_path.exists():
                dll_path = Path('ProfitDLL64.dll')
            
            logger.info(f"DLL path: {dll_path}")
            
            # Criar connection manager com OCO
            self.connection = ConnectionManagerOCO(str(dll_path))
            
            # Obter credenciais
            username = os.getenv('PROFIT_USERNAME', '')
            password = os.getenv('PROFIT_PASSWORD', '')
            
            if not username or not password:
                print("  [ERRO] Credenciais não configuradas em .env.production")
                return False
            
            # Inicializar conexão
            if self.connection.initialize(username=username, password=password):
                print("  [OK] Conectado à B3!")
                
                # Aguardar conexão com broker
                print("  Aguardando conexão com broker...")
                broker_connected = False
                for i in range(30):
                    status = self.connection.get_status()
                    if status.get('broker', False):
                        print(f"  [OK] Broker conectado após {i+1} segundos")
                        broker_connected = True
                        break
                    time.sleep(1)
                    if i % 5 == 4:
                        print(f"    Aguardando... ({i+1}s)")
                
                # Status final
                status = self.connection.get_status()
                print(f"    Login: {'OK' if status.get('connected', False) else 'X'}")
                print(f"    Market: {'OK' if status.get('market', False) else 'X'}")
                print(f"    Broker: {'OK' if broker_connected else 'X'}")
                
                if not broker_connected:
                    print("  [AVISO] Broker não conectado completamente")
                    print("  [INFO] Sistema funcionará com limitações:")
                    print("    - GetPosition desabilitado (rastreamento interno)")
                    print("    - Ordens podem falhar")
                    self.use_internal_tracking = True
                else:
                    self.use_internal_tracking = False
            else:
                print("  [ERRO] Falha na conexão")
                return False
            
            # 3. Verificar posição inicial
            print("\n[3/4] Verificando posições abertas...")
            # Usar rastreamento interno se broker não conectou
            if self.use_internal_tracking:
                print("  [INFO] Usando rastreamento interno de posições")
                self.has_open_position = False
                print("  [OK] Sistema pronto para operar")
            else:
                try:
                    self.check_position_status()
                except:
                    print("  [AVISO] GetPosition falhou, usando rastreamento interno")
                    self.use_internal_tracking = True
                    self.has_open_position = False
            
            if self.has_open_position:
                print(f"  [POSIÇÃO] Encontrada posição: {self.current_position} {self.current_position_side}")
                print("  [INFO] Sistema bloqueará novas entradas até fechar")
            else:
                print("  [OK] Sem posições abertas")
            
            # 4. Controles implementados
            print("\n[4/4] Controles de risco:")
            print("  ✓ Apenas uma posição por vez")
            print("  ✓ OCO automático (Stop + Take)")
            print("  ✓ Cancelamento de órfãs ao fechar")
            print("  ✓ Bloqueio com posição aberta")
            
            print("\n" + "=" * 80)
            print(" SISTEMA PRONTO!")
            print("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro na inicialização: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def check_position_status(self):
        """Verifica posição e limpa órfãs"""
        if not self.connection:
            return
        
        try:
            # Usar método apropriado baseado no modo
            if self.use_internal_tracking:
                position = self.connection.get_position_safe(self.symbol)
            else:
                position = self.connection.get_position(self.symbol)
            
            if position:
                # Tem posição
                if not self.has_open_position:
                    logger.info(f"[POSIÇÃO] Nova: {position['quantity']} {position['side']}")
                
                self.has_open_position = True
                self.current_position = position['quantity'] if position['side'] == 'BUY' else -position['quantity']
                self.current_position_side = position['side']
                
            else:
                # Sem posição
                if self.has_open_position:
                    logger.info("[POSIÇÃO] Fechada")
                    
                    # Atualizar métricas
                    if self.active_orders:
                        self.metrics['wins'] += 1  # Simplificado
                    
                    # Limpar órfãs
                    logger.info("[LIMPEZA] Cancelando órfãs...")
                    if self.connection.cancel_all_pending_orders(self.symbol):
                        logger.info("[OK] Órfãs canceladas")
                    
                    self.active_orders.clear()
                
                self.has_open_position = False
                self.current_position = 0
                self.current_position_side = None
                
        except Exception as e:
            logger.error(f"Erro ao verificar posição: {e}")
    
    def execute_trade(self, signal: int, confidence: float):
        """Executa trade com OCO"""
        
        # Verificar posição
        if self.has_open_position:
            logger.info(f"[BLOQUEADO] Posição aberta. Sinal ignorado: {signal}")
            self.metrics['blocked_signals'] += 1
            return False
        
        # Verificar limite diário
        if self.metrics['trades_today'] >= self.max_daily_trades:
            logger.warning(f"[LIMITE] {self.max_daily_trades} trades atingido")
            return False
        
        # Verificar trading habilitado
        if not self.enable_trading:
            logger.info(f"[SIMULADO] {'BUY' if signal > 0 else 'SELL'} @ {confidence:.2%}")
            return False
        
        try:
            side = "BUY" if signal > 0 else "SELL"
            quantity = 1
            
            # Obter preço atual (usar último conhecido ou default)
            current_price = self.current_price if self.current_price > 0 else 5500.0
            
            # Calcular stop e take
            if signal > 0:  # BUY
                stop_price = current_price * (1 - self.stop_loss)
                take_price = current_price * (1 + self.take_profit)
            else:  # SELL
                stop_price = current_price * (1 + self.stop_loss)
                take_price = current_price * (1 - self.take_profit)
            
            # Arredondar para múltiplo de 5
            stop_price = round(stop_price / 5) * 5
            take_price = round(take_price / 5) * 5
            
            logger.info("=" * 60)
            logger.info(f"[TRADE] {side}")
            logger.info(f"  Confiança: {confidence:.2%}")
            logger.info(f"  Stop: {stop_price:.0f}")
            logger.info(f"  Take: {take_price:.0f}")
            
            # Enviar OCO
            order_ids = self.connection.send_order_with_bracket(
                symbol=self.symbol,
                side=side,
                quantity=quantity,
                entry_price=0,  # Mercado
                stop_price=stop_price,
                take_price=take_price
            )
            
            if order_ids:
                self.active_orders = order_ids
                self.has_open_position = True
                self.current_position = quantity if signal > 0 else -quantity
                self.current_position_side = side
                self.metrics['trades_today'] += 1
                
                logger.info(f"[SUCESSO] Ordens: {order_ids}")
                return True
            else:
                logger.error("[ERRO] Falha ao enviar")
                return False
                
        except Exception as e:
            logger.error(f"Erro no trade: {e}")
            return False
    
    def position_monitor_loop(self):
        """Monitor de posições"""
        while self.running:
            try:
                # Verificar periodicamente
                if (datetime.now() - self.last_position_check).seconds >= self.position_check_interval:
                    self.check_position_status()
                    self.last_position_check = datetime.now()
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Erro no monitor: {e}")
                time.sleep(5)
    
    def trading_loop(self):
        """Loop principal de trading"""
        logger.info("Iniciando loop de trading...")
        
        while self.running:
            try:
                # Aqui você adicionaria a lógica de predição ML
                # Por enquanto, apenas exemplo simples
                
                # Simular sinal ocasional para teste
                import random
                if random.random() < 0.001:  # 0.1% chance
                    signal = random.choice([-1, 1])
                    confidence = 0.65 + random.random() * 0.25
                    
                    if confidence >= self.min_confidence:
                        self.execute_trade(signal, confidence)
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Erro no trading: {e}")
                time.sleep(5)
    
    def metrics_loop(self):
        """Loop de métricas"""
        while self.running:
            try:
                # Calcular win rate
                total = self.metrics['wins'] + self.metrics['losses']
                win_rate = self.metrics['wins'] / total if total > 0 else 0
                
                # Log periódico
                logger.info(
                    f"[METRICS] Trades: {self.metrics['trades_today']} | "
                    f"Win Rate: {win_rate:.1%} | "
                    f"Bloqueados: {self.metrics['blocked_signals']} | "
                    f"Posição: {'SIM' if self.has_open_position else 'NÃO'}"
                )
                
                time.sleep(60)  # A cada minuto
                
            except Exception as e:
                logger.error(f"Erro nas métricas: {e}")
                time.sleep(60)
    
    def start(self):
        """Inicia sistema"""
        if not self.initialize():
            return False
        
        self.running = True
        
        # Iniciar threads
        threads = [
            threading.Thread(target=self.position_monitor_loop, daemon=True, name="PositionMonitor"),
            threading.Thread(target=self.trading_loop, daemon=True, name="Trading"),
            threading.Thread(target=self.metrics_loop, daemon=True, name="Metrics")
        ]
        
        for thread in threads:
            thread.start()
            logger.info(f"Thread {thread.name} iniciada")
        
        return True
    
    def stop(self):
        """Para sistema"""
        logger.info("Parando sistema...")
        
        self.running = False
        
        # Cancelar órfãs se não tem posição
        if self.connection and not self.has_open_position:
            logger.info("Cancelando ordens pendentes...")
            self.connection.cancel_all_pending_orders(self.symbol)
        
        # Desconectar
        if self.connection:
            self.connection.disconnect()
        
        logger.info("Sistema parado")


def main():
    """Função principal"""
    system = HybridSystemOCO()
    
    try:
        if system.start():
            print("\nSistema rodando. Pressione Ctrl+C para parar...")
            
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n[!] Parando...")
        system.stop()
        print("[OK] Sistema parado com segurança")
        
    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
        system.stop()


if __name__ == "__main__":
    main()