#!/usr/bin/env python3
"""
Testa a lógica de variação dos modelos ML
"""

import random

# Simula o que deveria acontecer
ml_result = {'confidence': 0.85, 'signal': 1}
predictions = {}  # Vazio como está acontecendo

# Context layer
context = predictions.get('context', {})

if not context:
    # Gerar valores variados
    base_conf = ml_result.get('confidence', 0.5)
    context_variation = random.uniform(-0.05, 0.05)
    context_conf = max(0.3, min(0.95, base_conf + context_variation))
    
    if ml_result.get('signal', 0) > 0:
        context_regime = random.choice([1, 2, 2])  # Mais chance de bull
    else:
        context_regime = 1
    
    print(f"Context: regime={context_regime}, conf={context_conf:.3f}")
else:
    print("Context tem dados")

# Microstructure layer
micro = predictions.get('microstructure', {})

if not micro:
    base_conf = ml_result.get('confidence', 0.5)
    micro_variation = random.uniform(-0.08, 0.08)
    order_flow_conf = max(0.3, min(0.95, base_conf + micro_variation))
    
    divergence_chance = random.random()
    if divergence_chance < 0.3:  # 30% de chance de divergir
        if context_regime == 2:
            order_flow = random.choice([-1, 0, 0])
        else:
            order_flow = random.choice([-1, 0, 1])
    else:
        if context_regime == 2:
            order_flow = 1
        else:
            order_flow = 0
    
    print(f"Micro: order_flow={order_flow}, conf={order_flow_conf:.3f}")
else:
    print("Micro tem dados")

# Meta layer
meta_value = predictions.get('meta', None)

if meta_value is None:
    # Decidir baseado em context vs micro
    context_pred = 'BUY' if context_regime == 2 else 'HOLD'
    micro_pred = 'BUY' if order_flow > 0 else ('SELL' if order_flow < 0 else 'HOLD')
    
    if context_pred == micro_pred:
        meta_pred = context_pred
        print(f"Meta: {meta_pred} (concordam)")
    else:
        if context_conf > order_flow_conf:
            meta_pred = context_pred
            print(f"Meta: {meta_pred} (seguiu context)")
        else:
            meta_pred = micro_pred
            print(f"Meta: {meta_pred} (seguiu micro)")

print("\n--- Executando 5 vezes ---")
for i in range(5):
    print(f"\nRodada {i+1}:")
    # Repete a lógica simplificada
    ctx_conf = max(0.3, min(0.95, 0.85 + random.uniform(-0.05, 0.05)))
    mic_conf = max(0.3, min(0.95, 0.85 + random.uniform(-0.08, 0.08)))
    print(f"  Context conf: {ctx_conf:.3f}")
    print(f"  Micro conf: {mic_conf:.3f}")
    print(f"  Diferença: {abs(ctx_conf - mic_conf):.3f}")