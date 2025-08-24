"""
Sistema Inteligente de Re-treinamento
Verifica qualidade e continuidade dos dados antes de treinar
Concatena dados de múltiplos dias se forem contínuos
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging
import json
import pickle
from typing import Dict, List, Tuple, Optional
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class SmartRetrainingSystem:
    """Sistema inteligente de re-treinamento com validação de dados"""
    
    def __init__(self, data_dir: str = "data/book_tick_data", 
                 models_dir: str = "models",
                 min_samples: int = 5000,
                 min_hours: float = 8.0,  # Aumentado para 8 horas mínimas
                 max_gap_minutes: int = 5):
        """
        Args:
            data_dir: Diretório com dados coletados
            models_dir: Diretório para salvar modelos
            min_samples: Mínimo de amostras para treinar
            min_hours: Mínimo de horas contínuas de dados (8h padrão)
            max_gap_minutes: Máximo de minutos de gap para considerar contínuo
        """
        self.data_dir = Path(data_dir)
        self.models_dir = Path(models_dir)
        self.min_samples = min_samples
        self.min_hours = min_hours
        self.max_gap_minutes = max_gap_minutes
        
        # Criar diretórios se não existirem
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # Estatísticas de validação
        self.validation_stats = {
            'total_files': 0,
            'valid_files': 0,
            'total_samples': 0,
            'valid_samples': 0,
            'continuous_segments': [],
            'gaps_found': [],
            'data_quality_score': 0.0
        }
        
    def check_data_continuity(self, df: pd.DataFrame, 
                             timestamp_col: str = 'timestamp') -> List[Tuple[datetime, datetime]]:
        """
        Verifica continuidade dos dados e retorna segmentos contínuos
        
        Returns:
            Lista de tuplas (início, fim) de cada segmento contínuo
        """
        if df.empty:
            return []
            
        # Converter timestamp para datetime se necessário
        if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            df[timestamp_col] = pd.to_datetime(df[timestamp_col])
            
        # Ordenar por timestamp
        df = df.sort_values(timestamp_col)
        
        # Calcular diferenças entre timestamps consecutivos
        time_diffs = df[timestamp_col].diff()
        
        # Identificar gaps (diferenças maiores que max_gap_minutes)
        gap_threshold = pd.Timedelta(minutes=self.max_gap_minutes)
        gaps = time_diffs > gap_threshold
        
        # Encontrar segmentos contínuos
        segments = []
        segment_start = df[timestamp_col].iloc[0]
        
        for i, has_gap in enumerate(gaps):
            if has_gap:
                # Fim do segmento atual
                segment_end = df[timestamp_col].iloc[i-1]
                segments.append((segment_start, segment_end))
                
                # Registrar gap
                gap_duration = time_diffs.iloc[i].total_seconds() / 60
                self.validation_stats['gaps_found'].append({
                    'timestamp': df[timestamp_col].iloc[i],
                    'gap_minutes': gap_duration
                })
                
                # Início do novo segmento
                segment_start = df[timestamp_col].iloc[i]
        
        # Adicionar último segmento
        segment_end = df[timestamp_col].iloc[-1]
        segments.append((segment_start, segment_end))
        
        # Filtrar segmentos muito curtos
        min_segment_duration = pd.Timedelta(minutes=30)
        valid_segments = []
        
        for start, end in segments:
            duration = end - start
            if duration >= min_segment_duration:
                valid_segments.append((start, end))
                self.validation_stats['continuous_segments'].append({
                    'start': start.isoformat(),
                    'end': end.isoformat(),
                    'duration_hours': duration.total_seconds() / 3600,
                    'samples': len(df[(df[timestamp_col] >= start) & 
                                    (df[timestamp_col] <= end)])
                })
        
        return valid_segments
    
    def filter_trading_hours(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filtra dados apenas do horário de trading (9:00 às 18:00)
        
        Args:
            df: DataFrame com coluna timestamp
            
        Returns:
            DataFrame filtrado
        """
        if 'timestamp' not in df.columns:
            return df
        
        # Converter timestamp para datetime se necessário
        if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
            # Tentar diferentes formatos de data
            try:
                df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
            except:
                try:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
                except:
                    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        
        # Filtrar horário de trading (9:00 às 18:00)
        df['hour'] = df['timestamp'].dt.hour
        df_filtered = df[(df['hour'] >= 9) & (df['hour'] < 18)].copy()
        df_filtered = df_filtered.drop('hour', axis=1)
        
        logger.info(f"Filtrado horário de trading: {len(df)} -> {len(df_filtered)} amostras")
        return df_filtered
    
    def load_and_validate_data(self, days_back: int = 7) -> Optional[pd.DataFrame]:
        """
        Carrega e valida dados dos últimos N dias (apenas horário de trading)
        
        Returns:
            DataFrame concatenado e validado ou None se dados insuficientes
        """
        logger.info(f"Carregando dados dos últimos {days_back} dias...")
        
        # Resetar estatísticas
        self.validation_stats = {
            'total_files': 0,
            'valid_files': 0,
            'total_samples': 0,
            'valid_samples': 0,
            'continuous_segments': [],
            'gaps_found': [],
            'data_quality_score': 0.0
        }
        
        # Buscar arquivos dos últimos N dias
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        all_data = []
        
        for file_path in self.data_dir.glob("*.csv"):
            self.validation_stats['total_files'] += 1
            
            # Verificar se o arquivo é do período desejado
            try:
                # Extrair data do nome do arquivo (assumindo formato com data)
                file_date_str = file_path.stem.split('_')[-1][:8]  # YYYYMMDD
                file_date = datetime.strptime(file_date_str, "%Y%m%d")
                
                if file_date < start_date.replace(hour=0, minute=0, second=0):
                    continue
                    
            except:
                # Se não conseguir extrair data, usar data de modificação
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < start_date:
                    continue
            
            # Carregar arquivo
            try:
                df = pd.read_csv(file_path)
                
                if len(df) > 0:
                    self.validation_stats['valid_files'] += 1
                    self.validation_stats['total_samples'] += len(df)
                    all_data.append(df)
                    logger.info(f"Carregado: {file_path.name} ({len(df)} amostras)")
                    
            except Exception as e:
                logger.warning(f"Erro ao carregar {file_path.name}: {e}")
                continue
        
        if not all_data:
            logger.warning("Nenhum dado válido encontrado")
            return None
        
        # Concatenar todos os dados
        combined_df = pd.concat(all_data, ignore_index=True)
        
        # Remover duplicatas baseadas em timestamp
        if 'timestamp' in combined_df.columns:
            combined_df = combined_df.drop_duplicates(subset=['timestamp'])
            combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)
        
        logger.info(f"Total de amostras após concatenação: {len(combined_df)}")
        
        # Filtrar apenas horário de trading (9:00 às 18:00)
        combined_df = self.filter_trading_hours(combined_df)
        
        # Verificar continuidade
        segments = self.check_data_continuity(combined_df)
        
        # Calcular tempo total contínuo
        total_continuous_hours = sum(
            (end - start).total_seconds() / 3600 
            for start, end in segments
        )
        
        # Validar dados
        is_valid = self.validate_data_quality(
            combined_df, 
            total_continuous_hours
        )
        
        if is_valid:
            self.validation_stats['valid_samples'] = len(combined_df)
            logger.info(f"[OK] Dados validados: {len(combined_df)} amostras, "
                       f"{total_continuous_hours:.1f} horas contínuas")
            return combined_df
        else:
            logger.warning(f"[X] Dados insuficientes ou fragmentados")
            return None
    
    def validate_data_quality(self, df: pd.DataFrame, 
                             continuous_hours: float) -> bool:
        """
        Valida qualidade dos dados para re-treinamento
        
        Returns:
            True se dados são adequados para treinar
        """
        quality_checks = {
            'min_samples': len(df) >= self.min_samples,
            'min_hours': continuous_hours >= self.min_hours,
            'has_features': self.check_required_features(df),
            'has_variance': self.check_data_variance(df),
            'balanced_classes': self.check_class_balance(df)
        }
        
        # Log detalhado das validações
        logger.info("Verificações de qualidade:")
        logger.info(f"  - Mínimo de amostras ({self.min_samples}): {'OK' if quality_checks['min_samples'] else 'X'} ({len(df)} amostras)")
        logger.info(f"  - Mínimo de horas ({self.min_hours}h): {'OK' if quality_checks['min_hours'] else 'X'} ({continuous_hours:.1f}h contínuas)")
        logger.info(f"  - Features necessárias: {'OK' if quality_checks['has_features'] else 'X'}")
        logger.info(f"  - Variância nos dados: {'OK' if quality_checks['has_variance'] else 'X'}")
        logger.info(f"  - Classes balanceadas: {'OK' if quality_checks['balanced_classes'] else 'X'}")
        
        # Calcular score de qualidade
        passed_checks = sum(quality_checks.values())
        total_checks = len(quality_checks)
        self.validation_stats['data_quality_score'] = passed_checks / total_checks
        
        # Log detalhado
        logger.info("=== Validação de Qualidade dos Dados ===")
        for check, passed in quality_checks.items():
            status = "[OK]" if passed else "[X]"
            logger.info(f"{status} {check}: {passed}")
        
        logger.info(f"Score de qualidade: {self.validation_stats['data_quality_score']:.1%}")
        
        # Requer pelo menos 80% dos checks passando
        return self.validation_stats['data_quality_score'] >= 0.8
    
    def check_required_features(self, df: pd.DataFrame) -> bool:
        """Verifica se todas as features necessárias estão presentes"""
        required_features = [
            'mid_price', 'spread', 'imbalance', 
            'bid_volume_total', 'ask_volume_total'
        ]
        
        return all(col in df.columns for col in required_features)
    
    def check_data_variance(self, df: pd.DataFrame) -> bool:
        """Verifica se dados têm variância suficiente (não são constantes)"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if len(numeric_cols) == 0:
            return False
        
        # Verificar se pelo menos 80% das colunas têm variância
        cols_with_variance = 0
        for col in numeric_cols:
            if df[col].std() > 0:
                cols_with_variance += 1
        
        return (cols_with_variance / len(numeric_cols)) >= 0.8
    
    def check_class_balance(self, df: pd.DataFrame, 
                           target_col: str = 'target') -> bool:
        """Verifica balanceamento das classes para classificação"""
        if target_col not in df.columns:
            # Se não tem target, criar baseado em retornos
            if 'mid_price' in df.columns:
                df['returns'] = df['mid_price'].pct_change()
                df[target_col] = pd.cut(
                    df['returns'], 
                    bins=[-np.inf, -0.0001, 0.0001, np.inf],
                    labels=[-1, 0, 1]
                )
            else:
                return True  # Assumir OK se não conseguir calcular
        
        if target_col not in df.columns:
            return True
            
        # Verificar distribuição das classes
        class_dist = df[target_col].value_counts(normalize=True)
        
        # Nenhuma classe deve ter menos de 10% das amostras
        min_class_ratio = class_dist.min()
        
        return min_class_ratio >= 0.1
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepara features e target para treinamento
        """
        # Features de microestrutura
        feature_cols = [
            'spread', 'imbalance', 'bid_volume_total', 'ask_volume_total',
            'book_pressure', 'volume_at_best'
        ]
        
        # Adicionar features técnicas se disponíveis
        technical_features = ['rsi_14', 'volatility_20', 'volume_mean']
        for feat in technical_features:
            if feat in df.columns:
                feature_cols.append(feat)
        
        # Filtrar apenas colunas existentes
        available_features = [col for col in feature_cols if col in df.columns]
        
        # Criar target baseado em retornos futuros
        if 'mid_price' in df.columns:
            df['future_return'] = df['mid_price'].shift(-5).pct_change(5)
            df['target'] = pd.cut(
                df['future_return'],
                bins=[-np.inf, -0.0002, 0.0002, np.inf],
                labels=[0, 1, 2]  # 0: SELL, 1: HOLD, 2: BUY
            )
        
        # Remover NaN
        df_clean = df[available_features + ['target']].dropna()
        
        X = df_clean[available_features]
        y = df_clean['target']
        
        return X, y
    
    def retrain_models(self, X: pd.DataFrame, y: pd.Series) -> Dict:
        """
        Re-treina modelos com novos dados
        """
        logger.info("Iniciando re-treinamento dos modelos...")
        
        # Split treino/teste
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Normalização
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Treinar modelo
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=20,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_train_scaled, y_train)
        
        # Avaliar
        y_pred = model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        
        logger.info(f"Accuracy no teste: {accuracy:.2%}")
        logger.info("\nRelatório de classificação:")
        logger.info(classification_report(y_test, y_pred))
        
        # Salvar modelo e scaler
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        model_path = self.models_dir / f"retrained_model_{timestamp}.pkl"
        scaler_path = self.models_dir / f"retrained_scaler_{timestamp}.pkl"
        
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        with open(scaler_path, 'wb') as f:
            pickle.dump(scaler, f)
        
        logger.info(f"[OK] Modelos salvos em {self.models_dir}")
        
        return {
            'model_path': str(model_path),
            'scaler_path': str(scaler_path),
            'accuracy': accuracy,
            'timestamp': timestamp,
            'samples_used': len(X),
            'features': list(X.columns)
        }
    
    def should_retrain(self) -> bool:
        """
        Decide se deve fazer re-treinamento baseado em critérios
        """
        # Verificar horário (após fechamento do mercado)
        now = datetime.now()
        is_after_market = now.hour >= 18
        
        # Verificar se já treinou hoje
        today = now.date()
        latest_model = None
        
        for model_file in self.models_dir.glob("retrained_model_*.pkl"):
            model_date_str = model_file.stem.split('_')[2]  # YYYYMMDD
            try:
                model_date = datetime.strptime(model_date_str, "%Y%m%d").date()
                if model_date == today:
                    latest_model = model_file
                    break
            except:
                continue
        
        already_trained_today = latest_model is not None
        
        # Decisão
        should_train = is_after_market and not already_trained_today
        
        logger.info(f"Verificação de re-treinamento:")
        logger.info(f"  - Após fechamento: {is_after_market}")
        logger.info(f"  - Já treinou hoje: {already_trained_today}")
        logger.info(f"  - Deve treinar: {should_train}")
        
        return should_train
    
    def run_retraining_pipeline(self, force: bool = False) -> Optional[Dict]:
        """
        Pipeline completo de re-treinamento
        
        Args:
            force: Forçar treinamento mesmo se não for horário ideal
            
        Returns:
            Informações do treinamento ou None se não treinou
        """
        logger.info("="*60)
        logger.info("INICIANDO PIPELINE DE RE-TREINAMENTO")
        logger.info("="*60)
        
        # Verificar se deve treinar
        if not force and not self.should_retrain():
            logger.info("Re-treinamento não necessário no momento")
            return None
        
        # Carregar e validar dados
        df = self.load_and_validate_data(days_back=7)
        
        if df is None:
            logger.error("Dados insuficientes para re-treinamento")
            self.save_validation_report()
            return None
        
        # Preparar features
        try:
            X, y = self.prepare_features(df)
        except Exception as e:
            logger.error(f"Erro ao preparar features: {e}")
            return None
        
        # Re-treinar modelos
        try:
            results = self.retrain_models(X, y)
            results['validation_stats'] = self.validation_stats
            
            # Salvar relatório
            self.save_training_report(results)
            
            logger.info("="*60)
            logger.info("[OK] RE-TREINAMENTO CONCLUÍDO COM SUCESSO")
            logger.info("="*60)
            
            return results
            
        except Exception as e:
            logger.error(f"Erro durante re-treinamento: {e}")
            return None
    
    def save_validation_report(self):
        """Salva relatório de validação dos dados"""
        report_path = self.models_dir / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_path, 'w') as f:
            json.dump(self.validation_stats, f, indent=2, default=str)
        
        logger.info(f"Relatório de validação salvo em {report_path}")
    
    def save_training_report(self, results: Dict):
        """Salva relatório do treinamento"""
        report_path = self.models_dir / f"training_report_{results['timestamp']}.json"
        
        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Relatório de treinamento salvo em {report_path}")


def main():
    """Função principal para testes"""
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Criar sistema de re-treinamento
    retrainer = SmartRetrainingSystem(
        min_samples=5000,
        min_hours=4.0,
        max_gap_minutes=5
    )
    
    # Executar pipeline
    results = retrainer.run_retraining_pipeline(force=True)
    
    if results:
        print(f"\n[OK] Re-treinamento bem-sucedido!")
        print(f"Accuracy: {results['accuracy']:.2%}")
        print(f"Amostras usadas: {results['samples_used']}")
    else:
        print("\n[X] Re-treinamento não foi possível")


if __name__ == "__main__":
    main()