#!/usr/bin/env python3
"""
Monitor simples de volume - Verifica se está sendo capturado
"""
import json
import os
import time
from datetime import datetime

def check_volume_status():
    """Verifica status do volume no sistema"""
    
    # Verificar arquivo de monitor
    hmarl_file = "data/monitor/hmarl_status.json"
    if os.path.exists(hmarl_file):
        with open(hmarl_file, 'r') as f:
            data = json.load(f)
            volume = data.get('market_data', {}).get('volume', 0)
            price = data.get('market_data', {}).get('price', 0)
            timestamp = data.get('timestamp', '')
            
            return {
                'timestamp': timestamp,
                'price': price,
                'volume': volume,
                'status': 'OK' if volume > 0 else 'ZERO'
            }
    return None

def check_latest_log():
    """Verifica último volume no log"""
    import glob
    log_files = glob.glob("logs/system_complete_oco_events_*.log")
    
    if not log_files:
        return None
        
    latest_log = max(log_files, key=os.path.getmtime)
    
    # Procurar último TRADE VOLUME
    try:
        with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        # Procurar de trás para frente
        for line in reversed(lines[-100:]):  # Últimas 100 linhas
            if 'TRADE VOLUME' in line:
                # Extrair volume
                if 'Volume:' in line:
                    parts = line.split('Volume:')[1].split('|')[0].strip().split()[0]
                    try:
                        volume = int(parts)
                        
                        # Verificar se é valor incorreto conhecido
                        if volume == 2290083475312:
                            return {'value': volume, 'status': 'BUG_V1'}
                        elif volume == 7577984695221092352:
                            return {'value': volume, 'status': 'BUG_V2'}
                        elif 0 < volume < 1000:
                            return {'value': volume, 'status': 'CORRETO'}
                        else:
                            return {'value': volume, 'status': 'SUSPEITO'}
                    except:
                        pass
    except:
        pass
    
    return None

def main():
    print("="*60)
    print("MONITOR DE VOLUME - QUANTUM TRADER")
    print("="*60)
    print("Pressione Ctrl+C para sair\n")
    
    last_volume = 0
    volume_changes = 0
    
    while True:
        try:
            # Verificar status atual
            status = check_volume_status()
            log_volume = check_latest_log()
            
            # Limpar tela
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print("="*60)
            print(f"MONITOR DE VOLUME - {datetime.now().strftime('%H:%M:%S')}")
            print("="*60)
            
            if status:
                print(f"\n[MONITOR STATUS]")
                print(f"  Timestamp: {status['timestamp']}")
                print(f"  Preço: R$ {status['price']:.2f}")
                print(f"  Volume: {status['volume']} contratos")
                
                if status['volume'] != last_volume:
                    volume_changes += 1
                    last_volume = status['volume']
                
                if status['volume'] > 0:
                    print(f"  >>> CAPTURANDO VOLUME! <<<")
                else:
                    print(f"  [!] Volume ainda zerado")
            
            if log_volume:
                print(f"\n[LOG STATUS]")
                print(f"  Último volume: {log_volume['value']}")
                print(f"  Status: {log_volume['status']}")
                
                if log_volume['status'] == 'BUG_V1':
                    print("  >>> BUG ANTIGO (2290083475312) - Precisa correção")
                elif log_volume['status'] == 'BUG_V2':
                    print("  >>> BUG NOVO (7577984695221092352) - Precisa correção")
                elif log_volume['status'] == 'CORRETO':
                    print(f"  >>> VOLUME CORRETO! {log_volume['value']} contratos")
                else:
                    print(f"  >>> VALOR SUSPEITO - Verificar")
            
            print(f"\n[ESTATÍSTICAS]")
            print(f"  Mudanças de volume detectadas: {volume_changes}")
            print(f"  Status geral: {'FUNCIONANDO' if status and status['volume'] > 0 else 'NÃO CAPTURANDO'}")
            
            # Diagnóstico
            print(f"\n[DIAGNÓSTICO]")
            if status and status['volume'] > 0:
                print("  ✓ Sistema capturando volume corretamente")
            elif log_volume and log_volume['status'] in ['BUG_V1', 'BUG_V2']:
                print("  ✗ Sistema com bug de decodificação")
                print("  SOLUÇÃO:")
                print("    1. Parar sistema: taskkill /F /IM python.exe")
                print("    2. Verificar correção em src/profit_trade_structures.py")
                print("    3. Reiniciar: python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
            else:
                print("  ? Volume não detectado - mercado pode estar parado")
            
            time.sleep(5)  # Atualizar a cada 5 segundos
            
        except KeyboardInterrupt:
            print("\n\nMonitor encerrado")
            break
        except Exception as e:
            print(f"Erro: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()