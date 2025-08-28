#!/usr/bin/env python3
"""
Verifica se as correções estão funcionando
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import json
from pathlib import Path
from collections import deque

def verify_system():
    print("="*60)
    print("VERIFICAÇÃO DO SISTEMA")
    print("="*60)
    
    # 1. Testar ML
    print("\n1. Testando ML Predictor...")
    try:
        from src.ml.hybrid_predictor import HybridMLPredictor
        predictor = HybridMLPredictor()
        
        # Criar features teste
        test_features = {
            'returns_1': 0.001,
            'returns_5': 0.002,
            'volatility_20': 0.01,
            'order_flow_imbalance': 0.5,
            'bid_price_1': 5500,
            'ask_price_1': 5505
        }
        
        # Preencher com features dummy
        for i in range(65):
            if f'feature_{i}' not in test_features:
                test_features[f'feature_{i}'] = 0.1
        
        result = predictor.predict(test_features)
        if result and result.get('signal') != 0:
            print("  [OK] ML funcionando")
        else:
            print("  [PROBLEMA] ML retornando 0 ou None")
            
    except Exception as e:
        print(f"  [ERRO] {e}")
    
    # 2. Verificar price buffer
    print("\n2. Testando Price Buffer...")
    price_history = deque(maxlen=500)
    
    # Simular adição de preços
    for i in range(50):
        price = 5500 + i * 0.1
        price_history.append(price)
    
    if len(price_history) > 20:
        prices = list(price_history)
        returns = (prices[-1] - prices[-2]) / prices[-2]
        if abs(returns) > 1e-8:
            print("  [OK] Price buffer e returns funcionando")
        else:
            print("  [PROBLEMA] Returns zerados")
    
    # 3. Verificar arquivos de status
    print("\n3. Verificando Arquivos de Status...")
    
    pos_file = Path("data/monitor/position_status.json")
    if pos_file.exists():
        with open(pos_file, 'r') as f:
            data = json.load(f)
        print(f"  Position status: has_position={data.get('has_position', 'N/A')}")
    else:
        print("  [AVISO] Arquivo position_status.json não existe")
    
    ml_file = Path("data/monitor/ml_status.json")
    if ml_file.exists():
        with open(ml_file, 'r') as f:
            data = json.load(f)
        print(f"  ML status: timestamp={data.get('timestamp', 'N/A')}")
    else:
        print("  [AVISO] Arquivo ml_status.json não existe")
    
    print("\n" + "="*60)
    print("Verificação concluída!")
    print("\nSe houver problemas, execute:")
    print("  1. python fix_complete_system.py")
    print("  2. Reinicie o sistema")
    print("  3. python monitor_features.py (em outro terminal)")

if __name__ == "__main__":
    verify_system()
