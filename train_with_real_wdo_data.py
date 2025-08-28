#!/usr/bin/env python3
"""
Treina modelos ML com dados reais do WDO
Processa CSV grande de forma eficiente
"""

import pandas as pd
import numpy as np
from pathlib import Path
import joblib
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import RobustScaler, StandardScaler
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.metrics import accuracy_score, classification_report
import xgboost as xgb

print("="*80)
print(" TREINAMENTO COM DADOS REAIS DO WDO")
print("="*80)

# Configurações
CSV_PATH = r"C:\Users\marth\Downloads\WDO_FUT\WDOFUT_BMF_T.csv"
MODELS_DIR = Path("models/hybrid")
CHUNK_SIZE = 100000  # Ler em chunks de 100k linhas
MAX_ROWS = 5000000  # Usar no máximo 5M linhas (últimas)

def process_trades_to_features(df):
    """
    Converte trades em features de ML
    """
    features = {}
    
    # Agregar por minuto
    df['datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str).str.zfill(6), 
                                    format='%Y%m%d %H%M%S')
    df.set_index('datetime', inplace=True)
    
    # Resample para barras de 1 minuto
    ohlc = df['price'].resample('1min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    })
    
    volume = df['vol'].resample('1min').sum()
    trades = df['price'].resample('1min').count()
    
    # Calcular returns
    features['returns_1'] = ohlc['close'].pct_change(1)
    features['returns_5'] = ohlc['close'].pct_change(5)
    features['returns_10'] = ohlc['close'].pct_change(10)
    features['returns_20'] = ohlc['close'].pct_change(20)
    
    # Volatilidade
    features['volatility_10'] = features['returns_1'].rolling(10).std()
    features['volatility_20'] = features['returns_1'].rolling(20).std()
    features['volatility_50'] = features['returns_1'].rolling(50).std()
    
    # Volume features
    features['volume_ratio'] = volume / volume.rolling(20).mean()
    features['trade_intensity'] = trades / trades.rolling(20).mean()
    
    # Microestrutura - Order Flow
    # Classificar trades como buy/sell baseado em uptick/downtick
    df['price_change'] = df['price'].diff()
    df['trade_sign'] = np.where(df['price_change'] > 0, 1, 
                                np.where(df['price_change'] < 0, -1, 0))
    
    # Order flow imbalance
    buy_volume = df[df['trade_sign'] == 1].resample('1min')['vol'].sum()
    sell_volume = df[df['trade_sign'] == -1].resample('1min')['vol'].sum()
    total_volume = buy_volume + sell_volume
    
    features['order_flow_imbalance'] = (buy_volume - sell_volume) / (total_volume + 1)
    features['signed_volume'] = df['trade_sign'].resample('1min').sum()
    
    # RSI
    def calculate_rsi(prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    features['rsi_14'] = calculate_rsi(ohlc['close'])
    
    # Spread sintético (baseado em volatilidade)
    features['spread'] = features['volatility_10'] * 0.5  # Aproximação
    
    # Book pressure sintético
    features['bid_pressure'] = buy_volume / (total_volume + 1)
    features['ask_pressure'] = sell_volume / (total_volume + 1)
    features['book_imbalance'] = features['bid_pressure'] - features['ask_pressure']
    
    # Target: Direção do próximo movimento
    features['target'] = np.where(ohlc['close'].shift(-5) > ohlc['close'], 1,
                                 np.where(ohlc['close'].shift(-5) < ohlc['close'], -1, 0))
    
    # Criar DataFrame final
    feature_df = pd.DataFrame(features)
    
    # Remover NaN
    feature_df = feature_df.dropna()
    
    return feature_df

def train_models(X_train, X_test, y_train, y_test, model_type='context'):
    """
    Treina modelos para uma camada específica
    """
    models = {}
    
    print(f"\nTreinando modelos {model_type}...")
    
    # Random Forest
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=20,
        random_state=42,
        n_jobs=-1
    )
    rf.fit(X_train, y_train)
    y_pred = rf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"  RandomForest: {acc:.3f}")
    models['rf'] = rf
    
    # XGBoost
    xgb_model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        use_label_encoder=False,
        eval_metric='mlogloss'
    )
    xgb_model.fit(X_train, y_train)
    y_pred = xgb_model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"  XGBoost: {acc:.3f}")
    models['xgb'] = xgb_model
    
    # Extra Trees
    et = ExtraTreesClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        n_jobs=-1
    )
    et.fit(X_train, y_train)
    y_pred = et.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"  ExtraTrees: {acc:.3f}")
    models['et'] = et
    
    return models

