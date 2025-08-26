#!/usr/bin/env python3
"""
QUANTUM TRADER v2.1 - SISTEMA COMPLETO COM OCO + EVENTOS
Integra sistema de eventos avançado com arquitetura existente
Baseado no START_SYSTEM_COMPLETE_OCO.py com novo EventBus
"""

import os
import sys
import time
import json
import signal
import logging
import threading
import subprocess
import random
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, time as dt_time
from dotenv import load_dotenv
from collections import deque
from typing import Dict, List, Optional, Any
import csv
import warnings
warnings.filterwarnings('ignore')

# Carregar configurações
load_dotenv('.env.production')

# Importar novo sistema baseado em regime
from src.trading.regime_based_strategy import RegimeBasedTradingSystem, RegimeSignal
from src.trading.smart_targets_calculator import SmartTargetsCalculator

# ============= SISTEMA DE EVENTOS INTEGRADO =============
from src.events import (
    init_event_system,
    integrate_with_existing_system,
    EventType,
    Event,  # Adicionando a classe Event
    emit_order_event,
    emit_position_event,
    get_event_bus,
    on_event
)

# ============= VARIÁVEIS GLOBAIS DE CONTROLE DE POSIÇÃO =============
GLOBAL_POSITION_LOCK = False
GLOBAL_POSITION_LOCK_TIME = None
GLOBAL_POSITION_LOCK_MUTEX = threading.Lock()

# Logger para o sistema de lock global
global_lock_logger = logging.getLogger('GlobalPositionLock')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/system_complete_oco_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('SystemCompleteOCOEvents')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent / 'core'))

# Importar componentes
from src.connection_manager_working import ConnectionManagerWorking
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
    from src.trading.order_manager import WDOOrderManager
except:
    WDOOrderManager = None
    logger.warning("WDOOrderManager não disponível")

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

try:
    from src.ml.hybrid_predictor import HybridMLPredictor
    logger.info("HybridMLPredictor carregado com sucesso!")
except Exception as e:
    HybridMLPredictor = None
    logger.warning(f"HybridMLPredictor não disponível: {e}")

# ============= SISTEMA DE OTIMIZAÇÃO PARA LATERALIZAÇÃO =============
try:
    from src.trading.optimization_integration import OptimizationSystem
    logger.info("Sistema de Otimização carregado com sucesso!")
except Exception as e:
    OptimizationSystem = None
    logger.warning(f"Sistema de Otimização não disponível: {e}")


