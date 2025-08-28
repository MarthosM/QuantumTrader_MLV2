#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testa o fluxo de atualização do sistema
"""

import time
import json
from datetime import datetime
from pathlib import Path

def check_file_updates():
    """Monitora atualização dos arquivos em tempo real"""
    
    print("="*70)
    print("MONITORANDO ATUALIZAÇÃO DOS ARQUIVOS")
    print("="*70)
    print("\nVerificando a cada 2 segundos...\n")
    
    files_to_monitor = {
        'ml_status.json': 'data/monitor/ml_status.json',
        'hmarl_status.json': 'data/monitor/hmarl_status.json'
    }
    
    last_timestamps = {}
    
    try:
        while True:
            updates = []
            
            for name, path in files_to_monitor.items():
                if Path(path).exists():
                    with open(path, 'r') as f:
                        data = json.load(f)
                    
                    current_timestamp = data.get('timestamp', '')
                    
                    if current_timestamp:
                        # Checar se mudou
                        if name not in last_timestamps:
                            last_timestamps[name] = current_timestamp
                            updates.append(f"{name}: INICIAL")
                        elif last_timestamps[name] != current_timestamp:
                            # Calcular idade
                            file_time = datetime.fromisoformat(current_timestamp)
                            age = (datetime.now() - file_time).total_seconds()
                            
                            # Pegar dados relevantes
                            if 'ml_status' in path:
                                action = data.get('meta_pred', 'N/A')
                                conf = data.get('ml_confidence', 0)
                                updates.append(f"{name}: ATUALIZADO! {action} {conf:.1%} (idade: {age:.1f}s)")
                            else:
                                consensus = data.get('consensus', {})
                                action = consensus.get('action', 'N/A')
                                conf = consensus.get('confidence', 0)
                                updates.append(f"{name}: ATUALIZADO! {action} {conf:.1%} (idade: {age:.1f}s)")
                            
                            last_timestamps[name] = current_timestamp
                        else:
                            # Não mudou, calcular idade
                            file_time = datetime.fromisoformat(current_timestamp)
                            age = (datetime.now() - file_time).total_seconds()
                            
                            if age > 30:
                                updates.append(f"{name}: PARADO há {age:.0f}s")
            
            if updates:
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] " + " | ".join(updates))
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\nMonitoramento parado.")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    check_file_updates()