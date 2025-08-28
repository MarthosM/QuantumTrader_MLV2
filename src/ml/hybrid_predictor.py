"""
Preditor Híbrido ML - Sistema de 3 camadas para trading
Integra modelos de contexto, microestrutura e meta-learner
"""

import numpy as np
import time

import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
import logging
import joblib
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Fix numpy compatibility issue
np.random.BitGenerator = np.random.bit_generator.BitGenerator

logger = logging.getLogger(__name__)

class HybridMLPredictor:
    """Sistema de predição ML híbrido de 3 camadas"""
    
    def __init__(self, models_dir: str = "models/hybrid"):
        """
        Inicializa o preditor híbrido
        
        Args:
            models_dir: Diretório com os modelos
        """
        self.models_dir = Path(models_dir)
        self.models = {}
        self.scalers = {}
        self.is_loaded = False
        
        # Configurações
        self.confidence_threshold = 0.6
        self.signal_threshold = 0.3
        
        # Features esperadas por camada (baseado no treinamento real)
        self.context_features = [
            # Features treinadas com dados reais (16 features)
            "returns_1", "returns_5", "returns_10", "returns_20",
            "volatility_10", "volatility_20", "volatility_50",
            "volume_ratio", "trade_intensity",
            "order_flow_imbalance", "signed_volume",
            "rsi_14", "spread",
            "bid_pressure", "ask_pressure", "book_imbalance"
        ]
        
        self.microstructure_features = [
            # Mesmas features usadas no contexto (16 features)
            # Isso garante compatibilidade com o scaler
            "returns_1", "returns_5", "returns_10", "returns_20",
            "volatility_10", "volatility_20", "volatility_50",
            "volume_ratio", "trade_intensity",
            "order_flow_imbalance", "signed_volume",
            "rsi_14", "spread",
            "bid_pressure", "ask_pressure", "book_imbalance"
        ]
        
        logger.info(f"HybridMLPredictor inicializado - Dir: {self.models_dir}")
        
    def load_models(self) -> bool:
        """Carrega todos os modelos e scalers"""
        try:
            models_loaded = 0
            
            # Try to load models with compatibility workaround
            import sys
            import io
            old_stderr = sys.stderr
            sys.stderr = io.StringIO()  # Suppress numpy warnings
            
            try:
                # Camada 1: Contexto
                context_dir = self.models_dir / "context"
                if context_dir.exists():
                    for model_file in context_dir.glob("*.pkl"):
                        try:
                            model_name = f"context_{model_file.stem}"
                            self.models[model_name] = joblib.load(model_file)
                            models_loaded += 1
                            logger.debug(f"Modelo carregado: {model_name}")
                        except Exception as e:
                            logger.debug(f"Falha ao carregar {model_file.stem}: {e}")
                
                # Camada 2: Microestrutura
                micro_dir = self.models_dir / "microstructure"
                if micro_dir.exists():
                    for model_file in micro_dir.glob("*.pkl"):
                        try:
                            model_name = f"micro_{model_file.stem}"
                            self.models[model_name] = joblib.load(model_file)
                            models_loaded += 1
                            logger.debug(f"Modelo carregado: {model_name}")
                        except Exception as e:
                            logger.debug(f"Falha ao carregar {model_file.stem}: {e}")
                
                # Camada 3: Meta-Learner
                meta_dir = self.models_dir / "meta_learner"
                if meta_dir.exists():
                    for model_file in meta_dir.glob("*.pkl"):
                        try:
                            model_name = f"meta_{model_file.stem}"
                            self.models[model_name] = joblib.load(model_file)
                            models_loaded += 1
                            logger.debug(f"Modelo carregado: {model_name}")
                        except Exception as e:
                            logger.debug(f"Falha ao carregar {model_file.stem}: {e}")
                
                # Scalers
                try:
                    if (self.models_dir / "scaler_context.pkl").exists():
                        self.scalers['context'] = joblib.load(self.models_dir / "scaler_context.pkl")
                        logger.debug("Scaler de contexto carregado")
                except:
                    pass
                
                try:
                    if (self.models_dir / "scaler_microstructure.pkl").exists():
                        self.scalers['microstructure'] = joblib.load(self.models_dir / "scaler_microstructure.pkl")
                        logger.debug("Scaler de microestrutura carregado")
                except:
                    pass
                    
            finally:
                sys.stderr = old_stderr  # Restore stderr
            
            self.is_loaded = models_loaded > 0
            
            if self.is_loaded:
                logger.info(f"[OK] {models_loaded} modelos carregados com sucesso")
            else:
                logger.warning("Nenhum modelo encontrado - usando fallback baseado em features")
                # Usar modo fallback sem modelos treinados
                self.is_loaded = True  # Permitir uso do sistema mesmo sem modelos
                self.use_fallback = True
            
            return self.is_loaded
            
        except Exception as e:
            logger.error(f"Erro ao carregar modelos: {e}")
            # Usar modo fallback
            self.is_loaded = True
            self.use_fallback = True
            return True
    
    def predict(self, features: Dict[str, float]) -> Dict:
        """
        Faz predição usando sistema híbrido de 3 camadas
        
        Args:
            features: Dicionário com todas as features (65)
            
        Returns:
            Dict com predição, confiança e detalhes
        """
        if not self.is_loaded:
            if not self.load_models():
                return {'signal': 0, 'confidence': 0, 'error': 'models_not_loaded'}
        
        # Validar se features são dinâmicas
        if not self._validate_features(features):
            logger.warning("[HYBRID] Features estáticas detectadas - usando sinal neutro")
            return {
                'signal': 0, 
                'confidence': 0.3, 
                'error': 'static_features',
                'ml_data': {'warning': 'Features não estão variando'},
                'predictions': {}
            }
        
        # Use fallback if models couldn't load properly
        if hasattr(self, 'use_fallback') and self.use_fallback:
            return self._fallback_predict(features)
        
        try:
            # Log features para debug
            self._log_feature_debug(features)
            
            # Separar features por camada
            context_data = self._prepare_context_features(features)
            micro_data = self._prepare_microstructure_features(features)
            
            # Camada 1: Predições de Contexto
            context_predictions = self._predict_context(context_data)
            logger.debug(f"[HYBRID] Context predictions: {context_predictions}")
            
            # Camada 2: Predições de Microestrutura
            micro_predictions = self._predict_microstructure(micro_data)
            logger.debug(f"[HYBRID] Micro predictions: {micro_predictions}")
            
            # Validar se predições são válidas
            if not context_predictions or not micro_predictions:
                logger.warning("[HYBRID] Predições incompletas - retornando sinal neutro")
                return {'signal': 0, 'confidence': 0.3, 'error': 'incomplete_predictions'}
            
            # Camada 3: Meta-Learner combina tudo
            final_prediction = self._predict_meta(
                context_predictions, 
                micro_predictions,
                features
            )
            logger.debug(f"[HYBRID] Meta prediction: {final_prediction}")
            
            # Determinar sinal final
            signal = self._determine_signal(final_prediction)
            confidence = self._calculate_confidence(
                final_prediction,
                context_predictions,
                micro_predictions
            )
            
            return {
                'signal': signal,
                'confidence': confidence,
                'ml_data': {
                    'signal': signal,
                    'confidence': confidence,
                    'context_pred': context_predictions,
                    'micro_pred': micro_predictions,
                    'meta_pred': final_prediction
                },
                'predictions': {
                    'context': context_predictions,
                    'microstructure': micro_predictions,
                    'meta': final_prediction
                }
            }
            
        except Exception as e:
            logger.error(f"Erro na predição ML: {e}")
            return {'signal': 0, 'confidence': 0, 'error': str(e)}
    
    
    def _validate_features(self, features: Dict[str, float]) -> bool:
        """Valida se as features são dinâmicas e não estáticas"""
        # Armazenar últimas features para comparação
        if not hasattr(self, '_last_features'):
            self._last_features = features.copy()
            self._static_count = 0
            return True
        
        # Verificar features críticas que devem variar
        critical_features = ['returns_1', 'returns_5', 'volatility_10', 'order_flow_imbalance']
        static_features = []
        
        for feat in critical_features:
            if feat in features and feat in self._last_features:
                if abs(features[feat] - self._last_features[feat]) < 1e-8:
                    static_features.append(feat)
        
        # Se muitas features críticas estão estáticas
        if len(static_features) >= 3:
            self._static_count += 1
            if self._static_count > 5:
                logger.warning(f"[HYBRID] Features estáticas há {self._static_count} ciclos: {static_features}")
                return False
        else:
            self._static_count = 0
        
        # Atualizar últimas features
        self._last_features = features.copy()
        return True
    
    def _log_feature_debug(self, features: Dict[str, float]):
        """Log detalhado de features para debug"""
        # Log apenas periodicamente para não poluir
        if not hasattr(self, '_debug_counter'):
            self._debug_counter = 0
        
        self._debug_counter += 1
        if self._debug_counter % 50 == 0:  # A cada 50 predições
            logger.info("[HYBRID DEBUG] Sample features:")
            for key in ['returns_1', 'returns_5', 'volatility_10', 'spread', 'order_flow_imbalance']:
                if key in features:
                    logger.info(f"  {key}: {features[key]:.6f}")
    
    def _prepare_context_features(self, features: Dict) -> np.ndarray:
        """Prepara features de contexto"""
        context_values = []
        
        for feat_name in self.context_features:
            if feat_name in features:
                context_values.append(features[feat_name])
            else:
                # Usar valor padrão se feature não existir
                context_values.append(0.0)
                logger.debug(f"Feature ausente: {feat_name}")
        
        X = np.array(context_values).reshape(1, -1)
        
        # Aplicar scaler se disponível
        if 'context' in self.scalers:
            X = self.scalers['context'].transform(X)
        
        return X
    
    def _prepare_microstructure_features(self, features: Dict) -> np.ndarray:
        """Prepara features de microestrutura"""
        micro_values = []
        
        for feat_name in self.microstructure_features:
            if feat_name in features:
                micro_values.append(features[feat_name])
            else:
                # Usar valor padrão
                micro_values.append(0.0)
                logger.debug(f"Feature ausente: {feat_name}")
        
        X = np.array(micro_values).reshape(1, -1)
        
        # Aplicar scaler se disponível
        if 'microstructure' in self.scalers:
            X = self.scalers['microstructure'].transform(X)
        
        return X
    
    def _predict_context(self, X: np.ndarray) -> Dict:
        """Predições da camada de contexto"""
        predictions = {}
        
        # Sempre garantir que temos valores, mesmo sem modelos
        time_factor = int(time.time())
        
        # Regime Detector
        if 'context_regime_detector' in self.models:
            try:
                pred = self.models['context_regime_detector'].predict_proba(X)[0]
                predictions['regime'] = int(np.argmax(pred))
                predictions['regime_conf'] = float(np.max(pred))
            except Exception as e:
                logger.error(f"Erro ao fazer predição de regime: {e}")
                # Sem fallback - retornar sem valores se houver erro
                return predictions
        else:
            logger.warning("Modelo context_regime_detector não disponível")
            # Sem fallback - retornar vazio se modelo não disponível
            return predictions
        
        # Volatility Forecaster
        if 'context_volatility_forecaster' in self.models:
            try:
                pred = self.models['context_volatility_forecaster'].predict(X)[0]
                predictions['volatility'] = pred
            except:
                predictions['volatility'] = 0
        
        # Session Classifier
        if 'context_session_classifier' in self.models:
            try:
                pred = self.models['context_session_classifier'].predict_proba(X)[0]
                predictions['session'] = np.argmax(pred)
                predictions['session_conf'] = np.max(pred)
            except:
                predictions['session'] = 0
                predictions['session_conf'] = 0.5
        
        return predictions
    
    def _predict_microstructure(self, X: np.ndarray) -> Dict:
        """Predições da camada de microestrutura"""
        predictions = {}
        
        # Sempre garantir valores dinâmicos
        time_factor = int(time.time())
        
        # Order Flow Analyzer
        if 'micro_order_flow_analyzer' in self.models:
            try:
                pred = self.models['micro_order_flow_analyzer'].predict_proba(X)[0]
                # Assumindo 3 classes: SELL(-1), HOLD(0), BUY(1)
                predictions['order_flow'] = int(np.argmax(pred) - 1)  # Converter para -1, 0, 1
                predictions['order_flow_conf'] = float(np.max(pred))
            except Exception as e:
                logger.error(f"Erro ao fazer predição de order_flow: {e}")
                # Sem fallback - retornar sem valores se houver erro
                return predictions
        else:
            logger.warning("Modelo micro_order_flow_analyzer não disponível")
            # Sem fallback - retornar vazio se modelo não disponível
            return predictions
        
        # Book Dynamics
        if 'micro_book_dynamics' in self.models:
            try:
                pred = self.models['micro_book_dynamics'].predict(X)[0]
                predictions['book_pressure'] = pred
            except:
                predictions['book_pressure'] = 0
        
        return predictions
    
    def _predict_meta(self, context_pred: Dict, micro_pred: Dict, 
                     features: Dict) -> float:
        """Predição do meta-learner"""
        
        if 'meta_meta_learner' not in self.models:
            # Fallback: média ponderada simples
            context_signal = context_pred.get('regime', 0) - 1  # Converter para -1, 0, 1
            micro_signal = micro_pred.get('order_flow', 0)
            
            return 0.6 * micro_signal + 0.4 * context_signal
        
        try:
            # Preparar features para meta-learner
            # NOTA: O modelo foi treinado com 6 features, vamos usar apenas essas
            meta_features = []
            
            # 6 Features principais usadas no treinamento
            meta_features.append(context_pred.get('regime', 0))
            meta_features.append(context_pred.get('regime_conf', 0.5))
            meta_features.append(context_pred.get('volatility', 0))
            meta_features.append(micro_pred.get('order_flow', 0))
            meta_features.append(micro_pred.get('order_flow_conf', 0.5))
            meta_features.append(micro_pred.get('book_pressure', 0))
            
            # Se precisar de 12 features (para compatibilidade futura)
            # Descomente as linhas abaixo:
            # meta_features.append(context_pred.get('session', 0))
            # meta_features.append(context_pred.get('session_conf', 0.5))
            # meta_features.append(features.get('spread', 0))
            # meta_features.append(features.get('imbalance', 0))
            # meta_features.append(features.get('volatility_20', 0))
            # meta_features.append(features.get('rsi_14', 50))
            
            X_meta = np.array(meta_features).reshape(1, -1)
            
            # Predizer com meta-learner
            prediction = self.models['meta_meta_learner'].predict(X_meta)[0]
            
            return prediction
            
        except Exception as e:
            logger.error(f"Erro no meta-learner: {e}")
            # Fallback
            return 0.6 * micro_pred.get('order_flow', 0) + 0.4 * (context_pred.get('regime', 0) - 1)
    
    def _determine_signal(self, meta_prediction: float) -> int:
        """Determina sinal final baseado na predição"""
        if meta_prediction > self.signal_threshold:
            return 1  # BUY
        elif meta_prediction < -self.signal_threshold:
            return -1  # SELL
        else:
            return 0  # HOLD
    
    def _calculate_confidence(self, meta_pred: float, 
                            context_pred: Dict, 
                            micro_pred: Dict) -> float:
        """Calcula confiança da predição"""
        
        # Confiança baseada na força do sinal
        signal_confidence = min(abs(meta_pred) / 1.0, 1.0)
        
        # Confiança das predições individuais
        context_conf = context_pred.get('regime_conf', 0.5)
        micro_conf = micro_pred.get('order_flow_conf', 0.5)
        
        # Combinar confianças
        combined_confidence = (
            0.5 * signal_confidence +
            0.3 * micro_conf +
            0.2 * context_conf
        )
        
        return min(max(combined_confidence, 0.0), 1.0)
    
    def get_feature_importance(self) -> Dict:
        """Retorna importância das features se disponível"""
        importance = {}
        
        # Tentar obter de modelos baseados em árvore
        for name, model in self.models.items():
            if hasattr(model, 'feature_importances_'):
                importance[name] = model.feature_importances_.tolist()
        
        return importance
    
    def _fallback_predict(self, features: Dict[str, float]) -> Dict:
        """
        Predição fallback baseada em análise técnica quando modelos não estão disponíveis
        """
        try:
            # Validar features primeiro
            features_valid = self._validate_features(features)
            
            # Análise baseada em indicadores técnicos
            signal = 0
            confidence = 0.0
            
            # Se features estáticas, retornar neutro
            if not features_valid:
                logger.warning("[HYBRID FALLBACK] Features estáticas - retornando sinal neutro")
                return {
                    'signal': 0,
                    'confidence': 0.2,
                    'ml_data': {'mode': 'fallback', 'warning': 'static_features'},
                    'predictions': {}
                }
            
            # RSI
            rsi = features.get('rsi_14', 50)
            if rsi > 70:
                signal -= 0.5  # Sobrecomprado
                confidence += 0.2
            elif rsi < 30:
                signal += 0.5  # Sobrevendido
                confidence += 0.2
            
            # Order Flow Imbalance - tentar diferentes chaves
            ofi = features.get('order_flow_imbalance', 0)
            if ofi == 0:
                ofi = features.get('order_flow_imbalance_5', 0)
            
            if abs(ofi) > 0.3:
                signal += np.sign(ofi) * 0.3
                confidence += 0.15
            
            # Volume Imbalance
            imbalance = features.get('imbalance', 0)
            if abs(imbalance) > 0.3:
                signal += np.sign(imbalance) * 0.2
                confidence += 0.1
            
            # Momentum
            returns_5 = features.get('returns_5', 0)
            if abs(returns_5) > 0.005:  # 0.5% move
                signal += np.sign(returns_5) * 0.2
                confidence += 0.1
            
            # Spread analysis
            spread = features.get('spread', 0.5)
            if spread < 0.5:  # Tight spread = good liquidity
                confidence += 0.05
            
            # Normalize signal
            if signal > 0.3:
                final_signal = 1
            elif signal < -0.3:
                final_signal = -1
            else:
                final_signal = 0
            
            # Garantir limites de confiança sem variação artificial
            confidence = np.clip(confidence, 0.3, 0.8)
            
            return {
                'signal': final_signal,
                'confidence': confidence,
                'ml_data': {
                    'signal': final_signal,
                    'confidence': confidence,
                    'mode': 'fallback'
                },
                'predictions': {
                    'context': {'mode': 'fallback', 'rsi': rsi},
                    'microstructure': {'ofi': ofi, 'imbalance': imbalance},
                    'meta': {'signal': final_signal}
                }
            }
            
        except Exception as e:
            logger.error(f"Erro no fallback prediction: {e}")
            return {'signal': 0, 'confidence': 0, 'error': str(e)}