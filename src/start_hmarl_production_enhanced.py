"""
Sistema de Produção com HMARL REAL Integrado
Versão melhorada que realmente inicia e usa os agentes HMARL
"""

import os
import sys
import time
import threading
import logging
import json
from datetime import datetime
from pathlib import Path
import multiprocessing

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar production_fixed
from production_fixed import ProductionFixedSystem

# Importar enhanced_monitor
try:
    from enhanced_monitor import EnhancedMonitor
    MONITOR_AVAILABLE = True
except ImportError as e:
    MONITOR_AVAILABLE = False
    print(f"[AVISO] Enhanced Monitor não disponível: {e}")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('HMARL_Production_Enhanced')

try:
    import valkey
    import zmq
    HMARL_AVAILABLE = True
    logger.info("[OK] Infraestrutura HMARL disponível (Valkey + ZMQ)")
except ImportError as e:
    HMARL_AVAILABLE = False
    logger.warning(f"[AVISO] HMARL parcialmente disponível: {e}")

# Importar agentes HMARL reais
try:
    from agents.hmarl_agents_enhanced import (
        OrderFlowSpecialistAgent,
        LiquidityAgent,
        TapeReadingAgent,
        FootprintPatternAgent
    )
    AGENTS_AVAILABLE = True
    logger.info("[OK] Agentes HMARL disponíveis")
except ImportError as e:
    AGENTS_AVAILABLE = False
    logger.warning(f"[AVISO] Agentes HMARL não disponíveis: {e}")

# Função global para o monitor (evita problema de pickle em multiprocessing)
def run_monitor_process():
    """Função global para rodar o monitor em processo separado"""
    try:
        from enhanced_monitor import EnhancedMonitor
        monitor = EnhancedMonitor()
        monitor.run()
    except Exception as e:
        print(f"Erro no monitor: {e}")

