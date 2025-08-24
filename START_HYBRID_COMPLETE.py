#!/usr/bin/env python3
"""
QUANTUM TRADER v2.0 - SISTEMA HÍBRIDO COMPLETO DE PRODUÇÃO
Integra: Modelos Híbridos (3 camadas) + Conexão Real B3 + Trading + Monitor
Baseado no START_PRODUCTION_COMPLETE.py funcional
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

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/hybrid_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('HybridComplete')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent / 'core'))

# Importar componentes do sistema funcional
from src.connection_manager_working import ConnectionManagerWorking
from src.connection_manager_oco import ConnectionManagerOCO
from core.enhanced_production_system import EnhancedProductionSystem
from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
from src.trading.order_manager import WDOOrderManager, OrderSide, OrderStatus
from src.trading.adaptive_risk_manager import AdaptiveRiskManager
from src.monitoring.hmarl_monitor_bridge import get_bridge

class QuantumTraderHybridComplete:
    """Sistema híbrido completo com modelos ML de 3 camadas + conexão real B3"""
    
    def __init__(self):
        self.running = False
        self.connection = None
        self.system = None
        self.monitor_process = None
        self.data_lock = threading.Lock()
        
        # Configurações
        self.enable_trading = os.getenv('ENABLE_TRADING', 'false').lower() == 'true'
        self.enable_recording = os.getenv('ENABLE_DATA_RECORDING', 'true').lower() == 'true'
        self.enable_daily_training = os.getenv('ENABLE_DAILY_TRAINING', 'true').lower() == 'true'
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE', '0.60'))
        self.symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
        
        # Modelos híbridos
        self.models = {}
        self.scalers = {}
        self.models_dir = Path("models/hybrid")
        self.model_version = "v1.0"
        
        # HMARL Real-time
        self.hmarl_agents = HMARLAgentsRealtime()
        
        # Order Manager para WDO
        self.order_manager = WDOOrderManager()
        
        # Gestão de Risco Adaptativa
        self.risk_manager = AdaptiveRiskManager(self.symbol)
        self.use_adaptive_risk = True  # Ativar gestão adaptativa
        
        # Bridge para monitor
        self.monitor_bridge = get_bridge()
        
        # Buffers de dados
        self.price_history = deque(maxlen=500)
        self.book_snapshots = deque(maxlen=200)
        self.tick_buffer = deque(maxlen=1000)
        self.book_buffer = deque(maxlen=1000)
        
        # Preço atual para gestão de ordens
        self.current_price = 0
        self.last_mid_price = 0
        
        # Estatísticas
        self.stats = {
            'features_calculated': 0,
            'predictions_made': 0,
            'hybrid_predictions': 0,
            'hmarl_predictions': 0,
            'trades_executed': 0,
            'callbacks_received': 0,
            'data_records_saved': 0,
            'model_accuracy': 0.0,
            'start_time': time.time()
        }
        
        # Controle de posição
        self.has_open_position = False
        self.current_position = 0  # Quantidade de contratos em posição
        
        # Arquivos de gravação
        self.data_files = {}
        self.record_count = {'book': 0, 'tick': 0}
        
        # Re-treinamento
        self.last_training_date = None
        self.training_data_queue = []
        
        print("\n" + "=" * 80)
        print(" QUANTUM TRADER v2.0 - SISTEMA HÍBRIDO COMPLETO")
        print(" 3-Layer ML + Conexão B3 + 65 Features + Trading + Monitor")
        print("=" * 80)
        
    def load_hybrid_models(self):
        """Carrega modelos híbridos treinados (3 camadas) com seleção inteligente"""
        try:
            print("\n[*] Carregando modelos híbridos de 3 camadas...")
            
            # Verificar se há modelos re-treinados disponíveis
            try:
                from src.training.model_selector import ModelSelector
                
                print("  [*] Verificando modelos re-treinados disponíveis...")
                selector = ModelSelector(
                    models_dir="models",
                    min_accuracy=0.55,
                    max_model_age_days=30
                )
                
                # Verificar se deve re-avaliar modelos
                if selector.should_reevaluate(hours_since_last=24):
                    print("  [*] Re-avaliando modelos disponíveis...")
                    best_model = selector.select_best_model()
                else:
                    best_model = selector.get_current_best_model()
                
                # Se encontrou modelo re-treinado, usar como modelo principal
                if best_model and 'retrained' in str(best_model.get('model_path', '')):
                    print(f"  [✓] Usando modelo re-treinado: {best_model['model_path'].name}")
                    model, scaler = selector.load_best_model()
                    if model and scaler:
                        # Criar estrutura alternativa para modelo re-treinado
                        self.models['context'] = {
                            'retrained_main': model,  # Modelo re-treinado principal
                            'regime_detector': model,  # Usar como fallback
                            'volatility_forecaster': model,
                            'session_classifier': model
                        }
                        self.scalers['context'] = scaler
                        self.has_retrained_model = True
                        print("  [✓] Modelo re-treinado carregado como principal")
                else:
                    self.has_retrained_model = False
                    
            except Exception as e:
                print(f"  [!] ModelSelector não disponível: {e}")
                self.has_retrained_model = False
            
            # Carregar modelos padrão se não houver re-treinado
            if not self.has_retrained_model:
                # Layer 1: Context Models
                context_dir = self.models_dir / "context"
                if context_dir.exists():
                    self.models['context'] = {
                        'regime_detector': joblib.load(context_dir / "regime_detector.pkl"),
                        'volatility_forecaster': joblib.load(context_dir / "volatility_forecaster.pkl"),
                        'session_classifier': joblib.load(context_dir / "session_classifier.pkl")
                    }
                    print("  [OK] Layer 1 (Context): 3 modelos padrão carregados")
                
                # Scalers para modelos padrão
                self.scalers['context'] = joblib.load(self.models_dir / "scaler_context.pkl")
            
            # Layer 2: Microstructure Models (sempre carregar)
            micro_dir = self.models_dir / "microstructure"
            if micro_dir.exists():
                self.models['microstructure'] = {
                    'order_flow_analyzer': joblib.load(micro_dir / "order_flow_analyzer.pkl"),
                    'book_dynamics': joblib.load(micro_dir / "book_dynamics.pkl")
                }
                print("  [OK] Layer 2 (Microstructure): 2 modelos carregados")
            
            # Layer 3: Meta-learner
            meta_dir = self.models_dir / "meta_learner"
            if meta_dir.exists():
                self.models['meta_learner'] = joblib.load(meta_dir / "meta_learner.pkl")
                print("  [OK] Layer 3 (Meta-Learner): 1 modelo carregado")
            
            # Scaler microstructure
            self.scalers['microstructure'] = joblib.load(self.models_dir / "scaler_microstructure.pkl")
            
            # Versão
            config_path = self.models_dir / "config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.model_version = config.get('timestamp', 'unknown')
            
            print(f"  [OK] Versão dos modelos: {self.model_version}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao carregar modelos híbridos: {e}")
            return False
        
    def initialize(self):
        """Inicializa todos os componentes"""
        try:
            # 1. Modelos híbridos
            print("\n[1/6] Carregando modelos híbridos ML...")
            if not self.load_hybrid_models():
                print("  [AVISO] Rodando sem modelos híbridos")
            
            # 2. Sistema de features (legado)
            print("\n[2/6] Inicializando sistema de 65 features...")
            self.system = EnhancedProductionSystem()
            self.system._load_ml_models()
            print(f"  [OK] Sistema de features com {len(self.system.models)} modelos legados")
            
            # 3. Conexão com B3
            print("\n[3/6] Estabelecendo conexão REAL com B3...")
            USERNAME = os.getenv('PROFIT_USERNAME', '29936354842')
            PASSWORD = os.getenv('PROFIT_PASSWORD', 'Ultra3376!')
            
            dll_path = "./ProfitDLL64.dll"
            if not os.path.exists(dll_path):
                dll_path = "C:\\Users\\marth\\Downloads\\ProfitDLL\\DLLs\\Win64\\ProfitDLL.dll"
            
            # Usar ConnectionManagerOCO para suporte a ordens bracket
            self.use_oco = os.getenv('USE_OCO_ORDERS', 'true').lower() == 'true'
            if self.use_oco:
                logger.info("[CONFIG] Usando ordens OCO (stop/take automatico)")
                self.connection = ConnectionManagerOCO(dll_path)
            else:
                logger.info("[CONFIG] Usando ordens simples (stop/take manual)")
                self.connection = ConnectionManagerWorking(dll_path)
            
            if self.connection.initialize(username=USERNAME, password=PASSWORD):
                print("  [OK] CONECTADO À B3!")
                
                # Aguardar conexão completa com broker (importante para envio de ordens)
                print("  [*] Aguardando conexão completa com broker...")
                for i in range(30):  # Espera até 30 segundos
                    status = self.connection.get_status()
                    if status['broker']:
                        print(f"  [OK] Broker conectado após {i+1} segundos")
                        break
                    time.sleep(1)
                    if i % 5 == 4:
                        print(f"    Aguardando... ({i+1}s)")
                
                # Mostrar status final
                status = self.connection.get_status()
                print(f"    Login: {'OK' if status['connected'] else 'X'}")
                print(f"    Market: {'OK' if status['market'] else 'X'}")
                print(f"    Broker: {'OK' if status['broker'] else 'X'}")
                print(f"    Símbolo: {self.symbol}")
                
                if not status['broker']:
                    print("  [AVISO] Broker não conectou completamente - ordens podem falhar")
            else:
                print("  [ERRO] Falha na conexão")
                return False
            
            # 4. Gravação de dados
            if self.enable_recording:
                print("\n[4/6] Configurando gravação de dados...")
                self._setup_data_recording()
                print(f"  [OK] Gravação habilitada em data/book_tick_data/")
            
            # 5. Sistema de trading
            print("\n[5/6] Configurando sistema de trading...")
            if self.enable_trading:
                print(f"  [OK] Trading ATIVO - Confiança mínima: {self.min_confidence:.0%}")
                print(f"    Modelos Híbridos: {'OK' if self.models else 'X'}")
                print(f"    Re-treinamento diário: {'OK' if self.enable_daily_training else 'X'}")
            else:
                print("  [INFO] Trading em modo SIMULAÇÃO")
            
            # 6. Monitor
            print("\n[6/6] Iniciando monitor de console...")
            try:
                self.monitor_process = subprocess.Popen(
                    ['python', 'core/monitor_console_enhanced.py'],
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                )
                print("  [OK] Monitor iniciado em nova janela")
            except:
                print("  [INFO] Execute 'python core/monitor_console_enhanced.py' manualmente")
            
            # Iniciar thread de re-treinamento
            if self.enable_daily_training:
                threading.Thread(target=self._training_scheduler, daemon=True).start()
                print("\n[*] Re-treinamento diário agendado para 18:40 (após fechamento do mercado)")
            
            print("\n" + "=" * 80)
            print(" SISTEMA HÍBRIDO INICIALIZADO COM SUCESSO!")
            print("=" * 80)
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
            writer.writerow(['timestamp', 'symbol', 'price', 'volume', 'side', 'aggressor'])
    
    def create_context_features(self, df_tick):
        """Cria features de contexto para Layer 1"""
        try:
            features = pd.DataFrame(index=[0])
            
            if len(df_tick) > 0:
                prices = [t['price'] for t in df_tick if 'price' in t]
                
                if len(prices) >= 50:
                    # Médias móveis
                    features['sma_5'] = np.mean(prices[-5:])
                    features['sma_20'] = np.mean(prices[-20:])
                    features['sma_50'] = np.mean(prices[-50:])
                    features['sma_trend'] = (features['sma_5'] - features['sma_20']) / (features['sma_20'] + 1e-8)
                    
                    # Momentum
                    features['momentum_10'] = (prices[-1] - prices[-10]) / (prices[-10] + 1e-8)
                    features['momentum_30'] = (prices[-1] - prices[-30]) / (prices[-30] + 1e-8)
                    features['momentum_60'] = (prices[-1] - prices[-min(60, len(prices))]) / (prices[-min(60, len(prices))] + 1e-8)
                    
                    # Volatilidade
                    price_array = np.array(prices[-61:]) if len(prices) > 60 else np.array(prices)
                    if len(price_array) > 1:
                        returns = np.diff(price_array) / price_array[:-1]
                    else:
                        returns = np.array([])
                    features['volatility_10'] = np.std(returns[-10:]) if len(returns) >= 10 else 0
                    features['volatility_30'] = np.std(returns[-30:]) if len(returns) >= 30 else 0
                    features['volatility_60'] = np.std(returns) if len(returns) > 0 else 0
                    features['volatility_ratio'] = features['volatility_10'] / (features['volatility_30'] + 1e-8)
                    
                    # ATR
                    features['atr'] = (max(prices[-20:]) - min(prices[-20:])) / (np.mean(prices[-20:]) + 1e-8)
                    
                    # Volume
                    volumes = [t.get('volume', 0) for t in df_tick[-60:]]
                    features['volume_ma_10'] = np.mean(volumes[-10:]) if len(volumes) >= 10 else 0
                    features['volume_ma_30'] = np.mean(volumes[-30:]) if len(volumes) >= 30 else 0
                    features['volume_ratio'] = volumes[-1] / (features['volume_ma_30'] + 1e-8) if volumes else 1
                    features['volume_trend'] = features['volume_ma_10'] / (features['volume_ma_30'] + 1e-8)
                    
                    # Temporal
                    now = datetime.now()
                    features['hour'] = now.hour
                    features['minute'] = now.minute
                    features['day_of_week'] = now.weekday()
                    features['session'] = 1 if 9 <= now.hour < 12 else (2 if 12 <= now.hour < 15 else 0)
                    
                    # Aggressor
                    features['aggressor_ratio'] = np.mean([t.get('aggressor', 0) for t in df_tick[-100:]])
                    features['trade_intensity'] = sum(volumes[-100:]) if len(volumes) >= 100 else 0
                    
                    return features.fillna(0)
            
            # Retornar features vazias se não houver dados suficientes
            for col in ['sma_5', 'sma_20', 'sma_50', 'sma_trend', 'momentum_10', 'momentum_30',
                       'momentum_60', 'volatility_10', 'volatility_30', 'volatility_60',
                       'volatility_ratio', 'atr', 'volume_ma_10', 'volume_ma_30', 'volume_ratio',
                       'volume_trend', 'hour', 'minute', 'day_of_week', 'session',
                       'aggressor_ratio', 'trade_intensity']:
                features[col] = 0
                
            return features
            
        except Exception as e:
            logger.error(f"Erro ao criar context features: {e}")
            return pd.DataFrame()
    
    def create_book_features(self, df_book):
        """Cria features de book para Layer 2"""
        try:
            features = pd.DataFrame(index=[0])
            
            if len(df_book) > 0:
                last_book = df_book[-1] if isinstance(df_book, list) else df_book
                
                # Spread
                features['spread'] = last_book.get('spread', 0.5)
                features['spread_ma'] = np.mean([b.get('spread', 0.5) for b in df_book[-20:]]) if len(df_book) >= 20 else 0.5
                features['spread_std'] = np.std([b.get('spread', 0.5) for b in df_book[-20:]]) if len(df_book) >= 20 else 0.1
                features['spread_normalized'] = (features['spread'] - features['spread_ma']) / (features['spread_std'] + 1e-8)
                
                # Imbalance
                features['imbalance'] = last_book.get('imbalance', 0)
                features['imbalance_ma'] = np.mean([b.get('imbalance', 0) for b in df_book[-20:]]) if len(df_book) >= 20 else 0
                features['imbalance_momentum'] = features['imbalance'] - features['imbalance_ma']
                
                # Volume
                features['book_pressure'] = last_book.get('book_pressure', 0.5)
                features['volume_at_best'] = last_book.get('volume_at_best', 100)
                features['volume_ratio'] = last_book.get('volume_ratio', 1)
                
                # Price
                features['mid_price'] = last_book.get('mid_price', 5000)
                mid_prices = [b.get('mid_price', 5000) for b in df_book[-10:]]
                features['mid_return_1'] = (mid_prices[-1] - mid_prices[-2]) / mid_prices[-2] if len(mid_prices) >= 2 else 0
                features['mid_return_5'] = (mid_prices[-1] - mid_prices[-5]) / mid_prices[-5] if len(mid_prices) >= 5 else 0
                features['mid_return_10'] = (mid_prices[-1] - mid_prices[-10]) / mid_prices[-10] if len(mid_prices) >= 10 else 0
                
                # Order flow
                features['bid_change'] = 0
                features['ask_change'] = 0
                features['net_order_flow'] = 0
                features['bid_ask_ratio'] = 1
                features['microprice'] = features['mid_price']
            else:
                # Features padrão
                for col in ['spread', 'spread_ma', 'spread_std', 'spread_normalized',
                           'imbalance', 'imbalance_ma', 'imbalance_momentum',
                           'book_pressure', 'volume_at_best', 'volume_ratio',
                           'mid_price', 'mid_return_1', 'mid_return_5', 'mid_return_10',
                           'bid_change', 'ask_change', 'net_order_flow',
                           'bid_ask_ratio', 'microprice']:
                    features[col] = 0 if col != 'mid_price' else 5000
            
            return features
            
        except Exception as e:
            logger.error(f"Erro ao criar book features: {e}")
            return pd.DataFrame()
    
    def make_hybrid_prediction(self):
        """Faz predição usando modelos híbridos de 3 camadas"""
        try:
            if not self.models:
                return None
            
            # Preparar dados
            tick_data = list(self.tick_buffer)
            book_data = list(self.book_buffer)
            
            if len(tick_data) < 50 or len(book_data) < 20:
                return None
            
            # Criar features
            context_features = self.create_context_features(tick_data)
            book_features = self.create_book_features(book_data)
            
            if context_features.empty or book_features.empty:
                return None
            
            # Layer 1: Context Prediction com tratamento de erro
            context_scaled = self.scalers['context'].transform(context_features)
            context_proba = None  # Inicializar para garantir que existe
            try:
                context_pred = self.models['context']['regime_detector'].predict(context_scaled)[0]
                context_proba = self.models['context']['regime_detector'].predict_proba(context_scaled)[0]
                logger.info(f"[ML Context] Pred: {context_pred}, Proba: {context_proba}, Max Conf: {context_proba.max():.2%}")
            except (AttributeError, Exception) as e:
                # Fallback para incompatibilidade de versão sklearn
                logger.debug(f"[ML Context] Usando fallback: {e}")
                try:
                    proba = self.models['context']['regime_detector'].predict_proba(context_scaled)[0]
                    context_pred = np.argmax(proba) - 1  # Converter para -1, 0, 1
                    context_proba = proba
                    logger.info(f"[ML Context Fallback] Pred: {context_pred}, Proba: {context_proba}, Max Conf: {proba.max():.2%}")
                except Exception as e2:
                    logger.warning(f"[ML Context] Fallback completo: {e2}")
                    context_pred = 0
                    context_proba = np.array([0.33, 0.34, 0.33])
            
            # Layer 2: Microstructure Prediction com tratamento de erro
            book_scaled = self.scalers['microstructure'].transform(book_features)
            micro_proba = None  # Inicializar para garantir que existe
            try:
                micro_pred = self.models['microstructure']['order_flow_analyzer'].predict(book_scaled)[0]
                micro_proba = self.models['microstructure']['order_flow_analyzer'].predict_proba(book_scaled)[0]
                logger.info(f"[ML Micro] Pred: {micro_pred}, Proba: {micro_proba}, Max Conf: {micro_proba.max():.2%}")
            except (AttributeError, Exception) as e:
                # Fallback para incompatibilidade de versão sklearn
                logger.debug(f"[ML Micro] Usando fallback: {e}")
                try:
                    proba = self.models['microstructure']['order_flow_analyzer'].predict_proba(book_scaled)[0]
                    micro_pred = np.argmax(proba) - 1  # Converter para -1, 0, 1
                    micro_proba = proba
                    logger.info(f"[ML Micro Fallback] Pred: {micro_pred}, Proba: {micro_proba}, Max Conf: {proba.max():.2%}")
                except Exception as e2:
                    logger.warning(f"[ML Micro] Fallback completo: {e2}")
                    micro_pred = 0
                    micro_proba = np.array([0.33, 0.34, 0.33])
            
            # Layer 3: Meta-learner
            meta_features = pd.DataFrame({
                'context_pred': [context_pred],
                'micro_pred': [micro_pred],
                'agreement': [1 if context_pred == micro_pred else 0],
                'confidence_gap': [abs(context_pred - micro_pred)]
            })
            
            try:
                final_pred = self.models['meta_learner'].predict(meta_features)[0]
                confidence = self.models['meta_learner'].predict_proba(meta_features)[0].max()
            except (AttributeError, Exception) as e:
                # Fallback simples: usar consenso dos dois modelos
                logger.debug(f"Meta-learner fallback: {e}")
                if context_pred == micro_pred:
                    final_pred = context_pred
                    confidence = 0.7  # Alta confiança se concordam
                else:
                    final_pred = 0  # HOLD se discordam
                    confidence = 0.4  # Baixa confiança
            
            self.stats['hybrid_predictions'] += 1
            
            # Salvar status ML para o monitor com probabilidades
            # Calcular confidence das camadas individuais
            # IMPORTANTE: Verificar se as variáveis existem E têm valores válidos
            try:
                if hasattr(context_proba, 'max'):
                    context_conf = float(context_proba.max())
                else:
                    context_conf = float(max(context_proba)) if context_proba is not None else 0.5
            except:
                context_conf = 0.5
                
            try:
                if hasattr(micro_proba, 'max'):
                    micro_conf = float(micro_proba.max())
                else:
                    micro_conf = float(max(micro_proba)) if micro_proba is not None else 0.5
            except:
                micro_conf = 0.5
            
            ml_status = {
                'context_pred': int(context_pred),
                'context_conf': float(context_conf),
                'micro_pred': int(micro_pred),
                'micro_conf': float(micro_conf),
                'meta_pred': int(final_pred),
                'ml_confidence': float(confidence),
                'ml_status': 'ACTIVE',
                'timestamp': datetime.now().isoformat()
            }
            
            ml_status_file = Path('data/monitor/ml_status.json')
            ml_status_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(ml_status_file, 'w') as f:
                    json.dump(ml_status, f)
            except:
                pass
            
            return {
                'signal': int(final_pred),  # -1: SELL, 0: HOLD, 1: BUY
                'confidence': float(confidence),
                'context_pred': context_pred,
                'micro_pred': micro_pred,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Erro na predição híbrida: {e}")
            return None
    
    def make_hmarl_prediction(self):
        """Faz predição usando HMARL com dados reais do mercado"""
        try:
            # Alimentar apenas dados novos (incremental)
            # Usar apenas o último trade para atualização incremental
            if len(self.tick_buffer) > 0:
                # Pegar apenas o último trade (mais recente)
                last_trade = self.tick_buffer[-1]
                if last_trade.get('price') and last_trade.get('volume'):
                    self.hmarl_agents.update_market_data(
                        price=last_trade['price'],
                        volume=last_trade['volume']
                    )
            
            if len(self.book_buffer) > 0:
                # Pegar apenas o último book (incremental)
                last_book = self.book_buffer[-1]
                # Calcular métricas do book
                book_metrics = {
                    'spread': last_book.get('spread', 0.5),
                    'imbalance': last_book.get('imbalance', 0),
                    'bid_volume_total': last_book.get('total_bid_vol', 0),
                    'ask_volume_total': last_book.get('total_ask_vol', 0)
                }
                self.hmarl_agents.update_market_data(book_data=book_metrics)
            
            # Obter consenso dos agentes
            consensus = self.hmarl_agents.get_consensus()
            
            # Enviar dados para o monitor via bridge
            try:
                self.monitor_bridge.write_hmarl_data(consensus)
            except Exception as e:
                logger.debug(f"Erro ao enviar dados para monitor: {e}")
            
            self.stats['hmarl_predictions'] += 1
            
            return consensus
            
        except Exception as e:
            logger.error(f"Erro na predição HMARL: {e}")
            return None
    
    def _training_scheduler(self):
        """Agendador de re-treinamento diário inteligente após fechamento do mercado com shutdown automático"""
        while self.running:
            try:
                now = datetime.now()
                training_time = dt_time(18, 40)  # 18:40 - Após fechamento do mercado
                
                if now.time() >= training_time and self.last_training_date != now.date():
                    logger.info("="*60)
                    logger.info("Iniciando re-treinamento pós-mercado...")
                    logger.info(f"Horário: {now.strftime('%H:%M:%S')}")
                    logger.info("="*60)
                    
                    # Importar sistema de re-treinamento
                    try:
                        from src.training.smart_retraining_system import SmartRetrainingSystem
                        
                        # Criar instância do retrainer com requisitos atualizados
                        retrainer = SmartRetrainingSystem(
                            data_dir="data/book_tick_data",
                            models_dir="models",
                            min_samples=5000,  # Mínimo de 5000 amostras
                            min_hours=8.0,     # Mínimo de 8 horas de dados do mercado
                            max_gap_minutes=5  # Máximo de 5 minutos de gap
                        )
                        
                        # Executar pipeline de re-treinamento
                        results = retrainer.run_retraining_pipeline(force=False)
                        
                        if results:
                            logger.info(f"✅ Re-treinamento concluído com sucesso!")
                            logger.info(f"  - Accuracy: {results['accuracy']:.2%}")
                            logger.info(f"  - Amostras usadas: {results['samples_used']}")
                            logger.info(f"  - Modelos salvos: {results['model_path']}")
                            
                            # Recarregar os novos modelos automaticamente
                            print("\n[*] Recarregando modelos após re-treinamento bem-sucedido...")
                            self.load_hybrid_models()
                            print("[✓] Modelos atualizados e em uso!")
                            
                            self.last_training_date = now.date()
                        else:
                            logger.warning("Re-treinamento não foi possível - dados insuficientes ou fragmentados")
                            
                    except ImportError as e:
                        logger.error(f"Erro ao importar sistema de re-treinamento: {e}")
                    except Exception as e:
                        logger.error(f"Erro durante re-treinamento: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    logger.info("="*60)
                    
                    # SHUTDOWN AUTOMÁTICO APÓS RE-TREINAMENTO
                    logger.info("\n" + "="*60)
                    logger.info("SHUTDOWN AUTOMÁTICO PÓS RE-TREINAMENTO")
                    logger.info("="*60)
                    logger.info("Re-treinamento finalizado. Iniciando shutdown do sistema...")
                    logger.info(f"Horário: {datetime.now().strftime('%H:%M:%S')}")
                    logger.info("="*60)
                    
                    # Aguardar 5 segundos antes de desligar
                    time.sleep(5)
                    
                    # Parar o sistema
                    self.running = False
                    self.stop()
                    
                    # Forçar saída do loop
                    break
                    
                time.sleep(300)  # Verificar a cada 5 minutos
            except Exception as e:
                logger.error(f"Erro no scheduler de treinamento: {e}")
                time.sleep(300)
    
    def run(self):
        """Loop principal do sistema"""
        self.running = True
        print("\n[SISTEMA ATIVO] Trading HÍBRIDO com dados REAIS da B3")
        print("Modelos: 3-Layer ML + HMARL | Re-treinamento: 18:30")
        print("Pressione Ctrl+C para parar\n")
        
        iteration = 0
        last_status_time = time.time()
        last_prediction_time = time.time()
        last_save_time = time.time()
        
        try:
            while self.running:
                iteration += 1
                
                # Obter dados do mercado
                status = self.connection.get_status()
                
                # Processar book se disponível
                if status.get('last_book') and status['last_book'].get('timestamp'):
                    self._process_book(status['last_book'])
                    
                    # Atualizar ordens ativas com novo preço
                    self.update_active_orders()
                    
                    # Adicionar como trade também (simplificado)
                    trade_data = {
                        'timestamp': status['last_book'].get('timestamp'),
                        'price': status['last_book'].get('mid_price', 0),
                        'volume': status['last_book'].get('volume_at_best', 0),
                        'aggressor': 0,
                        'side': ''
                    }
                    self._process_trade(trade_data)
                
                # Fazer predições a cada 1 segundo
                if time.time() - last_prediction_time > 1.0 and len(self.tick_buffer) > 50:
                    # Predição híbrida ML
                    ml_prediction = self.make_hybrid_prediction()
                    
                    # Adicionar log de debug para ML
                    if ml_prediction:
                        logger.debug(
                            f"[ML DEBUG] Signal: {ml_prediction.get('signal')} | "
                            f"Confidence: {ml_prediction.get('confidence', 0):.3f}"
                        )
                        
                        if ml_prediction['confidence'] >= self.min_confidence:
                            signal_map = {-1: 'SELL', 0: 'HOLD', 1: 'BUY'}
                            signal = signal_map[ml_prediction['signal']]
                            
                            if ml_prediction['signal'] != 0:  # Não é HOLD
                                logger.info(
                                    f"[SINAL ML HÍBRIDO] {signal} | "
                                    f"Conf: {ml_prediction['confidence']:.1%} | "
                                    f"Context: {ml_prediction['context_pred']} | "
                                    f"Micro: {ml_prediction['micro_pred']}"
                                )
                    else:
                        logger.debug("[ML DEBUG] Sem predição ML disponível")
                    
                    # Predição HMARL real-time
                    hmarl_prediction = self.make_hmarl_prediction()
                    
                    if hmarl_prediction and hmarl_prediction['confidence'] >= 0.5:
                        logger.info(
                            f"[SINAL HMARL] {hmarl_prediction['action']} | "
                            f"Signal: {hmarl_prediction['signal']:.3f} | "
                            f"Conf: {hmarl_prediction['confidence']:.1%}"
                        )
                        
                        # Log dos agentes individuais
                        agent_signals = self.hmarl_agents.get_agent_signals()
                        for agent_name, agent_data in agent_signals.items():
                            if agent_data['confidence'] > 0.6:
                                logger.debug(
                                    f"  {agent_name}: {agent_data['signal']} "
                                    f"(strength: {agent_data['strength']:.2f}, "
                                    f"conf: {agent_data['confidence']:.2f})"
                                )
                    
                    # Combinar sinais para decisão final
                    executed_trade = False
                    
                    # 1. Primeiro tenta consenso ML+HMARL
                    if ml_prediction and hmarl_prediction:
                        # Consenso entre ML e HMARL
                        ml_signal = ml_prediction['signal']
                        hmarl_signal = 1 if hmarl_prediction['signal'] > 0.3 else (-1 if hmarl_prediction['signal'] < -0.3 else 0)
                        
                        if ml_signal == hmarl_signal and ml_signal != 0:
                            # Ambos concordam
                            final_confidence = (ml_prediction['confidence'] * 0.4 + hmarl_prediction['confidence'] * 0.6)
                            
                            if final_confidence >= self.min_confidence:
                                action = 'BUY' if ml_signal > 0 else 'SELL'
                                logger.info(
                                    f"[CONSENSO ML+HMARL] {action} | "
                                    f"Confiança: {final_confidence:.1%} | "
                                    f"Ambos concordam"
                                )
                                
                                # Executar trade com stop e take
                                self.execute_trade_with_risk_management(
                                    side=OrderSide.BUY if ml_signal > 0 else OrderSide.SELL,
                                    confidence=final_confidence
                                )
                                executed_trade = True
                    
                    # 2. Se não houve consenso, usa HMARL sozinho se confiança alta
                    if not executed_trade and hmarl_prediction:
                        hmarl_signal = hmarl_prediction['signal']
                        hmarl_conf = hmarl_prediction['confidence']
                        
                        # HMARL forte: signal > 0.5 ou < -0.5 E confidence > 65%
                        if (abs(hmarl_signal) > 0.5 and hmarl_conf > 0.65):
                            action = 'BUY' if hmarl_signal > 0 else 'SELL'
                            logger.info(
                                f"[SINAL HMARL FORTE] {action} | "
                                f"Signal: {hmarl_signal:.3f} | "
                                f"Confiança: {hmarl_conf:.1%} | "
                                f"Executando só com HMARL"
                            )
                            
                            # Executar com confidence reduzida (só HMARL)
                            self.execute_trade_with_risk_management(
                                side=OrderSide.BUY if hmarl_signal > 0 else OrderSide.SELL,
                                confidence=hmarl_conf * 0.8  # Reduz 20% por ser só HMARL
                            )
                            executed_trade = True
                    
                    # 3. Se não houve trade e ML tem sinal muito forte
                    if not executed_trade and ml_prediction:
                        if ml_prediction['confidence'] >= 0.75 and ml_prediction['signal'] != 0:
                            action = 'BUY' if ml_prediction['signal'] > 0 else 'SELL'
                            logger.info(
                                f"[SINAL ML FORTE] {action} | "
                                f"Confiança: {ml_prediction['confidence']:.1%} | "
                                f"Executando só com ML"
                            )
                            
                            self.execute_trade_with_risk_management(
                                side=OrderSide.BUY if ml_prediction['signal'] > 0 else OrderSide.SELL,
                                confidence=ml_prediction['confidence'] * 0.8  # Reduz 20% por ser só ML
                            )
                    
                    last_prediction_time = time.time()
                
                # Status a cada 10 segundos
                if time.time() - last_status_time > 10:
                    uptime = int(time.time() - self.stats['start_time'])
                    callbacks_total = self.stats['callbacks_received']
                    
                    # Mostrar status
                    print(f"\r[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Callbacks: {callbacks_total} | "
                          f"ML: {self.stats['hybrid_predictions']} | "
                          f"HMARL: {self.stats['hmarl_predictions']} | "
                          f"Trades: {self.stats['trades_executed']} | "
                          f"Data: {self.record_count['book'] + self.record_count['tick']} | "
                          f"Up: {uptime}s", end='')
                    last_status_time = time.time()
                
                # Salvar dados a cada 30 segundos
                if self.enable_recording and time.time() - last_save_time > 30:
                    self._save_buffers()
                    last_save_time = time.time()
                
                time.sleep(0.1)  # 100ms
                
        except KeyboardInterrupt:
            print("\n\n[INFO] Parada solicitada pelo usuário")
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
            import traceback
            traceback.print_exc()
    
    def _process_book(self, book_data):
        """Processa dados do book"""
        try:
            # Atualizar risk manager com novos dados
            if hasattr(self, 'risk_manager') and book_data.get('mid_price'):
                self.risk_manager.update_buffers(
                    price=book_data['mid_price'],
                    volume=book_data.get('total_volume', 0)
                )
            
            # Calcular métricas do book
            book_metrics = {}
            
            # Se tem dados de bid/ask
            if book_data.get('bids') and book_data.get('asks'):
                bids = book_data['bids']
                asks = book_data['asks']
                
                if len(bids) > 0 and len(asks) > 0:
                    bid_price = bids[0].get('price', 0)
                    ask_price = asks[0].get('price', 0)
                    
                    if bid_price > 0 and ask_price > 0:
                        book_metrics['spread'] = ask_price - bid_price
                        book_metrics['mid_price'] = (bid_price + ask_price) / 2
                        
                        # Atualizar preço atual para gestão de ordens
                        self.current_price = book_metrics['mid_price']
                        self.last_mid_price = self.current_price
                        
                        # Volumes totais
                        bid_vol_total = sum(b.get('volume', 0) for b in bids[:5])
                        ask_vol_total = sum(a.get('volume', 0) for a in asks[:5])
                        
                        book_metrics['total_bid_vol'] = bid_vol_total
                        book_metrics['total_ask_vol'] = ask_vol_total
                        
                        # Imbalance
                        if bid_vol_total + ask_vol_total > 0:
                            book_metrics['imbalance'] = (bid_vol_total - ask_vol_total) / (bid_vol_total + ask_vol_total)
                        else:
                            book_metrics['imbalance'] = 0
                        
                        # Volume at best
                        book_metrics['volume_at_best'] = bids[0].get('volume', 0) + asks[0].get('volume', 0)
                        
                        # Book pressure
                        book_metrics['book_pressure'] = bid_vol_total / (bid_vol_total + ask_vol_total) if (bid_vol_total + ask_vol_total) > 0 else 0.5
            
            # Adicionar métricas ao book_data
            book_data.update(book_metrics)
            
            # Adicionar ao buffer
            self.book_buffer.append(book_data)
            self.stats['callbacks_received'] += 1
            
            # Alimentar HMARL em tempo real se temos métricas
            if book_metrics:
                hmarl_book_data = {
                    'spread': book_metrics.get('spread', 0.5),
                    'imbalance': book_metrics.get('imbalance', 0),
                    'bid_volume_total': book_metrics.get('total_bid_vol', 0),
                    'ask_volume_total': book_metrics.get('total_ask_vol', 0)
                }
                self.hmarl_agents.update_market_data(book_data=hmarl_book_data)
            
            # Gravar se habilitado
            if self.enable_recording and self.data_files.get('book'):
                with self.data_lock:
                    self._write_book_record(book_data)
                    
        except Exception as e:
            logger.error(f"Erro ao processar book: {e}")
    
    def _process_trade(self, trade_data):
        """Processa dados de trade"""
        try:
            # Adicionar ao buffer
            self.tick_buffer.append(trade_data)
            self.price_history.append(trade_data.get('price', 0))
            
            # Alimentar HMARL em tempo real (incremental)
            if trade_data.get('price') and trade_data.get('volume'):
                self.hmarl_agents.update_market_data(
                    price=trade_data['price'],
                    volume=trade_data['volume']
                )
            
            # Gravar se habilitado
            if self.enable_recording and self.data_files.get('tick'):
                with self.data_lock:
                    self._write_tick_record(trade_data)
                    
        except Exception as e:
            logger.error(f"Erro ao processar trade: {e}")
    
    def _write_book_record(self, book):
        """Grava registro de book"""
        try:
            with open(self.data_files['book'], 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    book.get('timestamp', datetime.now()),
                    self.symbol,
                    book.get('bid_price_1', 0), book.get('bid_vol_1', 0),
                    0, 0, 0, 0, 0, 0, 0, 0,  # Níveis 2-5 (simplificado)
                    book.get('ask_price_1', 0), book.get('ask_vol_1', 0),
                    0, 0, 0, 0, 0, 0, 0, 0,  # Níveis 2-5 (simplificado)
                    book.get('spread', 0),
                    book.get('mid_price', 0),
                    book.get('imbalance', 0),
                    book.get('total_bid_vol', 0),
                    book.get('total_ask_vol', 0)
                ])
            self.record_count['book'] += 1
        except:
            pass
    
    def _write_tick_record(self, trade):
        """Grava registro de trade"""
        try:
            with open(self.data_files['tick'], 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    trade.get('timestamp', datetime.now()),
                    self.symbol,
                    trade.get('price', 0),
                    trade.get('volume', 0),
                    trade.get('side', ''),
                    trade.get('aggressor', 0)
                ])
            self.record_count['tick'] += 1
        except:
            pass
    
    def execute_trade_with_risk_management(self, side: OrderSide, confidence: float):
        """Executa trade com stop loss e take profit adequados para WDO"""
        try:
            # Verificar se temos preço atual válido
            if self.current_price <= 0:
                logger.warning("Preço atual inválido, não pode executar trade")
                return
            
            # Verificar posição real via API
            if hasattr(self.connection, 'get_position'):
                position = self.connection.get_position(self.symbol)
                if position != 0:
                    logger.info(f"[POSIÇÃO EXISTENTE] {position} contratos em posição. Aguardando fechamento...")
                    return
            
            # Verificar flag de controle de posição
            if self.has_open_position:
                logger.info("[CONTROLE] Já existe operação em andamento, aguardando...")
                return
            
            # Verificar se já temos ordens ativas no manager
            if len(self.order_manager.active_orders) > 0:
                logger.info("Já existem ordens ativas, aguardando fechamento")
                return
            
            # Usar gestão de risco adaptativa se ativada
            if self.use_adaptive_risk:
                # Atualizar buffers do risk manager com dados recentes
                if hasattr(self, 'last_book') and self.last_book:
                    # Usar spread como proxy para volatilidade instantânea
                    if 'bids' in self.last_book and 'asks' in self.last_book:
                        if self.last_book['bids'] and self.last_book['asks']:
                            bid = self.last_book['bids'][0]['price']
                            ask = self.last_book['asks'][0]['price']
                            spread = ask - bid
                            # Estimar high/low baseado no spread
                            self.risk_manager.update_buffers(
                                price=self.current_price,
                                high=self.current_price + spread * 2,
                                low=self.current_price - spread * 2,
                                volume=self.last_book.get('total_volume', 1000)
                            )
                else:
                    # Atualizar apenas com preço
                    self.risk_manager.update_buffers(price=self.current_price)
                
                # Calcular níveis adaptativos
                risk_levels = self.risk_manager.calculate_adaptive_levels(
                    entry_price=self.current_price,
                    side='BUY' if side == OrderSide.BUY else 'SELL',
                    confidence=confidence
                )
                
                # Verificar se deve operar
                if not self.risk_manager.should_trade(risk_levels):
                    logger.warning("Condições de mercado desfavoráveis, pulando trade")
                    return
                
                # Usar níveis calculados
                stop_points = risk_levels['stop_points']
                take_points = risk_levels['take_points']
                
                logger.info(f"[RISCO ADAPTATIVO] Regime: {risk_levels['volatility_regime']}, "
                           f"Fase: {risk_levels['market_phase']}, ATR: {risk_levels['atr']:.1f}")
                
            else:
                # Fallback: estratégia fixa otimizada para mercado lateral
                if confidence >= 0.70:
                    # Alta confiança: pode arriscar um pouco mais
                    stop_points = 5.0   # 5 pontos fixo
                    take_points = 8.0   # 8 pontos fixo (1:1.6)
                else:
                    # Confiança normal: conservador
                    stop_points = 5.0   # 5 pontos fixo
                    take_points = 7.0   # 7 pontos fixo (1:1.4)
            
            # Criar ordem
            order = self.order_manager.create_order(
                symbol=self.symbol,
                side=side,
                quantity=1,  # Começar com 1 contrato
                entry_price=self.current_price,
                stop_points=stop_points,
                take_points=take_points,
                confidence=confidence,
                is_simulated=(not self.enable_trading)  # Marcar como simulada se trading desabilitado
            )
            
            # Log detalhado
            logger.info("=" * 60)
            logger.info("ORDEM EXECUTADA COM GESTÃO DE RISCO")
            logger.info("=" * 60)
            logger.info(f"Símbolo: {self.symbol}")
            logger.info(f"Lado: {side.value}")
            logger.info(f"Quantidade: {order.quantity} contrato(s)")
            logger.info(f"Preço Entrada: {order.entry_price:.1f}")
            logger.info(f"Stop Loss: {order.stop_loss:.1f} ({stop_points:.1f} pontos)")
            logger.info(f"Take Profit: {order.take_profit:.1f} ({take_points:.1f} pontos)")
            logger.info(f"Risco: R$ {stop_points * 10:.2f}")
            logger.info(f"Retorno: R$ {take_points * 10:.2f}")
            logger.info(f"Risk:Reward: 1:{take_points/stop_points:.2f}")
            logger.info(f"Confiança: {confidence:.1%}")
            logger.info("=" * 60)
            
            if self.enable_trading:
                # Verificar conexão antes de enviar (market ou broker)
                status = self.connection.get_status()
                if not (status['market'] or status['broker']):
                    logger.warning("[AVISO] Sem conexão com market ou broker - ordem não será enviada")
                    logger.info("  Verifique a conexão no ProfitChart")
                    order.status = OrderStatus.REJECTED
                else:
                    if not status['broker']:
                        logger.info("[INFO] Broker não conectado, enviando via market apenas")
                    # Enviar ordem real via ProfitDLL com OCO (stop/take automático)
                    # Converter OrderSide enum para string
                    side_str = "BUY" if side == OrderSide.BUY else "SELL"
                    
                    # Verificar se temos o ConnectionManagerOCO
                    if hasattr(self.connection, 'send_order_with_bracket'):
                        # Usar ordens OCO com stop e take automáticos
                        logger.info("[OCO] Enviando ordem com stop/take automático")
                        result = self.connection.send_order_with_bracket(
                            symbol=self.symbol,
                            side=side_str,
                            quantity=order.quantity,
                            entry_price=order.entry_price,
                            stop_price=order.stop_loss,
                            take_price=order.take_profit
                        )
                        
                        if result and 'main_order' in result:
                            logger.info(f"[REAL] Ordem OCO enviada com sucesso!")
                            logger.info(f"  Principal: {result.get('main_order')}")
                            logger.info(f"  Stop Loss: {result.get('stop_order')} @ {order.stop_loss:.1f}")
                            logger.info(f"  Take Profit: {result.get('take_order')} @ {order.take_profit:.1f}")
                            order.profit_id = result['main_order']
                            order.status = OrderStatus.OPEN
                        else:
                            logger.error(f"[ERRO] Falha ao enviar ordem OCO")
                            order.status = OrderStatus.REJECTED
                    else:
                        # Fallback: ordem simples sem OCO
                        logger.info("[SIMPLES] Enviando ordem sem OCO (stop/take manual)")
                        result = self.connection.send_order(
                            symbol=self.symbol,
                            side=side_str,
                            order_type="LIMIT",  # Usar ordem limitada com preço
                            quantity=order.quantity,
                            price=order.entry_price
                        )
                        
                        if result > 0:
                            logger.info(f"[REAL] Ordem simples enviada! OrderID: {result}")
                            logger.info(f"  ATENÇÃO: Stop/Take serão monitorados manualmente")
                            order.profit_id = result
                            order.status = OrderStatus.OPEN
                        else:
                            logger.error(f"[ERRO] Falha ao enviar ordem. Código: {result}")
                            order.status = OrderStatus.REJECTED
            else:
                logger.info("[SIMULAÇÃO] Ordem registrada em modo simulação")
            
            self.stats['trades_executed'] += 1
            
        except Exception as e:
            logger.error(f"Erro ao executar trade: {e}")
    
    def update_active_orders(self):
        """Atualiza status das ordens ativas com preço atual"""
        if self.current_price <= 0:
            return
        
        for order_id, order in list(self.order_manager.active_orders.items()):
            if order.is_active():
                # Verificar stop/take
                result = self.order_manager.update_order_price(order, self.current_price)
                
                if result:
                    # Ordem foi fechada
                    if result == 'STOP_LOSS':
                        loss = abs(order.stop_loss - order.entry_price) * order.quantity * 10
                        logger.warning(f"[STOP LOSS] Perda: R$ {loss:.2f}")
                    elif result == 'TAKE_PROFIT':
                        profit = abs(order.take_profit - order.entry_price) * order.quantity * 10
                        logger.info(f"[TAKE PROFIT] Lucro: R$ {profit:.2f}")
                    
                    # Mover para histórico
                    self.order_manager.order_history.append(order)
                    del self.order_manager.active_orders[order_id]
                    
                # Aplicar trailing stop se em lucro
                elif order.side == OrderSide.BUY:
                    if self.current_price > order.entry_price + 3:  # 3 pontos de lucro
                        self.order_manager.apply_trailing_stop(order, self.current_price, trailing_points=3)
                elif order.side == OrderSide.SELL:
                    if self.current_price < order.entry_price - 3:  # 3 pontos de lucro
                        self.order_manager.apply_trailing_stop(order, self.current_price, trailing_points=3)
    
    def _save_buffers(self):
        """Salva buffers periodicamente"""
        # Implementação simplificada
        pass
    
    def stop(self):
        """Para o sistema"""
        print("\n[INFO] Parando sistema...")
        self.running = False
        
        # Fechar conexão
        if self.connection:
            self.connection.disconnect()
        
        # Parar monitor
        if self.monitor_process:
            self.monitor_process.terminate()
        
        # Estatísticas finais
        uptime = int(time.time() - self.stats['start_time'])
        print(f"\n[ESTATÍSTICAS FINAIS]")
        print(f"  Uptime: {uptime}s")
        print(f"  Predições ML Híbridas: {self.stats['hybrid_predictions']}")
        print(f"  Predições HMARL: {self.stats['hmarl_predictions']}")
        print(f"  Trades Executados: {self.stats['trades_executed']}")
        print(f"  Callbacks: {self.stats['callbacks_received']}")
        print(f"  Dados Gravados: {self.record_count}")
        
        print("\n[OK] Sistema parado com sucesso")


def main():
    """Função principal"""
    # Configurar sinais
    def signal_handler(sig, frame):
        print("\n[!] Sinal de parada recebido...")
        if trader:
            trader.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Criar e inicializar sistema
    trader = QuantumTraderHybridComplete()
    
    if trader.initialize():
        trader.run()
    else:
        print("\n[ERRO] Falha na inicialização")
        sys.exit(1)


if __name__ == "__main__":
    main()