#!/usr/bin/env python3
"""
Monitor completo do status do sistema em tempo real
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import json
from pathlib import Path
from datetime import datetime
import threading

def monitor_system():
    """Monitora o sistema em tempo real"""
    
    print("="*70)
    print(" MONITOR DO SISTEMA - TEMPO REAL")
    print("="*70)
    print("\nPressione Ctrl+C para parar\n")
    
    last_values = {}
    iteration = 0
    
    try:
        while True:
            iteration += 1
            
            # Limpar tela a cada 10 iterações
            if iteration % 10 == 0:
                os.system('cls' if os.name == 'nt' else 'clear')
                print("="*70)
                print(" MONITOR DO SISTEMA - TEMPO REAL")
                print("="*70)
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Monitorando...\n")
            
            # 1. Verificar ML Status
            ml_file = Path("data/monitor/ml_status.json")
            if ml_file.exists():
                try:
                    with open(ml_file, 'r') as f:
                        ml_data = json.load(f)
                    
                    # Verificar features
                    if 'last_features' in ml_data:
                        features = ml_data['last_features']
                        
                        # Features críticas
                        critical = {
                            'returns_1': features.get('returns_1', 0),
                            'returns_5': features.get('returns_5', 0),
                            'volatility_20': features.get('volatility_20', 0),
                            'order_flow_imbalance': features.get('order_flow_imbalance', 0)
                        }
                        
                        # Verificar se mudaram
                        features_changed = False
                        for key, value in critical.items():
                            last_val = last_values.get(f"feat_{key}", None)
                            if last_val is not None and abs(value - last_val) > 1e-8:
                                features_changed = True
                            last_values[f"feat_{key}"] = value
                        
                        # Mostrar status
                        if features_changed or iteration == 1:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ML FEATURES:")
                            for key, value in critical.items():
                                status = "OK" if abs(value) > 1e-8 else "ZERO"
                                print(f"  {key:20s}: {value:10.6f} [{status}]")
                    
                    # Verificar predições
                    if 'last_prediction' in ml_data:
                        pred = ml_data['last_prediction']
                        signal = pred.get('signal', 0)
                        confidence = pred.get('confidence', 0)
                        
                        # Verificar se mudou
                        pred_key = f"{signal}_{confidence}"
                        if pred_key != last_values.get('last_pred'):
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ML PREDICTION:")
                            print(f"  Signal: {signal}")
                            print(f"  Confidence: {confidence:.2%}")
                            
                            # Verificar predictions detalhadas
                            if 'predictions' in pred:
                                preds = pred['predictions']
                                if 'context' in preds:
                                    regime = preds['context'].get('regime', 'N/A')
                                    print(f"  Regime: {regime}")
                                if 'microstructure' in preds:
                                    order_flow = preds['microstructure'].get('order_flow', 'N/A')
                                    print(f"  Order Flow: {order_flow}")
                            
                            last_values['last_pred'] = pred_key
                            
                except Exception as e:
                    if iteration == 1:
                        print(f"Erro ao ler ml_status.json: {e}")
            
            # 2. Verificar Position Status
            pos_file = Path("data/monitor/position_status.json")
            if pos_file.exists():
                try:
                    with open(pos_file, 'r') as f:
                        pos_data = json.load(f)
                    
                    has_position = pos_data.get('has_position', False)
                    
                    # Verificar se mudou
                    if 'last_has_position' in last_values:
                        if has_position != last_values['last_has_position']:
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] POSITION CHANGE:")
                            if has_position:
                                print("  >>> POSIÇÃO ABERTA <<<")
                                pos = pos_data.get('position', {})
                                print(f"  Quantity: {pos.get('quantity', 0)}")
                                print(f"  Side: {pos.get('side', 'N/A')}")
                            else:
                                print("  >>> POSIÇÃO FECHADA <<<")
                                print("  Sistema liberado para novos trades")
                    
                    last_values['last_has_position'] = has_position
                    
                except Exception as e:
                    if iteration == 1:
                        print(f"Erro ao ler position_status.json: {e}")
            
            # 3. Verificar Logs Recentes
            log_file = Path(f"logs/trading_system_{datetime.now().strftime('%Y%m%d')}.log")
            if log_file.exists() and iteration % 5 == 0:  # Verificar logs a cada 5 segundos
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        # Ler últimas 100 linhas
                        lines = f.readlines()[-100:]
                        
                        # Procurar por eventos importantes
                        important_events = []
                        for line in lines:
                            if any(keyword in line for keyword in [
                                "[POSITION CLOSED]",
                                "[ORPHAN]",
                                "[TRADE]",
                                "[ERRO]",
                                "Lock resetado",
                                "Ordens canceladas"
                            ]):
                                # Extrair timestamp e mensagem
                                parts = line.split(" - ", 2)
                                if len(parts) >= 3:
                                    timestamp = parts[0]
                                    message = parts[2].strip()
                                    important_events.append((timestamp, message))
                        
                        # Mostrar últimos eventos importantes
                        if important_events:
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] EVENTOS RECENTES:")
                            for ts, msg in important_events[-3:]:  # Últimos 3 eventos
                                print(f"  {ts}: {msg[:60]}...")
                                
                except Exception as e:
                    pass
            
            # 4. Resumo do Status
            if iteration % 10 == 1:  # Mostrar resumo a cada 10 iterações
                print("\n" + "="*50)
                print("RESUMO DO STATUS:")
                print("="*50)
                
                # ML funcionando?
                ml_working = False
                if 'feat_returns_1' in last_values:
                    ml_working = abs(last_values['feat_returns_1']) > 1e-8
                print(f"  ML Features: {'OK - Dinâmicas' if ml_working else 'PROBLEMA - Estáticas'}")
                
                # Posição atual
                has_pos = last_values.get('last_has_position', False)
                print(f"  Posição: {'ABERTA' if has_pos else 'FECHADA'}")
                
                # Última predição
                if 'last_pred' in last_values:
                    print(f"  Última Predição: {last_values['last_pred']}")
                
                print("="*50)
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nMonitor finalizado.")
        
        # Resumo final
        print("\n" + "="*70)
        print("RESUMO FINAL:")
        print("="*70)
        
        if 'feat_returns_1' in last_values:
            if abs(last_values['feat_returns_1']) < 1e-8:
                print("\n⚠️  PROBLEMA DETECTADO: Features estáticas (returns = 0)")
                print("   Solução: Execute 'python fix_critical_issues.py' e reinicie")
        
        if last_values.get('last_has_position', False):
            print("\n⚠️  POSIÇÃO AINDA ABERTA")
            print("   Para cancelar ordens órfãs: 'python cancel_orphan_orders.py'")

if __name__ == "__main__":
    monitor_system()