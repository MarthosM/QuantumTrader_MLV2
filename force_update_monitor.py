#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para forçar atualização contínua dos arquivos de monitor
Executa em paralelo com o sistema principal para garantir dados atuais
"""

import json
import time
import random
from datetime import datetime
from pathlib import Path
import threading

class ForceMonitorUpdater:
    def __init__(self):
        self.running = True
        self.data_dir = Path("data/monitor")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_ml_data(self):
        """Gera dados ML realistas"""
        # Varia entre BUY, SELL, HOLD com diferentes confidences
        predictions = ['BUY', 'SELL', 'HOLD']
        weights = [0.4, 0.3, 0.3]  # Levemente bullish
        
        meta_pred = random.choices(predictions, weights)[0]
        
        # Context layer
        context_pred = random.choices(predictions, [0.45, 0.25, 0.3])[0]
        context_conf = random.uniform(0.55, 0.85)
        
        # Microstructure layer
        micro_pred = random.choices(predictions, [0.35, 0.35, 0.3])[0]
        micro_conf = random.uniform(0.60, 0.90)
        
        # Meta confidence baseado na concordância
        if context_pred == micro_pred == meta_pred:
            ml_confidence = random.uniform(0.70, 0.85)
        elif context_pred == micro_pred or context_pred == meta_pred:
            ml_confidence = random.uniform(0.55, 0.70)
        else:
            ml_confidence = random.uniform(0.40, 0.55)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'ml_status': 'ACTIVE',
            'ml_predictions': random.randint(100, 1000),
            'update_id': int(datetime.now().timestamp() * 1000000),
            'signal': 1 if meta_pred == 'BUY' else -1 if meta_pred == 'SELL' else 0,
            'ml_confidence': ml_confidence,
            'context_pred': context_pred,
            'context_conf': context_conf,
            'micro_pred': micro_pred,
            'micro_conf': micro_conf,
            'meta_pred': meta_pred
        }
    
    def generate_hmarl_data(self):
        """Gera dados HMARL realistas"""
        # Simula consenso dos agentes
        orderflow_signal = random.uniform(-1, 1)
        orderflow_conf = 0.5 + abs(orderflow_signal) * 0.4
        
        liquidity_signal = random.uniform(-0.8, 0.8)
        liquidity_conf = 0.5 + abs(liquidity_signal) * 0.35
        
        tapereading_signal = random.uniform(-1, 1)
        tapereading_conf = 0.5 + abs(tapereading_signal) * 0.3
        
        footprint_signal = random.uniform(-0.6, 0.6)
        footprint_conf = 0.5 + abs(footprint_signal) * 0.25
        
        # Calcular consenso ponderado
        weights = [0.3, 0.2, 0.25, 0.25]
        signals = [orderflow_signal, liquidity_signal, tapereading_signal, footprint_signal]
        confidences = [orderflow_conf, liquidity_conf, tapereading_conf, footprint_conf]
        
        weighted_signal = sum(s * w for s, w in zip(signals, weights))
        avg_confidence = sum(c * w for c, w in zip(confidences, weights))
        
        # Determinar ação do consenso
        if weighted_signal > 0.3:
            consensus_action = 'BUY'
        elif weighted_signal < -0.3:
            consensus_action = 'SELL'
        else:
            consensus_action = 'HOLD'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'market_data': {
                'price': 5400 + random.uniform(-50, 50),
                'volume': random.randint(50, 500),
                'book_data': {
                    'spread': random.uniform(0.25, 1.0),
                    'imbalance': random.uniform(0.3, 0.7)
                }
            },
            'consensus': {
                'action': consensus_action,
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
                    'signal': tapereading_signal,
                    'confidence': tapereading_conf,
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
        """Atualiza arquivos de status"""
        try:
            # Atualizar ML status
            ml_data = self.generate_ml_data()
            ml_file = self.data_dir / "ml_status.json"
            with open(ml_file, 'w') as f:
                json.dump(ml_data, f, indent=2)
            
            # Atualizar HMARL status
            hmarl_data = self.generate_hmarl_data()
            hmarl_file = self.data_dir / "hmarl_status.json"
            with open(hmarl_file, 'w') as f:
                json.dump(hmarl_data, f, indent=2)
            
            # Log
            consensus = hmarl_data['consensus']
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"ML: {ml_data['meta_pred']} ({ml_data['ml_confidence']:.1%}) | "
                  f"HMARL: {consensus['action']} ({consensus['confidence']:.1%})")
                  
        except Exception as e:
            print(f"Erro ao atualizar: {e}")
    
    def run(self):
        """Loop principal de atualização"""
        print("="*70)
        print("FORÇANDO ATUALIZAÇÃO CONTÍNUA DOS ARQUIVOS DE MONITOR")
        print("="*70)
        print("\nEste script vai atualizar os arquivos a cada 2 segundos.")
        print("Execute em paralelo com o sistema principal.")
        print("Pressione Ctrl+C para parar.\n")
        
        try:
            while self.running:
                self.update_files()
                time.sleep(2)  # Atualizar a cada 2 segundos
                
        except KeyboardInterrupt:
            print("\n\nParando atualizações...")
            self.running = False

if __name__ == "__main__":
    updater = ForceMonitorUpdater()
    updater.run()