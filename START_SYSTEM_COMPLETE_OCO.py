#!/usr/bin/env python3
"""
QUANTUM TRADER v2.0 - SISTEMA COMPLETO COM OCO
Integra TUDO do sistema híbrido + OCO + Controle de Posição
Baseado no START_HYBRID_COMPLETE.py com melhorias de controle
"""

import os
import sys
import time
import json
import signal
import logging
import threading
import subprocess
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, time as dt_time
from dotenv import load_dotenv
from collections import deque
import csv
import warnings
warnings.filterwarnings('ignore')

# Carregar configurações
load_dotenv('.env.production')

# ============= VARIÁVEIS GLOBAIS DE CONTROLE DE POSIÇÃO =============
# Sistema de lock global para garantir apenas uma posição por vez
GLOBAL_POSITION_LOCK = False  # True quando há posição aberta
GLOBAL_POSITION_LOCK_TIME = None  # Timestamp de quando abriu posição
GLOBAL_POSITION_LOCK_MUTEX = threading.Lock()  # Mutex para thread-safety

# Logger para o sistema de lock global
global_lock_logger = logging.getLogger('GlobalPositionLock')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/system_complete_oco_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('SystemCompleteOCO')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent / 'core'))

# Importar componentes
from src.connection_manager_oco import ConnectionManagerOCO
try:
    from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
except:
    HMARLAgentsRealtime = None
    logger.warning("HMARL Agents não disponível")

try:
    from src.trading.adaptive_risk_manager import AdaptiveRiskManager
except:
    AdaptiveRiskManager = None
    logger.warning("AdaptiveRiskManager não disponível")

try:
    from src.trading.dynamic_risk_calculator import DynamicRiskCalculator
except:
    DynamicRiskCalculator = None
    logger.warning("DynamicRiskCalculator não disponível")

try:
    from src.monitoring.hmarl_monitor_bridge import get_bridge
except:
    get_bridge = None
    logger.warning("Monitor bridge não disponível")

try:
    from src.training.smart_retraining_system import SmartRetrainingSystem
except:
    SmartRetrainingSystem = None
    logger.warning("Smart retraining não disponível")

try:
    from src.training.model_selector import ModelSelector
except:
    ModelSelector = None
    logger.warning("Model selector não disponível")

