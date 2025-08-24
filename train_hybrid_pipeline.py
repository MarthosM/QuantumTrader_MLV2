#!/usr/bin/env python3
"""
Pipeline de Treinamento Híbrido - Integra Book, Tick e HMARL
Arquitetura em 3 camadas para sistema completo de trading
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import joblib
import json
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# Imports para ML
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.metrics import accuracy_score, f1_score, classification_report

import lightgbm as lgb
import xgboost as xgb

class HybridTradingPipeline:
    """
    Pipeline completo que integra:
    1. Modelos de Contexto (usando tick data histórico)
    2. Análise de Microestrutura (usando book data)
    3. Meta-Learner (decisão final)
    """
    
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_configs = {}
        
        # Paths
        self.tick_data_path = Path(r"C:\Users\marth\Downloads\WDO_FUT\WDOFUT_BMF_T.csv")
        self.book_data_dir = Path("data/book_tick_data")
        self.models_dir = Path("models/hybrid")
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
    def load_book_data(self) -> pd.DataFrame:
        """Carrega e processa dados de book"""
        print("\n" + "=" * 80)
        print(" CARREGANDO DADOS DE BOOK")
        print("=" * 80)
        
        book_files = sorted(self.book_data_dir.glob('book_data_*.csv'))
        
        if not book_files:
            print("[AVISO] Nenhum arquivo de book encontrado!")
            # Retornar DataFrame vazio com colunas esperadas
            return pd.DataFrame(columns=['timestamp', 'spread', 'imbalance', 
                                        'total_bid_vol', 'total_ask_vol',
                                        'bid_vol_1', 'ask_vol_1', 'mid_price',
                                        'bid_price_1', 'ask_price_1'])
        
        all_data = []
        
        # Carregar todos os arquivos disponíveis
        for i, file in enumerate(book_files):
            try:
                df = pd.read_csv(file)
                if len(df) > 0:
                    all_data.append(df)
                    if (i + 1) % 10 == 0:
                        print(f"  Carregados {i + 1} arquivos...")
            except Exception as e:
                print(f"[AVISO] Erro ao ler {file.name}: {e}")
                continue
        
        if not all_data:
            print("[AVISO] Nenhum dado válido de book encontrado!")
            return pd.DataFrame(columns=['timestamp', 'spread', 'imbalance', 
                                        'total_bid_vol', 'total_ask_vol',
                                        'bid_vol_1', 'ask_vol_1', 'mid_price',
                                        'bid_price_1', 'ask_price_1'])
            
        df_book = pd.concat(all_data, ignore_index=True)
        # Aceitar múltiplos formatos de timestamp
        df_book['timestamp'] = pd.to_datetime(df_book['timestamp'], format='mixed')
        
        print(f"[OK] {len(df_book):,} registros de book carregados")
        return df_book
    
    def load_tick_data(self, sample_size: int = 1_000_000) -> pd.DataFrame:
        """Carrega dados de tick históricos"""
        print("\n" + "=" * 80)
        print(" CARREGANDO DADOS DE TICK")
        print("=" * 80)
        
        # Carregar amostra com nomes corretos
        df_tick = pd.read_csv(
            self.tick_data_path,
            names=['ticker', 'date', 'time', 'trade_number', 'price', 'qty', 
                   'vol', 'buy_agent', 'sell_agent', 'trade_type', 'aft'],
            skiprows=1,  # Pular header
            nrows=sample_size
        )
        
        # Criar timestamp combinando date e time
        df_tick['timestamp'] = pd.to_datetime(
            df_tick['date'].astype(str) + ' ' + df_tick['time'].astype(str).str.zfill(6),
            format='%Y%m%d %H%M%S'
        )
        
        # Renomear colunas para compatibilidade
        df_tick['volume'] = df_tick['qty']
        
        # Criar coluna aggressor (1 se comprador, -1 se vendedor)
        # Simplificação: usar tamanho do buy_agent vs sell_agent como proxy
        df_tick['aggressor'] = np.where(
            df_tick['buy_agent'].str.len() > df_tick['sell_agent'].str.len(),
            1, -1
        )
        
        print(f"[OK] {len(df_tick):,} registros de tick carregados")
        return df_tick
    
    def create_context_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria features de contexto de mercado
        Usadas para identificar regime, volatilidade e padrões macro
        """
        print("\nCriando features de contexto...")
        
        features = pd.DataFrame(index=df.index)
        
        # 1. Regime de Mercado (Trending vs Ranging)
        # SMA crossovers
        features['sma_5'] = df['price'].rolling(5).mean()
        features['sma_20'] = df['price'].rolling(20).mean()
        features['sma_50'] = df['price'].rolling(50).mean()
        features['sma_trend'] = (features['sma_5'] - features['sma_20']) / features['sma_20']
        
        # Momentum
        features['momentum_10'] = df['price'].pct_change(10)
        features['momentum_30'] = df['price'].pct_change(30)
        features['momentum_60'] = df['price'].pct_change(60)
        
        # 2. Volatilidade
        returns = df['price'].pct_change()
        features['volatility_10'] = returns.rolling(10).std()
        features['volatility_30'] = returns.rolling(30).std()
        features['volatility_60'] = returns.rolling(60).std()
        features['volatility_ratio'] = features['volatility_10'] / features['volatility_30']
        
        # ATR (Average True Range)
        high = df['price'].rolling(20).max()
        low = df['price'].rolling(20).min()
        features['atr'] = (high - low) / df['price']
        
        # 3. Volume Profile
        features['volume_ma_10'] = df['volume'].rolling(10).mean()
        features['volume_ma_30'] = df['volume'].rolling(30).mean()
        features['volume_ratio'] = df['volume'] / features['volume_ma_30']
        features['volume_trend'] = features['volume_ma_10'] / features['volume_ma_30']
        
        # 4. Padrões Temporais
        features['hour'] = df['timestamp'].dt.hour
        features['minute'] = df['timestamp'].dt.minute
        features['day_of_week'] = df['timestamp'].dt.dayofweek
        
        # Sessões de trading
        features['session'] = pd.cut(
            features['hour'],
            bins=[0, 11, 14, 24],
            labels=['morning', 'lunch', 'afternoon']
        )
        features['session'] = features['session'].cat.codes
        
        # 5. Microestrutura básica (do tick data)
        features['aggressor_ratio'] = df['aggressor'].rolling(100).mean()
        features['trade_intensity'] = df['volume'].rolling(100).sum()
        
        return features
    
    def create_book_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria features específicas de book (microestrutura)
        """
        print("\nCriando features de book...")
        
        features = pd.DataFrame(index=df.index)
        
        # 1. Spread metrics
        features['spread'] = df['spread']
        features['spread_ma'] = df['spread'].rolling(20).mean()
        features['spread_std'] = df['spread'].rolling(20).std()
        features['spread_normalized'] = (df['spread'] - features['spread_ma']) / features['spread_std']
        
        # 2. Book Imbalance
        features['imbalance'] = df['imbalance']
        features['imbalance_ma'] = df['imbalance'].rolling(20).mean()
        features['imbalance_momentum'] = df['imbalance'].diff(5)
        
        # 3. Volume metrics
        features['book_pressure'] = df['total_bid_vol'] / (df['total_bid_vol'] + df['total_ask_vol'])
        features['volume_at_best'] = df['bid_vol_1'] + df['ask_vol_1']
        features['volume_ratio'] = df['bid_vol_1'] / (df['ask_vol_1'] + 1)
        
        # 4. Price dynamics
        features['mid_price'] = df['mid_price']
        features['mid_return_1'] = df['mid_price'].pct_change(1)
        features['mid_return_5'] = df['mid_price'].pct_change(5)
        features['mid_return_10'] = df['mid_price'].pct_change(10)
        
        # 5. Order flow
        features['bid_change'] = df['bid_vol_1'].diff()
        features['ask_change'] = df['ask_vol_1'].diff()
        features['net_order_flow'] = features['bid_change'] - features['ask_change']
        
        # 6. Microstructure patterns
        features['bid_ask_ratio'] = df['bid_price_1'] / df['ask_price_1']
        features['microprice'] = (
            df['bid_price_1'] * df['ask_vol_1'] + 
            df['ask_price_1'] * df['bid_vol_1']
        ) / (df['bid_vol_1'] + df['ask_vol_1'] + 1)
        
        return features
    
    def create_targets(self, df: pd.DataFrame, feature_col: str = 'mid_price') -> Dict[str, pd.Series]:
        """
        Cria targets para diferentes horizontes de trading
        """
        print("\nCriando targets multi-horizonte...")
        
        targets = {}
        
        # Configurações por horizonte (ajustadas para WDO)
        horizons = {
            'scalping': {'ticks': 10, 'threshold': 0.00001},    # 0.001% (muito sensível)
            'intraday': {'ticks': 50, 'threshold': 0.00005},    # 0.005%
            'swing': {'ticks': 200, 'threshold': 0.0001}        # 0.01%
        }
        
        for name, config in horizons.items():
            future_return = df[feature_col].pct_change(config['ticks']).shift(-config['ticks'])
            
            target = pd.Series(index=df.index, dtype=int)
            target[future_return > config['threshold']] = 1   # BUY
            target[future_return < -config['threshold']] = -1  # SELL
            target.fillna(0, inplace=True)  # HOLD
            
            targets[name] = target
            
            # Estatísticas
            dist = target.value_counts(normalize=True)
            print(f"\n[{name.upper()}]")
            print(f"  Horizonte: {config['ticks']} ticks")
            print(f"  Threshold: ±{config['threshold']*100:.2%}")
            print(f"  Distribuição: SELL={dist.get(-1,0)*100:.1f}%, "
                  f"HOLD={dist.get(0,0)*100:.1f}%, "
                  f"BUY={dist.get(1,0)*100:.1f}%")
        
        return targets
    
    def train_context_models(self, features: pd.DataFrame, targets: Dict[str, pd.Series]):
        """
        Treina modelos de contexto (Camada 1)
        Estes modelos identificam o regime de mercado e condições macro
        """
        print("\n" + "=" * 80)
        print(" TREINAMENTO - CAMADA 1: MODELOS DE CONTEXTO")
        print("=" * 80)
        
        # Usar target de swing para contexto (horizonte maior)
        target = targets['swing']
        
        # Remover NaN
        mask = ~(features.isna().any(axis=1) | target.isna())
        X = features[mask]
        y = target[mask]
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scaler
        scaler = RobustScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Modelos
        models = {}
        
        # 1. Regime Detector (Random Forest)
        print("\n[1/3] Treinando Regime Detector...")
        rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        rf_model.fit(X_train_scaled, y_train)
        models['regime_detector'] = rf_model
        
        # Avaliar
        y_pred = rf_model.predict(X_test_scaled)
        acc = accuracy_score(y_test, y_pred)
        print(f"  Acurácia: {acc*100:.2f}%")
        
        # 2. Volatility Forecaster (LightGBM)
        print("\n[2/3] Treinando Volatility Forecaster...")
        lgb_model = lgb.LGBMClassifier(
            n_estimators=100,
            max_depth=7,
            learning_rate=0.05,
            random_state=42,
            verbosity=-1
        )
        lgb_model.fit(X_train_scaled, y_train)
        models['volatility_forecaster'] = lgb_model
        
        y_pred = lgb_model.predict(X_test_scaled)
        acc = accuracy_score(y_test, y_pred)
        print(f"  Acurácia: {acc*100:.2f}%")
        
        # 3. Session Classifier (XGBoost)
        print("\n[3/3] Treinando Session Classifier...")
        # Mapear labels para XGBoost
        label_map = {-1: 0, 0: 1, 1: 2}
        y_train_xgb = pd.Series(y_train).map(label_map)
        y_test_xgb = pd.Series(y_test).map(label_map)
        
        xgb_model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=7,
            learning_rate=0.05,
            random_state=42,
            verbosity=0
        )
        xgb_model.fit(X_train_scaled, y_train_xgb)
        models['session_classifier'] = {
            'model': xgb_model,
            'label_map': label_map,
            'inverse_map': {0: -1, 1: 0, 2: 1}
        }
        
        y_pred = xgb_model.predict(X_test_scaled)
        # Mapear de volta
        y_pred = pd.Series(y_pred).map({0: -1, 1: 0, 2: 1})
        acc = accuracy_score(y_test, y_pred)
        print(f"  Acurácia: {acc*100:.2f}%")
        
        # Salvar
        self.models['context'] = models
        self.scalers['context'] = scaler
        
        # Feature importance
        print("\n[FEATURE IMPORTANCE - TOP 10]")
        importance = pd.Series(
            rf_model.feature_importances_,
            index=X.columns
        ).sort_values(ascending=False)
        
        for i, (feat, imp) in enumerate(importance.head(10).items(), 1):
            print(f"  {i:2d}. {feat}: {imp:.4f}")
        
        return models
    
    def train_microstructure_models(self, features: pd.DataFrame, targets: Dict[str, pd.Series]):
        """
        Treina modelos de microestrutura (Camada 2)
        Estes modelos analisam book dynamics e order flow
        """
        print("\n" + "=" * 80)
        print(" TREINAMENTO - CAMADA 2: MODELOS DE MICROESTRUTURA")
        print("=" * 80)
        
        # Usar target de scalping para microestrutura (horizonte curto)
        target = targets['scalping']
        
        # Remover NaN
        mask = ~(features.isna().any(axis=1) | target.isna())
        X = features[mask]
        y = target[mask]
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scaler
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Modelos
        models = {}
        
        # 1. Order Flow Analyzer (LightGBM)
        print("\n[1/2] Treinando Order Flow Analyzer...")
        lgb_model = lgb.LGBMClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.03,
            random_state=42,
            verbosity=-1
        )
        lgb_model.fit(X_train_scaled, y_train)
        models['order_flow_analyzer'] = lgb_model
        
        y_pred = lgb_model.predict(X_test_scaled)
        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average='weighted')
        print(f"  Acurácia: {acc*100:.2f}%")
        print(f"  F1 Score: {f1:.3f}")
        
        # 2. Book Dynamics Model (Extra Trees)
        print("\n[2/2] Treinando Book Dynamics Model...")
        et_model = ExtraTreesClassifier(
            n_estimators=200,
            max_depth=8,
            random_state=42,
            n_jobs=-1
        )
        et_model.fit(X_train_scaled, y_train)
        models['book_dynamics'] = et_model
        
        y_pred = et_model.predict(X_test_scaled)
        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average='weighted')
        print(f"  Acurácia: {acc*100:.2f}%")
        print(f"  F1 Score: {f1:.3f}")
        
        # Salvar
        self.models['microstructure'] = models
        self.scalers['microstructure'] = scaler
        
        # Feature importance
        print("\n[FEATURE IMPORTANCE - TOP 10]")
        importance = pd.Series(
            lgb_model.feature_importances_,
            index=X.columns
        ).sort_values(ascending=False)
        
        for i, (feat, imp) in enumerate(importance.head(10).items(), 1):
            print(f"  {i:2d}. {feat}: {imp:.4f}")
        
        return models
    
    def train_meta_learner(self, context_preds: np.ndarray, micro_preds: np.ndarray, 
                           target: pd.Series):
        """
        Treina Meta-Learner (Camada 3)
        Combina predições das camadas 1 e 2 para decisão final
        """
        print("\n" + "=" * 80)
        print(" TREINAMENTO - CAMADA 3: META-LEARNER")
        print("=" * 80)
        
        # Criar features do meta-learner
        meta_features = pd.DataFrame({
            'context_pred': context_preds,
            'micro_pred': micro_preds,
            'agreement': (context_preds == micro_preds).astype(int),
            'confidence_gap': np.abs(context_preds - micro_preds)
        })
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            meta_features, target, test_size=0.2, random_state=42
        )
        
        # Meta model (Random Forest)
        print("\nTreinando Meta-Learner...")
        meta_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            random_state=42,
            n_jobs=-1
        )
        meta_model.fit(X_train, y_train)
        
        # Avaliar
        y_pred = meta_model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average='weighted')
        
        print(f"  Acurácia Final: {acc*100:.2f}%")
        print(f"  F1 Score Final: {f1:.3f}")
        
        # Confusion matrix
        print("\n[CLASSIFICATION REPORT]")
        print(classification_report(y_test, y_pred, 
                                   target_names=['SELL', 'HOLD', 'BUY']))
        
        self.models['meta_learner'] = meta_model
        
        return meta_model
    
    def save_models(self):
        """Salva todos os modelos treinados"""
        print("\n" + "=" * 80)
        print(" SALVANDO MODELOS")
        print("=" * 80)
        
        # Salvar modelos
        for layer_name, models in self.models.items():
            layer_dir = self.models_dir / layer_name
            layer_dir.mkdir(parents=True, exist_ok=True)
            
            if isinstance(models, dict):
                for model_name, model in models.items():
                    model_path = layer_dir / f"{model_name}.pkl"
                    joblib.dump(model, model_path)
                    print(f"  Salvando: {model_path}")
            else:
                model_path = layer_dir / f"{layer_name}.pkl"
                joblib.dump(models, model_path)
                print(f"  Salvando: {model_path}")
        
        # Salvar scalers
        for scaler_name, scaler in self.scalers.items():
            scaler_path = self.models_dir / f"scaler_{scaler_name}.pkl"
            joblib.dump(scaler, scaler_path)
            print(f"  Salvando: {scaler_path}")
        
        # Salvar configurações
        config = {
            'timestamp': datetime.now().isoformat(),
            'layers': list(self.models.keys()),
            'scalers': list(self.scalers.keys())
        }
        
        config_path = self.models_dir / 'config.json'
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"  Salvando: {config_path}")
        
    def run_complete_pipeline(self):
        """Executa o pipeline completo de treinamento"""
        
        print("\n" + "=" * 80)
        print(" PIPELINE HÍBRIDO DE TREINAMENTO")
        print("=" * 80)
        print("\nArquitetura:")
        print("  Camada 1: Modelos de Contexto (tick data)")
        print("  Camada 2: Modelos de Microestrutura (book data)")
        print("  Camada 3: Meta-Learner (decisão final)")
        
        # 1. Carregar dados
        df_tick = self.load_tick_data(sample_size=500_000)
        df_book = self.load_book_data()
        
        # Verificar se temos dados de book
        if len(df_book) == 0:
            print("\n[AVISO] Sem dados de book. Treinando apenas com tick data...")
            # Criar features apenas de tick
            context_features = self.create_context_features(df_tick)
            tick_targets = self.create_targets(df_tick, 'price')
            
            # Treinar apenas modelos de contexto
            context_models = self.train_context_models(context_features, tick_targets)
            
            # Salvar
            self.save_models()
            
            print("\n[AVISO] Pipeline parcial completado (apenas Camada 1)")
            return
        
        # 2. Criar features
        context_features = self.create_context_features(df_tick)
        book_features = self.create_book_features(df_book)
        
        # 3. Criar targets
        tick_targets = self.create_targets(df_tick, 'price')
        book_targets = self.create_targets(df_book, 'mid_price')
        
        # 4. Treinar Camada 1 (Contexto)
        context_models = self.train_context_models(context_features, tick_targets)
        
        # 5. Treinar Camada 2 (Microestrutura)
        micro_models = self.train_microstructure_models(book_features, book_targets)
        
        # 6. Criar predições para meta-learner (usando subset comum)
        # Aqui usaríamos dados sincronizados, mas para demo vamos simular
        print("\n" + "=" * 80)
        print(" PREPARANDO META-LEARNER")
        print("=" * 80)
        
        # Simular predições das camadas 1 e 2
        # Pegar features limpas
        context_clean = context_features.dropna()
        book_clean = book_features.dropna()
        
        # Determinar tamanho comum
        n_samples = min(len(context_clean), len(book_clean))
        n_samples = min(n_samples, 10000)  # Limitar para teste
        
        # Alinhar os dados
        context_clean = context_clean[:n_samples]
        book_clean = book_clean[:n_samples]
        
        # Fazer predições
        context_pred = context_models['regime_detector'].predict(
            self.scalers['context'].transform(context_clean)
        )
        
        micro_pred = micro_models['order_flow_analyzer'].predict(
            self.scalers['microstructure'].transform(book_clean)
        )
        
        # Target comum (usar o de book para simplicidade)
        target_meta = book_targets['scalping'].dropna()[:n_samples]
        
        # 7. Treinar Meta-Learner
        meta_model = self.train_meta_learner(context_pred, micro_pred, target_meta)
        
        # 8. Salvar modelos
        self.save_models()
        
        print("\n" + "=" * 80)
        print(" PIPELINE COMPLETO!")
        print("=" * 80)
        print("\n[RESUMO]")
        print(f"  Modelos de Contexto: {len(self.models.get('context', {}))}")
        print(f"  Modelos de Microestrutura: {len(self.models.get('microstructure', {}))}")
        print(f"  Meta-Learner: {'OK' if 'meta_learner' in self.models else 'FALHOU'}")
        print(f"\n  Todos os modelos salvos em: {self.models_dir}")
        

def main():
    """Função principal"""
    
    pipeline = HybridTradingPipeline()
    
    try:
        pipeline.run_complete_pipeline()
        
        print("\n" + "=" * 80)
        print(" SUCESSO!")
        print("=" * 80)
        print("\nPróximos passos:")
        print("  1. Validar modelos com dados out-of-sample")
        print("  2. Integrar com sistema HMARL")
        print("  3. Testar em paper trading")
        print("  4. Deploy em produção")
        
    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()