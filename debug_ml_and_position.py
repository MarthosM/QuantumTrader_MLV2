#!/usr/bin/env python3
"""
Script de debug profundo para ML e detecção de posição
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import json
import threading
from datetime import datetime
from pathlib import Path
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_ml_models():
    """Verifica se os modelos ML estão carregados corretamente"""
    print("\n" + "="*60)
    print("1. VERIFICANDO MODELOS ML")
    print("="*60)
    
    try:
        from src.ml.hybrid_predictor import HybridPredictor
        
        predictor = HybridPredictor()
        
        # Verificar se modelos foram carregados
        print("\nModelos carregados:")
        print(f"  Context models: {predictor.context_models is not None}")
        print(f"  Microstructure models: {predictor.microstructure_models is not None}")
        print(f"  Meta learner: {predictor.meta_learner is not None}")
        
        # Testar com features dummy
        dummy_features = {}
        # Adicionar todas as 65 features esperadas com valores variados
        for i in range(65):
            dummy_features[f'feature_{i}'] = 0.1 * (i + 1)
        
        # Features específicas que o modelo espera
        dummy_features.update({
            'returns_1': 0.001,
            'returns_5': 0.002,
            'returns_20': 0.003,
            'volatility_20': 0.01,
            'order_flow_imbalance': 0.5,
            'bid_price_1': 5500,
            'ask_price_1': 5505,
            'spread': 5,
            'mid_price': 5502.5
        })
        
        print("\nTestando predição com features dummy...")
        result = predictor.predict(dummy_features)
        
        if result:
            print(f"  Signal: {result.get('signal')}")
            print(f"  Confidence: {result.get('confidence')}")
            predictions = result.get('predictions', {})
            if predictions:
                print(f"  Context regime: {predictions.get('context', {}).get('regime')}")
                print(f"  Micro order_flow: {predictions.get('microstructure', {}).get('order_flow')}")
        else:
            print("  [ERRO] Predição retornou None")
            
    except Exception as e:
        print(f"  [ERRO] Falha ao testar ML: {e}")
        import traceback
        traceback.print_exc()

def check_price_buffer():
    """Verifica o buffer de preços em tempo real"""
    print("\n" + "="*60)
    print("2. VERIFICANDO PRICE BUFFER")
    print("="*60)
    
    # Tentar importar o sistema principal
    try:
        import gc
        import START_SYSTEM_COMPLETE_OCO_EVENTS as main
        
        # Procurar instância do TradingSystem via garbage collector
        system = None
        for obj in gc.get_objects():
            if hasattr(obj, '__class__') and obj.__class__.__name__ == 'TradingSystem':
                system = obj
                break
        
        if system:
            print("\nSistema encontrado!")
            print(f"  Price history size: {len(system.price_history)}")
            if len(system.price_history) > 0:
                prices = list(system.price_history)
                print(f"  Últimos 5 preços: {prices[-5:]}")
                
                # Verificar se preços estão mudando
                if len(set(prices[-10:])) == 1:
                    print("  [PROBLEMA] Todos os preços são iguais!")
                else:
                    print("  [OK] Preços estão variando")
            else:
                print("  [PROBLEMA] Price history vazio!")
                
        else:
            print("  [AVISO] Sistema não encontrado em memória")
            
    except Exception as e:
        print(f"  [ERRO] {e}")

def check_position_detection():
    """Verifica sistema de detecção de posição"""
    print("\n" + "="*60)
    print("3. VERIFICANDO DETECÇÃO DE POSIÇÃO")
    print("="*60)
    
    # Verificar arquivos de status
    status_files = {
        "position_status.json": "data/monitor/position_status.json",
        "ml_status.json": "data/monitor/ml_status.json"
    }
    
    for name, path in status_files.items():
        file_path = Path(path)
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                print(f"\n{name}:")
                if 'has_position' in data:
                    print(f"  has_position: {data['has_position']}")
                if 'position' in data:
                    pos = data['position']
                    print(f"  quantity: {pos.get('quantity', 0)}")
                    print(f"  side: {pos.get('side', 'none')}")
                if 'timestamp' in data:
                    print(f"  timestamp: {data['timestamp']}")
            except Exception as e:
                print(f"  [ERRO] Não conseguiu ler: {e}")
        else:
            print(f"\n{name}: NÃO EXISTE")
    
    # Verificar PositionChecker
    try:
        from src.monitoring.position_checker import PositionChecker
        print("\n[OK] PositionChecker disponível")
    except ImportError:
        print("\n[PROBLEMA] PositionChecker não encontrado!")

def monitor_realtime():
    """Monitor em tempo real do sistema"""
    print("\n" + "="*60)
    print("4. MONITOR TEMPO REAL (30 segundos)")
    print("="*60)
    print("\nMonitorando sistema por 30 segundos...")
    print("Pressione Ctrl+C para parar\n")
    
    start_time = time.time()
    last_values = {}
    
    try:
        while time.time() - start_time < 30:
            # Ler ml_status.json
            ml_status_file = Path("data/monitor/ml_status.json")
            if ml_status_file.exists():
                try:
                    with open(ml_status_file, 'r') as f:
                        data = json.load(f)
                    
                    # Verificar features
                    if 'last_features' in data:
                        features = data['last_features']
                        critical_features = ['returns_1', 'returns_5', 'volatility_20']
                        
                        changed = False
                        for feat in critical_features:
                            if feat in features:
                                value = features[feat]
                                if feat in last_values:
                                    if abs(value - last_values[feat]) > 1e-8:
                                        changed = True
                                last_values[feat] = value
                        
                        if changed:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Features mudaram!")
                            for feat in critical_features:
                                if feat in features:
                                    print(f"  {feat}: {features[feat]:.6f}")
                    
                    # Verificar predições
                    if 'last_prediction' in data:
                        pred = data['last_prediction']
                        signal = pred.get('signal', 0)
                        conf = pred.get('confidence', 0)
                        
                        # Só mostrar se mudou
                        pred_key = f"{signal}_{conf}"
                        if pred_key != last_values.get('pred_key'):
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Nova predição ML:")
                            print(f"  Signal: {signal}, Confidence: {conf:.2%}")
                            last_values['pred_key'] = pred_key
                            
                except Exception as e:
                    pass
            
            # Verificar position_status.json
            pos_status_file = Path("data/monitor/position_status.json")
            if pos_status_file.exists():
                try:
                    with open(pos_status_file, 'r') as f:
                        data = json.load(f)
                    
                    has_pos = data.get('has_position', False)
                    if 'last_has_pos' in last_values:
                        if has_pos != last_values['last_has_pos']:
                            if has_pos:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] POSIÇÃO ABERTA DETECTADA")
                            else:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] POSIÇÃO FECHADA DETECTADA")
                    last_values['last_has_pos'] = has_pos
                    
                except Exception as e:
                    pass
                    
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nMonitor interrompido")

def main():
    """Executa todos os testes de debug"""
    print("\n" + "="*80)
    print(" DEBUG COMPLETO: ML e DETECÇÃO DE POSIÇÃO")
    print("="*80)
    
    # 1. Verificar modelos ML
    check_ml_models()
    
    # 2. Verificar price buffer
    check_price_buffer()
    
    # 3. Verificar detecção de posição
    check_position_detection()
    
    # 4. Monitor em tempo real
    monitor_realtime()
    
    print("\n" + "="*80)
    print(" ANÁLISE COMPLETA")
    print("="*80)
    
    print("\n📊 RESUMO DOS PROBLEMAS:")
    print("\n1. Se ML retorna 0:")
    print("   - Verificar se modelos estão carregados")
    print("   - Verificar se features estão sendo calculadas")
    print("   - Verificar se price_history tem dados")
    print("\n2. Se posição não é detectada:")
    print("   - Verificar se PositionChecker está rodando")
    print("   - Verificar callbacks de posição")
    print("   - Verificar arquivos de status")
    
if __name__ == "__main__":
    main()