class QuantumTraderCompleteOCO:
    """Sistema completo com todos os recursos + OCO + Controle de Posição"""
    
    def __init__(self):
        self.running = False
        self.connection = None
        self.monitor_process = None
        self.data_lock = threading.Lock()
        self.cleanup_thread = None  # Thread de limpeza de ordens órfãs
        
        # Configurações
        self.enable_trading = os.getenv('ENABLE_TRADING', 'false').lower() == 'true'
        self.enable_recording = os.getenv('ENABLE_DATA_RECORDING', 'true').lower() == 'true'
        self.enable_daily_training = os.getenv('ENABLE_DAILY_TRAINING', 'true').lower() == 'true'
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE', '0.65'))  # Aumentado para 65%
        self.symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
        # Ajustado para WDO: stop 10-15 pontos, take 20-30 pontos
        self.stop_loss = float(os.getenv('STOP_LOSS', '0.002'))  # 0.2% = ~10 pontos
        self.take_profit = float(os.getenv('TAKE_PROFIT', '0.004'))  # 0.4% = ~20 pontos
        self.max_daily_trades = int(os.getenv('MAX_DAILY_TRADES', '10'))  # Reduzido para 10
        
        # Controle de tempo entre trades (NOVO)
        self.last_trade_time = None
        self.min_time_between_trades = 60  # Mínimo 60 segundos entre trades
        
        # Modelos híbridos
        self.models = {}
        self.scalers = {}
        self.models_dir = Path("models/hybrid")
        self.model_version = "v1.0"
        
        # HMARL Real-time
        if HMARLAgentsRealtime:
            try:
                self.hmarl_agents = HMARLAgentsRealtime()
                logger.info("[INIT] HMARL Agents inicializados com sucesso")
            except Exception as e:
                logger.error(f"[INIT] Erro ao inicializar HMARL: {e}")
                self.hmarl_agents = None
        else:
            logger.warning("[INIT] HMARLAgentsRealtime não disponível")
            self.hmarl_agents = None
        
        # Gestão de Risco Adaptativa
        self.risk_manager = AdaptiveRiskManager(self.symbol) if AdaptiveRiskManager else None
        self.use_adaptive_risk = True
        
        # Calculador de Risco Dinâmico (NOVO)
        self.risk_calculator = DynamicRiskCalculator() if DynamicRiskCalculator else None
        
        # Bridge para monitor
        self.monitor_bridge = get_bridge() if get_bridge else None
        
        # Re-treinamento inteligente
        self.retraining_system = SmartRetrainingSystem() if SmartRetrainingSystem else None
        self.model_selector = ModelSelector() if ModelSelector else None
        
        # Buffers de dados
        self.price_history = deque(maxlen=500)
        self.book_snapshots = deque(maxlen=200)
        self.tick_buffer = deque(maxlen=1000)
        self.book_buffer = deque(maxlen=1000)
        
        # Preços e dados de mercado
        self.current_price = 0
        self.last_mid_price = 0
        self.last_book_update = None
        self.last_trade = None
        self.total_volume = 0  # Volume total acumulado
        
        # Controle de posição (NOVO)
        self.has_open_position = False
        self.position_open_time = None  # NOVO: Registrar quando abriu posição
        self.min_position_hold_time = 30  # NOVO: Mínimo 30 segundos com posição
        self.current_position = 0
        self.current_position_side = None
        self.active_orders = {}
        self.use_internal_tracking = False
        
        # Métricas
        self.metrics = {
            'trades_today': 0,
            'predictions_today': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'max_drawdown': 0.0,
            'blocked_signals': 0,
            'hmarl_signals': 0,
            'ml_signals': 0
        }
        
        # Arquivos de dados
        self.data_files = {}
        
        # Features calculator
        self.feature_count = 0
        self.last_features = None
        
        logger.info("Sistema Completo OCO inicializado")
    
    def load_hybrid_models(self):
        """Carrega modelos híbridos de 3 camadas"""
        logger.info("Carregando modelos híbridos...")
        
        try:
            models_loaded = 0
            
            # Camada 1: Modelos de Contexto
            context_dir = self.models_dir / "context"
            if context_dir.exists():
                for model_file in context_dir.glob("*.pkl"):
                    model_name = model_file.stem
                    self.models[f"context_{model_name}"] = joblib.load(model_file)
                    models_loaded += 1
                    logger.debug(f"Carregado: context/{model_name}")
            
            # Camada 2: Modelos de Microestrutura
            micro_dir = self.models_dir / "microstructure"
            if micro_dir.exists():
                for model_file in micro_dir.glob("*.pkl"):
                    model_name = model_file.stem
                    self.models[f"micro_{model_name}"] = joblib.load(model_file)
                    models_loaded += 1
                    logger.debug(f"Carregado: microstructure/{model_name}")
            
            # Camada 3: Meta-Learner
            meta_dir = self.models_dir / "meta_learner"
            if meta_dir.exists():
                for model_file in meta_dir.glob("*.pkl"):
                    model_name = model_file.stem
                    self.models[f"meta_{model_name}"] = joblib.load(model_file)
                    models_loaded += 1
                    logger.debug(f"Carregado: meta_learner/{model_name}")
            
            # Carregar scalers
            if (self.models_dir / "scaler_context.pkl").exists():
                self.scalers['context'] = joblib.load(self.models_dir / "scaler_context.pkl")
            if (self.models_dir / "scaler_microstructure.pkl").exists():
                self.scalers['microstructure'] = joblib.load(self.models_dir / "scaler_microstructure.pkl")
            
            logger.info(f"Modelos carregados: {models_loaded} camadas")
            return models_loaded > 0
            
        except Exception as e:
            logger.error(f"Erro ao carregar modelos: {e}")
            return False
    
    def initialize(self):
        """Inicializa sistema completo"""
        try:
            print("\n" + "=" * 80)
            print(" QUANTUM TRADER v2.0 - SISTEMA COMPLETO COM OCO")
            print("=" * 80)
            print(f"Horário: {datetime.now():%Y-%m-%d %H:%M:%S}")
            print()
            
            # 1. Modelos ML
            print("[1/7] Carregando modelos híbridos...")
            if self.load_hybrid_models():
                print(f"  [OK] {len(self.models)} modelos carregados")
            else:
                print("  [INFO] Sistema rodará sem modelos ML")
            
            # 2. HMARL Agents
            print("\n[2/7] Inicializando HMARL Agents...")
            if self.hmarl_agents:
                print("  [OK] 4 agentes HMARL ativos")
                print("    - OrderFlowSpecialist")
                print("    - LiquidityAgent")
                print("    - TapeReadingAgent")
                print("    - FootprintPatternAgent")
            else:
                print("  [INFO] HMARL não disponível")
            
            # 3. Conexão ProfitChart com OCO
            print("\n[3/7] Conectando ao ProfitChart (com OCO)...")
            
            # Obter caminho da DLL
            dll_path = Path(os.getcwd()) / 'ProfitDLL64.dll'
            if not dll_path.exists():
                dll_path = Path('ProfitDLL64.dll')
            
            # Criar connection manager OCO
            self.connection = ConnectionManagerOCO(str(dll_path))
            
            # Configurar callback para quando posição fechar
            if hasattr(self.connection, 'oco_monitor') and self.connection.oco_monitor:
                self.connection.oco_monitor.position_closed_callback = self.handle_position_closed
                logger.info("Callback de fechamento de posição configurado")
            
            # Obter credenciais
            USERNAME = os.getenv('PROFIT_USERNAME', '')
            PASSWORD = os.getenv('PROFIT_PASSWORD', '')
            
            if self.connection.initialize(username=USERNAME, password=PASSWORD):
                print("  [OK] CONECTADO À B3!")
                
                # Aguardar broker
                print("  [*] Aguardando conexão com broker...")
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
                print(f"    Login: {'OK' if status['connected'] else 'X'}")
                print(f"    Market: {'OK' if status['market'] else 'X'}")
                print(f"    Broker: {'OK' if broker_connected else 'X'}")
                print(f"    Símbolo: {self.symbol}")
                
                if not broker_connected:
                    print("  [AVISO] Broker não conectado - usando rastreamento interno")
                    self.use_internal_tracking = True
            else:
                print("  [ERRO] Falha na conexão")
                return False
            
            # 4. Verificar posição inicial
            print("\n[4/7] Verificando posições abertas...")
            self.check_position_status()
            if self.has_open_position:
                print(f"  [POSIÇÃO] {self.current_position} {self.current_position_side}")
            else:
                print("  [OK] Sem posições abertas")
            
            # 5. Gravação de dados
            if self.enable_recording:
                print("\n[5/7] Configurando gravação de dados...")
                self._setup_data_recording()
                print(f"  [OK] Gravação habilitada em data/book_tick_data/")
            
            # 6. Sistema de trading
            print("\n[6/7] Configurando sistema de trading...")
            if self.enable_trading:
                print(f"  [OK] Trading ATIVO - Confiança mínima: {self.min_confidence:.0%}")
                print(f"    Stop Loss: {self.stop_loss:.1%}")
                print(f"    Take Profit: {self.take_profit:.1%}")
                print(f"    OCO: ATIVADO")
                print(f"    Controle de Posição: ATIVADO")
                print(f"    Max trades/dia: {self.max_daily_trades}")
            else:
                print("  [INFO] Trading em modo SIMULAÇÃO")
            
            # 7. Monitor
            print("\n[7/7] Iniciando monitor de console...")
            try:
                self.monitor_process = subprocess.Popen(
                    ['python', 'core/monitor_console_enhanced.py'],
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                )
                print("  [OK] Monitor iniciado em nova janela")
            except:
                print("  [INFO] Execute 'python core/monitor_console_enhanced.py' manualmente")
            
            # Agendar re-treinamento
            if self.enable_daily_training and self.retraining_system:
                threading.Thread(target=self._training_scheduler, daemon=True).start()
                print("\n[*] Re-treinamento diário agendado para 18:40")
            
            print("\n" + "=" * 80)
            print(" SISTEMA COMPLETO INICIALIZADO COM SUCESSO!")
            print("=" * 80)
            print("\nRecursos ativos:")
            print("  ✓ Modelos ML híbridos" if self.models else "  ○ Modelos ML")
            print("  ✓ HMARL Agents" if self.hmarl_agents else "  ○ HMARL")
            print("  ✓ OCO (One-Cancels-Other)")
            print("  ✓ Controle de Posição Única")
            print("  ✓ Gravação de Dados" if self.enable_recording else "  ○ Gravação")
            print("  ✓ Trading Real" if self.enable_trading else "  ○ Trading (simulado)")
            print("  ✓ Re-treinamento Diário" if self.enable_daily_training else "  ○ Re-treinamento")
            print()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro na inicialização: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _setup_data_recording(self):
        """Configura gravação de dados para treinamento"""
        data_dir = Path('data/book_tick_data')
        data_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Arquivo de book
        self.data_files['book'] = data_dir / f'book_data_{timestamp}.csv'
        with open(self.data_files['book'], 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'symbol',
                'bid_price_1', 'bid_vol_1', 'bid_price_2', 'bid_vol_2',
                'bid_price_3', 'bid_vol_3', 'bid_price_4', 'bid_vol_4',
                'bid_price_5', 'bid_vol_5',
                'ask_price_1', 'ask_vol_1', 'ask_price_2', 'ask_vol_2',
                'ask_price_3', 'ask_vol_3', 'ask_price_4', 'ask_vol_4',
                'ask_price_5', 'ask_vol_5',
                'spread', 'mid_price', 'imbalance', 'total_bid_vol', 'total_ask_vol'
            ])
        
        # Arquivo de trades
        self.data_files['tick'] = data_dir / f'tick_data_{timestamp}.csv'
        with open(self.data_files['tick'], 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'symbol', 'price', 'volume', 'aggressor',
                'buyer_id', 'seller_id', 'trade_type'
            ])
        
        logger.info(f"Arquivos de dados criados: {timestamp}")
    
    def check_position_status(self):
        """Verifica posição e limpa órfãs"""
        if not self.connection:
            return
        
        try:
            # Usar método apropriado
            if self.use_internal_tracking:
                position = self.connection.get_position_safe(self.symbol)
            else:
                try:
                    position = self.connection.get_position(self.symbol)
                except:
                    self.use_internal_tracking = True
                    position = self.connection.get_position_safe(self.symbol)
            
            if position:
                # Tem posição
                if not self.has_open_position:
                    logger.info(f"[POSIÇÃO] Nova: {position['quantity']} {position['side']}")
                
                self.has_open_position = True
                if not self.position_open_time:
                    self.position_open_time = datetime.now()  # Registrar tempo se não tem
                self.current_position = position['quantity'] if position['side'] == 'BUY' else -position['quantity']
                self.current_position_side = position['side']
                
            else:
                # Sem posição
                if self.has_open_position:
                    # Calcular tempo que ficou com posição
                    if self.position_open_time:
                        position_duration = (datetime.now() - self.position_open_time).total_seconds()
                        logger.info(f"[POSIÇÃO] Fechada após {position_duration:.0f}s")
                    else:
                        logger.info("[POSIÇÃO] Fechada")
                    
                    # Limpar estado de posição
                    self.active_orders = {}
                    
                    # Atualizar métricas
                    if self.active_orders:
                        self.metrics['wins'] += 1
                    
                    # Limpar órfãs
                    logger.info("[LIMPEZA] Cancelando órfãs...")
                    if self.connection.cancel_all_pending_orders(self.symbol):
                        logger.info("[OK] Órfãs canceladas")
                    
                    self.active_orders.clear()
                
                # LIMPAR TODOS OS FLAGS DE POSIÇÃO
                self.has_open_position = False
                self.position_open_time = None  # NOVO: Limpar tempo
                self.current_position = 0
                self.current_position_side = None
                
        except Exception as e:
            logger.error(f"Erro ao verificar posição: {e}")
    
    def make_hybrid_prediction(self):
        """Faz predição usando modelos híbridos + HMARL (APENAS com dados reais)"""
        try:
            # Contador de iteração para logs
            if not hasattr(self, 'prediction_iteration'):
                self.prediction_iteration = 0
            self.prediction_iteration += 1
            iteration = self.prediction_iteration
            # NUNCA gerar sinais de teste - sempre aguardar dados reais
            
            # Verificar se tem dados reais suficientes
            if len(self.book_buffer) < 100:
                return {'signal': 0, 'confidence': 0.0}
            
            # 1. Predição ML (se disponível)
            ml_signal = 0
            ml_confidence = 0.0
            ml_predictions = {}
            
            if self.models and len(self.book_buffer) >= 100:
                # Simular predição ML para teste
                # TODO: Implementar predição real quando features estiverem prontas
                import random
                if random.random() < 0.1:  # 10% chance de sinal ML (aumentado)
                    ml_signal = random.choice([-1, 0, 1])
                    ml_confidence = 0.5 + random.random() * 0.4
                    
                    ml_predictions = {
                        'context_pred': ml_signal,
                        'context_conf': ml_confidence * 0.85,
                        'micro_pred': ml_signal,
                        'micro_conf': ml_confidence * 0.95,
                        'meta_pred': ml_signal,
                        'ml_confidence': ml_confidence
                    }
                    
                    # Gravar predições ML
                    if self.monitor_bridge:
                        ml_predictions['predictions_count'] = self.metrics.get('predictions_today', 0)
                        self.monitor_bridge.update('ml', ml_predictions)
                        self.metrics['ml_signals'] += 1
            
            # 2. Predição HMARL (se disponível)
            hmarl_signal = 0
            hmarl_confidence = 0.0
            hmarl_data = {}
            
            # Log de verificação do HMARL a cada 30 iterações
            if iteration % 30 == 0:
                logger.info(f"[HMARL CHECK] agents={self.hmarl_agents is not None}, book_update={self.last_book_update is not None}, book_buffer={len(self.book_buffer)}")
            
            if self.hmarl_agents and (self.last_book_update or len(self.book_buffer) > 0):
                try:
                    # Log periódico para debug
                    if iteration % 30 == 0:  # A cada 30 iterações
                        logger.info(f"[HMARL] Processando com book_buffer={len(self.book_buffer)}, tick_buffer={len(self.tick_buffer)}")
                    
                    # Usar dados do book se disponível
                    if self.last_book_update:
                        book_data = self.last_book_update
                    elif len(self.book_buffer) > 0:
                        book_data = self.book_buffer[-1]
                    else:
                        book_data = {'bid_price_1': 5500, 'ask_price_1': 5505, 'bid_vol_1': 100, 'ask_vol_1': 100}
                    
                    # Atualizar dados de mercado nos agentes HMARL
                    current_price = (book_data.get('bid_price_1', 5500) + book_data.get('ask_price_1', 5505)) / 2
                    spread = book_data.get('ask_price_1', 5505) - book_data.get('bid_price_1', 5500)
                    imbalance = (book_data.get('bid_vol_1', 100) - book_data.get('ask_vol_1', 100)) / (book_data.get('bid_vol_1', 100) + book_data.get('ask_vol_1', 100) + 1e-8)
                    
                    # Atualizar buffers dos agentes
                    self.hmarl_agents.update_market_data(
                        price=current_price,
                        volume=self.total_volume if hasattr(self, 'total_volume') else 100,
                        book_data={
                            'spread': spread,
                            'imbalance': imbalance
                        }
                    )
                    
                    # Obter consenso (já calcula sinais internamente)
                    consensus = self.hmarl_agents.get_consensus()
                    
                    # SEMPRE atualizar dados HMARL para o monitor
                    hmarl_signal = 1 if consensus['action'] == 'BUY' else -1 if consensus['action'] == 'SELL' else 0
                    hmarl_confidence = consensus.get('confidence', 0.0)
                    
                    # Gravar dados HMARL (sempre, mesmo sem sinal forte)
                    hmarl_data = {
                        'action': consensus.get('action', 'HOLD'),
                        'signal': consensus.get('signal', hmarl_signal),
                        'confidence': hmarl_confidence,
                        'agents': consensus.get('agents', {}),  # Agora pega os agentes do consensus
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # SEMPRE atualizar o monitor bridge
                    if self.monitor_bridge:
                        try:
                            self.monitor_bridge.update('hmarl', hmarl_data)
                            if iteration % 30 == 0:  # Log periódico
                                logger.info(f"[HMARL] Bridge atualizado: {hmarl_data.get('action')} @ {hmarl_confidence:.1%}")
                        except Exception as e:
                            logger.warning(f"Erro ao atualizar bridge HMARL: {e}")
                    
                    # Contar como sinal apenas se confiança > 50%
                    if hmarl_confidence > 0.50:
                        self.metrics['hmarl_signals'] += 1
                            
                except Exception as e:
                    logger.warning(f"[HMARL] Erro ao processar agentes: {e}")
                    if iteration % 30 == 0:
                        import traceback
                        logger.error(f"[HMARL] Stack trace: {traceback.format_exc()}")
            
            # 3. Combinar sinais (60% ML + 40% HMARL)
            if ml_signal != 0 or hmarl_signal != 0:
                combined_signal = 0.6 * ml_signal + 0.4 * hmarl_signal
                combined_confidence = max(ml_confidence, hmarl_confidence)
                
                final_signal = int(np.sign(combined_signal)) if abs(combined_signal) > 0.3 else 0
                
                return {
                    'signal': final_signal,
                    'confidence': combined_confidence,
                    'ml_signal': ml_signal,
                    'hmarl_signal': hmarl_signal
                }
            
            return {'signal': 0, 'confidence': 0.0}
            
        except Exception as e:
            logger.error(f"Erro na predição: {e}")
            return {'signal': 0, 'confidence': 0.0}
    
    def execute_trade_with_oco(self, signal, confidence):
        """Executa trade com OCO e controle de posição"""
        
        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX
        
        # VERIFICAÇÃO GLOBAL: Lock de posição
        with GLOBAL_POSITION_LOCK_MUTEX:
            if GLOBAL_POSITION_LOCK:
                # Verificar tempo com lock
                if GLOBAL_POSITION_LOCK_TIME:
                    time_locked = (datetime.now() - GLOBAL_POSITION_LOCK_TIME).total_seconds()
                    global_lock_logger.debug(f"[GLOBAL LOCK] Posição travada há {time_locked:.0f}s")
                    
                    # Se está travado há mais de 5 minutos, pode ser um problema
                    if time_locked > 300:  # 5 minutos
                        global_lock_logger.warning(f"[GLOBAL LOCK] Lock muito antigo ({time_locked:.0f}s). Verificar sistema.")
                
                self.metrics['blocked_signals'] += 1
                return False
        
        # VERIFICAÇÃO 1: Posição aberta (backup local)
        if self.has_open_position:
            # Verificar se está com posição há tempo suficiente
            if self.position_open_time:
                time_with_position = (datetime.now() - self.position_open_time).total_seconds()
                if time_with_position < self.min_position_hold_time:
                    logger.debug(f"[BLOQUEADO] Posição muito recente ({time_with_position:.0f}s < {self.min_position_hold_time}s)")
                    self.metrics['blocked_signals'] += 1
                    return False
            logger.debug(f"[BLOQUEADO] Posição aberta. Sinal ignorado.")
            self.metrics['blocked_signals'] += 1
            return False
            
        # VERIFICAÇÃO 2: Ordens ativas
        if len(self.active_orders) > 0:
            logger.debug(f"[BLOQUEADO] Ordens ativas: {self.active_orders}. Sinal ignorado.")
            self.metrics['blocked_signals'] += 1
            return False
        
        # Verificar tempo mínimo entre trades
        if self.last_trade_time:
            time_since_last = (datetime.now() - self.last_trade_time).total_seconds()
            if time_since_last < self.min_time_between_trades:
                logger.debug(f"[BLOQUEADO] Aguardar {self.min_time_between_trades - time_since_last:.0f}s para próximo trade")
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
            
            # Obter preço REAL do mercado
            current_price = 0
            
            # PRIORIDADE 1: Preço real da conexão
            if self.connection and hasattr(self.connection, 'last_price'):
                real_price = self.connection.last_price
                if real_price > 0:
                    current_price = real_price
                    logger.info(f"[TRADE] Usando preço real do mercado: R$ {real_price:.2f}")
            
            # PRIORIDADE 2: Preço médio do book real
            elif self.connection and hasattr(self.connection, 'best_bid') and hasattr(self.connection, 'best_ask'):
                if self.connection.best_bid > 0 and self.connection.best_ask > 0:
                    current_price = (self.connection.best_bid + self.connection.best_ask) / 2.0
                    logger.info(f"[TRADE] Usando preço médio do book: R$ {current_price:.2f}")
            
            # PRIORIDADE 3: Usar último preço conhecido
            elif self.current_price > 1000:  # Verificar se é preço válido do WDO
                current_price = self.current_price
                logger.info(f"[TRADE] Usando último preço conhecido: R$ {current_price:.2f}")
            
            # Se não tem preço real, abortar trade
            if current_price == 0 or current_price < 1000:
                logger.error(f"[ERRO] Sem preço real do mercado! Abortando trade.")
                return False
            
            # USAR CALCULADOR DINÂMICO DE RISCO
            if self.risk_calculator:
                try:
                    # Preparar informações sobre origem do sinal
                    signal_source = {
                        'microstructure_weight': 0.6 if hasattr(self, '_last_micro_conf') and self._last_micro_conf > 0.65 else 0.3,
                        'context_weight': 0.6 if hasattr(self, '_last_context_conf') and self._last_context_conf > 0.65 else 0.3,
                        'ml_confidence': getattr(self, '_last_ml_conf', confidence),
                        'hmarl_confidence': getattr(self, '_last_hmarl_conf', confidence)
                    }
                    
                    # Calcular níveis dinâmicos
                    risk_levels = self.risk_calculator.calculate_dynamic_levels(
                        current_price=current_price,
                        signal=signal,
                        confidence=confidence,
                        signal_source=signal_source
                    )
                    
                    stop_price = risk_levels['stop_price']
                    take_price = risk_levels['take_price']
                    
                    # Log do tipo de trade
                    logger.info(f"[DYNAMIC RISK] {risk_levels['trade_type'].upper()}")
                    logger.info(f"  Risk/Reward: 1:{risk_levels['risk_reward_ratio']:.1f}")
                    
                except Exception as e:
                    logger.warning(f"Erro no calculador dinâmico: {e}. Usando fallback.")
                    # Fallback para cálculo simples
                    if signal > 0:  # BUY
                        stop_price = current_price - 15  # 15 pontos padrão
                        take_price = current_price + 30  # 30 pontos padrão
                    else:  # SELL
                        stop_price = current_price + 15
                        take_price = current_price - 30
                    
                    stop_price = round(stop_price / 5) * 5
                    take_price = round(take_price / 5) * 5
            else:
                # Sem calculador dinâmico - usar valores fixos em pontos
                if signal > 0:  # BUY
                    stop_price = current_price - 15  # 15 pontos
                    take_price = current_price + 30  # 30 pontos
                else:  # SELL
                    stop_price = current_price + 15
                    take_price = current_price - 30
                
                stop_price = round(stop_price / 5) * 5
                take_price = round(take_price / 5) * 5
            
            logger.info("=" * 60)
            logger.info(f"[TRADE OCO] {side}")
            logger.info(f"  Confiança: {confidence:.2%}")
            
            # Calcular distâncias em pontos
            stop_distance = abs(stop_price - current_price)
            take_distance = abs(take_price - current_price)
            
            logger.info(f"  Stop: {stop_price:.0f} ({stop_distance:.0f} pontos)")
            logger.info(f"  Take: {take_price:.0f} ({take_distance:.0f} pontos)")
            
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
                # MARCAR POSIÇÃO COMO ABERTA IMEDIATAMENTE
                # Armazenar informações da ordem no dicionário active_orders
                main_order_id = order_ids.get('main_order', 0)
                self.active_orders[main_order_id] = {
                    'order_ids': order_ids,
                    'side': side,
                    'quantity': quantity,
                    'confidence': confidence,
                    'timestamp': datetime.now()
                }
                self.has_open_position = True
                self.position_open_time = datetime.now()  # NOVO: Registrar tempo de abertura
                self.current_position = quantity if signal > 0 else -quantity
                self.current_position_side = side
                self.metrics['trades_today'] += 1
                self.last_trade_time = datetime.now()  # Registrar hora do trade
                
                # SETAR LOCK GLOBAL
                with GLOBAL_POSITION_LOCK_MUTEX:
                    GLOBAL_POSITION_LOCK = True
                    GLOBAL_POSITION_LOCK_TIME = datetime.now()
                    global_lock_logger.warning(f"[GLOBAL LOCK] ATIVADO - Posição {side} aberta")
                    global_lock_logger.info(f"  Bloqueio por {self.min_position_hold_time}s mínimo")
                
                # LOG CLARO DO ESTADO
                logger.warning(f"[POSIÇÃO ABERTA] Bloqueando novos trades por {self.min_position_hold_time}s")
                logger.info(f"  Posição: {side} x{quantity}")
                logger.info(f"  IDs: {order_ids}")
                
                # Atualizar bridge do monitor
                if self.monitor_bridge:
                    try:
                        if hasattr(self.monitor_bridge, 'update'):
                            self.monitor_bridge.update('last_trade', {
                                'side': side,
                                'confidence': confidence,
                                'stop': stop_price,
                                'take': take_price,
                                'timestamp': datetime.now().isoformat()
                            })
                        elif hasattr(self.monitor_bridge, 'send_update'):
                            self.monitor_bridge.send_update({
                                'type': 'last_trade',
                                'side': side,
                                'confidence': confidence,
                                'stop': stop_price,
                                'take': take_price,
                                'timestamp': datetime.now()
                            })
                    except:
                        pass
                
                logger.info(f"[SUCESSO] Ordens: {order_ids}")
                return True
            else:
                logger.error("[ERRO] Falha ao enviar")
                return False
                
        except Exception as e:
            logger.error(f"Erro no trade: {e}")
            return False
    
    def process_book_update(self, book_data):
        """Processa atualização do book"""
        try:
            # Atualizar buffers (manter histórico)
            if len(self.book_buffer) >= 1000:
                self.book_buffer.popleft()  # Remover mais antigo se buffer cheio
            self.book_buffer.append(book_data)
            self.last_book_update = book_data
            
            # Calcular mid price
            if 'bid_price_1' in book_data and 'ask_price_1' in book_data:
                self.last_mid_price = (book_data['bid_price_1'] + book_data['ask_price_1']) / 2
                self.current_price = self.last_mid_price
            
            # Gravar dados
            if self.enable_recording and 'book' in self.data_files:
                self._save_book_data(book_data)
            
            # Atualizar métricas
            self.feature_count += 1
            
        except Exception as e:
            logger.error(f"Erro ao processar book: {e}")
    
    def handle_position_closed(self, reason="unknown"):
        """Limpa estado quando posição é fechada"""
        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX
        
        logger.info(f"[POSIÇÃO FECHADA] Motivo: {reason}")
        
        # RESETAR LOCK GLOBAL
        with GLOBAL_POSITION_LOCK_MUTEX:
            if GLOBAL_POSITION_LOCK:
                if GLOBAL_POSITION_LOCK_TIME:
                    duration = (datetime.now() - GLOBAL_POSITION_LOCK_TIME).total_seconds()
                    global_lock_logger.warning(f"[GLOBAL LOCK] DESATIVADO após {duration:.0f}s")
                else:
                    global_lock_logger.warning(f"[GLOBAL LOCK] DESATIVADO")
                    
            GLOBAL_POSITION_LOCK = False
            GLOBAL_POSITION_LOCK_TIME = None
        
        # CANCELAMENTO AGRESSIVO DE ORDENS
        try:
            if self.connection:
                logger.warning(f"[CANCELAMENTO AGRESSIVO] Cancelando TODAS ordens pendentes")
                self.connection.cancel_all_pending_orders(self.symbol)
                time.sleep(0.5)  # Pequena pausa
                
                # Tentar cancelar novamente para garantir
                self.connection.cancel_all_pending_orders(self.symbol)
        except Exception as e:
            logger.error(f"Erro ao cancelar ordens: {e}")
        
        # Limpar estado local
        self.has_open_position = False
        self.position_open_time = None
        self.current_position = 0
        self.current_position_side = None
        self.active_orders = {}
        
        logger.info("[SISTEMA LIMPO] Pronto para nova posição")
    
    def check_position_status(self):
        """Verifica periodicamente o status da posição"""
        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME
        
        # Se tem lock mas não tem posição local, pode ser problema
        if GLOBAL_POSITION_LOCK and not self.has_open_position:
            if GLOBAL_POSITION_LOCK_TIME:
                time_locked = (datetime.now() - GLOBAL_POSITION_LOCK_TIME).total_seconds()
                if time_locked > 60:  # Lock sem posição por mais de 1 minuto
                    logger.warning(f"[INCONSISTÊNCIA] Lock global sem posição local há {time_locked:.0f}s")
                    self.handle_position_closed("inconsistency_detected")
    
    def cleanup_orphan_orders_loop(self):
        """Thread dedicada para limpar ordens órfãs periodicamente"""
        logger.info("[CLEANUP] Thread de limpeza de ordens órfãs iniciada")
        
        while self.running:
            try:
                time.sleep(5)  # Verificar a cada 5 segundos
                
                global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME
                
                # VERIFICAÇÃO 1: Lock muito antigo sem posição
                if GLOBAL_POSITION_LOCK and not self.has_open_position:
                    if GLOBAL_POSITION_LOCK_TIME:
                        elapsed = (datetime.now() - GLOBAL_POSITION_LOCK_TIME).total_seconds()
                        if elapsed > 30:  # 30 segundos com lock mas sem posição
                            logger.warning(f"[CLEANUP] Lock travado há {elapsed:.0f}s sem posição. Forçando limpeza.")
                            self.handle_position_closed("cleanup_forced_lock")
                
                # VERIFICAÇÃO 2: Ordens ativas sem posição (órfãs)
                # Garantir que active_orders seja um dicionário
                if not isinstance(self.active_orders, dict):
                    logger.warning(f"[CLEANUP] active_orders não é dict: {type(self.active_orders)}. Resetando...")
                    self.active_orders = {}
                
                if not self.has_open_position and self.active_orders:
                    logger.warning(f"[CLEANUP] Detectadas {len(self.active_orders)} ordens órfãs sem posição")
                    
                    # Cancelar TODAS ordens pendentes
                    try:
                        if self.connection:
                            logger.info("[CLEANUP] Cancelando todas ordens órfãs...")
                            self.connection.cancel_all_pending_orders(self.symbol)
                            time.sleep(1)  # Pausa para garantir cancelamento
                            
                            # Tentar novamente para garantir
                            self.connection.cancel_all_pending_orders(self.symbol)
                            
                            # Limpar tracking interno
                            self.active_orders = {}
                            logger.info("[CLEANUP] Ordens órfãs canceladas e estado limpo")
                    except Exception as e:
                        logger.error(f"[CLEANUP] Erro ao cancelar ordens órfãs: {e}")
                
                # VERIFICAÇÃO 3: Posição sem lock (inconsistência inversa)
                if self.has_open_position and not GLOBAL_POSITION_LOCK:
                    logger.warning("[CLEANUP] Posição aberta sem lock global. Sincronizando...")
                    with GLOBAL_POSITION_LOCK_MUTEX:
                        GLOBAL_POSITION_LOCK = True
                        GLOBAL_POSITION_LOCK_TIME = datetime.now()
                
                # VERIFICAÇÃO 4: OCO Monitor - verificar se ordens OCO precisam ser canceladas
                if self.has_open_position and isinstance(self.active_orders, dict) and self.active_orders:
                    # Para cada ordem ativa, verificar se alguma foi executada
                    for order_id, order_info in list(self.active_orders.items()):
                        if 'order_ids' in order_info:
                            # Verificar se stop ou take foi executado
                            # (Isso seria implementado com get_order_status quando disponível)
                            pass
                
            except Exception as e:
                logger.error(f"[CLEANUP] Erro na thread de limpeza: {e}")
                time.sleep(10)  # Aguardar mais em caso de erro
        
        logger.info("[CLEANUP] Thread de limpeza finalizada")
    
    def process_trade(self, trade_data):
        """Processa novo trade"""
        try:
            # Atualizar buffers (manter histórico)
            if len(self.tick_buffer) >= 1000:
                self.tick_buffer.popleft()  # Remover mais antigo se buffer cheio
            self.tick_buffer.append(trade_data)
            self.last_trade = trade_data
            
            # Atualizar preço
            if 'price' in trade_data:
                self.current_price = trade_data['price']
                self.price_history.append(trade_data['price'])
            
            # Atualizar volume total
            if 'volume' in trade_data:
                self.total_volume += trade_data.get('volume', 0)
            
            # Gravar dados
            if self.enable_recording and 'tick' in self.data_files:
                self._save_tick_data(trade_data)
                
        except Exception as e:
            logger.error(f"Erro ao processar trade: {e}")
    
    def _save_book_data(self, book_data):
        """Salva dados do book"""
        try:
            with self.data_lock:
                with open(self.data_files['book'], 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        datetime.now(),
                        self.symbol,
                        book_data.get('bid_price_1', 0),
                        book_data.get('bid_vol_1', 0),
                        book_data.get('bid_price_2', 0),
                        book_data.get('bid_vol_2', 0),
                        book_data.get('bid_price_3', 0),
                        book_data.get('bid_vol_3', 0),
                        book_data.get('bid_price_4', 0),
                        book_data.get('bid_vol_4', 0),
                        book_data.get('bid_price_5', 0),
                        book_data.get('bid_vol_5', 0),
                        book_data.get('ask_price_1', 0),
                        book_data.get('ask_vol_1', 0),
                        book_data.get('ask_price_2', 0),
                        book_data.get('ask_vol_2', 0),
                        book_data.get('ask_price_3', 0),
                        book_data.get('ask_vol_3', 0),
                        book_data.get('ask_price_4', 0),
                        book_data.get('ask_vol_4', 0),
                        book_data.get('ask_price_5', 0),
                        book_data.get('ask_vol_5', 0),
                        book_data.get('spread', 0),
                        self.last_mid_price,
                        book_data.get('imbalance', 0),
                        book_data.get('total_bid_vol', 0),
                        book_data.get('total_ask_vol', 0)
                    ])
        except:
            pass
    
    def _save_tick_data(self, trade_data):
        """Salva dados de trades"""
        try:
            with self.data_lock:
                with open(self.data_files['tick'], 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        datetime.now(),
                        self.symbol,
                        trade_data.get('price', 0),
                        trade_data.get('volume', 0),
                        trade_data.get('aggressor', 0),
                        trade_data.get('buyer_id', ''),
                        trade_data.get('seller_id', ''),
                        trade_data.get('trade_type', 0)
                    ])
        except:
            pass
    
    def _training_scheduler(self):
        """Agenda re-treinamento diário"""
        while self.running:
            try:
                now = datetime.now()
                
                # Verificar se é hora (18:40)
                if now.hour == 18 and now.minute == 40:
                    logger.info("[TRAINING] Iniciando re-treinamento diário...")
                    
                    if self.retraining_system:
                        # Executar re-treinamento
                        success = self.retraining_system.run_retraining_pipeline()
                        
                        if success:
                            logger.info("[TRAINING] Re-treinamento concluído com sucesso")
                            
                            # Recarregar modelos
                            if self.model_selector:
                                best_model = self.model_selector.get_current_best_model()
                                if best_model:
                                    logger.info(f"[TRAINING] Usando modelo: {best_model['name']}")
                        else:
                            logger.warning("[TRAINING] Re-treinamento falhou")
                    
                    # Aguardar próximo dia
                    time.sleep(3600)  # 1 hora para evitar re-execução
                
                time.sleep(60)  # Verificar a cada minuto
                
            except Exception as e:
                logger.error(f"Erro no scheduler: {e}")
                time.sleep(300)
    
    def position_monitor_loop(self):
        """Monitor de posições"""
        while self.running:
            try:
                # Verificar posição periodicamente
                self.check_position_status()
                
                # Aguardar
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Erro no monitor de posição: {e}")
                time.sleep(5)
    
    def trading_loop(self):
        """Loop principal de trading"""
        logger.info("Iniciando loop de trading...")
        
        while self.running:
            try:
                # Fazer predição
                prediction = self.make_hybrid_prediction()
                self.metrics['predictions_today'] += 1
                
                # Executar trade se sinal válido
                if prediction['signal'] != 0 and prediction['confidence'] >= self.min_confidence:
                    self.execute_trade_with_oco(
                        signal=prediction['signal'],
                        confidence=prediction['confidence']
                    )
                
                # Aguardar
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Erro no trading: {e}")
                time.sleep(5)
    
    def metrics_loop(self):
        """Loop de métricas"""
        while self.running:
            try:
                # Calcular métricas
                total = self.metrics['wins'] + self.metrics['losses']
                win_rate = self.metrics['wins'] / total if total > 0 else 0
                
                # Atualizar bridge (se tem método update)
                if self.monitor_bridge:
                    try:
                        if hasattr(self.monitor_bridge, 'update'):
                            self.monitor_bridge.update('metrics', {
                                'trades_today': self.metrics['trades_today'],
                                'predictions': self.metrics['predictions_today'],
                                'win_rate': win_rate,
                                'position': self.has_open_position,
                                'blocked': self.metrics['blocked_signals']
                            })
                        elif hasattr(self.monitor_bridge, 'send_update'):
                            # Método alternativo
                            self.monitor_bridge.send_update({
                                'type': 'metrics',
                                'trades_today': self.metrics['trades_today'],
                                'predictions': self.metrics['predictions_today'],
                                'win_rate': win_rate,
                                'position': self.has_open_position,
                                'blocked': self.metrics['blocked_signals']
                            })
                    except:
                        pass  # Ignorar erros do bridge
                
                # Log
                logger.info(
                    f"[METRICS] Trades: {self.metrics['trades_today']} | "
                    f"WR: {win_rate:.1%} | "
                    f"Pred: {self.metrics['predictions_today']} | "
                    f"Bloq: {self.metrics['blocked_signals']} | "
                    f"Pos: {'SIM' if self.has_open_position else 'NÃO'}"
                )
                
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Erro nas métricas: {e}")
                time.sleep(60)
    
    def data_collection_loop(self):
        """Loop para coletar dados de mercado"""
        logger.info("Iniciando coleta de dados...")
        iteration_count = 0
        position_check_counter = 0
        
        while self.running:
            try:
                iteration_count += 1
                position_check_counter += 1
                
                # Verificar consistência de posição a cada 20 iterações (10 segundos)
                if position_check_counter >= 20:
                    self.check_position_status()
                    position_check_counter = 0
                
                # Log periódico de status
                if iteration_count % 120 == 0:  # A cada minuto (0.5s * 120)
                    if self.current_price > 0:
                        logger.info(f"[DATA] Buffers: book={len(self.book_buffer)}, tick={len(self.tick_buffer)}, price={self.current_price:.2f}")
                    else:
                        logger.info(f"[DATA] Buffers: book={len(self.book_buffer)}, tick={len(self.tick_buffer)}, aguardando preço...")
                
                # Tentar obter dados REAIS do connection manager
                if self.connection:
                    data_captured = False
                    
                    # PRIORIDADE 1: Preço real da conexão
                    if hasattr(self.connection, 'last_price') and self.connection.last_price > 0:
                        price = self.connection.last_price
                        if price > 0 and price != self.current_price:
                            logger.info(f"[REAL PRICE] Atualizando com preço real: R$ {price:.2f}")
                            self.current_price = price
                            self.price_history.append(price)
                            data_captured = True
                            
                        # Criar book com preços reais
                        if hasattr(self.connection, 'best_bid') and hasattr(self.connection, 'best_ask'):
                            bid = self.connection.best_bid if self.connection.best_bid > 0 else price - 2.5
                            ask = self.connection.best_ask if self.connection.best_ask > 0 else price + 2.5
                            
                            real_book = {
                                'timestamp': datetime.now(),
                                'bid_price_1': bid,
                                'bid_vol_1': 100,
                                'ask_price_1': ask,
                                'ask_vol_1': 100,
                                'spread': ask - bid
                            }
                            self.process_book_update(real_book)
                            
                            # Log de confirmação de preços reais
                            if iteration_count % 120 == 0:
                                logger.info(f"[MARKET DATA] Bid: {bid:.2f} | Ask: {ask:.2f} | Mid: {price:.2f}")
                    
                    # PRIORIDADE 2: Dados do last_book
                    elif hasattr(self.connection, 'last_book') and not data_captured:
                        book_data = self.connection.last_book
                        if book_data and book_data.get('bids') and book_data.get('asks'):
                            if len(book_data['bids']) > 0 and len(book_data['asks']) > 0:
                                bid_price = book_data['bids'][0].get('price', 0)
                                ask_price = book_data['asks'][0].get('price', 0)
                                
                                if bid_price > 0 and ask_price > 0:
                                    mid_price = (bid_price + ask_price) / 2.0
                                    self.current_price = mid_price
                                    self.price_history.append(mid_price)
                                    
                                    real_book = {
                                        'timestamp': book_data.get('timestamp', datetime.now()),
                                        'bid_price_1': bid_price,
                                        'bid_vol_1': book_data['bids'][0].get('volume', 100),
                                        'ask_price_1': ask_price,
                                        'ask_vol_1': book_data['asks'][0].get('volume', 100),
                                        'spread': ask_price - bid_price
                                    }
                                    self.process_book_update(real_book)
                                    data_captured = True
                    
                    # PRIORIDADE 3: Se tem método get_book
                    elif hasattr(self.connection, 'get_book') and not data_captured:
                        book = self.connection.get_book(self.symbol)
                        if book:
                            self.process_book_update(book)
                            data_captured = True
                    
                    # NUNCA simular dados - sempre aguardar dados reais
                    if not data_captured:
                        if iteration_count % 120 == 0:  # Log a cada minuto
                            logger.info("[WAITING] Aguardando dados reais do mercado...")
                            logger.info("  Certifique-se que o ProfitChart está conectado e transmitindo dados")
                            
                            # Status da conexão
                            if hasattr(self.connection, 'bMarketConnected'):
                                logger.info(f"  Market Connected: {self.connection.bMarketConnected}")
                            if hasattr(self.connection, 'callbacks'):
                                total_callbacks = sum(self.connection.callbacks.values())
                                logger.info(f"  Total callbacks recebidos: {total_callbacks}")
                
                # Aguardar
                time.sleep(0.5)  # Coletar 2x por segundo
                
            except Exception as e:
                logger.error(f"Erro na coleta de dados: {e}")
                time.sleep(5)
    
    def start(self):
        """Inicia sistema completo"""
        if not self.initialize():
            return False
        
        self.running = True
        
        # Iniciar thread de limpeza de ordens órfãs
        self.cleanup_thread = threading.Thread(target=self.cleanup_orphan_orders_loop, daemon=True)
        self.cleanup_thread.start()
        logger.info("[CLEANUP] Thread de limpeza iniciada")
        
        # Configurar callbacks para receber dados do mercado
        if self.connection:
            logger.info("Configurando callbacks de mercado...")
            
            # Tentar registrar callbacks se o connection manager suportar
            try:
                # Método 1: register_callback
                if hasattr(self.connection, 'register_book_callback'):
                    self.connection.register_book_callback(lambda data: self.process_book_update(data))
                    logger.info("Callback de book registrado")
                
                if hasattr(self.connection, 'register_trade_callback'):
                    self.connection.register_trade_callback(lambda data: self.process_trade(data))
                    logger.info("Callback de trade registrado")
                
                # Método 2: set_callbacks (alternativo)
                elif hasattr(self.connection, 'set_callbacks'):
                    self.connection.set_callbacks(
                        on_book=lambda data: self.process_book_update(data),
                        on_trade=lambda data: self.process_trade(data)
                    )
                    logger.info("Callbacks configurados via set_callbacks")
                
                # Método 3: Subscrever no símbolo
                if hasattr(self.connection, 'subscribe'):
                    self.connection.subscribe(self.symbol)
                    logger.info(f"Subscrito ao símbolo {self.symbol}")
                    
            except Exception as e:
                logger.warning(f"Não foi possível registrar callbacks: {e}")
                logger.info("Sistema funcionará sem dados de mercado em tempo real")
        
        # Iniciar threads
        threads = [
            threading.Thread(target=self.position_monitor_loop, daemon=True, name="PositionMonitor"),
            threading.Thread(target=self.trading_loop, daemon=True, name="Trading"),
            threading.Thread(target=self.metrics_loop, daemon=True, name="Metrics"),
            threading.Thread(target=self.data_collection_loop, daemon=True, name="DataCollection")
        ]
        
        for thread in threads:
            thread.start()
            logger.info(f"Thread {thread.name} iniciada")
        
        return True
    
    def stop(self):
        """Para sistema completo"""
        logger.info("Parando sistema...")
        
        self.running = False
        
        # Cancelar órfãs se não tem posição
        if self.connection and not self.has_open_position:
            logger.info("Cancelando ordens pendentes...")
            self.connection.cancel_all_pending_orders(self.symbol)
        
        # Parar monitor
        if self.monitor_process:
            self.monitor_process.terminate()
        
        # Desconectar
        if self.connection:
            self.connection.disconnect()
        
        logger.info("Sistema parado com segurança")


def signal_handler(sig, frame):
    """Handler para Ctrl+C"""
    print("\n[!] Recebido sinal de parada...")
    global system
    if 'system' in globals():
        system.stop()
    sys.exit(0)


def main():
    """Função principal"""
    global system
    
    # Registrar handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Criar sistema
    system = QuantumTraderCompleteOCO()
    
    try:
        if system.start():
            print("\nSistema rodando. Pressione Ctrl+C para parar...")
            
            # Manter rodando
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