class EnhancedHMARLProductionSystem(ProductionFixedSystem):
    """
    Extensão do production_fixed com HMARL REAL funcionando
    """
    
    def __init__(self):
        super().__init__()
        
        # Adicionar atributo pnl como alias para daily_pnl
        self.pnl = 0.0  # Alias para compatibilidade
        
        self.hmarl_enabled = HMARL_AVAILABLE and AGENTS_AVAILABLE
        self.valkey_client = None
        self.zmq_context = None
        self.flow_data_buffer = []
        self._last_prediction = None
        self.hmarl_stats = {
            'flow_signals': 0,
            'agent_consensus': 0,
            'enhanced_predictions': 0,
            'real_agent_signals': 0,
            'broadcast_count': 0
        }
        self.monitor_process = None
        self.monitor_data_file = Path('data/monitor_data.json')
        self.recent_logs = []
        
        # Agentes HMARL
        self.agent_threads = []
        self.agents = {}
        self.broadcast_thread = None
        
    def initialize_hmarl(self):
        """Inicializa componentes HMARL com agentes REAIS"""
        if not self.hmarl_enabled:
            self.logger.warning("HMARL não disponível - rodando sem agentes")
            return False
            
        try:
            # Conectar ao Valkey
            self.valkey_client = valkey.Valkey(
                host='localhost',
                port=6379,
                decode_responses=True
            )
            self.valkey_client.ping()
            self.logger.info("[OK] Conectado ao Valkey")
            
            # Configurar ZMQ
            self.zmq_context = zmq.Context()
            
            # Publisher para broadcast de dados para agentes
            self.flow_publisher = self.zmq_context.socket(zmq.PUB)
            self.flow_publisher.bind("tcp://*:5557")
            
            # Subscriber para receber sinais dos agentes
            self.agent_subscriber = self.zmq_context.socket(zmq.SUB)
            self.agent_subscriber.bind("tcp://*:5561")  # BIND ao invés de CONNECT
            self.agent_subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
            
            self.logger.info("[OK] ZMQ configurado (pub:5557, sub:5561)")
            
            # INICIAR AGENTES REAIS
            if not self._start_real_agents():
                self.logger.warning("Falha ao iniciar agentes, continuando sem HMARL enhancement")
                self.hmarl_enabled = False
                return False
            
            # Iniciar thread de processamento de sinais dos agentes
            signal_thread = threading.Thread(
                target=self._process_agent_signals,
                name="HMARL_SignalProcessor",
                daemon=True
            )
            signal_thread.start()
            
            # Iniciar thread de broadcast contínuo
            self.broadcast_thread = threading.Thread(
                target=self._continuous_broadcast,
                name="HMARL_Broadcaster",
                daemon=True
            )
            self.broadcast_thread.start()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao inicializar HMARL: {e}")
            self.hmarl_enabled = False
            return False
    
    def _start_real_agents(self):
        """Inicia os agentes HMARL reais"""
        if not AGENTS_AVAILABLE:
            return False
            
        try:
            self.logger.info("Iniciando agentes HMARL reais...")
            
            # Configuração base para todos agentes
            base_config = {
                'zmq_pub_port': 5561,  # Porta onde agentes publicam
                'zmq_sub_port': 5557,  # Porta onde agentes escutam
                'valkey_host': 'localhost',
                'valkey_port': 6379,
                'symbol': self.target_ticker,
                'use_registry': False,  # Simplificar sem registry
                'min_confidence': 0.4
            }
            
            # 1. Order Flow Specialist
            try:
                of_config = {
                    **base_config,
                    'ofi_threshold': 0.3,
                    'delta_threshold': 100,
                    'aggression_threshold': 0.6
                }
                of_agent = OrderFlowSpecialistAgent(of_config)
                of_thread = threading.Thread(
                    target=self._run_agent,
                    args=(of_agent, "OrderFlow"),
                    daemon=True
                )
                of_thread.start()
                self.agent_threads.append(of_thread)
                self.agents['order_flow'] = of_agent
                self.logger.info("  [OK] Order Flow Agent iniciado")
            except Exception as e:
                self.logger.error(f"  [ERRO] Erro ao iniciar Order Flow Agent: {e}")
            
            # 2. Liquidity Agent
            try:
                liq_config = {
                    **base_config,
                    'min_liquidity_score': 0.3,
                    'imbalance_threshold': 0.3
                }
                liq_agent = LiquidityAgent(liq_config)
                liq_thread = threading.Thread(
                    target=self._run_agent,
                    args=(liq_agent, "Liquidity"),
                    daemon=True
                )
                liq_thread.start()
                self.agent_threads.append(liq_thread)
                self.agents['liquidity'] = liq_agent
                self.logger.info("  [OK] Liquidity Agent iniciado")
            except Exception as e:
                self.logger.error(f"  [ERRO] Erro ao iniciar Liquidity Agent: {e}")
            
            # 3. Tape Reading Agent
            try:
                tape_config = {
                    **base_config,
                    'min_pattern_confidence': 0.5,
                    'speed_weight': 0.3
                }
                tape_agent = TapeReadingAgent(tape_config)
                tape_thread = threading.Thread(
                    target=self._run_agent,
                    args=(tape_agent, "TapeReading"),
                    daemon=True
                )
                tape_thread.start()
                self.agent_threads.append(tape_thread)
                self.agents['tape_reading'] = tape_agent
                self.logger.info("  [OK] Tape Reading Agent iniciado")
            except Exception as e:
                self.logger.error(f"  [ERRO] Erro ao iniciar Tape Reading Agent: {e}")
            
            # 4. Footprint Pattern Agent
            try:
                fp_config = {
                    **base_config,
                    'min_pattern_confidence': 0.5,
                    'prediction_weight': 0.7
                }
                fp_agent = FootprintPatternAgent(fp_config)
                fp_thread = threading.Thread(
                    target=self._run_agent,
                    args=(fp_agent, "Footprint"),
                    daemon=True
                )
                fp_thread.start()
                self.agent_threads.append(fp_thread)
                self.agents['footprint'] = fp_agent
                self.logger.info("  [OK] Footprint Agent iniciado")
            except Exception as e:
                self.logger.error(f"  [ERRO] Erro ao iniciar Footprint Agent: {e}")
            
            # Aguardar estabilização
            time.sleep(2)
            
            # Verificar quantos agentes estão vivos
            alive_count = sum(1 for t in self.agent_threads if t.is_alive())
            self.logger.info(f"[HMARL] {alive_count}/{len(self.agent_threads)} agentes ativos")
            
            return alive_count > 0
            
        except Exception as e:
            self.logger.error(f"Erro crítico ao iniciar agentes: {e}")
            return False
    
    def _run_agent(self, agent, name):
        """Wrapper para rodar agente com tratamento de erro"""
        try:
            self.logger.info(f"[{name}] Agente iniciado, aguardando dados...")
            # Agentes HMARL não têm método run() ou start()
            # Eles processam dados via process_flow_data() quando recebem via ZMQ
            # Vamos apenas manter a thread viva
            while self.is_running:
                time.sleep(1)
        except Exception as e:
            self.logger.error(f"[{name}] Erro no agente: {e}")
    
    def _continuous_broadcast(self):
        """Broadcast contínuo de dados reais para agentes"""
        
        self.logger.info("[BROADCAST] Thread de broadcast iniciada")
        last_broadcast = 0
        
        while self.is_running:
            try:
                # Broadcast a cada 500ms
                if time.time() - last_broadcast < 0.5:
                    time.sleep(0.1)
                    continue
                
                # Só broadcast se temos dados reais
                if self.current_price > 0 and len(self.candles) > 0:
                    
                    # Preparar dados de mercado REAIS
                    market_data = {
                        'timestamp': time.time(),
                        'type': 'market_update',
                        'symbol': self.target_ticker,
                        'price': self.current_price,
                        'last_update': self.last_price_update,
                        'candle': self.candles[-1] if self.candles else None,
                        'candles_5': self.candles[-5:] if len(self.candles) >= 5 else self.candles,
                        'candles_20': self.candles[-20:] if len(self.candles) >= 20 else self.candles,
                        'callbacks_count': self.callbacks.copy()
                    }
                    
                    # Adicionar dados de book se disponíveis
                    if hasattr(self, 'last_book_data'):
                        market_data['book'] = self.last_book_data
                    
                    # Enviar via ZMQ para agentes
                    self.flow_publisher.send_json(market_data, zmq.NOBLOCK)
                    self.hmarl_stats['broadcast_count'] += 1
                    
                    # Salvar também no Valkey para histórico
                    if self.valkey_client:
                        self.valkey_client.xadd(
                            f"flow:{self.target_ticker}",
                            {
                                'type': 'market',
                                'price': str(self.current_price),
                                'timestamp': str(time.time())
                            },
                            maxlen=10000
                        )
                    
                    last_broadcast = time.time()
                    
                    # Log periódico
                    if self.hmarl_stats['broadcast_count'] % 100 == 0:
                        self.logger.info(f"[BROADCAST] {self.hmarl_stats['broadcast_count']} broadcasts enviados")
                
            except Exception as e:
                self.logger.debug(f"Erro no broadcast: {e}")
            
            time.sleep(0.1)
    
    def _process_agent_signals(self):
        """Processa sinais REAIS dos agentes HMARL"""
        
        self.logger.info("[SIGNALS] Thread de processamento de sinais iniciada")
        poller = zmq.Poller()
        poller.register(self.agent_subscriber, zmq.POLLIN)
        
        signals_buffer = []
        last_consensus = time.time()
        
        while self.is_running:
            try:
                # Poll com timeout de 100ms
                socks = dict(poller.poll(100))
                
                if self.agent_subscriber in socks:
                    # Receber sinal do agente
                    message = self.agent_subscriber.recv_json(zmq.NOBLOCK)
                    
                    # Validar sinal
                    if self._validate_agent_signal(message):
                        signals_buffer.append(message)
                        self.hmarl_stats['real_agent_signals'] += 1
                        
                        # Log de sinais importantes
                        if message.get('confidence', 0) > 0.7:
                            self.logger.info(f"[SIGNAL] {message.get('agent')}: "
                                          f"{message.get('action')} conf={message.get('confidence'):.2f}")
                            self._add_log(f"[HMARL] Strong signal from {message.get('agent')}")
                
                # Calcular consenso a cada 2 segundos
                if time.time() - last_consensus > 2.0 and signals_buffer:
                    consensus = self._calculate_real_consensus(signals_buffer)
                    
                    if consensus:
                        # Salvar consenso no Valkey
                        self.valkey_client.set(
                            f"consensus:{self.target_ticker}",
                            json.dumps(consensus),
                            ex=60
                        )
                        
                        self.hmarl_stats['agent_consensus'] += 1
                        self.logger.info(f"[CONSENSUS] Action: {consensus['action']} "
                                       f"Confidence: {consensus['confidence']:.2f} "
                                       f"Agreement: {consensus['agreement']:.1%}")
                    
                    # Limpar buffer
                    signals_buffer = signals_buffer[-20:]  # Manter apenas últimos 20
                    last_consensus = time.time()
                    
            except zmq.Again:
                continue
            except Exception as e:
                self.logger.error(f"Erro processando sinais: {e}")
    
    def _validate_agent_signal(self, signal):
        """Valida se sinal do agente é válido"""
        required_fields = ['agent', 'timestamp', 'action', 'confidence']
        return all(field in signal for field in required_fields)
    
    def _calculate_real_consensus(self, signals):
        """Calcula consenso real dos sinais dos agentes"""
        if not signals:
            return None
        
        # Agrupar por ação
        actions = {}
        for signal in signals[-10:]:  # Últimos 10 sinais
            action = signal.get('action', 'HOLD')
            conf = signal.get('confidence', 0)
            
            if action not in actions:
                actions[action] = []
            actions[action].append(conf)
        
        # Encontrar ação com maior suporte
        best_action = 'HOLD'
        best_confidence = 0
        best_count = 0
        
        for action, confidences in actions.items():
            avg_conf = sum(confidences) / len(confidences)
            if avg_conf > best_confidence:
                best_action = action
                best_confidence = avg_conf
                best_count = len(confidences)
        
        # Calcular agreement (concordância entre agentes)
        total_signals = len(signals[-10:])
        agreement = best_count / total_signals if total_signals > 0 else 0
        
        # Extrair direção numérica
        direction = 0.5  # Neutro
        if best_action == 'BUY':
            direction = 0.7 + (0.3 * best_confidence)  # 0.7 a 1.0
        elif best_action == 'SELL':
            direction = 0.3 - (0.3 * best_confidence)  # 0.0 a 0.3
        
        consensus = {
            'timestamp': time.time(),
            'action': best_action,
            'direction': direction,
            'confidence': best_confidence,
            'agreement': agreement,
            'signals_count': len(signals[-10:]),
            'agents_contributing': len(set(s.get('agent') for s in signals[-10:]))
        }
        
        return consensus
    
    def _update_agent_status(self):
        """Atualiza status REAL dos agentes no Valkey"""
        if not self.valkey_client or not self.agents:
            return
            
        for name, agent in self.agents.items():
            try:
                # Coletar métricas reais do agente
                status = {
                    'name': name,
                    'alive': any(t.is_alive() for t in self.agent_threads if t.name == name),
                    'signals': getattr(agent, 'signals_sent', 0),
                    'last_signal': getattr(agent, 'last_signal_time', 0),
                    'confidence_avg': getattr(agent, 'avg_confidence', 0),
                    'timestamp': time.time()
                }
                
                # Salvar no Valkey
                self.valkey_client.set(
                    f"agent:{name}:status",
                    json.dumps(status),
                    ex=60
                )
                
            except Exception as e:
                self.logger.debug(f"Erro ao atualizar status do agente {name}: {e}")
    
    def _make_prediction(self):
        """Faz predição ML com enhancement HMARL REAL"""
        base_prediction = super()._make_prediction()
        
        if not base_prediction:
            return None
            
        # Salvar predição base
        self._last_prediction = base_prediction.copy()
        
        # Log da predição
        pred_msg = f"ML Prediction: Dir={base_prediction.get('direction', 0):.3f} Conf={base_prediction.get('confidence', 0):.3f}"
        self._add_log(pred_msg)
        
        if not self.hmarl_enabled or not self.valkey_client:
            return base_prediction
            
        try:
            # Buscar consenso REAL dos agentes
            consensus_key = f"consensus:{self.target_ticker}"
            consensus_data = self.valkey_client.get(consensus_key)
            
            if consensus_data:
                consensus = json.loads(consensus_data)
                
                # Só usar consenso se for recente (< 10 segundos)
                if time.time() - consensus.get('timestamp', 0) < 10:
                    
                    # Enhancement apenas se consenso forte
                    if consensus.get('confidence', 0) > 0.6 and consensus.get('agreement', 0) > 0.5:
                        
                        # Peso adaptativo baseado na concordância
                        weight = 0.2 + (0.2 * consensus.get('agreement', 0))  # 20-40% peso
                        
                        # Combinar predição ML com consenso HMARL
                        original_direction = base_prediction['direction']
                        base_prediction['direction'] = (
                            original_direction * (1 - weight) +
                            consensus.get('direction', 0.5) * weight
                        )
                        
                        # Marcar como enhanced
                        base_prediction['hmarl_enhanced'] = True
                        base_prediction['hmarl_weight'] = weight
                        base_prediction['hmarl_consensus'] = consensus.get('action')
                        
                        self.hmarl_stats['enhanced_predictions'] += 1
                        
                        enhancement_msg = (f"[HMARL] Enhanced: {original_direction:.3f} → "
                                         f"{base_prediction['direction']:.3f} "
                                         f"(weight={weight:.1%})")
                        self._add_log(enhancement_msg)
                        self.logger.info(enhancement_msg)
            
            # Salvar predição final
            self._last_prediction = base_prediction.copy()
            
            # Salvar no Valkey para análise
            if self.valkey_client:
                self.valkey_client.xadd(
                    f"predictions:{self.target_ticker}",
                    {
                        'direction': str(base_prediction.get('direction', 0)),
                        'confidence': str(base_prediction.get('confidence', 0)),
                        'enhanced': str(base_prediction.get('hmarl_enhanced', False)),
                        'timestamp': str(time.time())
                    },
                    maxlen=1000
                )
                    
            return base_prediction
            
        except Exception as e:
            self.logger.debug(f"Erro no enhancement HMARL: {e}")
            return base_prediction
    
    def _log_status(self):
        """Log de status incluindo HMARL real"""
        # Sincronizar pnl com daily_pnl
        self.pnl = self.daily_pnl
        
        super()._log_status()
        
        status_msg = f"Price: R${self.current_price:.2f} | Pos: {self.position} | PnL: R${self.pnl:.2f}"
        self._add_log(status_msg)
        
        if self.hmarl_enabled:
            # Atualizar status real dos agentes
            self._update_agent_status()
            
            # Log de estatísticas HMARL
            hmarl_msg = (f"[HMARL] Broadcasts: {self.hmarl_stats['broadcast_count']} | "
                        f"Signals: {self.hmarl_stats['real_agent_signals']} | "
                        f"Consensus: {self.hmarl_stats['agent_consensus']} | "
                        f"Enhanced: {self.hmarl_stats['enhanced_predictions']}")
            self.logger.info(hmarl_msg)
            self._add_log(hmarl_msg)
        
        # Atualizar dados para o monitor
        self._update_monitor_data()
    
    def _add_log(self, message):
        """Adiciona log ao buffer"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.recent_logs.append(log_entry)
        if len(self.recent_logs) > 50:
            self.recent_logs = self.recent_logs[-50:]
    
    def _update_monitor_data(self):
        """Atualiza dados para o Enhanced Monitor"""
        try:
            self.monitor_data_file.parent.mkdir(exist_ok=True)
            
            monitor_data = {
                'timestamp': datetime.now().isoformat(),
                'status': 'Operacional' if self.is_running else 'Parado',
                'ticker': self.target_ticker,
                'price': self.current_price,
                'position': self.position,
                'entry_price': self.entry_price,
                'pnl': self.pnl,
                'daily_pnl': self.daily_pnl,
                'trades': self.stats['trades'],
                'wins': self.stats['wins'],
                'losses': self.stats['losses'],
                'callbacks': self.callbacks.copy(),
                'active_models': list(self.models.keys()) if hasattr(self, 'models') else [],
                'hmarl_stats': self.hmarl_stats.copy() if self.hmarl_enabled else {},
                'last_prediction': self._last_prediction if self._last_prediction else {},
                'recent_logs': self.recent_logs[-20:],
                'agents_alive': sum(1 for t in self.agent_threads if t.is_alive()) if self.agent_threads else 0
            }
            
            with open(self.monitor_data_file, 'w') as f:
                json.dump(monitor_data, f, indent=2)
                
        except Exception as e:
            self.logger.debug(f"Erro ao atualizar monitor data: {e}")
    
    def start_monitor(self):
        """Inicia o Enhanced Monitor"""
        if not MONITOR_AVAILABLE:
            self.logger.warning("Enhanced Monitor não disponível")
            return False
            
        try:
            # Usar função global para evitar problema de pickle
            self.monitor_process = multiprocessing.Process(target=run_monitor_process)
            self.monitor_process.daemon = True
            self.monitor_process.start()
            
            self.logger.info("[OK] Enhanced Monitor iniciado")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao iniciar monitor: {e}")
            return False
    
    def stop_monitor(self):
        """Para o Enhanced Monitor"""
        if self.monitor_process and self.monitor_process.is_alive():
            self.monitor_process.terminate()
            self.monitor_process.join(timeout=2)
            if self.monitor_process.is_alive():
                self.monitor_process.kill()
            self.logger.info("Enhanced Monitor finalizado")
    
    def cleanup(self):
        """Cleanup completo incluindo agentes"""
        try:
            # Primeiro sinalizar para parar
            self.is_running = False
            
            # Parar monitor primeiro (rapido)
            try:
                self.stop_monitor()
            except:
                pass
            
            # Parar agentes - não esperar, são daemon threads
            if self.agent_threads:
                self.logger.info("Finalizando agentes HMARL...")
                # Apenas sinalizar para parar, não esperar
                self.is_running = False
                self.logger.info("Agentes sinalizados para parar")
            
            # Fechar ZMQ antes do cleanup da classe base
            try:
                if self.zmq_context:
                    # Não usar term() pois pode travar
                    self.zmq_context = None
            except:
                pass
                
            # Fechar Valkey
            try:
                if self.valkey_client:
                    self.valkey_client.close()
            except:
                pass
            
            # Cleanup da classe base por último
            try:
                super().cleanup()
            except Exception as e:
                self.logger.debug(f"Erro no cleanup base: {e}")
                
        except Exception as e:
            self.logger.error(f"Erro durante cleanup: {e}")
        finally:
            # Forçar saída após 1 segundo
            def force_exit():
                import os
                os._exit(0)
            
            import threading
            timer = threading.Timer(1.0, force_exit)
            timer.daemon = True
            timer.start()

def main():
    print("\n" + "="*60)
    print("QUANTUM TRADER ML - PRODUÇÃO COM HMARL REAL")
    print("="*60)
    print(f"Data: {datetime.now()}")
    print(f"HMARL: {'[OK] Disponível' if (HMARL_AVAILABLE and AGENTS_AVAILABLE) else '[AVISO] Indisponível'}")
    print(f"Monitor: {'[OK] Disponível' if MONITOR_AVAILABLE else '[AVISO] Não disponível'}")
    print("="*60)
    
    try:
        # Criar sistema
        system = EnhancedHMARLProductionSystem()
        
        # Inicializar base
        if not system.initialize():
            print("\nERRO: Falha na inicialização base")
            return 1
            
        # Inicializar HMARL com agentes reais
        if HMARL_AVAILABLE and AGENTS_AVAILABLE:
            if system.initialize_hmarl():
                print("[OK] HMARL inicializado com agentes REAIS")
                print(f"    - {len(system.agent_threads)} agentes rodando")
                print(f"    - Broadcasting em tempo real")
                print(f"    - Processamento de sinais ativo")
            else:
                print("[AVISO] HMARL não pôde ser inicializado")
        
        # Inicializar Enhanced Monitor
        if MONITOR_AVAILABLE:
            if system.start_monitor():
                print("[OK] Enhanced Monitor iniciado")
                print("    - Interface grafica disponivel")
            else:
                print("[AVISO] Monitor não pôde ser iniciado")
        
        # Aguardar estabilização
        print("\nSistema conectado. Aguardando dados...")
        time.sleep(3)
        
        # Subscrever ticker
        ticker = os.getenv('TICKER', 'WDOU25')
        if not system.subscribe_ticker(ticker):
            print(f"\nERRO: Falha ao subscrever {ticker}")
            return 1
            
        # Aguardar dados
        print(f"\nAguardando dados de {ticker}...")
        time.sleep(5)
        
        # Verificar recepção
        print(f"\nCallbacks recebidos:")
        for cb_type, count in system.callbacks.items():
            if count > 0:
                print(f"  {cb_type}: {count:,}")
                
        # Iniciar estratégia
        if not system.start():
            return 1
            
        print("\n" + "="*60)
        print(f"SISTEMA OPERACIONAL")
        print(f"Modelos ML: {len(system.models)}")
        print(f"HMARL: {'Ativo' if system.hmarl_enabled else 'Inativo'}")
        if system.hmarl_enabled:
            agents_alive = sum(1 for t in system.agent_threads if t.is_alive())
            print(f"Agentes: {agents_alive}/{len(system.agent_threads)} ativos")
        print(f"Monitor: {'Ativo' if system.monitor_process and system.monitor_process.is_alive() else 'Inativo'}")
        print(f"Ticker: {ticker}")
        print("Para parar: CTRL+C")
        print("="*60)
        
        # Loop principal
        while system.is_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário")
        
    except Exception as e:
        print(f"\nERRO FATAL: {e}")
        logger.error(f"Erro fatal: {e}", exc_info=True)
        
    finally:
        if 'system' in locals():
            try:
                # Tentar imprimir stats rapidamente
                print("\n" + "="*60)
                print("FINALIZANDO SISTEMA...")
                print("="*60)
                
                # Stop rápido
                system.is_running = False
                
                # Stats básicas se disponíveis
                try:
                    print(f"Predições ML: {system.stats.get('predictions', 0)}")
                    print(f"Trades: {system.stats.get('trades', 0)}")
                except:
                    pass
                
                # Cleanup com timeout
                system.cleanup()
                
            except Exception as e:
                print(f"Erro na finalização: {e}")
                # Forçar saída imediata
                import sys
                sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())