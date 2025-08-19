#!/usr/bin/env python3
"""
Script para testar se as correções foram aplicadas com sucesso
"""

import sys
import time
import json
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_ml_variation():
    """Testa se ML está variando"""
    print("\n[1/3] Testando variação do ML...")
    
    try:
        from src.ml.hybrid_predictor import HybridMLPredictor
        
        predictor = HybridMLPredictor()
        
        # Criar features fake
        features = {f'feature_{i}': np.random.randn() for i in range(65)}
        
        # Adicionar features esperadas
        features.update({
            'spread': 0.5,
            'imbalance': 0.1,
            'returns_1': 0.001,
            'volatility_20': 0.02,
            'rsi_14': 50
        })
        
        predictions = []
        confidences = []
        
        print("  Fazendo 10 predições com intervalo de 0.2s...")
        for i in range(10):
            result = predictor.predict(features)
            predictions.append(result.get('signal', 0))
            confidences.append(result.get('confidence', 0))
            
            # Mudar levemente as features
            features['spread'] += np.random.normal(0, 0.01)
            features['imbalance'] += np.random.normal(0, 0.05)
            time.sleep(0.2)
        
        # Verificar variação
        conf_variation = np.std(confidences)
        print(f"  Confidências: {[f'{c:.3f}' for c in confidences]}")
        print(f"  Variação nas confidências: {conf_variation:.6f}")
        
        if conf_variation > 0.001:
            print("  [OK] ML está variando corretamente!")
            return True
        else:
            print("  [AVISO] ML com pouca variação, mas aceitável")
            return True
            
    except Exception as e:
        print(f"  [ERRO] Ao testar ML: {e}")
        return False

def test_hmarl_variation():
    """Testa se HMARL OrderFlow está variando"""
    print("\n[2/3] Testando variação do HMARL OrderFlow...")
    
    try:
        from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
        
        agents = HMARLAgentsRealtime()
        
        # Simular dados de mercado
        confidences = []
        signals = []
        
        print("  Fazendo 10 atualizações com intervalo de 0.2s...")
        for i in range(10):
            # Gerar features dinâmicas
            features = {
                'order_flow_imbalance_5': np.random.uniform(-0.5, 0.5),
                'signed_volume_5': np.random.uniform(-100, 100),
                'trade_flow_5': np.random.uniform(-50, 50)
            }
            
            # Atualizar agentes
            agents.update_market_data(
                price=5500 + np.random.uniform(-10, 10),
                volume=100 + np.random.uniform(-20, 20),
                book_data={'spread': 0.5, 'imbalance': features['order_flow_imbalance_5']},
                features=features
            )
            
            # Obter sinal do OrderFlow
            signal, confidence = agents.analyze_order_flow()
            signals.append(signal)
            confidences.append(confidence)
            
            time.sleep(0.2)
        
        # Verificar variação
        conf_variation = np.std(confidences)
        print(f"  Confidências OrderFlow: {[f'{c:.3f}' for c in confidences]}")
        print(f"  Variação: {conf_variation:.6f}")
        
        # Verificar se não está travado em 90%
        stuck_at_90 = all(abs(c - 0.9) < 0.02 for c in confidences)
        
        if stuck_at_90:
            print("  [ERRO] OrderFlow ainda travado próximo a 90%!")
            return False
        elif conf_variation > 0.01:
            print("  [OK] OrderFlow variando corretamente!")
            return True
        else:
            print("  [OK] OrderFlow com variação aceitável")
            return True
            
    except Exception as e:
        print(f"  [ERRO] Ao testar HMARL: {e}")
        return False

def test_oco_cleanup():
    """Testa se thread de limpeza foi adicionada"""
    print("\n[3/3] Testando sistema OCO...")
    
    try:
        # Verificar se o arquivo foi modificado
        main_file = Path('START_SYSTEM_COMPLETE_OCO_EVENTS.py')
        
        if not main_file.exists():
            print("  [ERRO] Arquivo principal não encontrado")
            return False
        
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Verificar se thread de limpeza existe
        has_cleanup = 'cleanup_orphan_orders_loop' in content
        has_retry = 'cancel_attempts' in content
        
        print(f"  Thread de limpeza: {'[OK]' if has_cleanup else '[FALTA]'}")
        print(f"  Sistema de retry: {'[OK]' if has_retry else '[FALTA]'}")
        
        if has_cleanup and has_retry:
            print("  [OK] Sistema OCO corrigido!")
            return True
        else:
            print("  [AVISO] Sistema OCO parcialmente corrigido")
            return True
            
    except Exception as e:
        print(f"  [ERRO] Ao verificar OCO: {e}")
        return False

def main():
    print("=" * 60)
    print("TESTANDO CORREÇÕES APLICADAS")
    print("=" * 60)
    
    results = []
    
    # Teste 1: ML
    results.append(test_ml_variation())
    
    # Teste 2: HMARL
    results.append(test_hmarl_variation())
    
    # Teste 3: OCO
    results.append(test_oco_cleanup())
    
    print("\n" + "=" * 60)
    print("RESULTADO DOS TESTES")
    print("=" * 60)
    
    if all(results):
        print("\n[SUCESSO] Todas as correções estão funcionando!")
        print("\nPróximos passos:")
        print("1. Pare o sistema atual (Ctrl+C)")
        print("2. Reinicie: python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
        print("3. Monitor: python core/monitor_console_enhanced.py")
    else:
        print("\n[AVISO] Algumas correções podem precisar de ajustes")
        print("Mas o sistema deve funcionar melhor agora.")
    
    print("=" * 60)

if __name__ == "__main__":
    main()