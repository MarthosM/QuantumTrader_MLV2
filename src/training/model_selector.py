"""
Sistema de Seleção Automática de Modelos
Escolhe o melhor modelo baseado em métricas de performance e validação
"""

import os
import json
import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import logging
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class ModelSelector:
    """Sistema inteligente de seleção de modelos"""
    
    def __init__(self, 
                 models_dir: str = "models",
                 validation_data_dir: str = "data/book_tick_data",
                 min_accuracy: float = 0.55,
                 max_model_age_days: int = 30,
                 validation_split: float = 0.2):
        """
        Args:
            models_dir: Diretório com modelos treinados
            validation_data_dir: Diretório com dados para validação
            min_accuracy: Accuracy mínima aceitável
            max_model_age_days: Idade máxima do modelo em dias
            validation_split: Porcentagem de dados para validação
        """
        self.models_dir = Path(models_dir)
        self.validation_data_dir = Path(validation_data_dir)
        self.min_accuracy = min_accuracy
        self.max_model_age_days = max_model_age_days
        self.validation_split = validation_split
        
        # Cache de modelos avaliados
        self.model_scores = {}
        self.current_models = None
        self.best_model_info = None
        
    def find_available_models(self) -> List[Dict]:
        """
        Encontra todos os modelos disponíveis no diretório
        
        Returns:
            Lista de dicionários com informações dos modelos
        """
        models = []
        
        # Buscar modelos re-treinados
        for model_file in self.models_dir.glob("retrained_model_*.pkl"):
            try:
                # Extrair timestamp do nome
                timestamp_str = model_file.stem.replace("retrained_model_", "")
                model_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                
                # Verificar idade do modelo
                age_days = (datetime.now() - model_date).days
                
                # Buscar scaler correspondente
                scaler_file = self.models_dir / f"retrained_scaler_{timestamp_str}.pkl"
                
                # Buscar relatório de treinamento
                report_file = self.models_dir / f"training_report_{timestamp_str}.json"
                
                model_info = {
                    'model_path': model_file,
                    'scaler_path': scaler_file if scaler_file.exists() else None,
                    'report_path': report_file if report_file.exists() else None,
                    'timestamp': model_date,
                    'age_days': age_days,
                    'is_recent': age_days <= self.max_model_age_days
                }
                
                # Adicionar métricas do relatório se disponível
                if report_file.exists():
                    with open(report_file, 'r') as f:
                        report = json.load(f)
                        model_info['training_accuracy'] = report.get('accuracy', 0)
                        model_info['samples_used'] = report.get('samples_used', 0)
                        model_info['features'] = report.get('features', [])
                
                models.append(model_info)
                
            except Exception as e:
                logger.warning(f"Erro ao processar {model_file}: {e}")
                continue
        
        # Buscar modelos originais/padrão
        # Verificar modelos XGBoost e outros modelos únicos
        for model_file in self.models_dir.glob("*.pkl"):
            if not model_file.name.startswith("retrained_"):
                model_info = {
                    'model_path': model_file,
                    'scaler_path': None,  # Scalers podem não existir para todos
                    'timestamp': datetime.fromtimestamp(model_file.stat().st_mtime),
                    'age_days': (datetime.now() - datetime.fromtimestamp(
                        model_file.stat().st_mtime)).days,
                    'is_original': True,
                    'model_type': 'standalone',
                    'training_accuracy': 0.60  # Assumir accuracy padrão para modelos originais
                }
                models.append(model_info)
        
        # Ordenar por data (mais recente primeiro)
        models.sort(key=lambda x: x['timestamp'], reverse=True)
        
        logger.info(f"Encontrados {len(models)} modelos disponíveis")
        return models
    
    def load_validation_data(self, hours_back: int = 24) -> Optional[pd.DataFrame]:
        """
        Carrega dados recentes para validação
        
        Args:
            hours_back: Horas de dados para validação
            
        Returns:
            DataFrame com dados de validação
        """
        try:
            # Buscar arquivos recentes
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            recent_files = []
            
            for file_path in self.validation_data_dir.glob("*.csv"):
                if datetime.fromtimestamp(file_path.stat().st_mtime) > cutoff_time:
                    recent_files.append(file_path)
            
            if not recent_files:
                logger.warning("Nenhum dado recente para validação")
                return None
            
            # Carregar e concatenar
            dfs = []
            for file_path in recent_files[-5:]:  # Últimos 5 arquivos
                try:
                    df = pd.read_csv(file_path)
                    dfs.append(df)
                except:
                    continue
            
            if dfs:
                validation_df = pd.concat(dfs, ignore_index=True)
                logger.info(f"Carregados {len(validation_df)} registros para validação")
                return validation_df
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados de validação: {e}")
        
        return None
    
    def evaluate_model(self, model_info: Dict, 
                      validation_data: pd.DataFrame) -> Dict:
        """
        Avalia um modelo com dados de validação
        
        Returns:
            Dicionário com métricas de avaliação
        """
        try:
            # Carregar modelo
            with open(model_info['model_path'], 'rb') as f:
                model = pickle.load(f)
            
            # Carregar scaler se disponível
            scaler = None
            if model_info.get('scaler_path') and model_info['scaler_path'].exists():
                with open(model_info['scaler_path'], 'rb') as f:
                    scaler = pickle.load(f)
            
            # Preparar features
            from src.training.smart_retraining_system import SmartRetrainingSystem
            retrainer = SmartRetrainingSystem()
            
            # Verificar se os dados têm a coluna target, senão criar
            if 'target' not in validation_data.columns and 'mid_price' in validation_data.columns:
                validation_data['future_return'] = validation_data['mid_price'].shift(-5).pct_change(5)
                validation_data['target'] = pd.cut(
                    validation_data['future_return'],
                    bins=[-np.inf, -0.0002, 0.0002, np.inf],
                    labels=[0, 1, 2]  # 0: SELL, 1: HOLD, 2: BUY
                )
            
            try:
                X, y = retrainer.prepare_features(validation_data)
            except Exception as e:
                logger.warning(f"Erro ao preparar features: {e}")
                # Fallback: usar validação simples sem re-treinamento
                return {'accuracy': 0.5, 'valid': False, 'error': str(e)}
            
            if len(X) == 0:
                return {'accuracy': 0, 'valid': False}
            
            # Aplicar scaler se disponível
            if scaler:
                X_scaled = scaler.transform(X)
            else:
                X_scaled = X
            
            # Fazer predições
            y_pred = model.predict(X_scaled)
            
            # Calcular métricas
            metrics = {
                'accuracy': accuracy_score(y, y_pred),
                'precision': precision_score(y, y_pred, average='weighted', zero_division=0),
                'recall': recall_score(y, y_pred, average='weighted', zero_division=0),
                'f1_score': f1_score(y, y_pred, average='weighted', zero_division=0),
                'samples_evaluated': len(y),
                'valid': True
            }
            
            # Penalizar modelos muito antigos
            age_penalty = min(model_info['age_days'] / 30, 1.0) * 0.1
            metrics['adjusted_score'] = metrics['accuracy'] * (1 - age_penalty)
            
            logger.info(f"Modelo {model_info['model_path'].name}: "
                       f"Accuracy={metrics['accuracy']:.3f}, "
                       f"F1={metrics['f1_score']:.3f}, "
                       f"Age={model_info['age_days']}d")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Erro ao avaliar modelo {model_info['model_path']}: {e}")
            return {'accuracy': 0, 'valid': False}
    
    def select_best_model(self, force_evaluation: bool = False) -> Optional[Dict]:
        """
        Seleciona o melhor modelo baseado em validação com dados recentes
        
        Args:
            force_evaluation: Forçar re-avaliação mesmo se já foi feita recentemente
            
        Returns:
            Informações do melhor modelo ou None
        """
        logger.info("="*60)
        logger.info("SELEÇÃO AUTOMÁTICA DE MODELO")
        logger.info("="*60)
        
        # Encontrar modelos disponíveis
        available_models = self.find_available_models()
        
        if not available_models:
            logger.error("Nenhum modelo disponível")
            return None
        
        # Carregar dados de validação
        validation_data = self.load_validation_data(hours_back=24)
        
        if validation_data is None or len(validation_data) < 100:
            logger.warning("Dados de validação insuficientes, usando métricas de treinamento")
            # Usar métricas de treinamento como fallback
            best_model = self._select_by_training_metrics(available_models)
        else:
            # Avaliar cada modelo
            logger.info(f"Avaliando {len(available_models)} modelos...")
            
            for model_info in available_models:
                # Pular modelos muito antigos
                if model_info['age_days'] > self.max_model_age_days:
                    logger.info(f"Pulando modelo antigo ({model_info['age_days']} dias)")
                    continue
                
                # Avaliar modelo
                metrics = self.evaluate_model(model_info, validation_data)
                model_info['validation_metrics'] = metrics
                
                # Guardar score
                self.model_scores[str(model_info['model_path'])] = metrics
            
            # Selecionar melhor modelo
            best_model = self._select_best_by_metrics(available_models)
        
        if best_model:
            self.best_model_info = best_model
            
            logger.info("="*60)
            logger.info("[OK] MELHOR MODELO SELECIONADO:")
            logger.info(f"   Arquivo: {best_model['model_path'].name}")
            logger.info(f"   Idade: {best_model['age_days']} dias")
            
            if 'validation_metrics' in best_model:
                metrics = best_model['validation_metrics']
                logger.info(f"   Accuracy: {metrics['accuracy']:.3f}")
                logger.info(f"   F1-Score: {metrics['f1_score']:.3f}")
                logger.info(f"   Score Ajustado: {metrics.get('adjusted_score', 0):.3f}")
            elif 'training_accuracy' in best_model:
                logger.info(f"   Training Accuracy: {best_model['training_accuracy']:.3f}")
            
            logger.info("="*60)
            
            # Salvar seleção
            self._save_selection(best_model)
            
            return best_model
        
        logger.error("Nenhum modelo atende aos critérios mínimos")
        return None
    
    def _select_by_training_metrics(self, models: List[Dict]) -> Optional[Dict]:
        """Seleciona modelo baseado em métricas de treinamento"""
        valid_models = []
        
        for model in models:
            # Pular modelos muito antigos
            if model['age_days'] > self.max_model_age_days:
                continue
                
            # Verificar accuracy de treinamento
            if 'training_accuracy' in model:
                if model['training_accuracy'] >= self.min_accuracy:
                    valid_models.append(model)
            elif model.get('is_original'):
                # Modelos originais têm prioridade menor
                model['training_accuracy'] = self.min_accuracy
                valid_models.append(model)
        
        if not valid_models:
            return None
        
        # Ordenar por accuracy e idade
        valid_models.sort(
            key=lambda x: (x.get('training_accuracy', 0), -x['age_days']), 
            reverse=True
        )
        
        return valid_models[0]
    
    def _select_best_by_metrics(self, models: List[Dict]) -> Optional[Dict]:
        """Seleciona melhor modelo baseado em métricas de validação"""
        valid_models = []
        
        for model in models:
            if 'validation_metrics' not in model:
                continue
                
            metrics = model['validation_metrics']
            if not metrics.get('valid', False):
                continue
                
            # Verificar accuracy mínima
            if metrics['accuracy'] >= self.min_accuracy:
                valid_models.append(model)
        
        if not valid_models:
            # Fallback para métricas de treinamento
            return self._select_by_training_metrics(models)
        
        # Ordenar por score ajustado (considera accuracy e idade)
        valid_models.sort(
            key=lambda x: x['validation_metrics'].get('adjusted_score', 0),
            reverse=True
        )
        
        return valid_models[0]
    
    def _save_selection(self, model_info: Dict):
        """Salva informações do modelo selecionado"""
        selection_file = self.models_dir / "current_model_selection.json"
        
        selection_data = {
            'model_path': str(model_info['model_path']),
            'scaler_path': str(model_info.get('scaler_path', '')),
            'selected_at': datetime.now().isoformat(),
            'age_days': model_info['age_days'],
            'metrics': model_info.get('validation_metrics', {}),
            'training_accuracy': model_info.get('training_accuracy', 0)
        }
        
        with open(selection_file, 'w') as f:
            json.dump(selection_data, f, indent=2, default=str)
        
        logger.info(f"Seleção salva em {selection_file}")
    
    def get_current_best_model(self) -> Optional[Dict]:
        """
        Retorna o modelo atualmente selecionado como melhor
        
        Returns:
            Informações do modelo ou None
        """
        selection_file = self.models_dir / "current_model_selection.json"
        
        if selection_file.exists():
            try:
                with open(selection_file, 'r') as f:
                    selection = json.load(f)
                
                # Verificar se o modelo ainda existe
                model_path = Path(selection['model_path'])
                if model_path.exists():
                    return {
                        'model_path': model_path,
                        'scaler_path': Path(selection.get('scaler_path', '')) 
                                      if selection.get('scaler_path') else None,
                        'metrics': selection.get('metrics', {}),
                        'selected_at': selection.get('selected_at')
                    }
            except Exception as e:
                logger.error(f"Erro ao ler seleção atual: {e}")
        
        return None
    
    def should_reevaluate(self, hours_since_last: int = 24) -> bool:
        """
        Verifica se deve re-avaliar os modelos
        
        Args:
            hours_since_last: Horas desde última avaliação
            
        Returns:
            True se deve re-avaliar
        """
        selection_file = self.models_dir / "current_model_selection.json"
        
        if not selection_file.exists():
            return True
        
        try:
            # Verificar quando foi a última seleção
            last_modified = datetime.fromtimestamp(selection_file.stat().st_mtime)
            hours_passed = (datetime.now() - last_modified).total_seconds() / 3600
            
            return hours_passed >= hours_since_last
            
        except:
            return True
    
    def load_best_model(self) -> Tuple[Optional[Any], Optional[Any]]:
        """
        Carrega o melhor modelo e scaler
        
        Returns:
            (modelo, scaler) ou (None, None) se falhar
        """
        best = self.get_current_best_model()
        
        if not best:
            # Tentar selecionar um modelo
            best = self.select_best_model()
        
        if not best:
            logger.error("Nenhum modelo disponível para carregar")
            return None, None
        
        try:
            # Carregar modelo
            with open(best['model_path'], 'rb') as f:
                model = pickle.load(f)
            
            # Carregar scaler se disponível
            scaler = None
            if best.get('scaler_path') and best['scaler_path'].exists():
                with open(best['scaler_path'], 'rb') as f:
                    scaler = pickle.load(f)
            
            logger.info(f"Modelo carregado: {best['model_path'].name}")
            return model, scaler
            
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            return None, None


def main():
    """Função principal para testes"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Criar seletor
    selector = ModelSelector(
        min_accuracy=0.55,
        max_model_age_days=30
    )
    
    # Selecionar melhor modelo
    best_model = selector.select_best_model(force_evaluation=True)
    
    if best_model:
        print(f"\n[OK] Melhor modelo: {best_model['model_path'].name}")
        
        # Carregar o modelo
        model, scaler = selector.load_best_model()
        if model:
            print("[OK] Modelo carregado com sucesso!")
    else:
        print("\n[ERRO] Nenhum modelo adequado encontrado")


if __name__ == "__main__":
    main()