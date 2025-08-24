"""
Script Principal de Produção - Sistema 65 Features + HMARL
Inicialização completa do sistema de trading
"""

import os
import sys
import time
import json
import logging
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Carregar configurações
load_dotenv('.env.production')

# Configurar logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/production_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ProductionSystem')

# Adicionar paths do projeto
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent))

# Importar componentes do sistema
from enhanced_production_system import EnhancedProductionSystem
from src.consensus.hmarl_consensus_system import IntegratedHMARLSystem
from src.trading_logging.structured_logger import TradingLogger
from src.metrics.metrics_and_alerts import TradingMetricsSystem
# from enhanced_monitor_v2 import EnhancedMonitorV2  # Desabilitado temporariamente


class QuantumTraderProduction:
    """Sistema de produção completo com 65 features e HMARL"""
    
    def __init__(self):
        logger.info("=" * 70)
        logger.info(" QUANTUM TRADER ML - SISTEMA DE PRODUÇÃO")
        logger.info(" 65 Features + 4 Agentes HMARL + Consenso ML")
        logger.info("=" * 70)
        
        self.running = False
        self.components = {}
        self.threads = []
        self.data_files = {}  # Inicializar antes de usar
        self.record_count = {'book': 0, 'tick': 0}
        
        # Carregar configuração
        self.load_configuration()
        
        # Inicializar componentes
        self.initialize_components()
        
    def load_configuration(self):
        """Carrega configuração de produção"""
        logger.info("\n[1/5] Carregando configuração...")
        
        config_path = Path('config_production.json')
        if config_path.exists():
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            logger.info(f"  [OK] Configuração carregada: {self.config['system']['name']}")
        else:
            logger.error("  [ERRO] Arquivo config_production.json não encontrado!")
            sys.exit(1)
        
        # Validar paths
        paths = ['data/', 'models/', 'logs/', 'backups/', 'cache/', 'metrics/']
        for path in paths:
            Path(path).mkdir(exist_ok=True)
        logger.info(f"  [OK] Diretórios validados")
    
    def initialize_components(self):
        """Inicializa todos os componentes do sistema"""
        success = True
        
        # 1. Sistema Enhanced de Produção
        logger.info("\n[2/5] Inicializando Sistema Enhanced...")
        try:
            self.components['production'] = EnhancedProductionSystem()
            
            # IMPORTANTE: Inicializar conexão com B3
            logger.info("  Conectando com B3 via DLL...")
            init_result = self.components['production'].initialize()
            if init_result:
                logger.info("  [OK] Conectado à B3 com sucesso!")
            else:
                logger.warning("  [AVISO] Falha na conexão com B3 - sistema rodará em modo simulado")
            
            logger.info("  [OK] Sistema Enhanced inicializado (65 features)")
            
            # Habilitar gravação de dados se configurado
            if os.getenv('ENABLE_DATA_RECORDING', 'true').lower() == 'true':
                self.setup_data_recording()
                logger.info("  [OK] Gravação de dados book/tick habilitada")
        except Exception as e:
            logger.error(f"  [ERRO] Erro ao inicializar Sistema Enhanced: {e}")
            success = False
        
        # 2. Sistema HMARL Integrado
        logger.info("\n[3/5] Inicializando Sistema HMARL...")
        try:
            self.components['hmarl'] = IntegratedHMARLSystem()
            logger.info("  [OK] Sistema HMARL inicializado (4 agentes)")
        except Exception as e:
            logger.error(f"  [ERRO] Erro ao inicializar HMARL: {e}")
            logger.warning("  [AVISO] Continuando sem HMARL - apenas ML será usado")
            # Não falha completamente, continua sem HMARL
        
        # 3. Sistema de Logging Estruturado
        logger.info("\n[4/5] Inicializando Logging Estruturado...")
        try:
            self.components['logger'] = TradingLogger()
            logger.info("  [OK] Logging estruturado inicializado")
        except Exception as e:
            logger.error(f"  [ERRO] Erro ao inicializar Logging: {e}")
            logger.warning("  [AVISO] Continuando com logging básico")
        
        # 4. Sistema de Métricas e Alertas
        logger.info("\n[5/5] Inicializando Métricas e Alertas...")
        try:
            prometheus_port = int(os.getenv('PROMETHEUS_PORT', 0))
            if os.getenv('PROMETHEUS_ENABLED', 'false').lower() == 'true':
                self.components['metrics'] = TradingMetricsSystem(prometheus_port)
                logger.info(f"  [OK] Métricas inicializadas (Prometheus: {prometheus_port})")
            else:
                self.components['metrics'] = TradingMetricsSystem(0)
                logger.info("  [OK] Métricas inicializadas (modo interno)")
        except Exception as e:
            logger.error(f"  [ERRO] Erro ao inicializar Métricas: {e}")
            logger.warning("  [AVISO] Continuando sem sistema de métricas")
        
        # 5. Monitor Visual (opcional - DESABILITADO por problemas de thread)
        # NOTA: Monitor visual tem problemas de thread-safety com tkinter
        # if self.config.get('monitoring', {}).get('enhanced_monitor', {}).get('enabled', False):
        #     try:
        #         self.components['monitor'] = EnhancedMonitorV2()
        #         logger.info("  [OK] Monitor visual inicializado")
        #     except Exception as e:
        #         logger.warning(f"  [AVISO] Monitor visual não pôde ser inicializado: {e}")
        logger.info("  [INFO] Monitor visual desabilitado (usar logs para monitoramento)")
        
        if 'production' not in self.components:
            logger.error("\n[ERRO] Sistema Enhanced é obrigatório e não foi inicializado!")
            return False
        
        logger.info("\n[SUCESSO] Componentes essenciais inicializados!")
        return True  # Sempre retornar True se chegou até aqui
    
    def setup_data_recording(self):
        """Configura gravação de dados book e tick"""
        import csv
        from datetime import datetime
        
        # Criar diretório para dados
        data_dir = Path('data/book_tick_data')
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Nome dos arquivos com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Arquivo para book data
        self.data_files['book'] = data_dir / f'book_data_{timestamp}.csv'
        with open(self.data_files['book'], 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'bid_price_1', 'bid_vol_1', 'bid_price_2', 'bid_vol_2',
                           'bid_price_3', 'bid_vol_3', 'bid_price_4', 'bid_vol_4', 'bid_price_5', 'bid_vol_5',
                           'ask_price_1', 'ask_vol_1', 'ask_price_2', 'ask_vol_2', 'ask_price_3', 'ask_vol_3',
                           'ask_price_4', 'ask_vol_4', 'ask_price_5', 'ask_vol_5', 'spread', 'mid_price', 'imbalance'])
        
        # Arquivo para tick data
        self.data_files['tick'] = data_dir / f'tick_data_{timestamp}.csv'
        with open(self.data_files['tick'], 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'price', 'volume', 'side', 'aggressor'])
        
        # Contador de registros
        self.record_count = {'book': 0, 'tick': 0}
    
    def record_book_data(self, book_data):
        """Grava dados do book"""
        if 'book' not in self.data_files:
            return
        
        try:
            import csv
            from datetime import datetime
            
            row = [datetime.now().isoformat()]
            
            # Adicionar bids (5 níveis)
            bids = book_data.get('bids', [])
            for i in range(5):
                if i < len(bids):
                    row.extend([bids[i]['price'], bids[i]['volume']])
                else:
                    row.extend([0, 0])
            
            # Adicionar asks (5 níveis)
            asks = book_data.get('asks', [])
            for i in range(5):
                if i < len(asks):
                    row.extend([asks[i]['price'], asks[i]['volume']])
                else:
                    row.extend([0, 0])
            
            # Calcular métricas
            if bids and asks:
                spread = asks[0]['price'] - bids[0]['price']
                mid_price = (asks[0]['price'] + bids[0]['price']) / 2
                bid_vol = sum(b['volume'] for b in bids[:5])
                ask_vol = sum(a['volume'] for a in asks[:5])
                imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0
            else:
                spread = mid_price = imbalance = 0
            
            row.extend([spread, mid_price, imbalance])
            
            # Gravar no arquivo
            with open(self.data_files['book'], 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            self.record_count['book'] += 1
            
            # Log periódico
            if self.record_count['book'] % 1000 == 0:
                logger.debug(f"Book records gravados: {self.record_count['book']}")
                
        except Exception as e:
            logger.error(f"Erro ao gravar book data: {e}")
    
    def record_tick_data(self, tick_data):
        """Grava dados de tick/trade"""
        if 'tick' not in self.data_files:
            return
        
        try:
            import csv
            from datetime import datetime
            
            row = [
                datetime.now().isoformat(),
                tick_data.get('price', 0),
                tick_data.get('volume', 0),
                tick_data.get('side', ''),
                tick_data.get('aggressor', '')
            ]
            
            # Gravar no arquivo
            with open(self.data_files['tick'], 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            self.record_count['tick'] += 1
            
            # Log periódico
            if self.record_count['tick'] % 1000 == 0:
                logger.debug(f"Tick records gravados: {self.record_count['tick']}")
                
        except Exception as e:
            logger.error(f"Erro ao gravar tick data: {e}")
    
    def start_trading_loop(self):
        """Loop principal de trading"""
        logger.info("\n[INICIANDO] Loop de trading...")
        
        production = self.components.get('production')
        if not production:
            logger.error("Sistema Enhanced não disponível!")
            return
        
        hmarl = self.components.get('hmarl')
        metrics = self.components.get('metrics')
        structured_logger = self.components.get('logger')
        
        logger.info("[DEBUG] Componentes carregados:")
        logger.info(f"  - Production: {'OK' if production else 'FALHOU'}")
        logger.info(f"  - HMARL: {'OK' if hmarl else 'N/A'}")
        logger.info(f"  - Metrics: {'OK' if metrics else 'N/A'}")
        logger.info(f"  - Logger: {'OK' if structured_logger else 'N/A'}")
        
        iteration = 0
        
        logger.info("[DEBUG] Entrando no loop principal...")
        
        while self.running:
            try:
                iteration += 1
                start_time = time.perf_counter()
                
                # Debug a cada 10 iterações
                if iteration % 10 == 1:
                    logger.debug(f"[DEBUG] Loop iteração {iteration}")
                
                # 1. Calcular 65 features
                try:
                    features = production._calculate_features()
                    feature_latency = (time.perf_counter() - start_time) * 1000
                    
                    if iteration == 1:
                        logger.info(f"[DEBUG] Features calculadas: {len(features) if features else 0}")
                except Exception as e:
                    logger.error(f"[ERRO] Erro ao calcular features: {e}")
                    features = {}
                    feature_latency = 0
                
                # Gravar dados do book se habilitado
                if hasattr(self, 'data_files') and production.book_manager:
                    book_state = production.book_manager.get_current_state()
                    if book_state and book_state.get('book_depth'):
                        self.record_book_data(book_state['book_depth'])
                
                if len(features) == 65:
                    # Log estruturado
                    if structured_logger:
                        structured_logger.log_feature_calculation(features, feature_latency)
                    
                    # Métricas
                    if metrics:
                        metrics.record_feature_calculation(65, feature_latency)
                    
                    # 2. Fazer predição ML
                    ml_start = time.perf_counter()
                    ml_prediction = production._make_ml_prediction(features)
                    ml_latency = (time.perf_counter() - ml_start) * 1000
                    
                    if ml_prediction != 0:
                        # Log estruturado
                        if structured_logger:
                            structured_logger.log_prediction(ml_prediction, 0.75, 65)
                        
                        # Métricas
                        if metrics:
                            metrics.record_prediction(0.75, ml_latency)
                        
                        # 3. Obter consenso HMARL (se disponível)
                        if hmarl:
                            consensus = hmarl.process_features_and_decide(features, ml_prediction)
                            
                            # Log estruturado
                            if structured_logger:
                                structured_logger.log_agent_consensus(
                                    {'hmarl': consensus.agent_votes},
                                    {
                                        'action': consensus.action.value,
                                        'confidence': consensus.confidence,
                                        'signal': consensus.combined_signal
                                    }
                                )
                        else:
                            # Sem HMARL, usar apenas ML
                            logger.debug("Usando apenas predição ML (HMARL não disponível)")
                            # Criar um consenso simplificado baseado apenas em ML
                            class SimpleConsensus:
                                def __init__(self, ml_pred):
                                    self.confidence = abs(ml_pred)
                                    self.combined_signal = ml_pred
                                    self.risk_assessment = {'risk_level': 'medium'}
                                    self.reasoning = "ML-only prediction"
                                    from enum import Enum
                                    class Action(Enum):
                                        BUY = 'BUY'
                                        SELL = 'SELL'
                                        HOLD = 'HOLD'
                                    if ml_pred > 0.3:
                                        self.action = type('obj', (object,), {'value': 'BUY'})
                                    elif ml_pred < -0.3:
                                        self.action = type('obj', (object,), {'value': 'SELL'})
                                    else:
                                        self.action = type('obj', (object,), {'value': 'HOLD'})
                            consensus = SimpleConsensus(ml_prediction)
                        
                        # 4. Executar decisão de trading
                        if consensus.confidence > float(os.getenv('MIN_CONFIDENCE', 0.60)):
                            if consensus.action.value in ['BUY', 'STRONG_BUY']:
                                self.execute_trade('BUY', consensus)
                            elif consensus.action.value in ['SELL', 'STRONG_SELL']:
                                self.execute_trade('SELL', consensus)
                        
                        # 5. Atualizar monitor visual
                        if 'monitor' in self.components:
                            self.update_monitor(features, consensus)
                
                # Log periódico
                if iteration % 30 == 0:  # A cada 30 segundos
                    self.log_system_status(iteration)
                    logger.info(f"[STATUS] Sistema ativo - Iteração {iteration}")
                    logger.info(f"[STATUS] Features disponíveis: {len(features) if 'features' in locals() else 0}/65")
                
                # Health check
                if iteration % 300 == 0:  # A cada 5 minutos
                    self.perform_health_check()
                
                # Aguardar próximo ciclo
                time.sleep(1)
                
                # Debug: mostrar que está vivo
                if iteration == 1:
                    logger.info("[DEBUG] Loop de trading rodando... (aguardando dados do mercado)")
                    logger.info("[INFO] Sistema aguardando callbacks do ProfitDLL...")
                    logger.info("[INFO] Se o mercado está fechado, não haverá dados.")
                
            except KeyboardInterrupt:
                logger.info("\n[AVISO] Interrupção manual detectada")
                break
                
            except Exception as e:
                logger.error(f"Erro no loop de trading: {e}")
                structured_logger.error("Trading loop error", exception=e)
                
                # Tentar recuperar
                if self.config['maintenance']['health_check']['restart_on_failure']:
                    logger.info("Tentando recuperar...")
                    time.sleep(5)
                else:
                    break
    
    def execute_trade(self, side: str, consensus):
        """Executa trade baseado no consenso"""
        logger.info(f"\n[TRADE] SINAL: {side}")
        logger.info(f"  Confiança: {consensus.confidence:.2%}")
        logger.info(f"  Sinal combinado: {consensus.combined_signal:.3f}")
        logger.info(f"  Risco: {consensus.risk_assessment['risk_level']}")
        
        # Log estruturado
        if 'logger' in self.components:
            self.components['logger'].log_trade_signal(
                side,
                consensus.confidence,
                consensus.reasoning
            )
        
        # Métricas
        if 'metrics' in self.components:
            self.components['metrics'].record_trade(side, 0)  # PnL será atualizado depois
        
        # Aqui seria feita a execução real via ProfitDLL
        # self.components['production'].execute_order(side, 1)
    
    def update_monitor(self, features: dict, consensus):
        """Atualiza monitor visual"""
        try:
            monitor = self.components['monitor']
            
            # Converter consensus para formato esperado
            consensus_dict = {
                'action': consensus.action.value,
                'confidence': consensus.confidence,
                'signal': consensus.combined_signal
            }
            
            # Atualizar painéis
            monitor.features_panel.update_features(features)
            monitor.agents_panel.update_consensus(consensus_dict)
            
        except Exception as e:
            logger.debug(f"Erro ao atualizar monitor: {e}")
    
    def log_system_status(self, iteration: int):
        """Log periódico do status do sistema"""
        if 'metrics' in self.components:
            metrics_summary = self.components['metrics'].get_dashboard_data()
            
            logger.info(f"\n[STATUS] SISTEMA - Iteração {iteration}")
            logger.info(f"  Features/seg: {metrics_summary['metrics']['counters'].get('features_calculated', 0) / max(1, iteration):.1f}")
            logger.info(f"  Predições: {metrics_summary['metrics']['counters'].get('predictions_made', 0)}")
            logger.info(f"  Trades: {metrics_summary['metrics']['counters'].get('trades_executed', 0)}")
            logger.info(f"  Alertas: {len(metrics_summary['alerts'])}")
        else:
            logger.info(f"\n[STATUS] SISTEMA - Iteração {iteration}")
            logger.info("  Métricas não disponíveis")
    
    def perform_health_check(self):
        """Verifica saúde do sistema"""
        logger.debug("Executando health check...")
        
        # Verificar componentes
        all_healthy = True
        
        for name, component in self.components.items():
            if component is None:
                logger.warning(f"  [AVISO] Componente {name} não está ativo")
                all_healthy = False
        
        # Verificar memória
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            max_memory_gb = float(os.getenv('MAX_MEMORY_GB', 2.0))
            if memory_mb > max_memory_gb * 1024:
                logger.warning(f"  [AVISO] Uso de memória alto: {memory_mb:.0f}MB")
                all_healthy = False
        except:
            pass
        
        if all_healthy:
            logger.debug("  [OK] Sistema saudável")
        else:
            logger.warning("  [AVISO] Problemas detectados no health check")
    
    def start(self):
        """Inicia o sistema de produção"""
        self.running = True
        
        logger.info("\n" + "=" * 70)
        logger.info(" SISTEMA EM PRODUÇÃO - TRADING INICIADO")
        logger.info("=" * 70)
        
        # Iniciar monitor enhanced de console em processo separado
        try:
            import subprocess
            monitor_process = subprocess.Popen(
                ['python', 'core/monitor_console_enhanced.py'],
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            logger.info("  [OK] Monitor Enhanced iniciado em nova janela")
            logger.info("  [INFO] Monitor exibe 65 features, 4 agentes HMARL e métricas")
            self.monitor_process = monitor_process
        except Exception as e:
            logger.warning(f"  [AVISO] Monitor Enhanced não pôde ser iniciado: {e}")
            logger.info("  [INFO] Execute 'python monitor_console_enhanced.py' em outro terminal")
            self.monitor_process = None
        
        # Iniciar loop principal
        try:
            self.start_trading_loop()
        except Exception as e:
            logger.error(f"Erro fatal no sistema: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            self.stop()
    
    def stop(self):
        """Para o sistema de produção"""
        logger.info("\n[PARANDO] Sistema de produção...")
        self.running = False
        
        # Parar monitor de console se estiver rodando
        if hasattr(self, 'monitor_process') and self.monitor_process:
            try:
                self.monitor_process.terminate()
                logger.info("  [OK] Monitor de console fechado")
            except:
                pass
        
        # Parar componentes
        if 'metrics' in self.components:
            self.components['metrics'].stop()
            logger.info("  [OK] Métricas paradas")
        
        if 'hmarl' in self.components:
            self.components['hmarl'].close()
            logger.info("  [OK] HMARL fechado")
        
        # Aguardar threads
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        # Salvar estado final
        self.save_final_state()
        
        logger.info("\n" + "=" * 70)
        logger.info(" SISTEMA PARADO COM SUCESSO")
        logger.info("=" * 70)
    
    def save_final_state(self):
        """Salva estado final do sistema"""
        try:
            state = {
                'timestamp': datetime.now().isoformat(),
                'components_active': list(self.components.keys())
            }
            
            # Adicionar métricas se disponível
            if 'metrics' in self.components:
                try:
                    state['metrics'] = self.components['metrics'].get_dashboard_data()
                except:
                    state['metrics'] = {}
            
            # Adicionar logs se disponível
            if 'logger' in self.components:
                try:
                    state['logs'] = self.components['logger'].get_stats()
                except:
                    state['logs'] = {}
            
            # Adicionar contadores de gravação de dados
            if hasattr(self, 'record_count'):
                state['data_recording'] = self.record_count
            
            state_file = Path('backups') / f"final_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logger.info(f"  [OK] Estado final salvo em {state_file}")
        except Exception as e:
            logger.error(f"  [ERRO] Erro ao salvar estado: {e}")


def main():
    """Função principal"""
    # Verificar se já existe uma instância rodando
    pid_file = Path('quantum_trader.pid')
    
    if pid_file.exists():
        logger.warning("[AVISO] Sistema já pode estar em execução. Verificar quantum_trader.pid")
        response = input("Continuar mesmo assim? (s/n): ")
        if response.lower() != 's':
            return
    
    # Salvar PID
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    
    try:
        # Criar e iniciar sistema
        logger.info("[MAIN] Criando sistema de produção...")
        system = QuantumTraderProduction()
        logger.info("[MAIN] Sistema criado, iniciando loop principal...")
        system.start()
        logger.info("[MAIN] Sistema finalizado normalmente")
        
    except KeyboardInterrupt:
        logger.info("\n[AVISO] Interrupção manual")
        
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        
    finally:
        # Remover arquivo PID
        if pid_file.exists():
            pid_file.unlink()
        
        logger.info("\nSistema finalizado")


if __name__ == "__main__":
    main()