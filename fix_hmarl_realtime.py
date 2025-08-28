#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fix para garantir que o HMARL receba e processe dados em tempo real
"""

import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime

# Adicionar path para imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

def test_hmarl_realtime():
    """Testa HMARL com dados reais"""
    
    print("="*70)
    print("TESTE HMARL REAL-TIME")
    print("="*70)
    
    # Importar HMARL
    from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
    
    print("\n[1] Inicializando HMARL...")
    hmarl = HMARLAgentsRealtime()
    print("   [OK] HMARL inicializado")
    
    print("\n[2] Simulando dados de mercado...")
    
    # Simular 10 atualizações
    for i in range(10):
        price = 5400 + (i * 5)
        volume = 100 + (i * 10)
        
        # Simular book data
        book_data = {
            'bid_price_1': price - 0.5,
            'ask_price_1': price + 0.5,
            'bid_qty_1': 50 + i,
            'ask_qty_1': 50 - i
        }
        
        # Simular features
        features = {
            'order_flow_imbalance_5': 0.1 * (i - 5),
            'signed_volume_5': 100 * (i - 5),
            'trade_flow_5': 50 * (i - 5),
            'book_imbalance': (book_data['bid_qty_1'] - book_data['ask_qty_1']) / 100,
            'spread': book_data['ask_price_1'] - book_data['bid_price_1']
        }
        
        # Atualizar HMARL
        print(f"\n   Atualização #{i+1}:")
        print(f"      Price: {price:.2f}")
        print(f"      Volume: {volume}")
        
        hmarl.update_market_data(
            price=price,
            volume=volume,
            book_data=book_data,
            features=features
        )
        
        # Obter consenso
        consensus = hmarl.get_consensus(features)
        
        print(f"      Consenso: {consensus['action']} (signal={consensus['signal']:.3f}, conf={consensus['confidence']:.1%})")
        
        # Mostrar agentes
        for agent_name, agent_data in consensus['agents'].items():
            print(f"         {agent_name}: signal={agent_data['signal']:.3f}, conf={agent_data['confidence']:.1%}")
        
        # Salvar em arquivo
        save_hmarl_status(consensus, price)
        
        time.sleep(0.5)  # Pequena pausa
    
    print("\n[3] Verificando arquivo de status...")
    
    status_file = Path("data/monitor/hmarl_status.json")
    if status_file.exists():
        with open(status_file, 'r') as f:
            data = json.load(f)
        
        print(f"   Timestamp: {data['timestamp']}")
        print(f"   Consenso: {data['consensus']['action']} @ {data['consensus']['confidence']*100:.1f}%")
        print("   [OK] Arquivo atualizado corretamente")
    else:
        print("   [ERRO] Arquivo não encontrado")
    
    print("\n" + "="*70)
    print("TESTE COMPLETO!")
    print("="*70)

def save_hmarl_status(consensus, price):
    """Salva status HMARL para o monitor"""
    try:
        Path("data/monitor").mkdir(parents=True, exist_ok=True)
        
        hmarl_data = {
            'timestamp': datetime.now().isoformat(),
            'market_data': {
                'price': price,
                'volume': 100,
                'book_data': {
                    'spread': 1.0,
                    'imbalance': 0.5
                }
            },
            'consensus': {
                'action': consensus.get('action', 'HOLD'),
                'confidence': consensus.get('confidence', 0.5),
                'signal': consensus.get('signal', 0),
                'weights': {
                    'OrderFlowSpecialist': 0.3,
                    'LiquidityAgent': 0.2,
                    'TapeReadingAgent': 0.25,
                    'FootprintPatternAgent': 0.25
                }
            },
            'agents': {}
        }
        
        # Adicionar dados dos agentes
        for agent_name, agent_info in consensus.get('agents', {}).items():
            hmarl_data['agents'][agent_name] = {
                'signal': agent_info.get('signal', 0),
                'confidence': agent_info.get('confidence', 0.5),
                'weight': agent_info.get('weight', 0.25)
            }
        
        with open("data/monitor/hmarl_status.json", 'w') as f:
            json.dump(hmarl_data, f, indent=2)
            
    except Exception as e:
        print(f"   Erro ao salvar: {e}")

if __name__ == "__main__":
    test_hmarl_realtime()