def main():
    """
    Pipeline principal de treinamento
    """
    
    # 1. Carregar dados
    print("\n[1] Carregando dados reais do WDO...")
    print(f"    Arquivo: {CSV_PATH}")
    
    # Contar total de linhas
    total_lines = 215974008  # Já sabemos do comando anterior
    print(f"    Total de linhas: {total_lines:,}")
    
    # Calcular quantas linhas pular para pegar apenas as últimas
    skip_rows = max(0, total_lines - MAX_ROWS)
    print(f"    Usando últimas {MAX_ROWS:,} linhas")
    
    # Ler dados em chunks
    chunks = []
    chunk_count = 0
    
    # Definir nomes das colunas (o CSV tem <> nos nomes)
    column_names = ['ticker', 'date', 'time', 'trade_number', 'price', 'qty', 
                   'vol', 'buy_agent', 'sell_agent', 'trade_type', 'aft']
    
    for chunk in pd.read_csv(CSV_PATH, 
                             chunksize=CHUNK_SIZE,
                             skiprows=range(1, skip_rows) if skip_rows > 0 else None,
                             names=column_names,
                             header=0,
                             dtype={
                                 'ticker': str,
                                 'date': int,
                                 'time': int,
                                 'trade_number': int,
                                 'price': float,
                                 'qty': int,
                                 'vol': float,
                                 'buy_agent': str,
                                 'sell_agent': str,
                                 'trade_type': str,
                                 'aft': str
                             }):
        chunks.append(chunk)
        chunk_count += 1
        print(f"    Chunk {chunk_count} carregado ({len(chunk):,} linhas)")
        
        if chunk_count * CHUNK_SIZE >= MAX_ROWS:
            break
    
    # Concatenar chunks
    df = pd.concat(chunks, ignore_index=True)
    print(f"    Total carregado: {len(df):,} linhas")
    
    # 2. Processar features
    print("\n[2] Processando features...")
    features_df = process_trades_to_features(df)
    print(f"    Features geradas: {features_df.shape}")
    print(f"    Colunas: {list(features_df.columns)}")
    
    # 3. Preparar dados para treinamento
    print("\n[3] Preparando dados para ML...")
    
    # Separar features e target
    feature_cols = [col for col in features_df.columns if col != 'target']
    X = features_df[feature_cols].values
    y = features_df['target'].values
    
    # Converter target para classes (0, 1, 2) ao invés de (-1, 0, 1)
    y = y + 1  # Agora: 0=SELL, 1=HOLD, 2=BUY
    
    print(f"    X shape: {X.shape}")
    print(f"    y shape: {y.shape}")
    print(f"    Classes: {np.unique(y, return_counts=True)}")
    
    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # 4. Escalar dados
    print("\n[4] Normalizando dados...")
    scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 5. Treinar modelos
    print("\n[5] Treinando modelos híbridos...")
    
    # Criar diretórios
    MODELS_DIR.mkdir(exist_ok=True)
    (MODELS_DIR / "context").mkdir(exist_ok=True)
    (MODELS_DIR / "microstructure").mkdir(exist_ok=True)
    (MODELS_DIR / "meta_learner").mkdir(exist_ok=True)
    
    # Treinar modelos de contexto
    context_models = train_models(X_train_scaled, X_test_scaled, y_train, y_test, 'context')
    
    # Salvar melhor modelo de contexto
    best_context = max(context_models.items(), key=lambda x: accuracy_score(y_test, x[1].predict(X_test_scaled)))
    joblib.dump(best_context[1], MODELS_DIR / "context" / "regime_detector.pkl")
    print(f"    Salvo: regime_detector.pkl")
    
    # Treinar modelos de microestrutura (usando features não escaladas para alguns)
    micro_models = train_models(X_train, X_test, y_train, y_test, 'microstructure')
    
    # Salvar melhor modelo de microestrutura
    best_micro = max(micro_models.items(), key=lambda x: accuracy_score(y_test, x[1].predict(X_test)))
    joblib.dump(best_micro[1], MODELS_DIR / "microstructure" / "order_flow_analyzer.pkl")
    print(f"    Salvo: order_flow_analyzer.pkl")
    
    # Meta-learner (combina predições)
    print("\n[6] Treinando meta-learner...")
    
    # Gerar predições dos modelos base
    context_pred = best_context[1].predict_proba(X_train_scaled)
    micro_pred = best_micro[1].predict_proba(X_train)
    
    # Combinar predições como features para meta-learner
    meta_features = np.hstack([context_pred, micro_pred])
    
    # Treinar meta-learner
    meta_model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    meta_model.fit(meta_features, y_train)
    
    # Validar
    context_pred_test = best_context[1].predict_proba(X_test_scaled)
    micro_pred_test = best_micro[1].predict_proba(X_test)
    meta_features_test = np.hstack([context_pred_test, micro_pred_test])
    
    y_meta_pred = meta_model.predict(meta_features_test)
    meta_acc = accuracy_score(y_test, y_meta_pred)
    print(f"    Meta-learner accuracy: {meta_acc:.3f}")
    
    # Salvar meta-learner
    joblib.dump(meta_model, MODELS_DIR / "meta_learner" / "meta_learner.pkl")
    
    # 7. Salvar scalers
    print("\n[7] Salvando scalers...")
    joblib.dump(scaler, MODELS_DIR / "scaler_context.pkl")
    joblib.dump(scaler, MODELS_DIR / "scaler_microstructure.pkl")
    
    # 8. Salvar configuração
    config = {
        'trained_at': datetime.now().isoformat(),
        'data_file': CSV_PATH,
        'total_samples': len(features_df),
        'features': feature_cols,
        'models': {
            'context': 'regime_detector.pkl',
            'microstructure': 'order_flow_analyzer.pkl',
            'meta': 'meta_learner.pkl'
        },
        'performance': {
            'context_acc': accuracy_score(y_test, best_context[1].predict(X_test_scaled)),
            'micro_acc': accuracy_score(y_test, best_micro[1].predict(X_test)),
            'meta_acc': meta_acc
        }
    }
    
    import json
    with open(MODELS_DIR / "config.json", 'w') as f:
        json.dump(config, f, indent=2)
    
    print("\n" + "="*80)
    print(" TREINAMENTO CONCLUÍDO COM SUCESSO!")
    print("="*80)
    print(f"\nPerformance Final:")
    print(f"  Context Model: {config['performance']['context_acc']:.1%}")
    print(f"  Microstructure Model: {config['performance']['micro_acc']:.1%}")
    print(f"  Meta-Learner: {config['performance']['meta_acc']:.1%}")
    print(f"\nModelos salvos em: {MODELS_DIR}")
    print("\nPróximos passos:")
    print("  1. Testar com: python test_ml_hmarl_integration.py")
    print("  2. Executar sistema: python START_SYSTEM_COMPLETE_OCO_EVENTS.py")

if __name__ == "__main__":
    main()