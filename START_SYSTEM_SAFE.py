#!/usr/bin/env python3
"""
Sistema de Trading Seguro - Versão com proteção contra crashes
Inclui ML + HMARL + OCO + Monitor
"""

import sys
import os
import time
import signal
import logging
import threading
from datetime import datetime
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SafeSystem')

# Adicionar diretórios ao path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Importar o sistema principal
try:
    from START_SYSTEM_COMPLETE_OCO_EVENTS import QuantumTraderCompleteOCOEvents
    SYSTEM_AVAILABLE = True
except ImportError as e:
    logger.error(f"Erro ao importar sistema: {e}")
    SYSTEM_AVAILABLE = False

class SafeTradingSystem:
    """Sistema de trading com proteção contra crashes"""
    
    def __init__(self):
        self.system = None
        self.running = False
        self.restart_count = 0
        self.max_restarts = 3
        self.monitor_thread = None
        self.last_heartbeat = time.time()
        
    def start_system(self):
        """Inicia o sistema principal com proteção"""
        try:
            logger.info("="*80)
            logger.info(" QUANTUM TRADER - SISTEMA SEGURO")
            logger.info("="*80)
            logger.info(f" Horário: {datetime.now():%Y-%m-%d %H:%M:%S}")
            logger.info(" ML + HMARL + OCO + Monitor")
            logger.info("="*80)
            
            if not SYSTEM_AVAILABLE:
                logger.error("Sistema principal não disponível!")
                return False
            
            # Criar instância do sistema
            self.system = QuantumTraderCompleteOCOEvents()
            
            # Verificar horário do mercado
            now = datetime.now()
            market_open = now.hour >= 9 and now.hour < 18
            
            if not market_open:
                logger.warning("="*80)
                logger.warning(" ATENÇÃO: MERCADO FECHADO")
                logger.warning("="*80)
                logger.warning(f" Horário atual: {now:%H:%M}")
                logger.warning(" Mercado opera: 09:00 - 18:00")
                logger.warning(" Sistema iniciará em modo de espera...")
                logger.warning("="*80)
            
            # Iniciar sistema
            if self.system.start():
                self.running = True
                logger.info("[OK] Sistema iniciado com sucesso")
                
                # Iniciar monitor de saúde
                self.start_health_monitor()
                
                return True
            else:
                logger.error("[ERRO] Falha ao iniciar sistema")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao iniciar sistema: {e}")
            return False
    
    def start_health_monitor(self):
        """Monitor de saúde do sistema"""
        def monitor():
            while self.running:
                try:
                    # Verificar se o sistema está vivo
                    if hasattr(self.system, 'trading_thread'):
                        if not self.system.trading_thread.is_alive():
                            logger.warning("Thread de trading morreu - tentando recuperar...")
                            self.handle_crash()
                            break
                    
                    # Verificar heartbeat (atualizar a cada loop do sistema)
                    if hasattr(self.system, 'last_loop_time'):
                        time_since_loop = time.time() - self.system.last_loop_time
                        if time_since_loop > 60:  # Sem atividade por 60s
                            logger.warning(f"Sistema sem atividade há {time_since_loop:.0f}s")
                    
                    # Verificar conexão
                    if hasattr(self.system, 'connection'):
                        if self.system.connection and not self.system.connection.is_connected:
                            logger.warning("Conexão perdida - reconectando...")
                            self.reconnect()
                    
                    time.sleep(5)  # Verificar a cada 5 segundos
                    
                except Exception as e:
                    logger.error(f"Erro no monitor de saúde: {e}")
                    time.sleep(5)
        
        self.monitor_thread = threading.Thread(target=monitor, name="HealthMonitor")
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def handle_crash(self):
        """Trata crash do sistema"""
        logger.warning("Detectado crash no sistema - tentando recuperar...")
        
        if self.restart_count >= self.max_restarts:
            logger.error(f"Máximo de restarts ({self.max_restarts}) atingido!")
            self.stop()
            return
        
        self.restart_count += 1
        logger.info(f"Tentativa de restart {self.restart_count}/{self.max_restarts}")
        
        # Parar sistema atual
        try:
            if self.system:
                self.system.stop()
        except:
            pass
        
        # Aguardar
        time.sleep(5)
        
        # Reiniciar
        if self.start_system():
            logger.info("[OK] Sistema recuperado com sucesso")
        else:
            logger.error("[ERRO] Falha ao recuperar sistema")
            self.stop()
    
    def reconnect(self):
        """Reconecta ao servidor"""
        try:
            if self.system and hasattr(self.system, 'connection'):
                logger.info("Tentando reconectar...")
                # Aqui você pode adicionar lógica de reconexão
                # Por enquanto, apenas registra
                logger.warning("Reconexão automática não implementada - reiniciando sistema")
                self.handle_crash()
        except Exception as e:
            logger.error(f"Erro ao reconectar: {e}")
    
    def run(self):
        """Loop principal do sistema"""
        try:
            if not self.start_system():
                return
            
            logger.info("\n" + "="*80)
            logger.info(" Sistema rodando - Pressione Ctrl+C para parar")
            logger.info("="*80)
            
            # Monitor principal
            while self.running:
                try:
                    # Verificar se sistema está rodando
                    if self.system and hasattr(self.system, 'running'):
                        if not self.system.running:
                            logger.warning("Sistema parou - verificando motivo...")
                            
                            # Verificar se foi parada normal ou crash
                            if self.restart_count < self.max_restarts:
                                logger.info("Tentando reiniciar sistema...")
                                self.handle_crash()
                            else:
                                break
                    
                    time.sleep(1)
                    
                except KeyboardInterrupt:
                    logger.info("\n[!] Interrupção do usuário")
                    break
                except Exception as e:
                    logger.error(f"Erro no loop principal: {e}")
                    time.sleep(5)
            
            logger.info("\nSistema finalizado")
            
        except Exception as e:
            logger.error(f"Erro fatal: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Para o sistema com segurança"""
        logger.info("\nParando sistema...")
        self.running = False
        
        try:
            if self.system:
                self.system.stop()
                logger.info("[OK] Sistema parado")
        except Exception as e:
            logger.error(f"Erro ao parar sistema: {e}")
        
        logger.info("="*80)
        logger.info(" SISTEMA FINALIZADO")
        logger.info("="*80)

def signal_handler(sig, frame):
    """Handler para Ctrl+C"""
    print("\n[!] Recebido sinal de parada...")
    global safe_system
    if 'safe_system' in globals():
        safe_system.stop()
    sys.exit(0)

def main():
    """Função principal"""
    global safe_system
    
    # Registrar handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Criar e executar sistema seguro
    safe_system = SafeTradingSystem()
    safe_system.run()

if __name__ == "__main__":
    main()