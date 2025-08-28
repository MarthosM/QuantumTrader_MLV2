#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica se os arquivos de status do monitor estão sendo atualizados
"""

import json
import time
from pathlib import Path
from datetime import datetime

def check_monitor_updates():
    """Verifica atualização dos arquivos de monitor"""
    
    print("="*70)
    print("VERIFICAÇÃO DE ATUALIZAÇÃO DO MONITOR")
    print("="*70)
    
    files_to_check = [
        "data/monitor/ml_status.json",
        "data/monitor/hmarl_status.json"
    ]
    
    print("\n[1] Verificando existência dos arquivos...")
    for file_path in files_to_check:
        if Path(file_path).exists():
            print(f"   [OK] {file_path}")
        else:
            print(f"   [X] {file_path} - NÃO EXISTE!")
    
    print("\n[2] Verificando timestamps...")
    for file_path in files_to_check:
        if Path(file_path).exists():
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Pegar timestamp do arquivo
            file_timestamp = data.get('timestamp')
            if file_timestamp:
                # Converter ISO para datetime
                file_dt = datetime.fromisoformat(file_timestamp)
                now = datetime.now()
                age = (now - file_dt).total_seconds()
                
                print(f"\n   [FILE] {Path(file_path).name}")
                print(f"      Timestamp: {file_timestamp}")
                print(f"      Idade: {age:.1f} segundos")
                
                if age < 5:
                    print(f"      [OK] ATUALIZADO (< 5s)")
                elif age < 30:
                    print(f"      [!] RECENTE ({age:.0f}s)")
                else:
                    print(f"      [X] DESATUALIZADO ({age:.0f}s)")
                
                # Mostrar conteúdo relevante
                if 'ml_status' in file_path:
                    print(f"      ML: {data.get('meta_pred', 'N/A')} @ {data.get('ml_confidence', 0)*100:.1f}%")
                else:
                    consensus = data.get('consensus', {})
                    print(f"      HMARL: {consensus.get('action', 'N/A')} @ {consensus.get('confidence', 0)*100:.1f}%")
    
    print("\n[3] Monitorando mudanças por 10 segundos...")
    print("   (Se o sistema estiver rodando, os arquivos devem atualizar)")
    
    initial_states = {}
    for file_path in files_to_check:
        if Path(file_path).exists():
            initial_states[file_path] = Path(file_path).stat().st_mtime
    
    time.sleep(10)
    
    print("\n[4] Verificando se houve atualizações...")
    updates_detected = False
    for file_path in files_to_check:
        if Path(file_path).exists():
            current_mtime = Path(file_path).stat().st_mtime
            if file_path in initial_states:
                if current_mtime != initial_states[file_path]:
                    print(f"   [OK] {Path(file_path).name} - ATUALIZADO!")
                    updates_detected = True
                else:
                    print(f"   [!] {Path(file_path).name} - sem mudanças")
    
    print("\n" + "="*70)
    if updates_detected:
        print("[OK] SISTEMA ATUALIZANDO CORRETAMENTE!")
    else:
        print("[X] SISTEMA NÃO ESTÁ ATUALIZANDO OS ARQUIVOS!")
        print("\nSoluções:")
        print("1. Verificar se o sistema está rodando:")
        print("   ps aux | grep START_SYSTEM")
        print("\n2. Reiniciar o sistema com as correções:")
        print("   python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
        print("\n3. Executar refresh manual:")
        print("   python refresh_monitor_files.py")
    print("="*70)

if __name__ == "__main__":
    check_monitor_updates()