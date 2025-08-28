"""
Monitor para verificar se features estão dinâmicas em tempo real
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import json
from datetime import datetime
from pathlib import Path

def monitor_features():
    """Monitora as features sendo calculadas pelo sistema"""
    
    print("="*60)
    print("MONITOR: Features Dinâmicas")
    print("="*60)
    print("\nMonitorando arquivos de status para verificar features...")
    print("Pressione Ctrl+C para parar\n")
    
    ml_status_file = Path("data/monitor/ml_status.json")
    last_features = {}
    static_count = 0
    
    try:
        while True:
            if ml_status_file.exists():
                try:
                    with open(ml_status_file, 'r') as f:
                        data = json.load(f)
                    
                    if 'last_features' in data:
                        features = data['last_features']
                        
                        # Verificar features críticas
                        critical_features = ['returns_1', 'returns_5', 'returns_20', 
                                           'volatility_20', 'order_flow_imbalance']
                        
                        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Features atuais:")
                        
                        static_features = []
                        for feat in critical_features:
                            if feat in features:
                                value = features.get(feat, 0)
                                print(f"  {feat:20s}: {value:10.6f}", end="")
                                
                                # Verificar se mudou
                                if feat in last_features:
                                    if abs(value - last_features[feat]) < 1e-8:
                                        print(" [ESTÁTICO]", end="")
                                        static_features.append(feat)
                                    else:
                                        change = (value - last_features[feat]) * 100
                                        print(f" [MUDOU {change:+.4f}%]", end="")
                                print()
                        
                        # Contar features estáticas
                        if len(static_features) >= 3:
                            static_count += 1
                            print(f"\n  ⚠️ AVISO: {len(static_features)} features estáticas há {static_count} ciclos")
                            if static_count > 10:
                                print("  ❌ PROBLEMA: Features travadas! Sistema precisa reiniciar.")
                        else:
                            if static_count > 0:
                                print(f"\n  ✅ Features voltaram a ser dinâmicas após {static_count} ciclos")
                            static_count = 0
                        
                        last_features = features.copy()
                    
                    # Verificar última predição
                    if 'last_prediction' in data:
                        pred = data['last_prediction']
                        print(f"\n  Última predição ML:")
                        print(f"    Signal: {pred.get('signal', 0)}")
                        print(f"    Confidence: {pred.get('confidence', 0):.2%}")
                        
                except Exception as e:
                    print(f"Erro ao ler arquivo: {e}")
            
            time.sleep(2)  # Verificar a cada 2 segundos
            
    except KeyboardInterrupt:
        print("\n\nMonitor finalizado.")

if __name__ == "__main__":
    monitor_features()
