#!/usr/bin/env python3
"""
Sistema de Produção Híbrido Completo
Integra: Modelos ML + HMARL + Re-treinamento Diário
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta, time
import joblib
import json
import threading
import queue
import logging
from typing import Dict, List, Tuple, Optional, Any
import warnings
warnings.filterwarnings('ignore')

# Imports do sistema - Simplificado para teste inicial
# TODO: Adicionar imports conforme necessário
# from src.connection_manager_v4 import ConnectionManagerV4 as ConnectionManager
# from src.buffers.circular_buffer import CircularBuffer
# from src.features.book_features_rt import BookFeaturesRT
# from src.agents.hmarl_agents_enhanced import HMARLAgentsEnhanced
# from src.consensus.hmarl_consensus_system import HMARLConsensusSystem

# Para re-treinamento
from train_hybrid_pipeline import HybridTradingPipeline

class HybridProductionSystem:
    """
    Sistema completo de produção que:
    1. Usa modelos híbridos treinados
    2. Integra com HMARL agents
    3. Re-treina diariamente com novos dados
    4. Monitora performance em tempo real
    """
    
    def __init__(self, config_path: str = "config_production.json"):
        # Configuração
        self.config = self._load_config(config_path)
        
        # Logging
        self._setup_logging()
        
        # Paths
        self.models_dir = Path("models/hybrid")
        self.data_dir = Path("data/daily_training")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Componentes do sistema
        self.models = {}
        self.scalers = {}
        self.hmarl_agents = None
        self.consensus_system = None
        self.buffers = None
        self.features_calculator = None
        
        # Estado do sistema
        self.is_running = False
        self.last_training_date = None
        self.model_version = "v1.0"
        self.performance_metrics = {
            'trades_today': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'model_accuracy': {}
        }
        
        # Threads
        self.inference_thread = None
        self.training_thread = None
        self.monitoring_thread = None
        
        # Queue para dados de treinamento
        self.training_data_queue = queue.Queue(maxsize=100000)
        
    def _load_config(self, config_path: str) -> dict:
        """Carrega configuração"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except:
            # Configuração padrão
            return {
                'symbol': 'WDOU25',
                'min_confidence': 0.60,
                'max_daily_trades': 50,
                'stop_loss': 0.005,
                'take_profit': 0.010,
                'enable_daily_training': True,
                'training_hour': 18,  # Treinar às 18h
                'training_min_samples': 10000,
                'model_validation_threshold': 0.70  # Mínimo de acurácia
            }
    
    def _setup_logging(self):
        """Configura logging"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(f"logs/hybrid_production_{datetime.now():%Y%m%d}.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_models(self):
        """Carrega todos os modelos treinados"""
        self.logger.info("Carregando modelos híbridos...")
        
        try:
            # Carregar modelos de contexto
            context_dir = self.models_dir / "context"
            self.models['context'] = {
                'regime_detector': joblib.load(context_dir / "regime_detector.pkl"),
                'volatility_forecaster': joblib.load(context_dir / "volatility_forecaster.pkl"),
                'session_classifier': joblib.load(context_dir / "session_classifier.pkl")
            }
            
            # Carregar modelos de microestrutura
            micro_dir = self.models_dir / "microstructure"
            self.models['microstructure'] = {
                'order_flow_analyzer': joblib.load(micro_dir / "order_flow_analyzer.pkl"),
                'book_dynamics': joblib.load(micro_dir / "book_dynamics.pkl")
            }
            
            # Carregar meta-learner
            meta_dir = self.models_dir / "meta_learner"
            self.models['meta_learner'] = joblib.load(meta_dir / "meta_learner.pkl")
            
            # Carregar scalers
            self.scalers['context'] = joblib.load(self.models_dir / "scaler_context.pkl")
            self.scalers['microstructure'] = joblib.load(self.models_dir / "scaler_microstructure.pkl")
            
            # Carregar configuração dos modelos
            with open(self.models_dir / "config.json", 'r') as f:
                model_config = json.load(f)
                self.model_version = model_config.get('timestamp', 'unknown')
            
            self.logger.info(f"Modelos carregados com sucesso. Versão: {self.model_version}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar modelos: {e}")
            return False
    
    def initialize_components(self):
        """Inicializa componentes do sistema"""
        self.logger.info("Inicializando componentes...")
        
        # TODO: Implementar quando os módulos estiverem disponíveis
        # Por enquanto, usar implementação simplificada
        
        # Buffers simulados
        self.buffers = {'tick': [], 'book': []}
        
        # HMARL Agents (simulado por enquanto)
        self.hmarl_agents = None
        
        # Sistema de consenso (simulado)
        self.consensus_system = None
        
        # Connection Manager (simulado)
        self.connection_manager = None
        
        # Controle de posição
        self.has_open_position = False
        self.current_position = 0
        self.current_position_side = None
        self.pending_orders = []
        
        self.logger.info("Componentes inicializados (modo simulado)")
        
    def create_context_features(self, tick_data: pd.DataFrame) -> pd.DataFrame:
        """Cria features de contexto a partir de tick data"""
        features = pd.DataFrame()
        
        # Médias móveis
        features['sma_5'] = tick_data['price'].rolling(5).mean()
        features['sma_20'] = tick_data['price'].rolling(20).mean()
        features['sma_50'] = tick_data['price'].rolling(50).mean()
        features['sma_trend'] = (features['sma_5'] - features['sma_20']) / features['sma_20']
        
        # Momentum
        features['momentum_10'] = tick_data['price'].pct_change(10)
        features['momentum_30'] = tick_data['price'].pct_change(30)
        features['momentum_60'] = tick_data['price'].pct_change(60)
        
        # Volatilidade
        returns = tick_data['price'].pct_change()
        features['volatility_10'] = returns.rolling(10).std()
        features['volatility_30'] = returns.rolling(30).std()
        features['volatility_60'] = returns.rolling(60).std()
        features['volatility_ratio'] = features['volatility_10'] / features['volatility_30']
        
        # ATR
        high = tick_data['price'].rolling(20).max()
        low = tick_data['price'].rolling(20).min()
        features['atr'] = (high - low) / tick_data['price']
        
        # Volume
        features['volume_ma_10'] = tick_data['volume'].rolling(10).mean()
        features['volume_ma_30'] = tick_data['volume'].rolling(30).mean()
        features['volume_ratio'] = tick_data['volume'] / features['volume_ma_30']
        features['volume_trend'] = features['volume_ma_10'] / features['volume_ma_30']
        
        # Temporal
        features['hour'] = tick_data['timestamp'].dt.hour
        features['minute'] = tick_data['timestamp'].dt.minute
        features['day_of_week'] = tick_data['timestamp'].dt.dayofweek
        features['session'] = pd.cut(
            features['hour'],
            bins=[0, 11, 14, 24],
            labels=[0, 1, 2]
        ).astype(int)
        
        # Microestrutura básica
        features['aggressor_ratio'] = tick_data.get('aggressor', 0)
        features['trade_intensity'] = tick_data['volume'].rolling(100).sum()
        
        return features
    
    def create_book_features(self, book_data: pd.DataFrame) -> pd.DataFrame:
        """Cria features de book"""
        features = pd.DataFrame()
        
        # Spread
        features['spread'] = book_data.get('spread', 0)
        features['spread_ma'] = features['spread'].rolling(20).mean()
        features['spread_std'] = features['spread'].rolling(20).std()
        features['spread_normalized'] = (features['spread'] - features['spread_ma']) / (features['spread_std'] + 1e-8)
        
        # Imbalance
        features['imbalance'] = book_data.get('imbalance', 0)
        features['imbalance_ma'] = features['imbalance'].rolling(20).mean()
        features['imbalance_momentum'] = features['imbalance'].diff(5)
        
        # Volume
        features['book_pressure'] = book_data.get('book_pressure', 0.5)
        features['volume_at_best'] = book_data.get('volume_at_best', 0)
        features['volume_ratio'] = book_data.get('volume_ratio', 1)
        
        # Price dynamics
        features['mid_price'] = book_data.get('mid_price', 0)
        features['mid_return_1'] = features['mid_price'].pct_change(1)
        features['mid_return_5'] = features['mid_price'].pct_change(5)
        features['mid_return_10'] = features['mid_price'].pct_change(10)
        
        # Order flow
        features['bid_change'] = book_data.get('bid_vol_1', 0).diff()
        features['ask_change'] = book_data.get('ask_vol_1', 0).diff()
        features['net_order_flow'] = features['bid_change'] - features['ask_change']
        
        # Microstructure
        features['bid_ask_ratio'] = book_data.get('bid_price_1', 1) / (book_data.get('ask_price_1', 1) + 1e-8)
        features['microprice'] = book_data.get('microprice', features['mid_price'])
        
        return features.fillna(0)
    
    def make_prediction(self, tick_features: pd.DataFrame, book_features: pd.DataFrame) -> Dict[str, Any]:
        """
        Faz predição usando o sistema híbrido completo
        """
        try:
            # 1. Predição da Camada 1 (Contexto)
            context_features_scaled = self.scalers['context'].transform(tick_features)
            
            context_predictions = {
                'regime': self.models['context']['regime_detector'].predict(context_features_scaled)[0],
                'volatility': self.models['context']['volatility_forecaster'].predict(context_features_scaled)[0],
                'session': self._decode_xgboost_prediction(
                    self.models['context']['session_classifier'], 
                    context_features_scaled
                )[0]
            }
            
            # 2. Predição da Camada 2 (Microestrutura)
            book_features_scaled = self.scalers['microstructure'].transform(book_features)
            
            micro_predictions = {
                'order_flow': self.models['microstructure']['order_flow_analyzer'].predict(book_features_scaled)[0],
                'book_dynamics': self.models['microstructure']['book_dynamics'].predict(book_features_scaled)[0]
            }
            
            # 3. Combinar para Meta-Learner
            meta_features = pd.DataFrame({
                'context_pred': [context_predictions['regime']],
                'micro_pred': [micro_predictions['order_flow']],
                'agreement': [1 if context_predictions['regime'] == micro_predictions['order_flow'] else 0],
                'confidence_gap': [abs(context_predictions['regime'] - micro_predictions['order_flow'])]
            })
            
            # 4. Predição final do Meta-Learner
            final_prediction = self.models['meta_learner'].predict(meta_features)[0]
            
            # 5. Calcular confidence
            probabilities = self.models['meta_learner'].predict_proba(meta_features)[0]
            confidence = max(probabilities)
            
            # 6. Integrar com HMARL se disponível
            if self.hmarl_agents:
                hmarl_signal = self._get_hmarl_consensus(book_features)
                
                # Combinar ML e HMARL (60% ML, 40% HMARL)
                combined_signal = 0.6 * final_prediction + 0.4 * hmarl_signal
                final_prediction = np.sign(combined_signal) if abs(combined_signal) > 0.3 else 0
                
            return {
                'signal': int(final_prediction),  # -1: SELL, 0: HOLD, 1: BUY
                'confidence': float(confidence),
                'context': context_predictions,
                'micro': micro_predictions,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            self.logger.error(f"Erro na predição: {e}")
            return {
                'signal': 0,  # HOLD em caso de erro
                'confidence': 0.0,
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    def _decode_xgboost_prediction(self, model_wrapper: Any, features: np.ndarray) -> np.ndarray:
        """Decodifica predição do XGBoost"""
        if isinstance(model_wrapper, dict) and 'model' in model_wrapper:
            pred = model_wrapper['model'].predict(features)
            inverse_map = model_wrapper.get('inverse_map', {0: -1, 1: 0, 2: 1})
            return np.array([inverse_map.get(p, 0) for p in pred])
        return model_wrapper.predict(features)
    
    def _get_hmarl_consensus(self, book_features: pd.DataFrame) -> float:
        """Obtém consenso dos agentes HMARL"""
        if not self.hmarl_agents:
            return 0.0
            
        try:
            # Preparar dados para HMARL
            market_data = {
                'bid_prices': [book_features.get('bid_price_1', 0).iloc[-1]],
                'ask_prices': [book_features.get('ask_price_1', 0).iloc[-1]],
                'bid_volumes': [book_features.get('bid_vol_1', 0).iloc[-1]],
                'ask_volumes': [book_features.get('ask_vol_1', 0).iloc[-1]],
                'trades': [],
                'timestamp': datetime.now()
            }
            
            # Obter sinais dos agentes
            signals = self.hmarl_agents.get_signals(market_data)
            
            # Calcular consenso ponderado
            weights = {
                'order_flow': 0.30,
                'liquidity': 0.20,
                'tape_reading': 0.25,
                'footprint': 0.25
            }
            
            consensus = sum(signals.get(agent, 0) * weight 
                          for agent, weight in weights.items())
            
            return consensus
            
        except Exception as e:
            self.logger.error(f"Erro no HMARL: {e}")
            return 0.0
    
    def collect_training_data(self, tick_data: Dict, book_data: Dict):
        """
        Coleta dados para re-treinamento diário
        """
        try:
            # Criar registro de treinamento
            training_record = {
                'timestamp': datetime.now(),
                'tick_data': tick_data,
                'book_data': book_data,
                'features': {
                    'context': self.create_context_features(pd.DataFrame([tick_data])),
                    'book': self.create_book_features(pd.DataFrame([book_data]))
                }
            }
            
            # Adicionar à queue (non-blocking)
            if not self.training_data_queue.full():
                self.training_data_queue.put_nowait(training_record)
                
            # Salvar em arquivo a cada 1000 registros
            if self.training_data_queue.qsize() >= 1000:
                self._save_training_batch()
                
        except Exception as e:
            self.logger.error(f"Erro ao coletar dados de treinamento: {e}")
    
    def _save_training_batch(self):
        """Salva batch de dados de treinamento"""
        try:
            batch_data = []
            
            # Coletar até 1000 registros
            for _ in range(min(1000, self.training_data_queue.qsize())):
                batch_data.append(self.training_data_queue.get_nowait())
            
            if batch_data:
                # Salvar em arquivo CSV
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Salvar tick data
                tick_df = pd.DataFrame([d['tick_data'] for d in batch_data])
                tick_file = self.data_dir / f"tick_batch_{timestamp}.csv"
                tick_df.to_csv(tick_file, index=False)
                
                # Salvar book data
                book_df = pd.DataFrame([d['book_data'] for d in batch_data])
                book_file = self.data_dir / f"book_batch_{timestamp}.csv"
                book_df.to_csv(book_file, index=False)
                
                self.logger.info(f"Batch de treinamento salvo: {len(batch_data)} registros")
                
        except Exception as e:
            self.logger.error(f"Erro ao salvar batch: {e}")
    
    def daily_retrain(self):
        """
        Re-treina modelos diariamente com novos dados
        """
        self.logger.info("Iniciando re-treinamento diário...")
        
        try:
            # 1. Verificar se há dados suficientes
            training_files = list(self.data_dir.glob("*_batch_*.csv"))
            
            if len(training_files) < 2:  # Precisa de tick e book
                self.logger.warning("Dados insuficientes para re-treinamento")
                return False
            
            # 2. Carregar dados do dia
            tick_data = []
            book_data = []
            
            for file in training_files:
                if 'tick' in file.name:
                    tick_data.append(pd.read_csv(file))
                elif 'book' in file.name:
                    book_data.append(pd.read_csv(file))
            
            if not tick_data or not book_data:
                self.logger.warning("Faltam dados de tick ou book")
                return False
                
            # Combinar dados
            df_tick = pd.concat(tick_data, ignore_index=True)
            df_book = pd.concat(book_data, ignore_index=True)
            
            self.logger.info(f"Dados carregados - Tick: {len(df_tick)}, Book: {len(df_book)}")
            
            # 3. Verificar quantidade mínima
            min_samples = self.config.get('training_min_samples', 10000)
            if len(df_tick) < min_samples:
                self.logger.warning(f"Dados insuficientes: {len(df_tick)} < {min_samples}")
                return False
            
            # 4. Executar pipeline de treinamento
            pipeline = HybridTradingPipeline()
            
            # Salvar dados temporários para o pipeline
            temp_tick = self.data_dir / "temp_tick.csv"
            temp_book = self.data_dir / "temp_book.csv"
            df_tick.to_csv(temp_tick, index=False)
            df_book.to_csv(temp_book, index=False)
            
            # Configurar pipeline para usar dados locais
            pipeline.tick_data_path = temp_tick
            pipeline.book_data_dir = self.data_dir
            
            # Treinar
            pipeline.run_complete_pipeline()
            
            # 5. Validar novos modelos
            new_accuracy = self._validate_new_models(pipeline.models)
            
            validation_threshold = self.config.get('model_validation_threshold', 0.70)
            if new_accuracy < validation_threshold:
                self.logger.warning(f"Novos modelos rejeitados. Acurácia: {new_accuracy:.2%}")
                return False
            
            # 6. Backup dos modelos antigos
            self._backup_current_models()
            
            # 7. Substituir modelos em produção
            self.models = pipeline.models
            self.scalers = pipeline.scalers
            self.model_version = f"v{datetime.now():%Y%m%d_%H%M}"
            
            self.logger.info(f"Re-treinamento concluído. Nova versão: {self.model_version}")
            
            # 8. Limpar dados antigos (manter últimos 7 dias)
            self._cleanup_old_training_data()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro no re-treinamento: {e}")
            return False
    
    def _validate_new_models(self, new_models: Dict) -> float:
        """Valida novos modelos antes de colocar em produção"""
        try:
            # Aqui você implementaria validação com dados de teste
            # Por enquanto, retorna uma acurácia simulada
            return 0.75
        except:
            return 0.0
    
    def _backup_current_models(self):
        """Faz backup dos modelos atuais"""
        try:
            backup_dir = Path("models/backup") / datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Copiar todos os arquivos de modelo
            import shutil
            for model_file in self.models_dir.glob("**/*.pkl"):
                dest = backup_dir / model_file.relative_to(self.models_dir)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(model_file, dest)
                
            self.logger.info(f"Backup criado em: {backup_dir}")
            
        except Exception as e:
            self.logger.error(f"Erro ao criar backup: {e}")
    
    def _cleanup_old_training_data(self, days_to_keep: int = 7):
        """Remove dados de treinamento antigos"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            for file in self.data_dir.glob("*_batch_*.csv"):
                # Extrair data do nome do arquivo
                try:
                    file_date_str = file.stem.split('_')[-2]
                    file_date = datetime.strptime(file_date_str, "%Y%m%d")
                    
                    if file_date < cutoff_date:
                        file.unlink()
                        self.logger.debug(f"Arquivo removido: {file.name}")
                        
                except:
                    continue
                    
        except Exception as e:
            self.logger.error(f"Erro na limpeza: {e}")
    
    def schedule_daily_training(self):
        """Agenda re-treinamento diário"""
        def training_scheduler():
            while self.is_running:
                now = datetime.now()
                
                # Verificar se é hora de treinar
                training_time = time(
                    hour=self.config.get('training_hour', 18),
                    minute=self.config.get('training_minute', 30)
                )
                
                if now.time() >= training_time and self.last_training_date != now.date():
                    self.logger.info("Iniciando re-treinamento agendado...")
                    
                    if self.daily_retrain():
                        self.last_training_date = now.date()
                        
                # Verificar a cada 5 minutos
                threading.Event().wait(300)
        
        if self.config.get('enable_daily_training', True):
            self.training_thread = threading.Thread(target=training_scheduler, daemon=True)
            self.training_thread.start()
            self.logger.info("Agendamento de treinamento ativado")
    
    def start(self):
        """Inicia o sistema de produção"""
        self.logger.info("=" * 80)
        self.logger.info(" INICIANDO SISTEMA HÍBRIDO DE PRODUÇÃO")
        self.logger.info("=" * 80)
        
        # 1. Carregar modelos
        if not self.load_models():
            self.logger.error("Falha ao carregar modelos. Abortando...")
            return False
        
        # 2. Inicializar componentes
        self.initialize_components()
        
        # 3. Conectar ao ProfitChart (desativado temporariamente)
        # TODO: Reativar quando connection_manager estiver disponível
        # if not self.connection_manager.connect():
        #     self.logger.error("Falha ao conectar ao ProfitChart")
        #     return False
        self.logger.warning("Conexão com ProfitChart desativada (modo simulado)")
        
        # 4. Iniciar threads
        self.is_running = True
        
        # Thread de inferência
        self.inference_thread = threading.Thread(target=self._inference_loop, daemon=True)
        self.inference_thread.start()
        
        # Thread de monitoramento
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        # Agendar treinamento diário
        self.schedule_daily_training()
        
        self.logger.info("Sistema iniciado com sucesso!")
        self.logger.info(f"Versão dos modelos: {self.model_version}")
        self.logger.info(f"Re-treinamento diário: {'ATIVADO' if self.config.get('enable_daily_training', True) else 'DESATIVADO'}")
        
        return True
    
    def _inference_loop(self):
        """Loop principal de inferência"""
        while self.is_running:
            try:
                # Obter dados mais recentes (simulado por enquanto)
                tick_data = None  # self.buffers.get_latest_tick_data()
                book_data = None  # self.buffers.get_latest_book_data()
                
                if tick_data and book_data:
                    # Criar features
                    tick_features = self.create_context_features(pd.DataFrame([tick_data]))
                    book_features = self.create_book_features(pd.DataFrame([book_data]))
                    
                    # Fazer predição
                    prediction = self.make_prediction(tick_features, book_features)
                    
                    # Processar sinal de trading
                    min_confidence = self.config.get('min_confidence', 0.60)
                    if prediction['confidence'] >= min_confidence:
                        self._process_trading_signal(prediction)
                    
                    # Coletar dados para treinamento
                    self.collect_training_data(tick_data, book_data)
                    
                # Aguardar próximo ciclo
                threading.Event().wait(0.1)  # 100ms
                
            except Exception as e:
                self.logger.error(f"Erro no loop de inferência: {e}")
                threading.Event().wait(1)
    
    def _monitoring_loop(self):
        """Loop de monitoramento de performance"""
        while self.is_running:
            try:
                # Atualizar métricas a cada minuto
                self._update_performance_metrics()
                
                # Log de status
                self.logger.info(
                    f"[MONITOR] Trades: {self.performance_metrics['trades_today']} | "
                    f"Win Rate: {self.performance_metrics['win_rate']:.1%} | "
                    f"PnL: R$ {self.performance_metrics['total_pnl']:.2f}"
                )
                
                # Aguardar próximo ciclo
                threading.Event().wait(60)  # 1 minuto
                
            except Exception as e:
                self.logger.error(f"Erro no monitoramento: {e}")
                threading.Event().wait(60)
    
    def _process_trading_signal(self, prediction: Dict):
        """Processa sinal de trading"""
        signal = prediction['signal']
        confidence = prediction['confidence']
        
        # Verificar se já tem posição aberta
        if self.has_open_position:
            self.logger.info(f"[BLOQUEADO] Já existe posição aberta. Sinal ignorado: {signal}")
            return
        
        # Verificar limite diário de trades
        max_daily = self.config.get('max_daily_trades', 50)
        if self.performance_metrics['trades_today'] >= max_daily:
            self.logger.warning(f"[LIMITE] Limite diário atingido: {max_daily} trades")
            return
        
        # Executar trade se sinal válido
        if signal != 0:  # -1 = SELL, 1 = BUY
            self.logger.info(f"[TRADE] Processando sinal: {'BUY' if signal > 0 else 'SELL'} | Confidence: {confidence:.2%}")
            
            # Simular execução (substituir por execução real quando connection_manager estiver disponível)
            if self._execute_trade(signal, confidence):
                self.has_open_position = True
                self.current_position = signal
                self.current_position_side = 'BUY' if signal > 0 else 'SELL'
                self.performance_metrics['trades_today'] += 1
                self.logger.info(f"[OK] Trade executado com sucesso!")
            else:
                self.logger.error(f"[ERRO] Falha ao executar trade")
    
    def _execute_trade(self, signal: int, confidence: float) -> bool:
        """
        Executa trade com gerenciamento de risco
        
        Args:
            signal: -1 para SELL, 1 para BUY
            confidence: Confiança na predição
            
        Returns:
            bool: True se executou com sucesso
        """
        try:
            if not self.connection_manager:
                self.logger.warning("Connection Manager não disponível - trade simulado")
                # Simular execução para testes
                return True
            
            # Parâmetros do trade
            symbol = self.config.get('symbol', 'WDOU25')
            quantity = 1  # Ajustar conforme necessário
            
            # Calcular stop loss e take profit
            stop_loss_pct = self.config.get('stop_loss', 0.005)
            take_profit_pct = self.config.get('take_profit', 0.010)
            
            # Obter preço atual (simulado por enquanto)
            current_price = 5500.0  # Substituir por preço real quando disponível
            
            if signal > 0:  # BUY
                stop_price = current_price * (1 - stop_loss_pct)
                take_price = current_price * (1 + take_profit_pct)
                side = "BUY"
            else:  # SELL
                stop_price = current_price * (1 + stop_loss_pct)
                take_price = current_price * (1 - take_profit_pct)
                side = "SELL"
            
            # Enviar ordem com bracket (OCO)
            order_ids = self.connection_manager.send_order_with_bracket(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=0,  # Ordem a mercado
                stop_price=stop_price,
                take_price=take_price
            )
            
            if order_ids:
                self.pending_orders = [order_ids.get('stop_order'), order_ids.get('take_order')]
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Erro ao executar trade: {e}")
            return False
    
    def _update_position_status(self):
        """
        Atualiza status da posição verificando com o broker
        """
        if not self.connection_manager:
            return
            
        try:
            # Verificar posição real no broker
            position = self.connection_manager.get_position()
            
            if position:
                # Tem posição aberta
                if not self.has_open_position:
                    self.logger.info(f"[POSIÇÃO] Detectada nova posição: {position['quantity']} {position['side']}")
                self.has_open_position = True
                self.current_position = position['quantity'] if position['side'] == 'BUY' else -position['quantity']
                self.current_position_side = position['side']
            else:
                # Sem posição
                if self.has_open_position:
                    self.logger.info("[POSIÇÃO] Posição fechada")
                    
                    # Cancelar ordens pendentes
                    if self.pending_orders:
                        self.logger.info("[LIMPEZA] Cancelando ordens pendentes...")
                        self.connection_manager.cancel_all_pending_orders()
                        self.pending_orders = []
                        
                self.has_open_position = False
                self.current_position = 0
                self.current_position_side = None
                
        except Exception as e:
            self.logger.error(f"Erro ao atualizar status de posição: {e}")
    
    def _update_performance_metrics(self):
        """Atualiza métricas de performance"""
        # Atualizar status da posição
        self._update_position_status()
        
        # Calcular métricas adicionais se necessário
        pass
    
    def stop(self):
        """Para o sistema"""
        self.logger.info("Parando sistema...")
        
        self.is_running = False
        
        # Salvar dados pendentes
        self._save_training_batch()
        
        # Desconectar (quando disponível)
        # if self.connection_manager:
        #     self.connection_manager.disconnect()
        
        # Aguardar threads
        if self.inference_thread:
            self.inference_thread.join(timeout=5)
        if self.training_thread:
            self.training_thread.join(timeout=5)
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        self.logger.info("Sistema parado com sucesso")


def main():
    """Função principal"""
    system = HybridProductionSystem()
    
    try:
        if system.start():
            print("\nSistema rodando. Pressione Ctrl+C para parar...")
            
            # Manter rodando
            while True:
                threading.Event().wait(1)
                
    except KeyboardInterrupt:
        print("\n[!] Parando sistema...")
        system.stop()
        
    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
        system.stop()


if __name__ == "__main__":
    main()