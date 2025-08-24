"""
EnhancedProductionSystem - Sistema de Produção com 65 Features e HMARL
Integra o novo sistema de features com o HMARL existente
"""

import os
import sys
import time
import threading
import logging
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import warnings
warnings.filterwarnings('ignore')

# Adicionar paths necessários
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

# Importar base do sistema
from src.production_fixed import ProductionFixedSystem

# Importar novos componentes de features
from src.features.book_features_rt import BookFeatureEngineerRT
from src.features.feature_mapping import FeatureMapper
from src.book_data_manager import BookDataManager
from src.buffers.circular_buffer import CandleBuffer, BookBuffer, TradeBuffer

# Tentar importar componentes HMARL
try:
    from start_hmarl_production_enhanced import EnhancedHMARLProductionSystem
    HMARL_BASE_AVAILABLE = True
except ImportError as e:
    HMARL_BASE_AVAILABLE = False
    print(f"[AVISO] HMARL base não disponível: {e}")

try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False
    print("[AVISO] ZMQ não disponível - broadcasting desabilitado")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('EnhancedProductionSystem')


class EnhancedProductionSystem(ProductionFixedSystem):
    """
    Sistema de Produção Enhanced com:
    - Cálculo completo de 65 features
    - Integração com HMARL
    - Gestão otimizada de buffers
    - Fallback para dados faltantes
    """
    
    def __init__(self):
        """Inicializa o sistema enhanced"""
        super().__init__()
        
        self.logger = logger
        
        # Componentes de features
        self.book_manager = BookDataManager(max_book_snapshots=100, max_trades=1000)
        self.feature_engineer = BookFeatureEngineerRT(self.book_manager)
        self.feature_mapper = FeatureMapper()
        
        # Buffers adicionais
        self.candle_buffer = CandleBuffer(max_size=200)
        self.last_candle_time = None
        
        # HMARL Integration
        self.hmarl_enabled = False
        self.zmq_context = None
        self.zmq_publisher = None
        self.agent_signals = {}
        self.last_agent_consensus = 0.5
        
        # Feature statistics
        self.feature_stats = {
            'calculations': 0,
            'avg_latency_ms': 0,
            'features_available': 0,
            'features_missing': 0,
            'last_update': None
        }
        
        # Enhanced callbacks tracking
        self.enhanced_callbacks = {
            'price_book': 0,
            'offer_book': 0,
            'trades': 0,
            'candles': 0
        }
        
        # Fallback configuration - DESABILITADO para usar apenas features reais
        self.use_fallback = False  # IMPORTANTE: Não usar valores mock/fallback
        self.fallback_values = {}  # Sem valores fallback
        
        # Enhanced monitoring
        self.enhanced_monitor_data = {
            'features': {},
            'hmarl_status': {},
            'performance': {}
        }
        
        # Thread safety
        self.feature_lock = threading.RLock()
        
        self.logger.info("EnhancedProductionSystem inicializado com 65 features")
    
    def initialize(self):
        """Inicializa sistema enhanced"""
        try:
            # Inicializar sistema base
            super().initialize()
            
            # Inicializar HMARL se disponível
            if ZMQ_AVAILABLE:
                self._initialize_hmarl()
            
            # Validar modelos para 65 features
            self._validate_models()
            
            self.logger.info("[OK] Sistema Enhanced inicializado com sucesso")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro na inicialização enhanced: {e}")
            return False
    
    def _initialize_hmarl(self):
        """Inicializa componentes HMARL"""
        try:
            self.zmq_context = zmq.Context()
            self.zmq_publisher = self.zmq_context.socket(zmq.PUB)
            self.zmq_publisher.bind("tcp://*:5556")
            
            self.hmarl_enabled = True
            self.logger.info("[OK] HMARL broadcasting inicializado na porta 5556")
            
        except Exception as e:
            self.logger.warning(f"[AVISO] HMARL não inicializado: {e}")
            self.hmarl_enabled = False
    
    def _validate_models(self):
        """Valida se modelos suportam 65 features"""
        try:
            for model_name, model in self.models.items():
                if hasattr(model, 'n_features_in_'):
                    n_features = model.n_features_in_
                    if n_features == 65:
                        self.logger.info(f"[OK] Modelo {model_name}: 65 features ✓")
                    else:
                        self.logger.warning(f"[AVISO] Modelo {model_name}: {n_features} features (esperado 65)")
                        
        except Exception as e:
            self.logger.error(f"Erro validando modelos: {e}")
    
    # Override dos callbacks principais
    
    def on_state_changed_callback(self, result):
        """Callback de mudança de estado"""
        # Chamar callback base
        super().on_state_changed_callback(result)
        
        # Atualizar status HMARL se conectado
        if self.hmarl_enabled and self.bMarketConnected:
            self._broadcast_market_status()
    
    def on_price_book_callback(self, asset, side, position, info):
        """Callback enhanced de price book"""
        try:
            # Processar callback base
            super().on_price_book_callback(asset, side, position, info)
            
            # Processar no book manager
            with self.feature_lock:
                book_data = {
                    'timestamp': datetime.now(),
                    'symbol': self.target_ticker,
                    'bids': []
                }
                
                # Converter dados do book
                if position <= 5:  # Primeiros 5 níveis
                    book_data['bids'].append({
                        'price': info.price,
                        'volume': info.qtd,
                        'trader_id': f"T{info.nOrders}"  # Simulado
                    })
                
                self.book_manager.on_price_book_callback(book_data)
                self.enhanced_callbacks['price_book'] += 1
                
                # Se temos dados suficientes, calcular features
                if self.enhanced_callbacks['price_book'] % 10 == 0:
                    self._calculate_and_broadcast_features()
                    
        except Exception as e:
            self.logger.error(f"Erro em price_book enhanced: {e}")
    
    def on_offer_book_callback(self, asset, side, position, info):
        """Callback enhanced de offer book"""
        try:
            # Processar callback base
            super().on_offer_book_callback(asset, side, position, info)
            
            # Processar no book manager
            with self.feature_lock:
                book_data = {
                    'timestamp': datetime.now(),
                    'symbol': self.target_ticker,
                    'asks': []
                }
                
                # Converter dados do book
                if position <= 5:  # Primeiros 5 níveis
                    book_data['asks'].append({
                        'price': info.price,
                        'volume': info.qtd,
                        'trader_id': f"T{info.nOrders}"  # Simulado
                    })
                
                self.book_manager.on_offer_book_callback(book_data)
                self.enhanced_callbacks['offer_book'] += 1
                
        except Exception as e:
            self.logger.error(f"Erro em offer_book enhanced: {e}")
    
    def on_daily_callback(self, asset, daily_info):
        """Callback enhanced de dados diários (candles)"""
        try:
            # Processar callback base
            super().on_daily_callback(asset, daily_info)
            
            # Adicionar candle ao buffer
            with self.feature_lock:
                candle_data = {
                    'timestamp': datetime.now(),
                    'open': daily_info.sOpen,
                    'high': daily_info.sHigh,
                    'low': daily_info.sLow,
                    'close': daily_info.sClose,
                    'volume': daily_info.sVol
                }
                
                # Adicionar aos buffers
                self.candle_buffer.add_candle(
                    timestamp=candle_data['timestamp'],
                    open=candle_data['open'],
                    high=candle_data['high'],
                    low=candle_data['low'],
                    close=candle_data['close'],
                    volume=candle_data['volume']
                )
                
                # Atualizar feature engineer
                self.feature_engineer._update_candle(candle_data)
                self.enhanced_callbacks['candles'] += 1
                
                # Calcular features a cada novo candle
                if self.candle_buffer.size() >= 20:  # Mínimo para indicadores
                    self._calculate_and_broadcast_features()
                    
        except Exception as e:
            self.logger.error(f"Erro em daily_callback enhanced: {e}")
    
    def _calculate_features(self) -> Dict:
        """
        Override do método base para usar 65 features
        """
        try:
            start_time = time.time()
            
            # Calcular 65 features usando o novo sistema
            with self.feature_lock:
                features = self.feature_engineer.calculate_incremental_features({})
                
                # Aplicar mapeamento para agentes HMARL
                features = self.feature_mapper.map_features(features)
                
                # Estatísticas
                calc_time = (time.time() - start_time) * 1000
                self.feature_stats['calculations'] += 1
                self.feature_stats['avg_latency_ms'] = (
                    (self.feature_stats['avg_latency_ms'] * (self.feature_stats['calculations'] - 1) + calc_time) 
                    / self.feature_stats['calculations']
                )
                self.feature_stats['last_update'] = datetime.now()
                
                # Contar features disponíveis
                non_zero = sum(1 for v in features.values() if v != 0)
                self.feature_stats['features_available'] = non_zero
                self.feature_stats['features_missing'] = 65 - non_zero
                
                # Log periódico
                if self.feature_stats['calculations'] % 100 == 0:
                    self.logger.info(
                        f"Features: {non_zero}/65 disponíveis | "
                        f"Latência média: {self.feature_stats['avg_latency_ms']:.2f}ms | "
                        f"Cálculos: {self.feature_stats['calculations']}"
                    )
                
                # Aplicar fallback se necessário
                if self.use_fallback and non_zero < 50:
                    features = self._apply_fallback(features)
                
                return features
                
        except Exception as e:
            self.logger.error(f"Erro calculando features: {e}")
            # Retornar features com fallback completo
            return self.fallback_values.copy()
    
    def _calculate_and_broadcast_features(self):
        """Calcula features e broadcast para HMARL"""
        try:
            # Calcular features
            features = self._calculate_features()
            
            # Fazer predição ML se possível
            if self.models and len(features) == 65:
                prediction = self._make_ml_prediction(features)
                
                # Broadcast para agentes HMARL
                if self.hmarl_enabled:
                    self._broadcast_to_agents(features, prediction)
                
                # Atualizar monitor
                self._update_enhanced_monitor(features, prediction)
                
        except Exception as e:
            self.logger.error(f"Erro em calculate_and_broadcast: {e}")
    
    def _make_ml_prediction(self, features: Dict) -> float:
        """Faz predição usando modelos com 65 features"""
        try:
            # Converter para array na ordem correta
            feature_vector = self.feature_engineer.get_feature_vector()
            
            # Log diagnóstico
            non_zero = np.count_nonzero(feature_vector)
            self.logger.debug(f"Feature vector: {len(feature_vector)} features, {non_zero} não-zero")
            
            predictions = []
            models_used = []
            
            for model_name, model in self.models.items():
                try:
                    # Verificar compatibilidade do modelo
                    expected_features = getattr(model, 'n_features_in_', None)
                    
                    # Aceitar modelos sem n_features_in_ ou com features compatíveis
                    if expected_features is None or expected_features == len(feature_vector) or expected_features == 65:
                        if hasattr(model, 'predict_proba'):
                            pred = model.predict_proba(feature_vector.reshape(1, -1))[0, 1]
                        else:
                            pred = model.predict(feature_vector.reshape(1, -1))[0]
                        
                        predictions.append(pred)
                        models_used.append(model_name)
                        
                    else:
                        self.logger.warning(f"Modelo {model_name} espera {expected_features} features, mas temos {len(feature_vector)}")
                        
                except Exception as e:
                    self.logger.warning(f"Erro em predição {model_name}: {e}")
            
            if predictions:
                # Ensemble - média das predições
                final_prediction = np.mean(predictions)
                self._last_prediction = final_prediction
                
                # Log apenas mudanças significativas
                if abs(final_prediction - 0.5) > 0.1:
                    self.logger.info(f"ML Prediction: {final_prediction:.3f} ({len(models_used)} modelos: {', '.join(models_used)})")
                
                return final_prediction
            else:
                self.logger.warning(f"Nenhum modelo fez predição! Features: {len(feature_vector)}, não-zero: {non_zero}")
                return 0.5  # Neutro se não há predições
            
        except Exception as e:
            self.logger.error(f"Erro em ML prediction: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return 0.5
    
    def _broadcast_to_agents(self, features: Dict, prediction: float):
        """Broadcast features para agentes HMARL via ZMQ"""
        if not self.hmarl_enabled or not self.zmq_publisher:
            return
        
        try:
            # Preparar mensagem
            message = {
                'timestamp': datetime.now().isoformat(),
                'type': 'features',
                'features': features,
                'ml_prediction': prediction,
                'market_data': {
                    'price': self.current_price,
                    'position': self.position,
                    'pnl': self.daily_pnl
                }
            }
            
            # Enviar via ZMQ
            self.zmq_publisher.send_json(message)
            
            # Log periódico
            if self.enhanced_callbacks['price_book'] % 100 == 0:
                self.logger.info(f"[HMARL] Broadcasting para agentes - Predição: {prediction:.3f}")
                
        except Exception as e:
            self.logger.error(f"Erro em broadcast HMARL: {e}")
    
    def _broadcast_market_status(self):
        """Broadcast status do mercado para agentes"""
        if not self.hmarl_enabled:
            return
        
        try:
            status = {
                'timestamp': datetime.now().isoformat(),
                'type': 'status',
                'connected': self.bMarketConnected,
                'broker_connected': self.bBrokerConnected,
                'ticker': self.target_ticker
            }
            
            if self.zmq_publisher:
                self.zmq_publisher.send_json(status)
                
        except Exception as e:
            self.logger.debug(f"Erro broadcasting status: {e}")
    
    def _apply_fallback(self, features: Dict) -> Dict:
        """
        Aplica valores fallback para features faltantes
        
        Args:
            features: Features calculadas (possivelmente incompletas)
            
        Returns:
            Features com fallback aplicado
        """
        enhanced_features = features.copy()
        
        for feature_name, default_value in self.fallback_values.items():
            if feature_name not in enhanced_features or enhanced_features[feature_name] == 0:
                enhanced_features[feature_name] = default_value
                
        return enhanced_features
    
    def _initialize_fallback_values(self) -> Dict:
        """Inicializa valores fallback para cada feature"""
        return {
            # Volatilidade - valores conservadores
            "volatility_10": 0.01,
            "volatility_20": 0.01,
            "volatility_50": 0.01,
            "volatility_100": 0.01,
            "volatility_ratio_10_20": 1.0,
            "volatility_ratio_20_50": 1.0,
            "volatility_ratio_50_100": 1.0,
            "volatility_ratio_100_200": 1.0,
            "volatility_gk": 0.01,
            "bb_position": 0.0,
            
            # Retornos - neutros
            "returns_1": 0.0,
            "returns_2": 0.0,
            "returns_5": 0.0,
            "returns_10": 0.0,
            "returns_20": 0.0,
            "returns_50": 0.0,
            "returns_100": 0.0,
            "log_returns_1": 0.0,
            "log_returns_5": 0.0,
            "log_returns_20": 0.0,
            
            # Order Flow - balanceado
            "order_flow_imbalance_10": 0.0,
            "order_flow_imbalance_20": 0.0,
            "order_flow_imbalance_50": 0.0,
            "order_flow_imbalance_100": 0.0,
            "cumulative_signed_volume": 0.0,
            "signed_volume": 0.0,
            "volume_weighted_return": 0.0,
            "agent_turnover": 0.0,
            
            # Volume - médios
            "volume_ratio_20": 1.0,
            "volume_ratio_50": 1.0,
            "volume_ratio_100": 1.0,
            "volume_zscore_20": 0.0,
            "volume_zscore_50": 0.0,
            "volume_zscore_100": 0.0,
            "trade_intensity": 0.0,
            "trade_intensity_ratio": 0.0,
            
            # Técnicos - neutros
            "ma_5_20_ratio": 1.0,
            "ma_20_50_ratio": 1.0,
            "momentum_5_20": 0.0,
            "momentum_20_50": 0.0,
            "sharpe_5": 0.0,
            "sharpe_20": 0.0,
            "time_normalized": 0.5,
            "rsi_14": 50.0,
            
            # Microestrutura - inativos
            "top_buyer_0_active": 0,
            "top_buyer_1_active": 0,
            "top_buyer_2_active": 0,
            "top_buyer_3_active": 0,
            "top_buyer_4_active": 0,
            "top_seller_0_active": 0,
            "top_seller_1_active": 0,
            "top_seller_2_active": 0,
            "top_seller_3_active": 0,
            "top_seller_4_active": 0,
            "top_buyers_count": 0,
            "top_sellers_count": 0,
            "buyer_changed": 0,
            "seller_changed": 0,
            "is_buyer_aggressor": 0,
            
            # Temporais - baseados em horário atual
            "minute": datetime.now().minute / 60.0,
            "hour": datetime.now().hour / 24.0,
            "day_of_week": datetime.now().weekday() / 4.0,
            "is_opening_30min": 0,
            "is_closing_30min": 0,
            "is_lunch_hour": 0
        }
    
    def _update_enhanced_monitor(self, features: Dict, prediction: float):
        """Atualiza dados para monitor enhanced"""
        try:
            self.enhanced_monitor_data = {
                'timestamp': datetime.now().isoformat(),
                'features': {
                    'total': 65,
                    'available': self.feature_stats['features_available'],
                    'missing': self.feature_stats['features_missing'],
                    'avg_latency_ms': self.feature_stats['avg_latency_ms']
                },
                'hmarl_status': {
                    'enabled': self.hmarl_enabled,
                    'agents_connected': len(self.agent_signals),
                    'last_consensus': self.last_agent_consensus,
                    'broadcasts': self.enhanced_callbacks['price_book']
                },
                'performance': {
                    'calculations': self.feature_stats['calculations'],
                    'callbacks': self.enhanced_callbacks,
                    'position': self.position,
                    'pnl': self.daily_pnl,
                    'prediction': prediction
                }
            }
            
            # Salvar para arquivo compartilhado
            if self.shared_data_file:
                with open(self.shared_data_file, 'w') as f:
                    json.dump(self.enhanced_monitor_data, f, indent=2)
                    
        except Exception as e:
            self.logger.debug(f"Erro atualizando monitor: {e}")
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas completas do sistema"""
        base_stats = super().get_statistics() if hasattr(super(), 'get_statistics') else {}
        
        enhanced_stats = {
            **base_stats,
            'features': self.feature_stats,
            'callbacks': self.enhanced_callbacks,
            'book_manager': self.book_manager.get_statistics(),
            'feature_engineer': self.feature_engineer.get_statistics(),
            'hmarl': {
                'enabled': self.hmarl_enabled,
                'agent_signals': len(self.agent_signals),
                'last_consensus': self.last_agent_consensus
            }
        }
        
        return enhanced_stats
    
    def cleanup(self):
        """Limpeza do sistema enhanced"""
        try:
            # Fechar ZMQ
            if self.zmq_publisher:
                self.zmq_publisher.close()
            if self.zmq_context:
                self.zmq_context.term()
            
            # Limpar buffers
            self.book_manager.reset()
            
            # Chamar cleanup base
            super().cleanup()
            
            self.logger.info("EnhancedProductionSystem finalizado")
            
        except Exception as e:
            self.logger.error(f"Erro no cleanup: {e}")


def main():
    """Função principal para executar o sistema enhanced"""
    logger.info("=" * 60)
    logger.info("ENHANCED PRODUCTION SYSTEM - 65 FEATURES + HMARL")
    logger.info("=" * 60)
    
    system = None
    
    try:
        # Criar sistema
        system = EnhancedProductionSystem()
        
        # Inicializar
        if not system.initialize():
            logger.error("Falha na inicialização")
            return
        
        logger.info("[OK] Sistema iniciado com sucesso")
        logger.info(f"Features: 65 | HMARL: {system.hmarl_enabled}")
        
        # Loop principal
        system.is_running = True
        last_stats_time = time.time()
        
        while system.is_running:
            try:
                time.sleep(0.1)
                
                # Estatísticas periódicas
                if time.time() - last_stats_time > 30:
                    stats = system.get_statistics()
                    logger.info(
                        f"[STATS] Features: {stats['features']['features_available']}/65 | "
                        f"Callbacks: {stats['callbacks']['price_book']} | "
                        f"Latência: {stats['features']['avg_latency_ms']:.2f}ms | "
                        f"PnL: R$ {stats.get('pnl', 0):.2f}"
                    )
                    last_stats_time = time.time()
                    
            except KeyboardInterrupt:
                logger.info("\n[INFO] Interrupção solicitada...")
                break
                
        logger.info("Finalizando sistema...")
        
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
        
    finally:
        if system:
            system.cleanup()
        logger.info("Sistema finalizado")


if __name__ == "__main__":
    main()