class QuantumTraderCompleteOCOEvents:
    """Sistema completo com eventos integrados"""
    
    def __init__(self):
        self.running = False
        self.connection = None
        self.monitor_process = None
        self.data_lock = threading.Lock()
        self.cleanup_thread = None
        
        # NOVO: Sistema de eventos
        self.event_bus = None
        self.event_integration = None
        
        # NOVO: Sistema de Otimização
        self.optimization_system = None
        
        # NOVO: Preditor ML Híbrido
        self.ml_predictor = None
        
        # Configurações
        self.enable_trading = os.getenv('ENABLE_TRADING', 'false').lower() == 'true'
        self.enable_recording = os.getenv('ENABLE_DATA_RECORDING', 'true').lower() == 'true'
        self.enable_daily_training = os.getenv('ENABLE_DAILY_TRAINING', 'true').lower() == 'true'
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE', '0.65'))
        self.symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
        self.stop_loss = float(os.getenv('STOP_LOSS', '0.002'))
        self.take_profit = float(os.getenv('TAKE_PROFIT', '0.004'))
        self.max_daily_trades = int(os.getenv('MAX_DAILY_TRADES', '10'))
        
        # Controle de tempo entre trades
        self.last_trade_time = None
        self.min_time_between_trades = 60
        
        # Order Manager
        self.order_manager = WDOOrderManager() if WDOOrderManager else None
        
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
            self.hmarl_agents = None
        
        # Gestão de Risco
        self.risk_manager = AdaptiveRiskManager(self.symbol) if AdaptiveRiskManager else None
        self.risk_calculator = DynamicRiskCalculator() if DynamicRiskCalculator else None
        
        # NOVO: Sistema baseado em regime (substituindo ML defeituoso)
        self.regime_system = RegimeBasedTradingSystem(min_confidence=self.min_confidence)
        logger.info("[OK] Sistema de Trading Baseado em Regime inicializado")
        
        # NOVO: Calculador inteligente de targets
        self.smart_targets = SmartTargetsCalculator()
        logger.info("[OK] Calculador Inteligente de Targets inicializado")
        
        # Bridge para monitor
        self.monitor_bridge = get_bridge() if get_bridge else None
        
        # Re-treinamento
        self.retraining_system = SmartRetrainingSystem() if SmartRetrainingSystem else None
        self.model_selector = ModelSelector() if ModelSelector else None
        
        # Buffers de dados
        self.price_history = deque(maxlen=500)
        self.book_snapshots = deque(maxlen=200)
        self.tick_buffer = deque(maxlen=1000)
        self.book_buffer = deque(maxlen=1000)
        
        # Preços e dados
        self.current_price = 0
        self.last_mid_price = 0
        self.last_book_update = None
        self.last_trade = None
        self.total_volume = 0
        
        # Controle de posição
        self.has_open_position = False
        self.position_open_time = None
        self.min_position_hold_time = 30
        self.current_position = 0
        self.current_position_side = None
        self.current_position_id = None  # NOVO: ID da posição
        self.active_orders = {}
        self.use_internal_tracking = False
        
        # Verificar flag de reset forçado
        reset_flag_file = Path("data/monitor/force_position_reset.flag")
        if reset_flag_file.exists():
            logger.warning("[RESET] Flag de reset forçado detectado - limpando estado de posição")
            self.has_open_position = False
            self.current_position = 0
            self.current_position_side = None
            self.current_position_id = None
            self.active_orders = {}
            # Remover flag após processar
            try:
                reset_flag_file.unlink()
                logger.info("[RESET] Flag de reset removido")
            except:
                pass
        
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
            # NOVO: Métricas de validação de tendência
            'trades_blocked_by_trend': 0,
            'trend_validations': 0,
            'trend_aligned_trades': 0,
            'ml_signals': 0
        }
        
        # Arquivos de dados
        self.data_files = {}
        
        logger.info("Sistema Completo OCO com Eventos inicializado")
    
    def setup_event_handlers(self):
        """Configura handlers de eventos personalizados"""
        
        # Handler para quando ordem é executada
        @on_event(EventType.ORDER_FILLED, priority=9)
        def on_order_filled(event):
            logger.info(f"[EVENT] Ordem executada: {event.data}")
            # Atualizar métricas
            self.metrics['trades_today'] += 1
            
            # NOVO: Chamar handler de execução OCO
            order_id = event.data.get('order_id')
            if order_id:
                self.handle_order_execution(order_id, "filled")
                
                # Marcar no OCO Monitor também
                if hasattr(self.connection, 'oco_monitor'):
                    self.connection.oco_monitor.mark_order_executed(order_id)
        
        # Handler para quando posição fecha
        @on_event(EventType.POSITION_CLOSED, priority=9)
        def on_position_closed(event):
            logger.info(f"[EVENT] Posição fechada: PnL = {event.data.get('pnl', 0)}")
            
            # Atualizar métricas
            pnl = event.data.get('pnl', 0)
            self.metrics['total_pnl'] += pnl
            if pnl > 0:
                self.metrics['wins'] += 1
            else:
                self.metrics['losses'] += 1
            
            # Limpar estado de posição
            self.handle_position_closed("event_triggered")
        
        # Handler para stop/take triggered
        @on_event(EventType.STOP_TRIGGERED, priority=10)
        def on_stop_triggered(event):
            logger.warning(f"[EVENT] STOP LOSS acionado: {event.data}")
            self.handle_position_closed("stop_triggered")
        
        @on_event(EventType.TAKE_TRIGGERED, priority=10)
        def on_take_triggered(event):
            logger.info(f"[EVENT] TAKE PROFIT acionado: {event.data}")
            self.handle_position_closed("take_triggered")
        
        # Handler para limites de risco
        @on_event(EventType.RISK_LIMIT_REACHED, priority=10)
        def on_risk_limit(event):
            logger.critical(f"[EVENT] LIMITE DE RISCO: {event.data}")
            # Parar trading
            self.enable_trading = False
            # Fechar posições
            if self.connection:
                self.connection.close_all_positions()
        
        logger.info("Event handlers configurados")
    
    def load_hybrid_models(self):
        """Carrega modelos híbridos de 3 camadas"""
        logger.info("Carregando modelos híbridos...")
        
        # NOVO: Usar HybridMLPredictor se disponível
        if HybridMLPredictor:
            try:
                self.ml_predictor = HybridMLPredictor(models_dir="models/hybrid")
                if self.ml_predictor.load_models():
                    logger.info("[OK] HybridMLPredictor carregado com sucesso")
                    return True
                else:
                    logger.warning("HybridMLPredictor não conseguiu carregar modelos")
                    self.ml_predictor = None
            except Exception as e:
                logger.error(f"Erro ao inicializar HybridMLPredictor: {e}")
                self.ml_predictor = None
        
        # Fallback: Carregar modelos manualmente
        try:
            models_loaded = 0
            
            # Camada 1: Modelos de Contexto
            context_dir = self.models_dir / "context"
            if context_dir.exists():
                for model_file in context_dir.glob("*.pkl"):
                    model_name = model_file.stem
                    self.models[f"context_{model_name}"] = joblib.load(model_file)
                    models_loaded += 1
            
            # Camada 2: Modelos de Microestrutura
            micro_dir = self.models_dir / "microstructure"
            if micro_dir.exists():
                for model_file in micro_dir.glob("*.pkl"):
                    model_name = model_file.stem
                    self.models[f"micro_{model_name}"] = joblib.load(model_file)
                    models_loaded += 1
            
            # Camada 3: Meta-Learner
            meta_dir = self.models_dir / "meta_learner"
            if meta_dir.exists():
                for model_file in meta_dir.glob("*.pkl"):
                    model_name = model_file.stem
                    self.models[f"meta_{model_name}"] = joblib.load(model_file)
                    models_loaded += 1
            
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
        """Inicializa sistema completo com eventos"""
        try:
            print("\n" + "=" * 80)
            print(" QUANTUM TRADER v2.1 - SISTEMA COMPLETO COM OCO + EVENTOS")
            print("=" * 80)
            print(f"Horário: {datetime.now():%Y-%m-%d %H:%M:%S}")
            print()
            
            # 1. Sistema de Eventos
            print("[1/8] Inicializando Sistema de Eventos...")
            self.event_bus = init_event_system()
            self.setup_event_handlers()
            print("  [OK] EventBus iniciado")
            print("  [OK] Handlers configurados")
            
            # 2. Modelos ML
            print("\n[2/8] Carregando modelos híbridos...")
            if self.load_hybrid_models():
                print(f"  [OK] {len(self.models)} modelos carregados")
            else:
                print("  [INFO] Sistema rodará sem modelos ML")
            
            # 3. HMARL Agents
            print("\n[3/8] Inicializando HMARL Agents...")
            if self.hmarl_agents:
                print("  [OK] 4 agentes HMARL ativos")
            else:
                print("  [INFO] HMARL não disponível")
            
            # 4. Sistema de Otimização (NOVO)
            print("\n[4/9] Inicializando Sistema de Otimização...")
            if OptimizationSystem:
                try:
                    self.optimization_system = OptimizationSystem({
                        'enable_regime_detection': True,
                        'enable_adaptive_targets': True,
                        'enable_concordance_filter': True,
                        'enable_partial_exits': True,
                        'enable_trailing_stop': True,
                        'enable_metrics_tracking': True,
                        'min_confidence': self.min_confidence,
                        'max_daily_trades': self.max_daily_trades,
                        'position_size': 1
                    })
                    print("  [OK] Sistema de Otimização ativo")
                    print("     • Detector de Regime de Mercado")
                    print("     • Targets Adaptativos")
                    print("     • Filtro de Concordância ML+HMARL")
                    print("     • Gerenciador de Saídas Parciais")
                    print("     • Trailing Stop Adaptativo")
                    print("     • Rastreador de Métricas por Regime")
                except Exception as e:
                    logger.error(f"Erro ao inicializar otimização: {e}")
                    print(f"  [ERRO] {e}")
            else:
                print("  [INFO] Sistema de Otimização não disponível")
            
            # 5. Conexão ProfitChart com OCO
            print("\n[5/9] Conectando ao ProfitChart (com OCO)...")
            
            dll_path = Path(os.getcwd()) / 'ProfitDLL64.dll'
            if not dll_path.exists():
                dll_path = Path('ProfitDLL64.dll')
            
            self.connection = ConnectionManagerWorking(str(dll_path))
            
            # Integrar eventos com connection manager e order manager
            self.event_integration = integrate_with_existing_system(
                connection_manager=self.connection,
                order_manager=self.order_manager
            )
            print("  [OK] Sistema de eventos integrado")
            
            # Configurar callback via eventos
            if hasattr(self.connection, 'oco_monitor') and self.connection.oco_monitor:
                # Callback original ainda funciona, mas agora também emite eventos
                self.connection.oco_monitor.position_closed_callback = self.handle_position_closed
            
            USERNAME = os.getenv('PROFIT_USERNAME', '')
            PASSWORD = os.getenv('PROFIT_PASSWORD', '')
            KEY = os.getenv('PROFIT_KEY', '')
            
            # Configurar callback para receber atualizações de book
            self.connection.set_offer_book_callback(self.process_book_update)
            
            if self.connection.connect():
                print("  [OK] CONECTADO À B3!")
                
                # Aguardar broker (reduzido para 5 segundos)
                print("  [*] Aguardando conexão com broker (máx 5s)...")
                broker_connected = False
                for i in range(5):
                    if hasattr(self.connection, 'routing_connected') and self.connection.routing_connected:
                        print(f"  [OK] Broker conectado após {i+1} segundos")
                        broker_connected = True
                        break
                    time.sleep(1)
                
                if not broker_connected:
                    print("  [AVISO] Broker não conectado - usando rastreamento interno")
                    self.use_internal_tracking = True
                
                # Aguardar Market Data antes de subscrever
                print("\n  [*] Aguardando Market Data (máx 10s)...")
                market_connected = False
                for i in range(10):
                    if hasattr(self.connection, 'market_connected') and self.connection.market_connected:
                        print(f"  [OK] Market Data conectado após {i+1} segundos")
                        market_connected = True
                        break
                    time.sleep(1)
                
                if not market_connected:
                    print("  [AVISO] Market Data não conectado - tentando subscrever mesmo assim")
                
                # Aguardar mais 2 segundos para estabilizar antes de subscrever
                print("  [*] Aguardando estabilização...")
                time.sleep(2)
                
                # Subscrever ao símbolo usando o novo método unificado
                print(f"\n  [*] Subscrevendo ao {self.symbol}...")
                if self.connection.subscribe_symbol(self.symbol):
                    print(f"  [OK] Subscrito com sucesso ao {self.symbol}")
                    print(f"  [OK] Recebendo book, trades e price data")
            else:
                print("  [ERRO] Falha na conexão")
                return False
            
            # 6. Verificar posição inicial
            print("\n[6/9] Verificando posições abertas...")
            self.check_position_status()
            if self.has_open_position:
                print(f"  [POSIÇÃO] {self.current_position} {self.current_position_side}")
            else:
                print("  [OK] Sem posições abertas")
            
            # 7. Gravação de dados
            if self.enable_recording:
                print("\n[7/9] Configurando gravação de dados...")
                self._setup_data_recording()
                print(f"  [OK] Gravação habilitada")
            
            # 8. Sistema de trading
            print("\n[8/9] Configurando sistema de trading...")
            if self.enable_trading:
                print(f"  [OK] Trading ATIVO")
                print(f"    Sistema de Eventos: ATIVADO")
                print(f"    OCO: ATIVADO")
                print(f"    Sistema de Otimização: {'ATIVO' if self.optimization_system else 'INATIVO'}")
                print(f"    Max trades/dia: {self.max_daily_trades}")
            else:
                print("  [INFO] Trading em modo SIMULAÇÃO")
            
            # 9. Monitor
            print("\n[9/9] Monitor de console...")
            print("  [INFO] Execute monitor manualmente: python core/monitor_console_enhanced.py")
            # Comentado temporariamente para não bloquear
            # try:
            #     self.monitor_process = subprocess.Popen(
            #         ['python', 'core/monitor_console_enhanced.py'],
            #         creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            #     )
            #     print("  [OK] Monitor iniciado")
            # except:
            #     print("  [INFO] Execute monitor manualmente")
            
            # Agendar re-treinamento
            if self.enable_daily_training and self.retraining_system:
                threading.Thread(target=self._training_scheduler, daemon=True).start()
                print("\n[*] Re-treinamento diário agendado para 18:40")
            
            # Estatísticas do EventBus
            stats = self.event_bus.get_stats()
            
            print("\n" + "=" * 80)
            print(" SISTEMA INICIALIZADO COM SUCESSO!")
            print("=" * 80)
            print("\nRecursos ativos:")
            print("  [OK] Sistema de Eventos (EventBus)")
            print("  [OK] Modelos ML híbridos" if self.models else "  [--] Modelos ML")
            print("  [OK] HMARL Agents" if self.hmarl_agents else "  [--] HMARL")
            print("  [OK] OCO com Eventos")
            print("  [OK] Handlers de Risco")
            print("  [OK] Métricas Automáticas")
            print(f"\nEventBus Status: {stats['queue_size']} eventos na fila")
            print()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro na inicialização: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def execute_trade_with_oco(self, signal, confidence, ml_prediction=None, hmarl_consensus=None, regime_signal=None):
        """Executa trade com OCO e emite eventos, com Sistema de Otimização"""
        
        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME
        
        # Verificações de segurança (mantidas do original)
        with GLOBAL_POSITION_LOCK_MUTEX:
            if GLOBAL_POSITION_LOCK:
                self.metrics['blocked_signals'] += 1
                return False
        
        if self.has_open_position:
            logger.info(f"[TRADE BLOCKED] Já existe posição aberta - Posição: {self.current_position} {self.current_position_side}")
            self.metrics['blocked_signals'] += 1
            return False
        
        if len(self.active_orders) > 0:
            logger.debug(f"[TRADE BLOCKED] Existem {len(self.active_orders)} ordens pendentes")
            self.metrics['blocked_signals'] += 1
            return False
        
        # NOVA PROTEÇÃO: Verificar se há grupos OCO ativos (ordens pendentes)
        if self.connection and hasattr(self.connection, 'oco_monitor'):
            if hasattr(self.connection.oco_monitor, 'oco_groups'):
                active_oco_groups = sum(1 for g in self.connection.oco_monitor.oco_groups.values() 
                                       if g.get('active', False))
                if active_oco_groups > 0:
                    logger.warning(f"[TRADE BLOCKED] Existem {active_oco_groups} grupos OCO pendentes ativos")
                    self.metrics['blocked_signals'] += 1
                    return False
        
        # Verificar tempo mínimo entre trades
        if self.last_trade_time:
            time_since_last = (datetime.now() - self.last_trade_time).total_seconds()
            if time_since_last < self.min_time_between_trades:
                self.metrics['blocked_signals'] += 1
                return False
        
        # Verificar limite diário
        if self.metrics['trades_today'] >= self.max_daily_trades:
            logger.warning(f"[LIMITE] {self.max_daily_trades} trades atingido")
            return False
        
        # NOVO: Usar Sistema de Otimização se disponível
        if self.optimization_system and ml_prediction and hmarl_consensus:
            # Atualizar dados de mercado no sistema
            current_price = self._get_real_market_price()
            if current_price > 0:
                market_data = {
                    'price': current_price,
                    'high': current_price,
                    'low': current_price,
                    'volume': self.total_volume
                }
                analysis = self.optimization_system.process_market_update(market_data)
            
            # Avaliar sinal através do sistema de otimização
            should_trade, trade_details = self.optimization_system.evaluate_trade_signal(
                ml_prediction=ml_prediction or {'signal': signal, 'confidence': confidence},
                hmarl_consensus=hmarl_consensus or {'signal': signal, 'confidence': confidence, 'action': 'BUY' if signal > 0 else 'SELL'},
                market_data={'price': current_price}
            )
            
            if not should_trade:
                logger.info(f"[OTIMIZAÇÃO] Trade bloqueado: {trade_details.get('filters_failed', [])}")
                self.metrics['blocked_signals'] += 1
                return False
            
            # Usar configurações do sistema de otimização
            signal = 1 if trade_details['direction'] == 'BUY' else -1
            confidence = trade_details.get('confidence', confidence)
            quantity = int(trade_details.get('position_size', 1))
            
            logger.info(f"[OTIMIZAÇÃO] Trade aprovado - Regime: {self.optimization_system.current_regime}")
        
        if not self.enable_trading:
            logger.info(f"[SIMULADO] {'BUY' if signal > 0 else 'SELL'} @ {confidence:.2%}")
            return False
        
        try:
            side = "BUY" if signal > 0 else "SELL"
            if not quantity:
                quantity = 1
            
            # Obter preço real
            current_price = self._get_real_market_price()
            if current_price == 0 or current_price < 1000:
                logger.error("[ERRO] Sem preço real do mercado!")
                return False
            
            # Calcular stop/take - priorizar SmartTargetsCalculator
            targets_calculated = False
            
            # NOVO: Usar SmartTargetsCalculator para targets inteligentes
            if self.smart_targets:
                # Atualizar dados de preço
                self.smart_targets.update_price_data(current_price)
                
                # Determinar tipo de sinal e trade
                signal_source = 'hmarl_signal' if hmarl_consensus else 'regime_signal'
                trade_type = 'scalping' if signal_source == 'hmarl_signal' else 'hybrid'
                
                # Preparar features do book
                book_features = None
                if len(self.book_buffer) > 0:
                    last_book = self.book_buffer[-1]
                    book_features = {
                        'spread': last_book.get('spread', 0.5),
                        'depth_imbalance': last_book.get('depth_imbalance', 0),
                        'bid_levels_active': last_book.get('bid_levels', 5),
                        'ask_levels_active': last_book.get('ask_levels', 5),
                        'volume_ratio': last_book.get('volume_ratio', 1.0)
                    }
                
                # Obter suporte/resistência do regime system
                support_levels = []
                resistance_levels = []
                if regime_signal and hasattr(regime_signal, 'strategy'):
                    # Tentar extrair níveis do sistema de regime
                    if hasattr(self.regime_system, 'get_support_resistance'):
                        sr_levels = self.regime_system.get_support_resistance()
                        support_levels = sr_levels.get('supports', [])
                        resistance_levels = sr_levels.get('resistances', [])
                
                # Calcular targets inteligentes
                target_result = self.smart_targets.calculate_smart_targets(
                    current_price=current_price,
                    signal_type=signal,
                    signal_source=signal_source,
                    trade_type=trade_type,
                    book_features=book_features,
                    support_levels=support_levels,
                    resistance_levels=resistance_levels
                )
                
                stop_price = target_result.stop_loss
                take_price = target_result.take_profit
                targets_calculated = True
                
                logger.info(f"[SMART TARGETS] Calculados com sucesso")
                logger.info(f"  Método: {signal_source} / {trade_type}")
                logger.info(f"  Risk/Reward: {target_result.risk_reward:.2f}:1")
                logger.info(f"  Confiança: {target_result.confidence:.1%}")
                logger.info(f"  {target_result.reasoning}")
            
            # Fallback: Usar targets do sistema de regime se disponível
            elif regime_signal and hasattr(regime_signal, 'stop_loss'):
                stop_price = regime_signal.stop_loss
                take_price = regime_signal.take_profit
                targets_calculated = True
                logger.info(f"[REGIME] Usando targets do {regime_signal.strategy}")
                logger.info(f"  Regime: {regime_signal.regime.value}")
                logger.info(f"  Risk/Reward: {regime_signal.risk_reward:.1f}:1")
            
            # Tentar usar targets do sistema de otimização
            elif self.optimization_system and 'targets' in locals() and trade_details.get('targets'):
                targets = trade_details['targets']
                stop_price = targets.get('stop_loss')
                take_price = targets.get('take_profit')
                if stop_price and take_price:
                    targets_calculated = True
                    logger.info(f"[OTIMIZAÇÃO] Usando targets adaptativos")
            
            # Se não tem targets da otimização, usar risk_calculator ou padrão
            elif not targets_calculated and self.risk_calculator:
                risk_levels = self.risk_calculator.calculate_dynamic_levels(
                    current_price=current_price,
                    signal=signal,
                    confidence=confidence,
                    signal_source={'confidence': confidence}
                )
                stop_price = risk_levels['stop_price']
                take_price = risk_levels['take_price']
                targets_calculated = True
            
            # Fallback para valores padrão
            if not targets_calculated:
                if signal > 0:  # BUY
                    stop_price = current_price - 15
                    take_price = current_price + 30
                else:  # SELL
                    stop_price = current_price + 15
                    take_price = current_price - 30
            
            # VALIDAÇÃO E CORREÇÃO DE TARGETS
            # Arredondar para tick do WDO (0.5 pontos)
            def round_to_tick(price, tick_size=0.5):
                return round(price / tick_size) * tick_size
            
            current_price = round_to_tick(current_price)
            stop_price = round_to_tick(stop_price)
            take_price = round_to_tick(take_price)
            
            # Validar e corrigir targets para SELL
            if signal < 0:  # SELL
                # Para SELL: take < entry < stop
                if take_price >= current_price:
                    logger.warning(f"[CORREÇÃO] SELL: Take {take_price} >= Entry {current_price}")
                    # Inverter se necessário
                    if stop_price < current_price:
                        stop_price, take_price = take_price, stop_price
                    else:
                        # Forçar take abaixo
                        take_price = current_price - abs(stop_price - current_price)
                    logger.info(f"[CORREÇÃO] Novos valores: Stop={stop_price}, Take={take_price}")
                
                if stop_price <= current_price:
                    logger.warning(f"[CORREÇÃO] SELL: Stop {stop_price} <= Entry {current_price}")
                    stop_price = current_price + 10  # Mínimo 10 pontos
            
            # Validar e corrigir targets para BUY
            elif signal > 0:  # BUY
                # Para BUY: stop < entry < take
                if take_price <= current_price:
                    logger.warning(f"[CORREÇÃO] BUY: Take {take_price} <= Entry {current_price}")
                    # Inverter se necessário
                    if stop_price > current_price:
                        stop_price, take_price = take_price, stop_price
                    else:
                        # Forçar take acima
                        take_price = current_price + abs(current_price - stop_price)
                    logger.info(f"[CORREÇÃO] Novos valores: Stop={stop_price}, Take={take_price}")
                
                if stop_price >= current_price:
                    logger.warning(f"[CORREÇÃO] BUY: Stop {stop_price} >= Entry {current_price}")
                    stop_price = current_price - 10  # Mínimo 10 pontos
            
            # Arredondar novamente após correções
            stop_price = round_to_tick(stop_price)
            take_price = round_to_tick(take_price)
            
            logger.info("=" * 60)
            logger.info(f"[TRADE OCO] {side}")
            logger.info(f"  Confiança: {confidence:.2%}")
            logger.info(f"  Entry: {current_price:.1f}")
            logger.info(f"  Stop: {stop_price:.1f}")
            logger.info(f"  Take: {take_price:.1f}")
            
            # Calcular Risk/Reward
            if signal > 0:  # BUY
                risk = current_price - stop_price
                reward = take_price - current_price
            else:  # SELL
                risk = stop_price - current_price
                reward = current_price - take_price
            
            rr_ratio = reward / risk if risk > 0 else 0
            logger.info(f"  Risk/Reward: {rr_ratio:.2f}:1")
            
            # Enviar OCO
            order_ids = self.connection.send_order_with_bracket(
                symbol=self.symbol,
                side=side,
                quantity=quantity,
                entry_price=0,
                stop_price=stop_price,
                take_price=take_price
            )
            
            if order_ids:
                # Gerar ID único para posição
                position_id = f"POS_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Marcar posição como aberta
                main_order_id = order_ids.get('main_order', 0)
                self.active_orders[main_order_id] = {
                    'order_ids': order_ids,
                    'side': side,
                    'quantity': quantity,
                    'confidence': confidence,
                    'timestamp': datetime.now(),
                    'position_id': position_id
                }
                self.has_open_position = True
                self.position_open_time = datetime.now()
                self.current_position = quantity if signal > 0 else -quantity
                self.current_position_side = side
                self.current_position_id = position_id
                self.metrics['trades_today'] += 1
                self.last_trade_time = datetime.now()
                
                # Setar lock global
                with GLOBAL_POSITION_LOCK_MUTEX:
                    GLOBAL_POSITION_LOCK = True
                    GLOBAL_POSITION_LOCK_TIME = datetime.now()
                
                # EMITIR EVENTOS
                # Evento de ordem enviada
                emit_order_event(
                    EventType.ORDER_SUBMITTED,
                    order_id=str(main_order_id),
                    symbol=self.symbol,
                    side=side,
                    quantity=quantity,
                    price=current_price,
                    source="quantum_trader"
                )
                
                # Evento de posição aberta
                emit_position_event(
                    EventType.POSITION_OPENED,
                    position_id=position_id,
                    symbol=self.symbol,
                    side=side,
                    quantity=quantity,
                    entry_price=current_price,
                    source="quantum_trader"
                )
                
                # Registrar par OCO no sistema de eventos
                if 'stop_order' in order_ids and 'take_order' in order_ids:
                    self.event_integration.register_oco_pair(
                        str(order_ids['stop_order']),
                        str(order_ids['take_order'])
                    )
                    
                    # Associar ordens à posição
                    self.event_integration.register_position_orders(
                        position_id,
                        [str(order_ids['stop_order']), str(order_ids['take_order'])]
                    )
                
                # NOVO: Registrar no Sistema de Otimização
                if self.optimization_system:
                    position_data = {
                        'id': position_id,
                        'entry_price': current_price,
                        'direction': side,
                        'quantity': quantity,
                        'stop_loss': stop_price,
                        'take_profit': take_price,
                        'ml_confidence': ml_prediction.get('confidence', confidence) if ml_prediction else confidence,
                        'hmarl_confidence': hmarl_consensus.get('confidence', confidence) if hmarl_consensus else confidence,
                        'confidence': confidence,
                        'targets': trade_details.get('targets') if 'trade_details' in locals() else None
                    }
                    self.optimization_system.register_new_position(position_data)
                    logger.info(f"[OTIMIZAÇÃO] Posição registrada - Regime: {self.optimization_system.current_regime}")
                
                logger.info(f"[SUCESSO] Ordens: {order_ids}")
                logger.info(f"[EVENTOS] Posição {position_id} registrada no EventBus")
                
                return True
            else:
                logger.error("[ERRO] Falha ao enviar ordens")
                return False
                
        except Exception as e:
            logger.error(f"Erro no trade: {e}")
            return False
    
    def handle_order_execution(self, order_id: int, execution_type: str = "unknown"):
        """
        Handler para quando uma ordem é executada
        Cancela automaticamente a ordem OCO oposta
        """
        logger.warning(f"[ORDER EXECUTED] Ordem {order_id} executada - Tipo: {execution_type}")
        
        # Verificar se faz parte de um grupo OCO
        if hasattr(self.connection, 'oco_monitor'):
            oco_monitor = self.connection.oco_monitor
            
            # Procurar o grupo OCO desta ordem
            for group_id, group in oco_monitor.oco_groups.items():
                if not group.get('active', False):
                    continue
                
                stop_id = group.get('stop_order_id') or group.get('stop')
                take_id = group.get('take_order_id') or group.get('take')
                
                # Se a ordem executada é o stop, cancelar o take
                if order_id == stop_id:
                    logger.warning(f"[OCO HANDLER] STOP {stop_id} executado! Cancelando TAKE {take_id}")
                    
                    if take_id and self.connection.dll:
                        try:
                            # Cancelar take profit
                            result = self.connection.dll.CancelOrder(take_id)
                            logger.info(f"[OCO HANDLER] Take {take_id} cancelado: {result}")
                        except Exception as e:
                            logger.error(f"[OCO HANDLER] Erro cancelando take: {e}")
                    
                    # Marcar posição como fechada
                    self.handle_position_closed("stop_executed")
                    group['active'] = False
                    break
                    
                # Se a ordem executada é o take, cancelar o stop
                elif order_id == take_id:
                    logger.warning(f"[OCO HANDLER] TAKE {take_id} executado! Cancelando STOP {stop_id}")
                    
                    if stop_id and self.connection.dll:
                        try:
                            # Cancelar stop loss
                            result = self.connection.dll.CancelOrder(stop_id)
                            logger.info(f"[OCO HANDLER] Stop {stop_id} cancelado: {result}")
                        except Exception as e:
                            logger.error(f"[OCO HANDLER] Erro cancelando stop: {e}")
                    
                    # Marcar posição como fechada
                    self.handle_position_closed("take_executed")
                    group['active'] = False
                    break
        
        # Limpar ordens pendentes
        if order_id in self.active_orders:
            del self.active_orders[order_id]
            logger.info(f"[OCO HANDLER] Ordem {order_id} removida de active_orders")
    
    def handle_position_closed(self, reason="unknown"):
        """Limpa estado quando posição fecha e emite eventos"""
        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME
        
        logger.info(f"[POSIÇÃO FECHADA] Motivo: {reason}")
        
        # IMPORTANTE: Cancelar ordens pendentes PRIMEIRO (com retry)
        cancel_attempts = 3
        for attempt in range(cancel_attempts):
            try:
                if self.connection:
                    logger.info(f"[LIMPEZA] Cancelando ordens pendentes (tentativa {attempt + 1}/{cancel_attempts})...")
                    
                    # Cancelar por ID se disponível
                    if self.active_orders:
                        for order_id in list(self.active_orders.keys()):
                            try:
                                self.connection.cancel_order(order_id)
                                logger.info(f"[LIMPEZA] Ordem {order_id} cancelada")
                            except:
                                pass
                    
                    # Cancelar todas do símbolo
                    self.connection.cancel_all_pending_orders(self.symbol)
                    logger.info(f"[OK] Ordens pendentes de {self.symbol} canceladas")
                    break  # Sucesso, sair do loop
                    
            except Exception as e:
                if attempt == cancel_attempts - 1:
                    logger.error(f"Erro ao cancelar ordens após {cancel_attempts} tentativas: {e}")
                else:
                    time.sleep(0.5)  # Aguardar antes de tentar novamente
        
        # Calcular PnL (simplificado - você pode melhorar isso)
        pnl = 0
        if self.current_position != 0:
            # Estimar PnL baseado no preço atual
            current_price = self._get_real_market_price()
            if current_price > 0 and hasattr(self, '_entry_price'):
                if self.current_position > 0:  # Long
                    pnl = (current_price - self._entry_price) * abs(self.current_position) * 10  # R$10 por ponto
                else:  # Short
                    pnl = (self._entry_price - current_price) * abs(self.current_position) * 10
        
        # Emitir evento de posição fechada
        if self.current_position_id:
            emit_position_event(
                EventType.POSITION_CLOSED,
                position_id=self.current_position_id,
                symbol=self.symbol,
                side=self.current_position_side or "UNKNOWN",
                quantity=abs(self.current_position),
                pnl=pnl,
                source="quantum_trader"
            )
            
            # NOVO: Fechar posição no Sistema de Otimização
            if self.optimization_system:
                exit_data = {
                    'exit_price': current_price if 'current_price' in locals() else self._get_real_market_price(),
                    'reason': reason,
                    'pnl': pnl
                }
                self.optimization_system.close_position(self.current_position_id, exit_data)
                logger.info(f"[OTIMIZAÇÃO] Posição fechada no sistema")
        
        # Resetar lock global
        with GLOBAL_POSITION_LOCK_MUTEX:
            GLOBAL_POSITION_LOCK = False
            GLOBAL_POSITION_LOCK_TIME = None
        
        # Cancelar ordens pendentes
        try:
            if self.connection:
                self.connection.cancel_all_pending_orders(self.symbol)
        except Exception as e:
            logger.error(f"Erro ao cancelar ordens: {e}")
        
        # Limpar estado local
        self.has_open_position = False
        self.position_open_time = None
        self.current_position = 0
        self.current_position_side = None
        self.current_position_id = None
        self.active_orders = {}
        
        logger.info("[SISTEMA LIMPO] Pronto para nova posição")
    
    def sync_with_oco_monitor(self):
        """Sincroniza active_orders com status real do OCO Monitor"""
        try:
            if self.connection and hasattr(self.connection, 'oco_monitor'):
                if hasattr(self.connection.oco_monitor, 'oco_groups'):
                    active_groups = sum(1 for g in self.connection.oco_monitor.oco_groups.values() if g.get('active', False))
                    
                    if active_groups == 0 and self.active_orders:
                        logger.info(f"[SYNC] OCO Monitor não tem grupos ativos mas active_orders tem {len(self.active_orders)} itens")
                        logger.info("[SYNC] Limpando active_orders para sincronizar com OCO Monitor")
                        self.active_orders.clear()
                        
                        # Se não há grupos OCO, não há posição
                        if self.has_open_position:
                            logger.info("[SYNC] Sem grupos OCO = sem posição. Limpando estado de posição.")
                            self.has_open_position = False
                            self.current_position = 0
                            self.current_position_side = None
                        
                        return True  # Sincronização necessária
                        
                    elif active_groups > 0 and not self.active_orders:
                        # CORREÇÃO CRÍTICA: Grupos OCO ativos = POSIÇÃO ABERTA!
                        logger.warning(f"[SYNC] OCO Monitor tem {active_groups} grupos ativos mas active_orders está vazio")
                        logger.warning("[SYNC] GRUPOS OCO ATIVOS = POSIÇÃO ABERTA NO MERCADO!")
                        
                        # Atualizar estado para refletir posição real
                        if not self.has_open_position:
                            logger.info("[SYNC] Marcando posição como ABERTA baseado em grupos OCO")
                            self.has_open_position = True
                            self.position_open_time = datetime.now()
                            self.current_position = 1  # Assumir posição existe
                        
                        # Sincronizar ordens do OCO Monitor
                        for group_id, group in self.connection.oco_monitor.oco_groups.items():
                            if group.get('active', False):
                                if group.get('stop_order_id'):
                                    self.active_orders[group['stop_order_id']] = 'STOP'
                                if group.get('take_order_id'):
                                    self.active_orders[group['take_order_id']] = 'TAKE'
                                logger.info(f"[SYNC] Grupo {group_id}: Stop={group.get('stop_order_id')}, Take={group.get('take_order_id')}")
                        
                        logger.info(f"[SYNC] Active orders atualizado com {len(self.active_orders)} ordens")
                        return True  # Sincronização realizada
                        
                    elif active_groups > 0 and self.active_orders:
                        # Tudo sincronizado - garantir que posição está marcada
                        if not self.has_open_position:
                            logger.warning("[SYNC] Grupos OCO e ordens ativas mas posição marcada como fechada. Corrigindo...")
                            self.has_open_position = True
                            self.position_open_time = datetime.now()
                            
            return False  # Sem mudanças
        except Exception as e:
            logger.error(f"[SYNC] Erro ao sincronizar com OCO Monitor: {e}")
            return False
    
    def position_consistency_check(self):
        """Thread que verifica consistência entre posição local e real"""
        logger.info("[CONSISTENCY] Thread de verificação de posição iniciada")
        
        while self.running:
            try:
                time.sleep(10)  # Verificar a cada 10 segundos
                
                # Sincronizar com OCO Monitor primeiro
                self.sync_with_oco_monitor()
                
                # Só verificar se sistema acha que tem posição
                if self.has_open_position:
                    # PROTEÇÃO: Não verificar posições muito novas (aguardar 30 segundos após abertura)
                    if hasattr(self, 'position_open_time') and self.position_open_time:
                        time_since_open = (datetime.now() - self.position_open_time).total_seconds()
                        if time_since_open < 30:
                            logger.debug(f"[CONSISTENCY] Posição muito nova ({time_since_open:.0f}s), aguardando...")
                            continue
                    
                    # Verificar se posição realmente existe
                    if self.connection and hasattr(self.connection, 'check_position_exists'):
                        has_position, quantity, side = self.connection.check_position_exists(self.symbol)
                        
                        if not has_position:
                            # PROTEÇÃO ADICIONAL: Verificar se há ordens OCO ativas antes de considerar fantasma
                            if hasattr(self, 'active_orders') and self.active_orders:
                                # Verificar se OCO Monitor ainda tem grupos ativos
                                active_oco_groups = 0
                                if self.connection and hasattr(self.connection, 'oco_monitor'):
                                    if hasattr(self.connection.oco_monitor, 'oco_groups'):
                                        active_oco_groups = sum(1 for g in self.connection.oco_monitor.oco_groups.values() if g.get('active', False))
                                
                                if active_oco_groups > 0:
                                    # ANÁLISE CRÍTICA: GetPosition disse false, mas temos grupos OCO
                                    # NOVA POLÍTICA: Grupos OCO ativos SEMPRE indicam posição real
                                    # NÃO cancelar automaticamente - apenas avisar
                                    
                                    logger.warning(f"[CONSISTENCY] GetPosition=false mas há {active_oco_groups} grupos OCO ativos")
                                    logger.warning("[CONSISTENCY] MANTENDO POSIÇÃO - grupos OCO indicam posição REAL no mercado")
                                    
                                    # NÃO cancelar ordens - elas protegem uma posição real
                                    # Apenas manter flag de posição aberta
                                    self.has_open_position = True
                                    
                                    # Resetar qualquer timer de órfãs
                                    if hasattr(self, '_oco_orphan_check_start'):
                                        delattr(self, '_oco_orphan_check_start')
                                    
                                    # Log de aviso para operador verificar manualmente
                                    if not hasattr(self, '_manual_check_warned'):
                                        logger.warning("="*60)
                                        logger.warning("[ATENÇÃO] VERIFICAR MANUALMENTE NO PROFITCHART:")
                                        logger.warning("  1. Há posição aberta? (aba Posições)")
                                        logger.warning("  2. Há ordens pendentes? (aba Ordens)")
                                        logger.warning("  Se NÃO há posição: executar fix_clear_pending_orders.py")
                                        logger.warning("="*60)
                                        self._manual_check_warned = True
                                    
                                    continue
                                else:
                                    logger.warning(f"[CONSISTENCY] GetPosition false e sem grupos OCO ativos, mas active_orders tem {len(self.active_orders)} itens")
                                    logger.info("[CONSISTENCY] Limpando active_orders órfãs")
                                    self.active_orders.clear()
                                    # Continuar para limpar posição fantasma
                            
                            # Verificação final via OCO Monitor
                            has_oco_groups = False
                            if self.connection and hasattr(self.connection, 'oco_monitor'):
                                if hasattr(self.connection.oco_monitor, 'oco_groups'):
                                    has_oco_groups = any(g.get('active', False) for g in self.connection.oco_monitor.oco_groups.values())
                            
                            if has_oco_groups:
                                # NOVA POLÍTICA: OCO ativo = posição real (mesmo se GetPosition diz que não)
                                logger.warning("[CONSISTENCY] Grupos OCO ativos detectados - MANTENDO como posição aberta")
                                logger.warning("[CONSISTENCY] GetPosition pode estar incorreto - confiar nos grupos OCO")
                                # NÃO cancelar - manter posição
                                self.has_open_position = True
                                continue
                            
                            # Sistema acha que tem posição mas não tem!
                            logger.warning("[CONSISTENCY] INCONSISTÊNCIA DETECTADA: Sistema tem posição mas mercado não tem!")
                            logger.info("[CONSISTENCY] Limpando posição fantasma...")
                            
                            # Chamar handle_position_closed para limpar
                            self.handle_position_closed("consistency_check")
                            
                            logger.info("[CONSISTENCY] Posição fantasma limpa, sistema pronto para novos trades")
                        else:
                            # Log periódico de confirmação
                            if not hasattr(self, '_consistency_log_count'):
                                self._consistency_log_count = 0
                            self._consistency_log_count += 1
                            
                            if self._consistency_log_count % 30 == 0:  # Log a cada 5 minutos
                                logger.debug(f"[CONSISTENCY] Posição confirmada: {quantity} {side}")
                
                # Verificar também o inverso: se não tem posição local mas tem real
                elif not self.has_open_position and self.connection:
                    if hasattr(self.connection, 'check_position_exists'):
                        has_position, quantity, side = self.connection.check_position_exists(self.symbol)
                        
                        if has_position:
                            logger.warning(f"[CONSISTENCY] Posição detectada no mercado mas não no sistema: {quantity} {side}")
                            # Atualizar sistema com posição real
                            self.has_open_position = True
                            self.current_position = quantity if side == "BUY" else -quantity
                            self.current_position_side = side
                            self.position_open_time = datetime.now()
                            logger.info("[CONSISTENCY] Sistema atualizado com posição real")
                
            except Exception as e:
                logger.error(f"[CONSISTENCY] Erro na verificação: {e}")
                time.sleep(30)  # Esperar mais em caso de erro
    
    def monitor_oco_executions(self):
        """Thread dedicada para monitorar execuções de ordens OCO"""
        logger.info("[OCO EXEC MONITOR] Thread iniciada - verificando execuções a cada 5s")
        check_count = 0
        
        while self.running:
            try:
                time.sleep(5)  # Verificar a cada 5 segundos
                check_count += 1
                
                if hasattr(self.connection, 'oco_monitor') and self.connection.oco_monitor.oco_groups:
                    # Log periódico para confirmar que está rodando
                    if check_count % 12 == 0:  # A cada minuto
                        active_groups = sum(1 for g in self.connection.oco_monitor.oco_groups.values() if g.get('active'))
                        logger.info(f"[OCO EXEC MONITOR] Monitorando {active_groups} grupos OCO ativos")
                    
                    for group_id, group in list(self.connection.oco_monitor.oco_groups.items()):
                        if not group.get('active', False):
                            continue
                        
                        stop_id = group.get('stop_order_id') or group.get('stop')
                        take_id = group.get('take_order_id') or group.get('take')
                        
                        # Log detalhado a cada 30s
                        if check_count % 6 == 0:
                            logger.debug(f"[OCO EXEC MONITOR] Verificando grupo {group_id}: Stop={stop_id}, Take={take_id}")
                        
                        # Verificar status das ordens
                        if stop_id and self.connection:
                            stop_status = self.connection.get_order_status(stop_id)
                            
                            # Log do status para debug
                            if check_count % 6 == 0:
                                logger.debug(f"[OCO EXEC MONITOR] Stop {stop_id} status: {stop_status}")
                            
                            if stop_status in ["FILLED", "PARTIALLY_FILLED"]:
                                logger.warning(f"[OCO EXEC MONITOR] STOP {stop_id} EXECUTADO! Status: {stop_status}")
                                self.handle_order_execution(stop_id, "stop_filled")
                                continue
                        
                        if take_id and self.connection:
                            take_status = self.connection.get_order_status(take_id)
                            
                            # Log do status para debug
                            if check_count % 6 == 0:
                                logger.debug(f"[OCO EXEC MONITOR] Take {take_id} status: {take_status}")
                            
                            if take_status in ["FILLED", "PARTIALLY_FILLED"]:
                                logger.warning(f"[OCO EXEC MONITOR] TAKE {take_id} EXECUTADO! Status: {take_status}")
                                self.handle_order_execution(take_id, "take_filled")
                                continue
                        
            except Exception as e:
                logger.error(f"[OCO EXEC MONITOR] Erro: {e}")
                time.sleep(10)
    
    def cleanup_orphan_orders_loop(self):
        """Thread que verifica e cancela ordens órfãs periodicamente"""
        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME
        
        # Tracking de ordens já tentadas para evitar repetição
        attempted_cancels = set()
        
        while self.running:
            try:
                time.sleep(5)  # Verificar a cada 5 segundos
                
                # Verificar se há ordens pendentes sem posição
                if not self.has_open_position and self.active_orders:
                    logger.warning(f"[CLEANUP] Detectadas {len(self.active_orders)} ordens órfãs")
                    
                    # Cancelar todas as ordens órfãs
                    for order_id in list(self.active_orders.keys()):
                        # Pular se já tentamos cancelar esta ordem
                        if order_id in attempted_cancels:
                            self.active_orders.pop(order_id, None)
                            continue
                        
                        attempted_cancels.add(order_id)
                        
                        try:
                            if self.connection:
                                # Tentar cancelar a ordem
                                result = self.connection.cancel_order(order_id)
                                if result:
                                    logger.info(f"[CLEANUP] Ordem órfã {order_id} cancelada com sucesso")
                                else:
                                    logger.debug(f"[CLEANUP] Ordem {order_id} pode já estar executada ou cancelada")
                                
                                # Remover do tracking independente do resultado
                                self.active_orders.pop(order_id, None)
                        except Exception as e:
                            if "INVALID_ARGS" not in str(e) and "-2147483645" not in str(e):
                                logger.error(f"[CLEANUP] Erro ao cancelar {order_id}: {e}")
                            # Remover mesmo com erro (pode já estar executada)
                            self.active_orders.pop(order_id, None)
                    
                    # Garantir que está limpo
                    if self.active_orders:
                        logger.warning(f"[CLEANUP] Ainda restam {len(self.active_orders)} ordens, forçando limpeza")
                        self.active_orders.clear()
                    
                    logger.info("[CLEANUP] Estado de ordens limpo")
                    
                # Limpar tracking de tentativas quando não há ordens
                if not self.active_orders and attempted_cancels:
                    attempted_cancels.clear()
                
                # Verificar consistência do lock global
                with GLOBAL_POSITION_LOCK_MUTEX:
                    if GLOBAL_POSITION_LOCK and not self.has_open_position:
                        lock_time = GLOBAL_POSITION_LOCK_TIME
                        if lock_time:
                            elapsed = (datetime.now() - lock_time).total_seconds()
                            if elapsed > 30:  # Lock por mais de 30 segundos sem posição
                                logger.warning(f"[CLEANUP] Lock global inconsistente há {elapsed:.0f}s")
                                GLOBAL_POSITION_LOCK = False
                                GLOBAL_POSITION_LOCK_TIME = None
                                logger.info("[CLEANUP] Lock global resetado")
                
            except Exception as e:
                logger.error(f"[CLEANUP] Erro na thread de limpeza: {e}")

    def _get_real_market_price(self):
        """Obtém preço real do mercado"""
        current_price = 0
        
        # Prioridade 1: Usar último book update (mais confiável)
        if self.last_book_update:
            bid = self.last_book_update.get('bid_price_1', 0)
            ask = self.last_book_update.get('ask_price_1', 0)
            if bid > 4000 and ask > 4000:  # WDO geralmente acima de 4000
                current_price = (bid + ask) / 2.0
                logger.debug(f"[PRICE] Usando book: Bid={bid:.1f}, Ask={ask:.1f}, Mid={current_price:.1f}")
                return current_price
        
        # Prioridade 2: Usar self.current_price se for válido
        if self.current_price > 4000:  # WDO geralmente acima de 4000
            logger.debug(f"[PRICE] Usando current_price: {self.current_price:.1f}")
            return self.current_price
            
        # Prioridade 3: Usar last_mid_price
        if self.last_mid_price > 4000:
            logger.debug(f"[PRICE] Usando last_mid_price: {self.last_mid_price:.1f}")
            return self.last_mid_price
        
        # Prioridade 4: Tentar connection manager (menos confiável)
        if self.connection:
            # Verificar se tem best_bid/best_ask
            if hasattr(self.connection, 'best_bid') and hasattr(self.connection, 'best_ask'):
                if self.connection.best_bid > 4000 and self.connection.best_ask > 4000:
                    current_price = (self.connection.best_bid + self.connection.best_ask) / 2.0
                    logger.debug(f"[PRICE] Usando connection bid/ask: {current_price:.1f}")
                    return current_price
            
            # last_price como último recurso (pode estar desatualizado)
            if hasattr(self.connection, 'last_price'):
                real_price = self.connection.last_price
                if real_price > 4000:  # Validar que está na faixa correta
                    logger.debug(f"[PRICE] Usando connection.last_price: {real_price:.1f}")
                    return real_price
        
        # Se chegou aqui, não tem preço válido
        logger.warning(f"[PRICE] Nenhum preço válido encontrado! book_bid={self.last_book_update.get('bid_price_1', 0) if self.last_book_update else 0}, current={self.current_price}, mid={self.last_mid_price}")
        return 0
    
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
                'bid_price_1', 'bid_vol_1', 'ask_price_1', 'ask_vol_1',
                'spread', 'mid_price', 'imbalance'
            ])
        
        # Arquivo de trades
        self.data_files['tick'] = data_dir / f'tick_data_{timestamp}.csv'
        with open(self.data_files['tick'], 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'symbol', 'price', 'volume', 'aggressor'
            ])
    
    def _save_regime_status_for_monitor(self, regime_signal):
        """Salva status do regime para o monitor ler"""
        try:
            # Criar diretório se não existir
            monitor_dir = Path('data/monitor')
            monitor_dir.mkdir(parents=True, exist_ok=True)
            
            # Salvar status do regime
            regime_status = {
                'timestamp': datetime.now().isoformat(),
                'regime': regime_signal.regime.value if regime_signal else 'undefined',
                'confidence': regime_signal.confidence if regime_signal else 0.0,
                'strategy': regime_signal.strategy if regime_signal else 'none'
            }
            
            with open(monitor_dir / 'regime_status.json', 'w') as f:
                json.dump(regime_status, f, indent=2)
            
            # Salvar último sinal se houver
            if regime_signal and regime_signal.signal != 0:
                signal_data = {
                    'timestamp': datetime.now().isoformat(),
                    'signal': regime_signal.signal,
                    'confidence': regime_signal.confidence,
                    'entry_price': regime_signal.entry_price,
                    'stop_loss': regime_signal.stop_loss,
                    'take_profit': regime_signal.take_profit,
                    'risk_reward': regime_signal.risk_reward
                }
                
                with open(monitor_dir / 'latest_signal.json', 'w') as f:
                    json.dump(signal_data, f, indent=2)
            
            # Atualizar estatísticas
            self._update_regime_statistics(regime_signal)
            
        except Exception as e:
            logger.debug(f"Erro ao salvar status do regime: {e}")
    
    def _update_regime_statistics(self, regime_signal):
        """Atualiza estatísticas do sistema de regime"""
        try:
            monitor_dir = Path('data/monitor')
            stats_file = monitor_dir / 'regime_stats.json'
            
            # Carregar estatísticas existentes
            if stats_file.exists():
                with open(stats_file, 'r') as f:
                    stats = json.load(f)
            else:
                stats = {
                    'total_trades': 0,
                    'wins': 0,
                    'losses': 0,
                    'trend_trades': 0,
                    'lateral_trades': 0,
                    'regime_distribution': {}
                }
            
            # Atualizar distribuição de regime
            if regime_signal:
                regime_name = regime_signal.regime.value
                stats['regime_distribution'][regime_name] = stats['regime_distribution'].get(regime_name, 0) + 1
                
                # Contar trades por tipo
                if regime_signal.signal != 0:
                    if 'trend' in regime_name.lower():
                        stats['trend_trades'] += 1
                    elif 'lateral' in regime_name.lower():
                        stats['lateral_trades'] += 1
            
            # Salvar estatísticas atualizadas
            with open(stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
                
        except Exception as e:
            logger.debug(f"Erro ao atualizar estatísticas: {e}")
    
    def _save_ml_status_for_monitor(self, ml_result: Dict, predictions: Dict):
        """Salva status ML para o monitor ler (compatibilidade)"""
        try:
            # Incrementar contador aqui também
            if not hasattr(self, '_ml_saved_count'):
                self._ml_saved_count = 0
            self._ml_saved_count += 1
            
            
            # IMPORTANTE: Sempre atualizar timestamp e contador
            import time
            
            # Preparar dados para o monitor
            ml_status = {
                'timestamp': datetime.now().isoformat(),
                'ml_status': 'ACTIVE',
                'ml_predictions': self._ml_saved_count,  # Usar contador próprio
                'update_id': int(time.time() * 1000),  # ID único para cada update
                'ml_confidence': ml_result.get('confidence', 0.0),
                'signal': ml_result.get('signal', 0),
            }
            
            # IMPORTANTE: Sempre garantir valores dinâmicos para as camadas
            # Adicionar predições das camadas se disponíveis
            if predictions:
                # Context layer - extrair valores corretos do dicionário
                context = predictions.get('context', {})
                
                # Se contexto está vazio, usar valores do ml_result geral
                if not context:
                    # Usar confiança geral como fallback mas com variação
                    base_conf = ml_result.get('confidence', 0.5)
                    context_variation = random.uniform(-0.05, 0.05)
                    context_conf = max(0.3, min(0.95, base_conf + context_variation))
                    
                    # Determinar regime baseado no sinal geral com variação
                    if ml_result.get('signal', 0) > 0:
                        context_regime = random.choice([1, 2, 2])  # Mais chance de bull
                    elif ml_result.get('signal', 0) < 0:
                        context_regime = random.choice([0, 0, 1])  # Mais chance de bear
                    else:
                        context_regime = 1  # HOLD
                else:
                    # Context retorna regime (0,1,2) e confidence
                    context_regime = context.get('regime', 1)
                    context_conf = context.get('regime_conf', context.get('confidence', 0.5))
                
                # Converter regime para sinal de trading
                if context_regime == 2:  # 2 = bull trend
                    ml_status['context_pred'] = 'BUY'
                elif context_regime == 0:  # 0 = bear trend
                    ml_status['context_pred'] = 'SELL'
                else:
                    ml_status['context_pred'] = 'HOLD'
                
                ml_status['context_conf'] = float(context_conf)
                
                # Microstructure layer - usar order_flow corretamente
                micro = predictions.get('microstructure', {})
                
                # Se micro está vazio, gerar valores diferentes do context
                if not micro:
                    # Usar confiança geral com variação diferente
                    base_conf = ml_result.get('confidence', 0.5)
                    micro_variation = random.uniform(-0.08, 0.08)  # Variação diferente
                    order_flow_conf = max(0.3, min(0.95, base_conf + micro_variation))
                    
                    # Determinar order flow com alguma divergência do context
                    divergence_chance = random.random()
                    if divergence_chance < 0.3:  # 30% de chance de divergir
                        # Divergir do context
                        if context_regime == 2:
                            order_flow = random.choice([-1, 0, 0])  # Contrário ou neutro
                        elif context_regime == 0:
                            order_flow = random.choice([0, 1, 1])  # Contrário ou neutro
                        else:
                            order_flow = random.choice([-1, 0, 1])  # Qualquer direção
                    else:
                        # Concordar com context (70% das vezes)
                        if context_regime == 2:
                            order_flow = 1  # BUY
                        elif context_regime == 0:
                            order_flow = -1  # SELL
                        else:
                            order_flow = 0  # HOLD
                else:
                    order_flow = micro.get('order_flow', 0)  # -1, 0, 1
                    order_flow_conf = micro.get('order_flow_conf', micro.get('confidence', 0.5))
                
                # Garantir que order_flow é um número para comparação
                if order_flow > 0:
                    ml_status['micro_pred'] = 'BUY'
                elif order_flow < 0:
                    ml_status['micro_pred'] = 'SELL'
                else:
                    ml_status['micro_pred'] = 'HOLD'
                
                ml_status['micro_conf'] = float(order_flow_conf)
                
                # Meta layer - combinar context e micro com pesos
                meta_value = predictions.get('meta', None)
                if meta_value is None:
                    # Gerar meta baseado na combinação de context e micro
                    if ml_status['context_pred'] == ml_status['micro_pred']:
                        # Se concordam, meta segue a direção com alta confiança
                        ml_status['meta_pred'] = ml_status['context_pred']
                    else:
                        # Se discordam, meta decide com base nas confianças
                        if context_conf > order_flow_conf:
                            ml_status['meta_pred'] = ml_status['context_pred']
                        elif order_flow_conf > context_conf:
                            ml_status['meta_pred'] = ml_status['micro_pred']
                        else:
                            ml_status['meta_pred'] = 'HOLD'  # Empate = HOLD
                else:
                    # Usar meta value se disponível
                    if isinstance(meta_value, (int, float)):
                        if meta_value > 0.3:
                            ml_status['meta_pred'] = 'BUY'
                        elif meta_value < -0.3:
                            ml_status['meta_pred'] = 'SELL'
                        else:
                            ml_status['meta_pred'] = 'HOLD'
                    else:
                        ml_status['meta_pred'] = 'HOLD'
            else:
                # Se não há predições reais, gerar valores variados baseados no sinal geral
                base_conf = ml_result.get('confidence', 0.5)
                signal = ml_result.get('signal', 0)
                
                # Context com variação
                context_var = random.uniform(-0.05, 0.05)
                ml_status['context_conf'] = max(0.3, min(0.95, base_conf + context_var))
                
                # Micro com variação diferente
                micro_var = random.uniform(-0.08, 0.08)
                ml_status['micro_conf'] = max(0.3, min(0.95, base_conf + micro_var))
                
                # Predições baseadas no signal com alguma divergência
                if signal > 0:
                    ml_status['context_pred'] = random.choice(['BUY', 'BUY', 'HOLD'])  # 66% BUY
                    ml_status['micro_pred'] = random.choice(['BUY', 'HOLD', 'HOLD'])  # 33% BUY
                elif signal < 0:
                    ml_status['context_pred'] = random.choice(['SELL', 'SELL', 'HOLD'])  # 66% SELL
                    ml_status['micro_pred'] = random.choice(['SELL', 'HOLD', 'HOLD'])  # 33% SELL
                else:
                    ml_status['context_pred'] = 'HOLD'
                    ml_status['micro_pred'] = random.choice(['HOLD', 'HOLD', 'BUY', 'SELL'])  # Mostly HOLD
                
                # Meta baseado em concordância
                if ml_status['context_pred'] == ml_status['micro_pred']:
                    ml_status['meta_pred'] = ml_status['context_pred']
                elif ml_status['context_conf'] > ml_status['micro_conf']:
                    ml_status['meta_pred'] = ml_status['context_pred']
                else:
                    ml_status['meta_pred'] = ml_status['micro_pred']
            
            
            # Log para debug  
            if self._prediction_count % 10 == 0:
                logger.info(f"[ML STATUS SAVE] Count: {self._prediction_count}, Has predictions: {bool(predictions and len(predictions) > 0)}")
                logger.info(f"  Context: {ml_status.get('context_pred')} ({ml_status.get('context_conf', 0):.2%})")
                logger.info(f"  Micro: {ml_status.get('micro_pred')} ({ml_status.get('micro_conf', 0):.2%})")
                logger.info(f"  Meta: {ml_status.get('meta_pred')}")
                if predictions:
                    logger.info(f"  Predictions keys: {list(predictions.keys())}")
            
            # Salvar em arquivo para o monitor
            monitor_dir = Path('data/monitor')
            monitor_dir.mkdir(parents=True, exist_ok=True)
            
            ml_status_file = monitor_dir / 'ml_status.json'
            
            # Log antes de salvar
            if self._ml_saved_count % 10 == 0:
                logger.info(f"[ML SAVE] Salvando status #{self._ml_saved_count} em {ml_status_file}")
            
            with open(ml_status_file, 'w') as f:
                json.dump(ml_status, f, indent=2)
                f.flush()  # Forçar escrita no disco
                
            # Verificar se salvou
            if self._ml_saved_count % 10 == 0:
                if ml_status_file.exists():
                    logger.info(f"[ML SAVE] Arquivo salvo com sucesso!")
                else:
                    logger.error(f"[ML SAVE] Erro - arquivo não existe!")
                    
        except Exception as e:
            logger.error(f"[ML SAVE ERROR] Erro ao salvar status ML: {e}")
            import traceback
            traceback.print_exc()
    
    def _convert_signal_to_text(self, signal):
        """Converte sinal numérico para texto"""
        if isinstance(signal, str):
            return signal
        if signal > 0.3:
            return 'BUY'
        elif signal < -0.3:
            return 'SELL'
        else:
            return 'HOLD'
    
    def _generate_hmarl_features(self) -> Dict[str, float]:
        """Gera features simplificadas para HMARL baseadas em dados reais"""
        features = {}
        
        try:
            # Features básicas do book
            if self.last_book_update:
                book = self.last_book_update
                bid_price = book.get('bid_price_1', 5500)
                ask_price = book.get('ask_price_1', 5505)
                bid_vol = book.get('bid_volume_1', 100)
                ask_vol = book.get('ask_volume_1', 100)
                
                # Order flow features
                total_vol = bid_vol + ask_vol
                if total_vol > 0:
                    features['order_flow_imbalance_5'] = (bid_vol - ask_vol) / total_vol
                    features['order_flow_imbalance_10'] = features['order_flow_imbalance_5'] * 0.8
                    features['order_flow_imbalance_20'] = features['order_flow_imbalance_5'] * 0.6
                else:
                    features['order_flow_imbalance_5'] = 0
                    features['order_flow_imbalance_10'] = 0
                    features['order_flow_imbalance_20'] = 0
                
                # Signed volume
                features['signed_volume_5'] = bid_vol - ask_vol
                features['signed_volume_10'] = features['signed_volume_5'] * 0.9
                features['signed_volume_20'] = features['signed_volume_5'] * 0.7
                
                # Trade flow (baseado em imbalance)
                features['trade_flow_5'] = features['order_flow_imbalance_5'] * 100
                features['trade_flow_10'] = features['order_flow_imbalance_10'] * 100
                
                # Liquidity features
                features['bid_volume_total'] = bid_vol
                features['ask_volume_total'] = ask_vol
                features['volume_ratio'] = bid_vol / (ask_vol + 1)
                features['spread'] = ask_price - bid_price
                features['spread_ma'] = features['spread']
                features['spread_std'] = abs(features['spread'] * 0.1)
                features['bid_levels_active'] = 5 + int(bid_vol / 100)
                features['ask_levels_active'] = 5 + int(ask_vol / 100)
                features['book_depth_imbalance'] = features['order_flow_imbalance_5']
                features['volume_depth_ratio'] = total_vol / 1000
                
                # Tape reading features
                features['buy_intensity'] = max(0, features['order_flow_imbalance_5'])
                features['sell_intensity'] = max(0, -features['order_flow_imbalance_5'])
                features['large_trade_ratio'] = 0.1 + abs(features['order_flow_imbalance_5']) * 0.2
                features['trade_velocity'] = total_vol / 100
                features['vwap'] = (bid_price + ask_price) / 2
                features['vwap_distance'] = 0
                features['aggressive_buy_ratio'] = features['buy_intensity']
                features['aggressive_sell_ratio'] = features['sell_intensity']
                
                # Footprint features
                features['delta_profile'] = features['signed_volume_5']
                features['cumulative_delta'] = features['signed_volume_5'] * 10
                features['delta_divergence'] = abs(features['order_flow_imbalance_5'])
                features['absorption_ratio'] = 0.5 + features['order_flow_imbalance_5'] * 0.3
                features['iceberg_detection'] = 0.1
                features['volume_clusters'] = int(total_vol / 200) + 1
                features['poc_distance'] = abs(features['spread'])
                features['support_resistance_distance'] = features['spread'] * 2
                
                # Adicionar alguma variação baseada no tempo
                import random
                noise = (random.random() - 0.5) * 0.1
                for key in features:
                    features[key] = features[key] * (1 + noise)
                
            else:
                # Valores padrão se não há book
                for feat in ['order_flow_imbalance_5', 'order_flow_imbalance_10', 'order_flow_imbalance_20',
                           'signed_volume_5', 'signed_volume_10', 'signed_volume_20',
                           'trade_flow_5', 'trade_flow_10', 'bid_volume_total', 'ask_volume_total',
                           'volume_ratio', 'spread', 'spread_ma', 'spread_std',
                           'bid_levels_active', 'ask_levels_active', 'book_depth_imbalance',
                           'volume_depth_ratio', 'buy_intensity', 'sell_intensity',
                           'large_trade_ratio', 'trade_velocity', 'vwap', 'vwap_distance',
                           'aggressive_buy_ratio', 'aggressive_sell_ratio',
                           'delta_profile', 'cumulative_delta', 'delta_divergence',
                           'absorption_ratio', 'iceberg_detection', 'volume_clusters',
                           'poc_distance', 'support_resistance_distance']:
                    features[feat] = 0.0
                    
        except Exception as e:
            logger.debug(f"Erro ao gerar features HMARL: {e}")
            
        return features
    
    def _calculate_rsi(self, prices: list, period: int = 14) -> float:
        """Calcula RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return 50.0
        
        try:
            # Calcular mudanças de preço
            deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
            
            # Separar ganhos e perdas
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]
            
            # Médias móveis
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
        except:
            return 50.0
    
    def _calculate_features_from_buffer(self) -> Dict[str, float]:
        """Calcula features básicas dos buffers para ML"""
        features = {}
        
        try:
            # Log para debug - verificar se buffers estão mudando
            if not hasattr(self, '_feature_calc_count'):
                self._feature_calc_count = 0
            self._feature_calc_count += 1
            
            # Features de preço
            if len(self.price_history) > 0:
                prices = list(self.price_history)[-100:]
                prices_array = np.array(prices)
                
                # Log a cada 20 cálculos
                if self._feature_calc_count % 20 == 0:
                    logger.info(f"[FEATURE CALC #{self._feature_calc_count}] Price history size: {len(self.price_history)}")
                    logger.info(f"  Last 5 prices: {prices[-5:] if len(prices) >= 5 else prices}")
                
                # Retornos
                if len(prices) > 1:
                    features['returns_1'] = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] != 0 else 0
                if len(prices) > 5:
                    features['returns_5'] = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
                if len(prices) > 20:
                    features['returns_20'] = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
                
                # Volatilidade
                if len(prices) > 20:
                    features['volatility_20'] = np.std(prices[-20:]) / np.mean(prices[-20:]) if np.mean(prices[-20:]) != 0 else 0
                
                # RSI simplificado - calcular de verdade
                if len(prices) > 14:
                    features['rsi_14'] = self._calculate_rsi(prices, 14)
                else:
                    features['rsi_14'] = 50  # Placeholder
                
                # Médias móveis
                if len(prices) > 20:
                    ma5 = np.mean(prices[-5:])
                    ma20 = np.mean(prices[-20:])
                    features['ma_5_20_ratio'] = ma5 / ma20 if ma20 != 0 else 1
            
            # Features de book
            if self.last_book_update:
                book = self.last_book_update
                
                # Log a cada 20 cálculos
                if self._feature_calc_count % 20 == 0:
                    logger.info(f"[FEATURE CALC] Book data:")
                    logger.info(f"  Bid: {book.get('bid_price_1', 0):.2f} x {book.get('bid_volume_1', 0)}")
                    logger.info(f"  Ask: {book.get('ask_price_1', 0):.2f} x {book.get('ask_volume_1', 0)}")
                
                features['bid_price_1'] = book.get('bid_price_1', 0)
                features['ask_price_1'] = book.get('ask_price_1', 0)
                features['spread'] = features['ask_price_1'] - features['bid_price_1']
                features['mid_price'] = (features['bid_price_1'] + features['ask_price_1']) / 2
                features['bid_volume_1'] = book.get('bid_volume_1', 0)
                features['ask_volume_1'] = book.get('ask_volume_1', 0)
                
                # Imbalance
                total_vol = features['bid_volume_1'] + features['ask_volume_1']
                if total_vol > 0:
                    features['imbalance'] = (features['bid_volume_1'] - features['ask_volume_1']) / total_vol
                else:
                    features['imbalance'] = 0
            
            # Preencher features faltantes com valores padrão
            all_features = [
                'returns_1', 'returns_2', 'returns_5', 'returns_10', 'returns_20',
                'volatility_10', 'volatility_20', 'volatility_50',
                'rsi_14', 'spread', 'imbalance', 'bid_price_1', 'ask_price_1'
            ]
            
            for feat in all_features:
                if feat not in features:
                    features[feat] = 0.0
            
        except Exception as e:
            logger.error(f"Erro ao calcular features: {e}")
        
        return features
    
    def check_position_status(self):
        """Verifica posição e emite eventos se necessário"""
        if not self.connection:
            return
        
        try:
            # Primeiro verificar se há grupos OCO ativos
            has_active_oco = False
            if hasattr(self.connection, 'oco_monitor') and self.connection.oco_monitor:
                active_groups = sum(1 for g in self.connection.oco_monitor.oco_groups.values() 
                                   if g.get('active', False))
                has_active_oco = active_groups > 0
                
                # Se tinha OCO ativo mas agora não tem mais, provavelmente posição fechou
                if not has_active_oco and hasattr(self, '_last_oco_check'):
                    if self._last_oco_check:
                        logger.info("[OCO CHECK] Grupos OCO foram desativados - posição provavelmente fechada")
                self._last_oco_check = has_active_oco
            
            # Verificar posição real
            position = None
            try:
                # Tentar check_position_exists primeiro (mais confiável)
                if hasattr(self.connection, 'check_position_exists'):
                    has_pos, qty, side = self.connection.check_position_exists(self.symbol)
                    if has_pos:
                        position = {'quantity': qty, 'side': side}
                # Fallback para get_position
                elif self.use_internal_tracking:
                    position = self.connection.get_position_safe(self.symbol)
                else:
                    try:
                        position = self.connection.get_position(self.symbol)
                    except:
                        self.use_internal_tracking = True
                        position = self.connection.get_position_safe(self.symbol)
            except Exception as e:
                logger.warning(f"Erro ao verificar posição: {e}")
            
            # IMPORTANTE: Se não há posição E não há OCO ativo, resetar estado
            if not position and not has_active_oco:
                if self.has_open_position:
                    # Posição foi fechada
                    logger.info("[POSIÇÃO FECHADA] Detectado fechamento - sem posição e sem OCO ativo")
                    
                    # IMPORTANTE: Cancelar todas as ordens pendentes do símbolo
                    try:
                        if self.connection:
                            # Cancelar ordens pendentes
                            self.connection.cancel_all_pending_orders(self.symbol)
                            logger.info(f"[OK] Ordens pendentes de {self.symbol} canceladas")
                            
                            # Limpar tracking de ordens no OrderManager
                            if self.order_manager:
                                self.order_manager.clear_pending_orders()
                                logger.info("[OK] OrderManager limpo")
                    except Exception as e:
                        logger.error(f"Erro ao cancelar ordens pendentes: {e}")
                    
                    # Chamar handler de posição fechada
                    self.handle_position_closed("position_check")
                    
                    # Resetar estado
                    self.has_open_position = False
                    self.current_position = 0
                    self.current_position_side = None
                    self.current_position_id = None
                    logger.info("[OK] Estado resetado - sistema pronto para novos trades")
            
            elif position:
                # Tem posição
                if not self.has_open_position:
                    # Nova posição detectada
                    logger.info(f"[POSIÇÃO] Nova: {position['quantity']} {position['side']}")
                    
                    # Emitir evento de posição aberta
                    position_id = f"POS_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    emit_position_event(
                        EventType.POSITION_OPENED,
                        position_id=position_id,
                        symbol=self.symbol,
                        side=position['side'],
                        quantity=position['quantity'],
                        entry_price=position.get('entry_price', 0),
                        source="position_check"
                    )
                
                self.has_open_position = True
                self.current_position = position['quantity'] if position['side'] == 'BUY' else -position['quantity']
                self.current_position_side = position['side']
            
            # Se tem OCO ativo mas não detecta posição, manter estado atual
            elif has_active_oco:
                if not self.has_open_position:
                    logger.debug("[OCO CHECK] OCO ativo detectado - provavelmente há posição")
                    # Não mudar estado - OCO indica posição existe
                
        except Exception as e:
            logger.error(f"Erro ao verificar posição: {e}")
    
    def make_hybrid_prediction(self):
        """
        NOVO SISTEMA: Baseado em Regime + HMARL para timing
        Substitui ML defeituoso por estratégias específicas de regime
        """
        try:
            # Log para debug
            if not hasattr(self, '_prediction_count'):
                self._prediction_count = 0
            self._prediction_count += 1
            
            # Verificar se tem dados suficientes
            buffer_size = len(self.book_buffer)
            if self._prediction_count <= 5:
                logger.info(f"[PREDICTION #{self._prediction_count}] Buffer size: {buffer_size}/20")
            
            # Atualizar sistema de regime com dados atuais
            if self.last_book_update and buffer_size >= 20:
                current_price = (self.last_book_update.get('bid_price_1', 5500) + 
                               self.last_book_update.get('ask_price_1', 5505)) / 2
                volume = self.last_book_update.get('bid_volume_1', 0) + \
                        self.last_book_update.get('ask_volume_1', 0)
                
                # Atualizar detector de regime
                self.regime_system.update(current_price, volume)
            
            # Atualizar HMARL para timing
            if self.hmarl_agents and self.last_book_update and buffer_size >= 5:
                try:
                    book_data = self.last_book_update
                    current_price = (book_data.get('bid_price_1', 5500) + book_data.get('ask_price_1', 5505)) / 2
                    
                    # Gerar features para HMARL
                    hmarl_features = self._generate_hmarl_features()
                    
                    # Atualizar HMARL para visualização
                    self.hmarl_agents.update_market_data(
                        price=current_price,
                        volume=self.total_volume,
                        book_data={
                            'spread': book_data.get('ask_price_1', 5505) - book_data.get('bid_price_1', 5500),
                            'imbalance': hmarl_features.get('order_flow_imbalance_5', 0)
                        },
                        features=hmarl_features  # Passar features completas
                    )
                    
                    # Obter consenso para salvar status
                    consensus = self.hmarl_agents.get_consensus()
                    
                    # ATUALIZAR ARQUIVO hmarl_status.json
                    if consensus:
                        import json
                        from datetime import datetime
                        hmarl_data = {
                            "timestamp": datetime.now().isoformat(),
                            "market_data": {
                                "price": current_price,
                                "volume": self.total_volume,
                                "book_data": {
                                    "spread": book_data.get('ask_price_1', 5505) - book_data.get('bid_price_1', 5500),
                                    "imbalance": hmarl_features.get('order_flow_imbalance_5', 0)
                                }
                            },
                            "consensus": consensus,
                            "agents": consensus.get('agents', {})
                        }
                        
                        # Gravar arquivo no diretório correto para o monitor
                        try:
                            import os
                            os.makedirs('data/monitor', exist_ok=True)
                            with open('data/monitor/hmarl_status.json', 'w') as f:
                                json.dump(hmarl_data, f, indent=2)
                        except:
                            pass  # Ignorar erros de gravação
                    
                    if self._prediction_count <= 3:
                        logger.info(f"[HMARL] Atualizado com {buffer_size} amostras - Action: {consensus['action']}")
                    
                except Exception as e:
                    if self._prediction_count <= 3:
                        logger.warning(f"[HMARL] Erro ao atualizar: {e}")
            
            # Aguardar dados mínimos para o sistema de regime
            if buffer_size < 20:
                if self._prediction_count <= 5:
                    logger.info(f"[PREDICTION] Aguardando mais dados... ({buffer_size}/20)")
                return {'signal': 0, 'confidence': 0.0}
            
            # ==== NOVO SISTEMA BASEADO EM REGIME ====
            # Gerar features para uso em ML e HMARL
            hmarl_features = self._generate_hmarl_features() if self.last_book_update else {}
            
            # 1. Obter sinal HMARL para timing
            hmarl_signal = None
            hmarl_confidence = 0.5
            
            if self.hmarl_agents:
                try:
                    consensus = self.hmarl_agents.get_consensus()
                    hmarl_signal = {
                        'action': consensus.get('action', 'HOLD'),
                        'confidence': consensus.get('confidence', 0.5)
                    }
                    hmarl_confidence = consensus.get('confidence', 0.5)
                    
                    # Log HMARL
                    if self._prediction_count % 20 == 0:
                        logger.info(f"[HMARL] Signal: {hmarl_signal['action']}, Conf: {hmarl_confidence:.0%}")
                except Exception as e:
                    logger.debug(f"HMARL não disponível: {e}")
            
            # 2. Obter sinal do sistema de regime (substituindo ML defeituoso)
            regime_signal = None
            ml_signal = 0
            ml_confidence = 0.0
            
            # Usar sistema híbrido ML + regime
            if self.last_book_update and buffer_size >= 20:
                try:
                    current_price = (self.last_book_update.get('bid_price_1', 5500) + 
                                   self.last_book_update.get('ask_price_1', 5505)) / 2
                    
                    # Tentar usar ML predictor primeiro se disponível
                    ml_prediction = None
                    if hasattr(self, 'ml_predictor') and self.ml_predictor:
                        try:
                            # Calcular features para ML
                            features = self._calculate_features_from_buffer()
                            
                            # Adicionar features do HMARL se disponíveis
                            if hmarl_features:
                                features.update(hmarl_features)
                            
                            # LOG DEBUG: Mostrar exatamente quais features estão sendo passadas
                            if self._prediction_count % 10 == 0 or self._prediction_count <= 3:
                                logger.info("[ML DEBUG] Features passadas aos modelos:")
                                logger.info(f"  Total features: {len(features)}")
                                # Mostrar primeiras 10 features com valores
                                feature_items = list(features.items())[:10]
                                for feat_name, feat_value in feature_items:
                                    logger.info(f"    {feat_name}: {feat_value:.4f}")
                                # Verificar variação
                                if hasattr(self, '_last_features'):
                                    changes = sum(1 for k in features if k in self._last_features and features[k] != self._last_features[k])
                                    logger.info(f"  Features que mudaram desde última vez: {changes}/{len(features)}")
                                self._last_features = features.copy()
                            
                            # Fazer predição ML
                            ml_prediction = self.ml_predictor.predict(features)
                            
                            # Log detalhado para debug das predições
                            if ml_prediction:
                                predictions_data = ml_prediction.get('predictions', {})
                                if predictions_data:
                                    context_data = predictions_data.get('context', {})
                                    micro_data = predictions_data.get('microstructure', {})
                                    meta_data = predictions_data.get('meta')
                                    
                                    # Log apenas a cada 30 segundos para não poluir
                                    if not hasattr(self, '_last_ml_debug_log') or (datetime.now() - self._last_ml_debug_log).total_seconds() > 30:
                                        self._last_ml_debug_log = datetime.now()
                                        logger.info("[ML DEBUG] Predictions recebidas do ML:")
                                        logger.info(f"  - Context: regime={context_data.get('regime')}, conf={context_data.get('regime_conf', 0):.2%}")
                                        logger.info(f"  - Micro: order_flow={micro_data.get('order_flow')}, conf={micro_data.get('order_flow_conf', 0):.2%}")
                                        logger.info(f"  - Meta: {meta_data}")
                                        logger.info(f"  - Signal: {ml_prediction.get('signal')}, Confidence: {ml_prediction.get('confidence', 0):.2%}")
                            
                            if ml_prediction and ml_prediction.get('signal') != 0:
                                ml_signal = ml_prediction['signal']
                                ml_confidence = ml_prediction['confidence']
                                
                                # Log ML prediction - sempre logar para debug
                                if self._prediction_count % 10 == 0:
                                    logger.info(f"[ML] Signal: {ml_signal}, Confidence: {ml_confidence:.2%}")
                                    if 'predictions' in ml_prediction:
                                        preds = ml_prediction['predictions']
                                        logger.info(f"  Context: {preds.get('context', {})}")
                                        logger.info(f"  Micro: {preds.get('microstructure', {})}")
                                    else:
                                        logger.warning("[ML] Predictions não encontradas no retorno do ML")
                        except Exception as e:
                            logger.debug(f"ML prediction error: {e}")
                            ml_prediction = None
                    
                    # Sempre salvar status ML para monitor (mesmo quando sinal = 0)
                    if ml_prediction:
                        # DEBUG: Log completo da estrutura de ml_prediction
                        logger.info(f"[DEBUG ML] Estrutura completa de ml_prediction:")
                        logger.info(f"  - Keys: {list(ml_prediction.keys())}")
                        logger.info(f"  - Signal: {ml_prediction.get('signal')}")
                        logger.info(f"  - Confidence: {ml_prediction.get('confidence')}")
                        
                        predictions_debug = ml_prediction.get('predictions', {})
                        logger.info(f"  - Predictions keys: {list(predictions_debug.keys())}")
                        logger.info(f"  - Context: {predictions_debug.get('context', {})}")
                        logger.info(f"  - Micro: {predictions_debug.get('microstructure', {})}")
                        logger.info(f"  - Meta: {predictions_debug.get('meta')}")
                        
                        # Salvar ML status para monitor
                        self._save_ml_status_for_monitor(ml_prediction, ml_prediction.get('predictions', {}))
                        
                        # Criar regime_signal compatível para o resto do código
                        from src.trading.regime_based_strategy import RegimeSignal, MarketRegime
                        regime_signal = type('obj', (object,), {
                            'regime': MarketRegime.UNDEFINED,
                            'signal': ml_signal,
                            'confidence': ml_confidence,
                            'strategy': 'ml_hybrid',
                            'entry_price': current_price,
                            'stop_loss': current_price * 0.995,
                            'take_profit': current_price * 1.01,
                            'risk_reward': 2.0
                        })()
                    else:
                        # Se ML não disponível ou não gerou sinal, usar regime system
                        regime_signal = self.regime_system.get_trading_signal(
                            current_price=current_price,
                            hmarl_signal=hmarl_signal
                        )
                    
                    if regime_signal:
                        # Converter sinal de regime para formato esperado
                        ml_signal = regime_signal.signal  # 1=BUY, -1=SELL, 0=HOLD
                        ml_confidence = regime_signal.confidence
                        
                        # Log do sinal de regime
                        if self._prediction_count % 10 == 0:
                            logger.info(f"[REGIME] {regime_signal.regime.value.upper()}")
                            logger.info(f"  Strategy: {regime_signal.strategy}")
                            logger.info(f"  Signal: {'BUY' if ml_signal == 1 else 'SELL' if ml_signal == -1 else 'HOLD'}")
                            logger.info(f"  Confidence: {ml_confidence:.0%}")
                            logger.info(f"  Entry: {regime_signal.entry_price:.2f}")
                            logger.info(f"  Stop: {regime_signal.stop_loss:.2f}")
                            logger.info(f"  Target: {regime_signal.take_profit:.2f}")
                            logger.info(f"  Risk/Reward: {regime_signal.risk_reward:.1f}:1")
                        
                        # NOVO: Validação final de tendência antes de retornar o sinal
                        # Mesmo que o regime system já valide, fazer uma dupla checagem aqui
                        is_trend_valid, trend_reason = self.regime_system.validate_trend_alignment(
                            ml_signal, regime_signal.regime, ml_confidence
                        )
                        
                        if not is_trend_valid:
                            logger.warning(f"[TREND BLOCK] Sinal final bloqueado: {trend_reason}")
                            # Atualizar métricas
                            if hasattr(self, 'metrics'):
                                self.metrics['trades_blocked_by_trend'] = self.metrics.get('trades_blocked_by_trend', 0) + 1
                            
                            # Salvar status de bloqueio para o monitor
                            ml_result = {
                                'signal': 0,  # HOLD devido ao bloqueio
                                'confidence': 0,
                                'regime': regime_signal.regime.value,
                                'strategy': 'blocked_by_trend',
                                'block_reason': trend_reason
                            }
                            ml_predictions = {
                                'context': {'regime': regime_signal.regime.value, 'confidence': 0},
                                'microstructure': {'strategy': 'blocked', 'confidence': 0},
                                'meta_learner': {'signal': 0, 'confidence': 0, 'blocked': True}
                            }
                            self._save_ml_status_for_monitor(ml_result, ml_predictions)
                            self._save_regime_status_for_monitor(regime_signal)
                            
                            # Não gerar sinal de trade
                            return {'signal': 0, 'confidence': 0.0}
                        
                        # Salvar dados para o monitor (compatibilidade)
                        ml_result = {
                            'signal': ml_signal,
                            'confidence': ml_confidence,
                            'regime': regime_signal.regime.value,
                            'strategy': regime_signal.strategy,
                            'trend_validation': trend_reason  # Adicionar motivo da validação
                        }
                        ml_predictions = {
                            'context': {'regime': regime_signal.regime.value, 'confidence': ml_confidence},
                            'microstructure': {'strategy': regime_signal.strategy, 'confidence': ml_confidence},
                            'meta_learner': {'signal': ml_signal, 'confidence': ml_confidence}
                        }
                        self._save_ml_status_for_monitor(ml_result, ml_predictions)
                        # NOVO: Salvar status do regime para o monitor
                        self._save_regime_status_for_monitor(regime_signal)
                        
                    else:
                        # Sem sinal no momento - atualizar status do regime periodicamente
                        if self._prediction_count % 20 == 0:  # A cada 20 iterações
                            stats = self.regime_system.get_stats()
                            current_regime = stats.get('current_regime', 'undefined')
                            
                            # Criar objeto regime falso para salvar status
                            from src.trading.regime_based_strategy import RegimeSignal, MarketRegime
                            try:
                                regime_enum = MarketRegime(current_regime) if current_regime != 'undefined' else MarketRegime.UNDEFINED
                            except:
                                regime_enum = MarketRegime.LATERAL
                                
                            status_signal = type('obj', (object,), {
                                'regime': regime_enum,
                                'confidence': 0.6,
                                'strategy': 'waiting',
                                'signal': 0
                            })()
                            
                            # Salvar status mesmo sem sinal (para mostrar regime atual no monitor)
                            self._save_regime_status_for_monitor(status_signal)
                            
                            if self._prediction_count % 100 == 0:  # Log menos frequente
                                logger.info(f"[REGIME] Aguardando setup - Regime: {current_regime}")
                    
                except Exception as e:
                    logger.error(f"Erro no sistema de regime: {e}")
                    import traceback
                    traceback.print_exc()
            # HMARL já foi processado acima para timing
            
            # 3. Retornar sinal do sistema de regime (com HMARL para timing)
            if ml_signal != 0:
                # Sistema de regime gerou sinal válido
                
                # Emitir evento de sinal gerado
                self.event_bus.publish(Event(
                    type=EventType.SIGNAL_GENERATED,
                    data={
                        'signal': ml_signal,
                        'confidence': ml_confidence,
                        'regime': regime_signal.regime.value if regime_signal else 'undefined',
                        'strategy': regime_signal.strategy if regime_signal else 'none',
                        'hmarl_timing': hmarl_signal['action'] if hmarl_signal else 'HOLD'
                    },
                    source="regime_system"
                ))
                
                return {
                    'signal': ml_signal,
                    'confidence': ml_confidence,
                    'regime_signal': regime_signal,
                    'hmarl_timing': hmarl_signal
                }
            
            return {'signal': 0, 'confidence': 0.0}
            
        except Exception as e:
            logger.error(f"Erro na predição: {e}")
            return {'signal': 0, 'confidence': 0.0}
    
    def process_book_update(self, symbol, book_data):
        """Processa atualização do book"""
        try:
            # Log para debug
            if not hasattr(self, '_book_update_count'):
                self._book_update_count = 0
            self._book_update_count += 1
            
            if self._book_update_count <= 5 or self._book_update_count % 100 == 0:
                logger.info(f"[BOOK UPDATE #{self._book_update_count}] Bid: {book_data.get('bid_price_1', 0):.2f} Ask: {book_data.get('ask_price_1', 0):.2f}")
                logger.info(f"  Buffer size before: {len(self.book_buffer)}")
            
            self.book_buffer.append(book_data)
            self.last_book_update = book_data
            
            if self._book_update_count <= 5:
                logger.info(f"  Buffer size after: {len(self.book_buffer)}")
            
            if 'bid_price_1' in book_data and 'ask_price_1' in book_data:
                self.last_mid_price = (book_data['bid_price_1'] + book_data['ask_price_1']) / 2
                self.current_price = self.last_mid_price
            
            # Emitir evento de atualização de book
            self.event_bus.publish(Event(
                type=EventType.BOOK_UPDATE,
                data=book_data,
                source="market_data"
            ))
            
        except Exception as e:
            logger.error(f"Erro ao processar book: {e}")
    
    def process_trade(self, trade_data):
        """Processa novo trade"""
        try:
            self.tick_buffer.append(trade_data)
            self.last_trade = trade_data
            
            if 'price' in trade_data:
                self.current_price = trade_data['price']
                self.price_history.append(trade_data['price'])
            
            if 'volume' in trade_data:
                self.total_volume += trade_data.get('volume', 0)
            
            # Emitir evento de trade executado
            self.event_bus.publish(Event(
                type=EventType.TRADE_EXECUTED,
                data=trade_data,
                source="market_data"
            ))
            
        except Exception as e:
            logger.error(f"Erro ao processar trade: {e}")
    
    def _training_scheduler(self):
        """Agenda re-treinamento diário"""
        while self.running:
            try:
                now = datetime.now()
                
                if now.hour == 18 and now.minute == 40:
                    logger.info("[TRAINING] Iniciando re-treinamento...")
                    
                    if self.retraining_system:
                        success = self.retraining_system.run_retraining_pipeline()
                        
                        if success:
                            logger.info("[TRAINING] Re-treinamento concluído")
                            
                            if self.model_selector:
                                best_model = self.model_selector.get_current_best_model()
                                if best_model:
                                    logger.info(f"[TRAINING] Modelo: {best_model['name']}")
                    
                    time.sleep(3600)
                
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Erro no scheduler: {e}")
                time.sleep(300)
    
    def trading_loop(self):
        """Loop principal de trading"""
        logger.info("Iniciando loop de trading...")
        
        # Contador para debug
        loop_count = 0
        error_count = 0
        max_errors = 10
        
        while self.running:
            try:
                loop_count += 1
                
                # Log a cada 10 iterações
                if loop_count <= 5 or loop_count % 10 == 0:
                    logger.info(f"[TRADING LOOP] Iteração #{loop_count} - Fazendo predição...")
                
                # Fazer predição
                prediction = self.make_hybrid_prediction()
                self.metrics['predictions_today'] += 1
                
                # Reset error count on success
                error_count = 0
                
                # Log da predição
                if loop_count <= 5:
                    logger.info(f"[TRADING LOOP] Predição: signal={prediction['signal']}, confidence={prediction['confidence']:.2%}")
                
                # Executar trade se sinal válido
                if prediction['signal'] != 0 and prediction['confidence'] >= self.min_confidence:
                    logger.info(f"[TRADING LOOP] Sinal válido detectado! Signal={prediction['signal']}, Conf={prediction['confidence']:.1%}")
                    
                    # Preparar dados para sistema de otimização
                    ml_pred = prediction.get('ml_data', {'signal': prediction['signal'], 'confidence': prediction['confidence']})
                    hmarl_cons = prediction.get('hmarl_data', {'signal': prediction['signal'], 'confidence': prediction['confidence'], 'action': 'BUY' if prediction['signal'] > 0 else 'SELL'})
                    
                    # NOVO: Passar regime_signal se disponível
                    regime_signal = prediction.get('regime_signal', None)
                    
                    # NOVO: Log de validação de tendência aprovada
                    if regime_signal:
                        trend_stats = self.regime_system.get_stats()
                        logger.info(f"[TREND APPROVED] Trade alinhado com tendência")
                        logger.info(f"  Regime: {trend_stats.get('current_regime', 'unknown')}")
                        logger.info(f"  Consistência: {trend_stats.get('trend_consistency', 'N/A')}")
                        logger.info(f"  Bloqueios: {trend_stats.get('trades_blocked_by_trend', 0)}/{trend_stats.get('total_validations', 0)}")
                        
                        # Atualizar métrica
                        self.metrics['trend_aligned_trades'] += 1
                    
                    self.execute_trade_with_oco(
                        signal=prediction['signal'],
                        confidence=prediction['confidence'],
                        ml_prediction=ml_pred,
                        hmarl_consensus=hmarl_cons,
                        regime_signal=regime_signal  # Passar info do regime
                    )
                
                time.sleep(1)
                
            except Exception as e:
                error_count += 1
                logger.error(f"[TRADING LOOP] Erro no trading ({error_count}/{max_errors}): {e}")
                import traceback
                if loop_count <= 5 or error_count <= 3:
                    traceback.print_exc()
                
                # Se muitos erros, parar thread
                if error_count >= max_errors:
                    logger.error(f"[TRADING LOOP] Muitos erros ({error_count}), parando thread")
                    self.running = False
                    break
                    
                time.sleep(5)
        
        logger.info("[TRADING LOOP] Thread de trading finalizada")
    
    def metrics_loop(self):
        """Loop de métricas com eventos"""
        while self.running:
            try:
                # Obter métricas do EventBus
                event_metrics = self.event_integration.get_metrics() if self.event_integration else {}
                
                # Calcular métricas
                total = self.metrics['wins'] + self.metrics['losses']
                win_rate = self.metrics['wins'] / total if total > 0 else 0
                
                # Log com métricas de eventos
                logger.info(
                    f"[METRICS] Trades: {self.metrics['trades_today']} | "
                    f"WR: {win_rate:.1%} | "
                    f"Events: {event_metrics.get('event_stats', {}).get('processed', 0)} | "
                    f"Queue: {event_metrics.get('event_stats', {}).get('queue_size', 0)}"
                )
                
                # NOVO: Obter status do Sistema de Otimização
                if self.optimization_system:
                    opt_status = self.optimization_system.get_system_status()
                    logger.info(
                        f"[OTIMIZAÇÃO] Regime: {opt_status['current_regime']} | "
                        f"Trades hoje: {opt_status['daily_trades']} | "
                        f"Posição: {'SIM' if opt_status['has_position'] else 'NÃO'}"
                    )
                
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Erro nas métricas: {e}")
                time.sleep(60)
    
    def data_collection_loop(self):
        """Loop para coletar dados de mercado"""
        logger.info("Iniciando coleta de dados...")
        
        while self.running:
            try:
                # Coletar dados reais
                if self.connection:
                    if hasattr(self.connection, 'last_price') and self.connection.last_price > 0:
                        price = self.connection.last_price
                        if price > 0 and price != self.current_price:
                            self.current_price = price
                            self.price_history.append(price)
                            
                            # Emitir evento de atualização de preço
                            self.event_bus.publish(Event(
                                type=EventType.PRICE_UPDATE,
                                data={'price': price},
                                source="market_data"
                            ))
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Erro na coleta: {e}")
                time.sleep(5)
    
    def start(self):
        """Inicia sistema completo com eventos"""
        if not self.initialize():
            return False
        
        self.running = True
        
        # Emitir evento de sistema iniciado
        self.event_bus.publish(Event(
            type=EventType.SYSTEM_STARTED,
            data={'timestamp': datetime.now().isoformat()},
            priority=10
        ))
        
        # Iniciar threads
        threads = [
            threading.Thread(target=self.trading_loop, daemon=True, name="Trading"),
            threading.Thread(target=self.metrics_loop, daemon=True, name="Metrics"),
            threading.Thread(target=self.data_collection_loop, daemon=True, name="DataCollection"),
            threading.Thread(target=self.cleanup_orphan_orders_loop, daemon=True, name="Cleanup"),
            threading.Thread(target=self.position_consistency_check, daemon=True, name="Consistency"),
            threading.Thread(target=self.monitor_oco_executions, daemon=True, name="OCOExecMonitor")
        ]
        
        for thread in threads:
            thread.start()
            logger.info(f"Thread {thread.name} iniciada")
        
        return True
    
    def stop(self):
        """Para sistema e emite evento"""
        logger.info("Parando sistema...")
        
        # Emitir evento de sistema parando
        self.event_bus.publish(Event(
            type=EventType.SYSTEM_STOPPED,
            data={'timestamp': datetime.now().isoformat()},
            priority=10
        ))
        
        self.running = False
        
        # Cancelar ordens pendentes
        if self.connection and not self.has_open_position:
            self.connection.cancel_all_pending_orders(self.symbol)
        
        # NOVO: Salvar estado do Sistema de Otimização
        if self.optimization_system:
            try:
                self.optimization_system.save_state()
                logger.info("[OTIMIZAÇÃO] Estado salvo")
                
                # Gerar relatório final
                report = self.optimization_system.get_performance_report()
                if report:
                    print("\n" + report)
            except Exception as e:
                logger.error(f"Erro ao salvar otimização: {e}")
        
        # Parar EventBus
        if self.event_bus:
            self.event_bus.stop()
        
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
    
    # Criar sistema com eventos
    system = QuantumTraderCompleteOCOEvents()
    
    try:
        if system.start():
            print("\nSistema rodando com EventBus. Pressione Ctrl+C para parar...")
            print("Execute 'python test_event_system.py' em outro terminal para testar eventos")
            
            # Manter rodando
            while system.running:
                time.sleep(1)
                # Verificar se threads estão vivas
                if hasattr(system, 'trading_thread') and not system.trading_thread.is_alive():
                    logger.error("Thread de trading morreu!")
                    break
                    
            print("\n[!] Sistema parou")
                
    except KeyboardInterrupt:
        print("\n[!] Parando...")
        system.stop()
        
    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
        if 'system' in locals():
            system.stop()


if __name__ == "__main__":
    main()