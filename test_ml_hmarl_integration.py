#!/usr/bin/env python3
"""
Teste de integração ML + HMARL
"""

import sys
import time
import numpy as np
from pathlib import Path

print("\n" + "="*80)
print(" TESTE DE INTEGRAÇÃO ML + HMARL")
print("="*80)

# 1. Testar HybridMLPredictor
print("\n[1] Testando HybridMLPredictor...")
try:
    from src.ml.hybrid_predictor import HybridMLPredictor
    
    predictor = HybridMLPredictor()
    if predictor.load_models():
        print("  [OK] Modelos carregados com sucesso")
        
        # Criar features de teste
        test_features = {
            'returns_1': 0.002,
            'returns_5': 0.005,
            'returns_20': 0.01,
            'volatility_20': 0.015,
            'rsi_14': 65,
            'spread': 0.5,
            'imbalance': 0.3,
            'bid_price_1': 5420,
            'ask_price_1': 5420.5,
            'bid_volume_1': 100,
            'ask_volume_1': 80,
            'order_flow_imbalance_5': 0.2,
            'signed_volume_5': 500,
            'trade_flow_5': 0.1
        }
        
        # Fazer predição
        result = predictor.predict(test_features)
        
        if result:
            print(f"  [OK] Predição ML: Signal={result.get('signal')}, Confidence={result.get('confidence', 0):.2%}")
            
            if 'predictions' in result:
                preds = result['predictions']
                if 'context' in preds and preds['context']:
                    print(f"    Context: {preds['context']}")
                if 'microstructure' in preds and preds['microstructure']:
                    print(f"    Micro: {preds['microstructure']}")
        else:
            print("  [ERRO] Predição ML retornou vazio")
    else:
        print("  [WARN] Modelos não encontrados - precisa treinar primeiro")
        print("    Execute: python train_hybrid_pipeline.py")
        
except Exception as e:
    print(f"  [ERRO] HybridMLPredictor: {e}")

# 2. Testar HMARLAgentsRealtime
print("\n[2] Testando HMARLAgentsRealtime...")
try:
    from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
    
    hmarl = HMARLAgentsRealtime()
    print("  [OK] HMARL inicializado")
    
    # Atualizar com dados de teste
    for i in range(10):
        price = 5420 + np.random.randn() * 5
        volume = 100 + np.random.randint(-20, 20)
        
        hmarl.update_market_data(
            price=price,
            volume=volume,
            book_data={
                'spread': 0.5,
                'imbalance': np.random.randn() * 0.3
            },
            features={
                'order_flow_imbalance_5': np.random.randn() * 0.5,
                'signed_volume_5': np.random.randint(-1000, 1000),
                'trade_flow_5': np.random.randn() * 0.2,
                'volume_ratio': 0.8 + np.random.random() * 0.4,
                'bid_ask_spread': 0.5,
                'liquidity_imbalance': np.random.randn() * 0.3,
                'price_momentum': np.random.randn() * 0.5,
                'delta_profile': np.random.randint(-100, 100),
                'absorption_ratio': np.random.random()
            }
        )
    
    # Obter consenso
    consensus = hmarl.get_consensus()
    
    if consensus:
        print(f"  [OK] Consenso HMARL: {consensus['action']}, Confidence={consensus['confidence']:.2%}")
        
        if 'agents' in consensus:
            print("    Agentes:")
            for agent_name, agent_data in consensus['agents'].items():
                signal = agent_data.get('signal', 0)
                conf = agent_data.get('confidence', 0)
                print(f"      {agent_name}: Signal={signal:.2f}, Conf={conf:.2%}")
    else:
        print("  [ERRO] Consenso HMARL retornou vazio")
        
except Exception as e:
    print(f"  [ERRO] HMARLAgentsRealtime: {e}")
    import traceback
    traceback.print_exc()

# 3. Testar integração completa
print("\n[3] Testando integração ML + HMARL...")
try:
    # Se ambos funcionaram, testar integração
    if 'predictor' in locals() and 'hmarl' in locals():
        print("  [OK] Ambos componentes disponíveis")
        
        # Simular fluxo de dados real
        for i in range(5):
            # Gerar dados simulados
            price = 5420 + np.sin(i/2) * 10
            
            features = {
                'returns_1': np.sin(i) * 0.002,
                'volatility_20': 0.01 + np.random.random() * 0.01,
                'rsi_14': 50 + np.sin(i) * 20,
                'spread': 0.5,
                'imbalance': np.sin(i) * 0.5,
                'bid_price_1': price - 0.25,
                'ask_price_1': price + 0.25,
                'order_flow_imbalance_5': np.sin(i) * 0.3,
                'signed_volume_5': np.sin(i) * 1000,
                'trade_flow_5': np.sin(i) * 0.2
            }
            
            # ML prediction
            ml_result = predictor.predict(features)
            ml_signal = ml_result.get('signal', 0)
            ml_conf = ml_result.get('confidence', 0)
            
            # HMARL update
            hmarl.update_market_data(price=price, features=features)
            hmarl_consensus = hmarl.get_consensus()
            hmarl_action = hmarl_consensus.get('action', 'HOLD')
            hmarl_conf = hmarl_consensus.get('confidence', 0.5)
            
            print(f"\n  Iteração {i+1}:")
            print(f"    ML: {ml_signal} ({ml_conf:.1%})")
            print(f"    HMARL: {hmarl_action} ({hmarl_conf:.1%})")
            
            # Consenso final (60% ML, 40% HMARL)
            hmarl_signal = 1 if hmarl_action == 'BUY' else -1 if hmarl_action == 'SELL' else 0
            final_signal = 0.6 * ml_signal + 0.4 * hmarl_signal
            final_conf = 0.6 * ml_conf + 0.4 * hmarl_conf
            
            action = 'BUY' if final_signal > 0.3 else 'SELL' if final_signal < -0.3 else 'HOLD'
            print(f"    FINAL: {action} ({final_conf:.1%})")
            
            time.sleep(0.5)
        
        print("\n  [OK] Integração funcionando corretamente!")
    else:
        print("  [SKIP] Componentes não disponíveis para teste de integração")
        
except Exception as e:
    print(f"  [ERRO] Integração: {e}")

print("\n" + "="*80)
print(" RESUMO DO TESTE")
print("="*80)

issues = []
successes = []

# Verificar resultados
if 'predictor' in locals() and hasattr(predictor, 'is_loaded') and predictor.is_loaded:
    successes.append("ML Hybrid Predictor funcionando")
else:
    issues.append("ML Hybrid Predictor não carregado - treinar modelos")

if 'hmarl' in locals() and 'consensus' in locals() and consensus:
    successes.append("HMARL Agents funcionando")
else:
    issues.append("HMARL Agents com problemas")

if successes:
    print("\nSUCESSOS:")
    for s in successes:
        print(f"  [OK] {s}")

if issues:
    print("\nPROBLEMAS:")
    for i in issues:
        print(f"  [!] {i}")
        
    print("\nSOLUÇÕES:")
    if "treinar modelos" in str(issues):
        print("  1. Execute: python train_hybrid_pipeline.py")
        print("  2. Aguarde o treinamento completar")
        print("  3. Execute este teste novamente")

print("\n" + "="*80)