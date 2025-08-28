"""
Script de teste para verificar correções no sistema ML
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import time
from src.ml.hybrid_predictor import HybridMLPredictor

def test_static_features():
    """Testa com features estáticas (deveria detectar e retornar sinal neutro)"""
    print("\n=== Teste 1: Features Estáticas ===")
    
    predictor = HybridMLPredictor()
    predictor.load_models()
    
    # Features estáticas (sempre os mesmos valores)
    static_features = {
        'returns_1': 0.0,
        'returns_5': 0.0,
        'returns_10': 0.0,
        'returns_20': 0.0,
        'volatility_10': 0.001,
        'volatility_20': 0.001,
        'volatility_50': 0.001,
        'volume_ratio': 1.0,
        'trade_intensity': 0.5,
        'order_flow_imbalance': 0.0,
        'signed_volume': 0.0,
        'rsi_14': 50.0,
        'spread': 0.5,
        'bid_pressure': 0.5,
        'ask_pressure': 0.5,
        'book_imbalance': 0.0
    }
    
    print("\nPrimeiras 5 predições com features estáticas:")
    for i in range(5):
        result = predictor.predict(static_features)
        print(f"  {i+1}. Signal: {result['signal']}, Confidence: {result.get('confidence', 0):.2%}, Error: {result.get('error', 'None')}")
        time.sleep(0.1)
    
    print("\nMais 3 predições (deve detectar como estático após 5 ciclos):")
    for i in range(3):
        result = predictor.predict(static_features)
        print(f"  {i+6}. Signal: {result['signal']}, Confidence: {result.get('confidence', 0):.2%}, Error: {result.get('error', 'None')}")
        time.sleep(0.1)

def test_dynamic_features():
    """Testa com features dinâmicas (deveria fazer predições normais)"""
    print("\n=== Teste 2: Features Dinâmicas ===")
    
    predictor = HybridMLPredictor()
    predictor.load_models()
    
    print("\n5 predições com features variando:")
    for i in range(5):
        # Features dinâmicas (valores mudam)
        dynamic_features = {
            'returns_1': np.random.uniform(-0.001, 0.001),
            'returns_5': np.random.uniform(-0.005, 0.005),
            'returns_10': np.random.uniform(-0.01, 0.01),
            'returns_20': np.random.uniform(-0.02, 0.02),
            'volatility_10': np.random.uniform(0.001, 0.01),
            'volatility_20': np.random.uniform(0.001, 0.02),
            'volatility_50': np.random.uniform(0.001, 0.03),
            'volume_ratio': np.random.uniform(0.8, 1.2),
            'trade_intensity': np.random.uniform(0.3, 0.7),
            'order_flow_imbalance': np.random.uniform(-0.5, 0.5),
            'signed_volume': np.random.uniform(-100, 100),
            'rsi_14': np.random.uniform(30, 70),
            'spread': np.random.uniform(0.1, 1.0),
            'bid_pressure': np.random.uniform(0.3, 0.7),
            'ask_pressure': np.random.uniform(0.3, 0.7),
            'book_imbalance': np.random.uniform(-0.5, 0.5)
        }
        
        result = predictor.predict(dynamic_features)
        print(f"  {i+1}. Signal: {result['signal']}, Confidence: {result.get('confidence', 0):.2%}")
        
        # Mostrar predições das camadas se disponível
        if 'predictions' in result and result['predictions']:
            context = result['predictions'].get('context', {})
            micro = result['predictions'].get('microstructure', {})
            if context:
                print(f"     Context: Regime={context.get('regime', 'N/A')}, Conf={context.get('regime_conf', 0):.2%}")
            if micro:
                print(f"     Micro: Flow={micro.get('order_flow', 'N/A')}, Conf={micro.get('order_flow_conf', 0):.2%}")
        
        time.sleep(0.1)

def test_without_temporal_variation():
    """Testa se removemos a variação temporal artificial"""
    print("\n=== Teste 3: Verificação de Variação Temporal ===")
    
    predictor = HybridMLPredictor()
    predictor.load_models()
    
    # Features fixas para teste
    test_features = {
        'returns_1': 0.001,
        'returns_5': 0.002,
        'returns_10': 0.003,
        'returns_20': 0.004,
        'volatility_10': 0.005,
        'volatility_20': 0.006,
        'volatility_50': 0.007,
        'volume_ratio': 1.1,
        'trade_intensity': 0.6,
        'order_flow_imbalance': 0.2,
        'signed_volume': 50,
        'rsi_14': 55,
        'spread': 0.4,
        'bid_pressure': 0.6,
        'ask_pressure': 0.4,
        'book_imbalance': 0.2
    }
    
    print("\n5 predições com as MESMAS features (sem variação artificial):")
    results = []
    for i in range(5):
        result = predictor.predict(test_features.copy())
        results.append(result)
        print(f"  {i+1}. Signal: {result['signal']}, Confidence: {result.get('confidence', 0):.4f}")
        time.sleep(0.1)
    
    # Verificar se confiança está variando artificialmente
    confidences = [r.get('confidence', 0) for r in results]
    if len(set(confidences)) == 1:
        print("\n[OK] SUCESSO: Confiança constante (sem variação artificial)")
    else:
        variation = max(confidences) - min(confidences)
        if variation < 0.01:  # Menos de 1% de variação
            print(f"\n[OK] Variação mínima detectada ({variation:.4f})")
        else:
            print(f"\n[AVISO] Ainda há variação na confiança ({variation:.4f})")

def main():
    print("="*60)
    print("TESTE DO SISTEMA ML CORRIGIDO")
    print("="*60)
    
    test_static_features()
    test_dynamic_features()
    test_without_temporal_variation()
    
    print("\n" + "="*60)
    print("TESTES CONCLUÍDOS")
    print("="*60)
    print("\nResumo das correções implementadas:")
    print("1. [OK] Removida função _add_temporal_variation")
    print("2. [OK] Adicionada validação de features estáticas")
    print("3. [OK] Melhorado logging de debug")
    print("4. [OK] Implementado fallback inteligente")
    print("\nO sistema agora deve responder a dados reais do mercado,")
    print("sem variação artificial nos resultados.")

if __name__ == "__main__":
    main()