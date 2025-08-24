#!/usr/bin/env python3
"""
Sistema de Treinamento para WDO Futures
Baseado no sistema original mas otimizado para 216M de registros
Seleção automática das melhores features
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
import xgboost as xgb
import lightgbm as lgb
import joblib
import gc
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')


class WDOModelTrainer:
    """
    Sistema otimizado de treinamento para WDO
    - Trabalha com amostras grandes (5-10M registros)
    - Seleção automática de features
    - Múltiplos horizontes de predição
    """
    
    def __init__(self, csv_path: str = "C:/Users/marth/Downloads/WDO_FUT/WDOFUT_BMF_T.csv"):
        self.csv_path = Path(csv_path)
        self.sample_size = 5_000_000  # 5M para treino inicial
        self.models = {}
        self.results = {}
        self.scaler = StandardScaler()
        self.selected_features = []
        
        # Múltiplos horizontes para diferentes estratégias
        self.horizons = {
            'scalping': 100,     # ~30 segundos
            'intraday': 500,     # ~2-5 minutos  
            'swing': 2000        # ~10-20 minutos
        }
        
    def load_and_prepare_data(self, sample_size: int = None):
        """Carrega dados com otimização de memória"""
        
        if sample_size:
            self.sample_size = sample_size
            
        print("=" * 80)
        print(f" CARREGANDO {self.sample_size:,} REGISTROS DE WDO")
        print("=" * 80)
        
        # Tipos otimizados para economia de memória
        dtypes = {
            '<ticker>': 'category',
            '<date>': 'uint32',
            '<time>': 'uint32',
            '<trade_number>': 'uint32',
            '<price>': 'float32',
            '<qty>': 'uint16',
            '<vol>': 'float32',
            '<buy_agent>': 'category',
            '<sell_agent>': 'category',
            '<trade_type>': 'category',
            '<aft>': 'category'
        }
        
        print(f"\nCarregando dados de: {self.csv_path}")
        start_time = datetime.now()
        
        # Usar skiprows para pegar dados aleatórios se arquivo muito grande
        total_lines = 216_000_000  # Conhecido do arquivo
        
        if self.sample_size < total_lines:
            # Pegar amostra distribuída
            skip_interval = total_lines // self.sample_size
            skip_rows = lambda x: x != 0 and x % skip_interval != 0
            
            df = pd.read_csv(
                self.csv_path,
                dtype=dtypes,
                skiprows=skip_rows,
                nrows=self.sample_size
            )
        else:
            df = pd.read_csv(self.csv_path, dtype=dtypes, nrows=self.sample_size)
        
        # Processar timestamps
        print("Processando timestamps...")
        df['timestamp'] = pd.to_datetime(
            df['<date>'].astype(str) + ' ' + df['<time>'].astype(str).str.zfill(6),
            format='%Y%m%d %H%M%S'
        )
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        load_time = (datetime.now() - start_time).total_seconds()
        
        print(f"\n[OK] Dados carregados em {load_time:.1f}s")
        print(f"[OK] Período: {df['timestamp'].min()} até {df['timestamp'].max()}")
        print(f"[OK] Preço médio: R$ {df['<price>'].mean():.2f}")
        
        return df
    
    def create_optimized_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria features otimizadas com base em análise de microestrutura
        Foco em features que realmente predizem movimento futuro
        """
        
        print("\n" + "=" * 80)
        print(" CRIAÇÃO DE FEATURES OTIMIZADAS")
        print("=" * 80)
        
        features = pd.DataFrame(index=df.index)
        price = df['<price>'].values.astype('float32')
        qty = df['<qty>'].values.astype('float32')
        vol = df['<vol>'].values.astype('float32')
        
        # =================================================================
        # 1. FEATURES DE RETORNO E MOMENTUM (Mais importantes)
        # =================================================================
        print("\n[1/8] Calculando retornos e momentum...")
        
        # Retornos multi-período (sem lookahead)
        for period in [1, 2, 5, 10, 20, 50, 100, 200]:
            features[f'return_{period}'] = pd.Series(price).pct_change(period)
            
        # Log returns para capturar não-linearidades
        features['log_return_1'] = np.log(price / np.roll(price, 1))
        features['log_return_5'] = np.log(price / np.roll(price, 5))
        features['log_return_20'] = np.log(price / np.roll(price, 20))
        
        # Momentum
        features['momentum_5_20'] = features['return_5'] - features['return_20']
        features['momentum_20_50'] = features['return_20'] - features['return_50']
        
        # =================================================================
        # 2. VOLATILIDADE E RISCO
        # =================================================================
        print("[2/8] Calculando volatilidade...")
        
        for window in [10, 20, 50, 100]:
            # Volatilidade realizada
            features[f'volatility_{window}'] = features['return_1'].rolling(window).std()
            
            # Volatilidade relativa
            features[f'vol_ratio_{window}'] = (
                features[f'volatility_{window}'] / 
                features[f'volatility_{window}'].rolling(window*2).mean()
            ).fillna(1)
            
        # Garman-Klass (aproximado com high-low do período)
        for window in [20, 50]:
            high = pd.Series(price).rolling(window).max()
            low = pd.Series(price).rolling(window).min()
            features[f'gk_vol_{window}'] = np.sqrt(
                (np.log(high/low)**2) / (4 * np.log(2))
            )
        
        # =================================================================
        # 3. MICROESTRUTURA E ORDER FLOW
        # =================================================================
        print("[3/8] Calculando order flow...")
        
        # Volume imbalance
        buy_volume = np.where(
            pd.Series(price).diff() > 0, qty, 0
        )
        sell_volume = np.where(
            pd.Series(price).diff() < 0, qty, 0
        )
        
        for window in [20, 50, 100]:
            buy_sum = pd.Series(buy_volume).rolling(window).sum()
            sell_sum = pd.Series(sell_volume).rolling(window).sum()
            total_vol = buy_sum + sell_sum
            
            features[f'volume_imbalance_{window}'] = (
                (buy_sum - sell_sum) / total_vol.clip(lower=1)
            )
            
        # Trade intensity
        features['trade_intensity'] = pd.Series(qty).rolling(50).sum() / 50
        features['trade_intensity_ratio'] = (
            features['trade_intensity'] / 
            features['trade_intensity'].rolling(200).mean()
        ).fillna(1)
        
        # =================================================================
        # 4. ANÁLISE DE AGENTES (Único no tick data)
        # =================================================================
        print("[4/8] Analisando comportamento de agentes...")
        
        # Identificar agentes institucionais (top brokers)
        top_agents = ['XP', 'BTG', 'Itau', 'Credit', 'Morgan', 'UBS', 'Goldman']
        
        # Fluxo institucional
        institutional_buy = df['<buy_agent>'].isin(top_agents).astype(int) * qty
        institutional_sell = df['<sell_agent>'].isin(top_agents).astype(int) * qty
        
        for window in [50, 100, 200]:
            features[f'institutional_flow_{window}'] = (
                pd.Series(institutional_buy).rolling(window).sum() -
                pd.Series(institutional_sell).rolling(window).sum()
            )
            
        # Diversidade de agentes - simplificado para performance
        # Contar agentes únicos em janelas maiores para evitar loop
        # (Feature removida temporariamente para otimização)
        
        # =================================================================
        # 5. INDICADORES TÉCNICOS ADAPTADOS
        # =================================================================
        print("[5/8] Calculando indicadores técnicos...")
        
        # RSI
        for period in [14, 21]:
            delta = pd.Series(price).diff()
            gain = (delta.where(delta > 0, 0)).rolling(period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
            rs = gain / loss.clip(lower=0.0001)
            features[f'rsi_{period}'] = 100 - (100 / (1 + rs))
            
        # Bollinger Bands
        for period in [20, 50]:
            sma = pd.Series(price).rolling(period).mean()
            std = pd.Series(price).rolling(period).std()
            features[f'bb_position_{period}'] = (price - sma) / (2 * std)
            features[f'bb_width_{period}'] = (4 * std) / sma
            
        # =================================================================
        # 6. PADRÕES DE VOLUME E LIQUIDEZ
        # =================================================================
        print("[6/8] Analisando padrões de volume...")
        
        # VWAP
        cumvol = pd.Series(vol).rolling(200).sum()
        cumqty = pd.Series(qty).rolling(200).sum()
        vwap = (cumvol / cumqty.clip(lower=1))
        features['price_vwap_ratio'] = price / vwap.fillna(method='ffill')
        
        # Volume profile
        for window in [50, 100]:
            vol_mean = pd.Series(qty).rolling(window).mean()
            vol_std = pd.Series(qty).rolling(window).std()
            features[f'volume_zscore_{window}'] = (
                (qty - vol_mean) / vol_std.clip(lower=0.001)
            )
            
        # =================================================================
        # 7. FEATURES TEMPORAIS
        # =================================================================
        print("[7/8] Adicionando features temporais...")
        
        features['hour'] = df['timestamp'].dt.hour
        features['minute'] = df['timestamp'].dt.minute
        features['day_of_week'] = df['timestamp'].dt.dayofweek
        
        # Períodos do pregão
        features['is_opening'] = (features['hour'] == 9).astype(int)
        features['is_closing'] = (features['hour'] >= 16).astype(int)
        features['is_lunch'] = ((features['hour'] >= 12) & (features['hour'] < 14)).astype(int)
        
        # =================================================================
        # 8. INTERAÇÕES E FEATURES COMPOSTAS
        # =================================================================
        print("[8/8] Criando features compostas...")
        
        # Momentum × Volume (detecta breakouts)
        features['momentum_volume'] = (
            features['momentum_5_20'] * features['volume_zscore_50']
        )
        
        # Volatilidade × Flow (detecta acumulação/distribuição)
        features['vol_flow'] = (
            features['volatility_50'] * features['volume_imbalance_50']
        )
        
        # Institucional × Momentum (smart money)
        features['smart_money'] = (
            features['institutional_flow_100'] * features['momentum_20_50']
        )
        
        print(f"\n[OK] Total de features criadas: {features.shape[1]}")
        
        # Limpeza e normalização
        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.fillna(0)
        
        # Converter para float32 para economia de memória
        for col in features.columns:
            if features[col].dtype == 'float64':
                features[col] = features[col].astype('float32')
                
        return features
    
    def select_best_features(self, features: pd.DataFrame, target: pd.Series, k: int = 50):
        """
        Seleciona as K melhores features usando múltiplos critérios
        """
        print("\n" + "=" * 80)
        print(" SELEÇÃO AUTOMÁTICA DE FEATURES")
        print("=" * 80)
        
        # Remover NaN do target
        mask = ~target.isna()
        X = features[mask]
        y = target[mask]
        
        # Ajustar k se for maior que o número de features disponíveis
        k = min(k, X.shape[1])
        
        print(f"\nSelecionando top {k} features de {X.shape[1]} totais...")
        print(f"Dataset size: {X.shape[0]:,} x {X.shape[1]} features")
        
        # Para datasets grandes, usar amostra para seleção de features
        if X.shape[0] > 100000:
            print(f"Dataset grande detectado. Usando amostra de 100k para seleção de features...")
            sample_idx = np.random.choice(X.shape[0], min(100000, X.shape[0]), replace=False)
            X_sample = X.iloc[sample_idx]
            y_sample = y.iloc[sample_idx]
        else:
            X_sample = X
            y_sample = y
        
        # 1. ANOVA F-statistic
        print("Calculando ANOVA F-scores...")
        selector_f = SelectKBest(f_classif, k=k)
        selector_f.fit(X_sample, y_sample)
        scores_f = pd.Series(selector_f.scores_, index=X.columns)
        
        # 2. Mutual Information (mais rápido com amostra)
        print("Calculando Mutual Information (pode demorar alguns minutos)...")
        mi_scores = mutual_info_classif(X_sample, y_sample, random_state=42, n_neighbors=3)
        scores_mi = pd.Series(mi_scores, index=X.columns)
        
        # 3. Combinar scores (média dos rankings)
        rank_f = scores_f.rank(ascending=False)
        rank_mi = scores_mi.rank(ascending=False)
        combined_rank = (rank_f + rank_mi) / 2
        
        # Selecionar top K
        self.selected_features = combined_rank.nsmallest(k).index.tolist()
        
        print(f"\n[OK] Features selecionadas:")
        print("\nTop 10 features:")
        for i, feat in enumerate(self.selected_features[:10], 1):
            print(f"  {i:2d}. {feat}")
            
        return features[self.selected_features]
    
    def create_multi_horizon_targets(self, df: pd.DataFrame) -> dict:
        """
        Cria targets para múltiplos horizontes de trading
        """
        print("\n" + "=" * 80)
        print(" CRIAÇÃO DE TARGETS MULTI-HORIZONTE")
        print("=" * 80)
        
        targets = {}
        
        for strategy, horizon in self.horizons.items():
            print(f"\n[{strategy.upper()}] Horizonte: {horizon} trades")
            
            # Calcular retorno futuro
            future_price = df['<price>'].shift(-horizon)
            returns = (future_price - df['<price>']) / df['<price>']
            
            # Thresholds baseados em desvio padrão
            std = returns.std()
            
            if strategy == 'scalping':
                # Mais sinais, menor threshold
                buy_threshold = 0.3 * std
                sell_threshold = -0.3 * std
            elif strategy == 'intraday':
                # Balanceado
                buy_threshold = 0.5 * std
                sell_threshold = -0.5 * std
            else:  # swing
                # Menos sinais, maior threshold
                buy_threshold = 0.7 * std
                sell_threshold = -0.7 * std
                
            # Criar target
            target = pd.Series(0, index=df.index, dtype='int8')
            target[returns > buy_threshold] = 1    # BUY
            target[returns < sell_threshold] = -1  # SELL
            
            # Estatísticas
            dist = target.value_counts(normalize=True).sort_index()
            print(f"  Threshold: ±{buy_threshold*100:.3f}%")
            print(f"  Distribuição: SELL={dist.get(-1,0)*100:.1f}%, "
                  f"HOLD={dist.get(0,0)*100:.1f}%, "
                  f"BUY={dist.get(1,0)*100:.1f}%")
            
            targets[strategy] = target
            
        return targets
    
    def train_ensemble(self, features: pd.DataFrame, target: pd.Series, strategy: str):
        """
        Treina ensemble de modelos para uma estratégia específica
        """
        print("\n" + "=" * 80)
        print(f" TREINAMENTO ENSEMBLE - {strategy.upper()}")
        print("=" * 80)
        
        # Preparar dados
        mask = ~target.isna()
        X = features[mask]
        y = target[mask]
        
        # Split temporal 80/20
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        
        print(f"\nTrain: {len(X_train):,} | Test: {len(X_test):,}")
        
        # Normalizar
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Calcular pesos das classes
        classes = np.array([-1, 0, 1])
        class_weights = compute_class_weight('balanced', classes=classes, y=y_train)
        class_weight_dict = dict(zip(classes, class_weights))
        
        models = {}
        
        # 1. LightGBM
        print("\n[1/4] Treinando LightGBM...")
        lgb_model = lgb.LGBMClassifier(
            n_estimators=500,
            num_leaves=31,
            learning_rate=0.01,
            feature_fraction=0.8,
            bagging_fraction=0.8,
            bagging_freq=5,
            class_weight=class_weight_dict,
            random_state=42,
            n_jobs=-1,
            verbose=-1
        )
        lgb_model.fit(X_train_scaled, y_train)
        models['lightgbm'] = lgb_model
        
        # 2. XGBoost
        print("[2/4] Treinando XGBoost...")
        # XGBoost precisa de labels 0, 1, 2 ao invés de -1, 0, 1
        # Criar mapeamento
        label_map = {-1: 0, 0: 1, 1: 2}  # SELL->0, HOLD->1, BUY->2
        y_train_xgb = y_train.map(label_map)
        y_test_xgb = y_test.map(label_map)
        
        xgb_model = xgb.XGBClassifier(
            n_estimators=500,
            max_depth=7,
            learning_rate=0.01,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbosity=0
        )
        # Ajustar pesos para XGBoost com labels mapeadas
        sample_weights = np.array([class_weight_dict[val] for val in y_train])
        xgb_model.fit(X_train_scaled, y_train_xgb, sample_weight=sample_weights)
        models['xgboost'] = xgb_model
        
        # 3. Random Forest
        print("[3/4] Treinando Random Forest...")
        rf_model = RandomForestClassifier(
            n_estimators=300,
            max_depth=10,
            min_samples_split=20,
            min_samples_leaf=10,
            class_weight=class_weight_dict,
            random_state=42,
            n_jobs=-1
        )
        rf_model.fit(X_train_scaled, y_train)
        models['random_forest'] = rf_model
        
        # 4. Extra Trees
        print("[4/4] Treinando Extra Trees...")
        et_model = ExtraTreesClassifier(
            n_estimators=300,
            max_depth=10,
            min_samples_split=20,
            min_samples_leaf=10,
            class_weight=class_weight_dict,
            random_state=42,
            n_jobs=-1
        )
        et_model.fit(X_train_scaled, y_train)
        models['extra_trees'] = et_model
        
        # Avaliar modelos
        print("\n" + "-" * 60)
        print("AVALIAÇÃO DOS MODELOS")
        print("-" * 60)
        
        for name, model in models.items():
            if name == 'xgboost':
                # XGBoost usa labels mapeadas
                y_pred = model.predict(X_test_scaled)
                # Mapear de volta para -1, 0, 1
                inverse_map = {0: -1, 1: 0, 2: 1}
                y_pred = pd.Series(y_pred).map(inverse_map).values
            else:
                y_pred = model.predict(X_test_scaled)
            
            # Métricas para sinais apenas (ignorar HOLD)
            mask_signals = y_test != 0
            if mask_signals.sum() > 0:
                accuracy = (y_pred[mask_signals] == y_test[mask_signals]).mean()
                print(f"\n{name.upper()}:")
                print(f"  Acurácia (sinais): {accuracy*100:.2f}%")
                
                # F1 score
                f1 = f1_score(y_test, y_pred, average='weighted')
                print(f"  F1 Score: {f1:.3f}")
                
        return models
    
    def save_models(self, strategy: str, models: dict):
        """Salva modelos treinados"""
        output_dir = Path('models') / strategy
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for name, model in models.items():
            if name == 'xgboost':
                # Criar wrapper para XGBoost com mapeamento de labels
                wrapper = {
                    'model': model,
                    'label_map': {-1: 0, 0: 1, 1: 2},
                    'inverse_map': {0: -1, 1: 0, 2: 1},
                    'type': 'xgboost_wrapper'
                }
                model_path = output_dir / f'{name}_{strategy}.pkl'
                joblib.dump(wrapper, model_path)
            else:
                model_path = output_dir / f'{name}_{strategy}.pkl'
                joblib.dump(model, model_path)
            print(f"  Salvando: {model_path}")
            
        # Salvar scaler
        scaler_path = output_dir / f'scaler_{strategy}.pkl'
        joblib.dump(self.scaler, scaler_path)
        
        # Salvar lista de features
        features_path = output_dir / f'features_{strategy}.json'
        with open(features_path, 'w') as f:
            json.dump(self.selected_features, f, indent=2)
            
    def run_complete_training(self):
        """Executa pipeline completo de treinamento"""
        
        print("\n" + "=" * 80)
        print(" PIPELINE COMPLETO DE TREINAMENTO WDO")
        print("=" * 80)
        print(f"\nData source: {self.csv_path}")
        print(f"Sample size: {self.sample_size:,} registros")
        
        # 1. Carregar dados
        df = self.load_and_prepare_data()
        
        # 2. Criar features
        features = self.create_optimized_features(df)
        
        # 3. Criar targets para cada estratégia
        targets = self.create_multi_horizon_targets(df)
        
        # 4. Treinar modelos para cada estratégia
        for strategy, target in targets.items():
            print(f"\n{'='*80}")
            print(f" ESTRATÉGIA: {strategy.upper()}")
            print(f"{'='*80}")
            
            # Selecionar melhores features
            features_selected = self.select_best_features(features, target)
            
            # Treinar ensemble
            models = self.train_ensemble(features_selected, target, strategy)
            
            # Salvar modelos
            print(f"\nSalvando modelos...")
            self.save_models(strategy, models)
            
            # Limpar memória
            gc.collect()
            
        print("\n" + "=" * 80)
        print(" TREINAMENTO COMPLETO!")
        print("=" * 80)
        print("\nModelos salvos em: models/")
        print("\nEstratégias treinadas:")
        for strategy in self.horizons.keys():
            print(f"  - {strategy}")
            
        return True


def main():
    """Função principal"""
    
    # Configurar trainer
    trainer = WDOModelTrainer()
    
    # Menu de opções
    print("\n" + "=" * 80)
    print(" SISTEMA DE TREINAMENTO WDO")
    print("=" * 80)
    print("\nOpções de tamanho de amostra:")
    print("  1. Rápido (1M registros) - ~5 min")
    print("  2. Normal (5M registros) - ~20 min")
    print("  3. Completo (10M registros) - ~40 min")
    print("  4. Custom")
    
    choice = input("\nEscolha [1-4]: ").strip()
    
    if choice == '1':
        trainer.sample_size = 1_000_000
    elif choice == '2':
        trainer.sample_size = 5_000_000
    elif choice == '3':
        trainer.sample_size = 10_000_000
    elif choice == '4':
        size = int(input("Tamanho da amostra: "))
        trainer.sample_size = size
    else:
        print("Opção inválida!")
        return
        
    # Executar treinamento
    start_time = datetime.now()
    
    try:
        trainer.run_complete_training()
        
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        print(f"\nTempo total: {elapsed:.1f} minutos")
        
    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()