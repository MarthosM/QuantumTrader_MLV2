#!/usr/bin/env python3
"""
Script para reiniciar o sistema com captura de volume funcionando
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path
from datetime import datetime

def kill_process_by_name(process_name):
    """Mata processo pelo nome"""
    try:
        # Windows
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/IM', f'{process_name}.exe'], 
                         capture_output=True)
            subprocess.run(['taskkill', '/F', '/IM', f'{process_name}'], 
                         capture_output=True)
        # Linux/Mac
        else:
            subprocess.run(['pkill', '-f', process_name], 
                         capture_output=True)
    except:
        pass

def main():
    print("\n" + "=" * 60)
    print("REINICIANDO SISTEMA COM CAPTURA DE VOLUME")
    print("=" * 60)
    print()
    
    # 1. Parar sistema atual
    print("[1/4] Parando sistema atual...")
    
    # Tentar parar gentilmente
    try:
        with open('quantum_trader.pid', 'r') as f:
            pid = int(f.read().strip())
            print(f"  Enviando sinal para PID {pid}...")
            
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
                
            time.sleep(3)
    except:
        print("  PID file não encontrado")
    
    # Matar processos python relacionados
    print("  Finalizando processos Python...")
    kill_process_by_name('python')
    kill_process_by_name('START_SYSTEM_COMPLETE_OCO_EVENTS')
    
    # Remover PID file
    try:
        os.remove('quantum_trader.pid')
        print("  PID file removido")
    except:
        pass
    
    print("[OK] Sistema parado")
    
    # 2. Aguardar
    print("\n[2/4] Aguardando 5 segundos...")
    time.sleep(5)
    
    # 3. Verificar configurações
    print("\n[3/4] Verificando configurações...")
    
    # Verificar DLL
    dll_path = Path("ProfitDLL64.dll")
    if not dll_path.exists():
        dll_path = Path("C:/Users/marth/OneDrive/Programacao/Python/QuantumTrader_Production/ProfitDLL64.dll")
    
    if dll_path.exists():
        print(f"  [OK] DLL encontrada: {dll_path}")
    else:
        print("  [X] DLL não encontrada!")
        return False
    
    # Verificar arquivo principal
    main_script = Path("START_SYSTEM_COMPLETE_OCO_EVENTS.py")
    if main_script.exists():
        print(f"  [OK] Script principal encontrado: {main_script}")
    else:
        print("  [X] Script principal não encontrado!")
        return False
    
    # Verificar VolumeTracker
    volume_tracker = Path("src/market_data/volume_capture_system.py")
    if volume_tracker.exists():
        print(f"  [OK] VolumeTracker encontrado")
    else:
        print("  [!] VolumeTracker não encontrado - volume não será capturado")
    
    # 4. Iniciar sistema
    print("\n[4/4] Iniciando sistema com volume...")
    
    # Criar comando
    cmd = [sys.executable, "START_SYSTEM_COMPLETE_OCO_EVENTS.py"]
    
    # Iniciar em novo processo
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        print("[OK] Sistema iniciado com PID:", process.pid)
        print()
        print("=" * 60)
        print("MONITORANDO INICIALIZAÇÃO...")
        print("=" * 60)
        print()
        
        # Monitorar saída por 30 segundos
        start_time = time.time()
        volume_detected = False
        connection_ok = False
        
        while time.time() - start_time < 30:
            line = process.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
                
            # Imprimir linha
            print(line.rstrip())
            
            # Verificar marcos importantes
            if "SISTEMA TOTALMENTE CONECTADO" in line:
                connection_ok = True
                print("\n>>> CONEXÃO ESTABELECIDA! <<<\n")
            
            if "[VOLUME TRACKER]" in line or "Volume:" in line:
                if "Total Volume:" in line and "0 contracts" not in line:
                    volume_detected = True
                    print("\n>>> VOLUME SENDO CAPTURADO! <<<\n")
            
            if "[TRADE]" in line and "Volume=" in line:
                if "Volume=0" not in line:
                    volume_detected = True
                    print("\n>>> VOLUME REAL DETECTADO! <<<\n")
        
        # Resultado
        print("\n" + "=" * 60)
        print("RESULTADO DA REINICIALIZAÇÃO")
        print("=" * 60)
        
        if connection_ok:
            print("[OK] Sistema conectado com sucesso")
        else:
            print("[!] Sistema pode não ter conectado completamente")
        
        if volume_detected:
            print("[OK] Volume sendo capturado corretamente!")
        else:
            print("[!] Volume ainda não detectado (pode estar aguardando trades)")
        
        print()
        print("Sistema rodando em background.")
        print("Use 'python stop_production.py' para parar.")
        print()
        
        return True
        
    except Exception as e:
        print(f"[X] Erro ao iniciar sistema: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)