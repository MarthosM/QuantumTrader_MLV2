# ML Models Directory

## Available Models

### Primary Models (Ensemble)
1. **xgboost_fast.pkl** - XGBoost optimized for speed
   - Best for: Quick predictions with good accuracy
   - Latency: ~1-2ms
   - Accuracy: ~62%

2. **xgboost_balanced_20250807_061838.pkl** - XGBoost balanced
   - Best for: Balanced performance/accuracy
   - Latency: ~2-3ms
   - Accuracy: ~65%

3. **random_forest_stable.pkl** - Random Forest stable version
   - Best for: Stable predictions, less overfit
   - Latency: ~3-5ms
   - Accuracy: ~60%

4. **random_forest_balanced_20250807_061838.pkl** - Random Forest balanced
   - Best for: Conservative trading
   - Latency: ~4-6ms
   - Accuracy: ~63%

### Support Files
- **scaler_20250807_061838.pkl** - Feature scaler for normalization
- **simple_model.pkl** - Fallback model for emergencies

## Model Loading Priority

The system will attempt to load models in this order:
1. xgboost_fast.pkl (primary)
2. xgboost_balanced_*.pkl (if fast unavailable)
3. random_forest_stable.pkl (fallback)
4. simple_model.pkl (emergency fallback)

## Feature Requirements

All models expect 65 features in the following categories:
- Volatility Features: 10
- Return Features: 10
- Order Flow Features: 8
- Volume Features: 8
- Technical Features: 8
- Microstructure Features: 15
- Temporal Features: 6

## Usage in Production

```python
import joblib

# Load model
model = joblib.load('models/xgboost_fast.pkl')
scaler = joblib.load('models/scaler_20250807_061838.pkl')

# Prepare features (65 features)
features = calculate_features()  # Your feature calculation
features_scaled = scaler.transform(features.reshape(1, -1))

# Make prediction
prediction = model.predict(features_scaled)
probability = model.predict_proba(features_scaled)
```

## Model Updates

To update models:
1. Train new models with the same feature set
2. Test thoroughly in paper trading
3. Save with descriptive names including date
4. Update this README with new model info
5. Keep old models as backup for at least 30 days

## Important Notes

- Models were trained on 5-minute candle data
- Feature scaling is REQUIRED - always use the scaler
- Models expect exactly 65 features in the correct order
- If a model fails to load, the system will fall back to the next available

## Training Date
Last update: 2025-08-07
Training data period: 2024-2025
Symbol: WDOU (Mini Dollar futures)