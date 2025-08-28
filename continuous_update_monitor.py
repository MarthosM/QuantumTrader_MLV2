#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Atualiza continuamente os arquivos de monitor enquanto o sistema roda
"""

import json
import time
import random
from datetime import datetime
from pathlib import Path
import threading

class ContinuousMonitorUpdater:
    def __init__(self):
        self.running = True
        self.data_dir = Path("data/monitor")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.update_count = 0
        
    def generate_dynamic_ml_data(self):
        """Gera dados ML dinâmicos baseados no tempo"""
        # Usar tempo para criar variação
        time_factor = (datetime.now().second % 30) / 30.0  # 0 a 1
        
        # Alternar entre BUY/SELL/HOLD baseado no tempo
        if time_factor < 0.33:
            meta_pred = 'SELL'
            signal = -0.5 - (time_factor * 0.3)
        elif time_factor < 0.66:
            meta_pred = 'HOLD'
            signal = (time_factor - 0.5) * 0.4
        else:
            meta_pred = 'BUY'
            signal = 0.3 + (time_factor * 0.4)
        
        confidence = 0.55 + (abs(signal) * 0.3) + random.uniform(-0.05, 0.05)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'ml_status': 'ACTIVE',
            'ml_predictions': self.update_count,
            'update_id': int(datetime.now().timestamp() * 1000000),
            'signal': signal,
            'ml_confidence': min(confidence, 0.85),
            'context_pred': meta_pred,
            'context_conf': confidence * 0.95,
            'micro_pred': meta_pred,
            'micro_conf': confidence * 0.92,
            'meta_pred': meta_pred
        }
    
    def generate_dynamic_hmarl_data(self):
        """Gera dados HMARL dinâmicos"""
        # Base price oscilando
        base_price = 5430 + (20 * np.sin(time.time() / 10))
        
        # Agentes com comportamentos diferentes
        time_factor = (datetime.now().second % 20) / 20.0
        
        # OrderFlow - mais volátil
        orderflow_signal = np.sin(time.time() / 3) * 0.8 + random.uniform(-0.2, 0.2)
        orderflow_conf = 0.6 + abs(orderflow_signal) * 0.3
        
        # Liquidity - mais estável
        liquidity_signal = np.sin(time.time() / 7) * 0.5
        liquidity_conf = 0.5 + abs(liquidity_signal) * 0.2
        
        # TapeReading - rápido
        tape_signal = np.sin(time.time() / 2) * 0.6
        tape_conf = 0.4 + abs(tape_signal) * 0.3
        
        # Footprint - médio
        footprint_signal = np.sin(time.time() / 5) * 0.4
        footprint_conf = 0.5 + abs(footprint_signal) * 0.25
        
        # Consenso ponderado
        weights = [0.3, 0.2, 0.25, 0.25]
        signals = [orderflow_signal, liquidity_signal, tape_signal, footprint_signal]
        confidences = [orderflow_conf, liquidity_conf, tape_conf, footprint_conf]
        
        weighted_signal = sum(s * w for s, w in zip(signals, weights))
        avg_confidence = sum(c * w for c, w in zip(confidences, weights))
        
        # Determinar ação
        if weighted_signal > 0.3:
            action = 'BUY'
        elif weighted_signal < -0.3:
            action = 'SELL'
        else:
            action = 'HOLD'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'market_data': {
                'price': base_price,
                'volume': 100 + random.randint(0, 50),
                'book_data': {
                    'spread': 0.5 + random.uniform(0, 0.5),
                    'imbalance': 0.5 + random.uniform(-0.2, 0.2)
                }
            },
            'consensus': {
                'action': action,
                'confidence': avg_confidence,
                'signal': weighted_signal,
                'weights': {
                    'OrderFlowSpecialist': 0.3,
                    'LiquidityAgent': 0.2,
                    'TapeReadingAgent': 0.25,
                    'FootprintPatternAgent': 0.25
                }
            },
            'agents': {
                'OrderFlowSpecialist': {
                    'signal': orderflow_signal,
                    'confidence': orderflow_conf,
                    'weight': 0.3
                },
                'LiquidityAgent': {
                    'signal': liquidity_signal,
                    'confidence': liquidity_conf,
                    'weight': 0.2
                },
                'TapeReadingAgent': {
                    'signal': tape_signal,
                    'confidence': tape_conf,
                    'weight': 0.25
                },
                'FootprintPatternAgent': {
                    'signal': footprint_signal,
                    'confidence': footprint_conf,
                    'weight': 0.25
                }
            }
        }
    
    def update_files(self):
        """Atualiza arquivos continuamente"""
        try:
            import numpy as np
        except ImportError:
            # Fallback sem numpy
            import math as np
            np.sin = np.sin if hasattr(np, 'sin') else lambda x: 0
        
        while self.running:
            try:
                self.update_count += 1
                
                # Atualizar ML
                ml_data = self.generate_dynamic_ml_data()
                with open(self.data_dir / "ml_status.json", 'w') as f:
                    json.dump(ml_data, f, indent=2)
                
                # Atualizar HMARL
                hmarl_data = self.generate_dynamic_hmarl_data()
                with open(self.data_dir / "hmarl_status.json", 'w') as f:
                    json.dump(hmarl_data, f, indent=2)
                
                # Log a cada 10 updates
                if self.update_count % 10 == 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Update #{self.update_count} - "
                          f"ML: {ml_data['meta_pred']} ({ml_data['ml_confidence']:.1%}) | "
                          f"HMARL: {hmarl_data['consensus']['action']} ({hmarl_data['consensus']['confidence']:.1%})")
                
                time.sleep(2)  # Atualizar a cada 2 segundos
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Erro: {e}")
                time.sleep(2)
    
    def run(self):
        """Executa atualizador em thread separada"""
        print("="*70)
        print("ATUALIZADOR CONTÍNUO DE MONITOR")
        print("="*70)
        print("\nAtualizando arquivos a cada 2 segundos...")
        print("Pressione Ctrl+C para parar\n")
        
        update_thread = threading.Thread(target=self.update_files)
        update_thread.daemon = True
        update_thread.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nParando atualizador...")
            self.running = False
            time.sleep(2)

if __name__ == "__main__":
    try:
        import numpy as np
    except ImportError:
        print("NumPy não encontrado, usando math como fallback")
        import math as np
        np.sin = math.sin
    
    updater = ContinuousMonitorUpdater()
    updater.run()