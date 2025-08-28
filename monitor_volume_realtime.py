"""
Monitor em tempo real do status de volume
Verifica se a correção está funcionando
"""
import json
import os
import time
from datetime import datetime
import subprocess

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_latest_log():
    """Encontra o log mais recente"""
    import glob
    log_files = glob.glob("logs/system_complete_oco_events_*.log")
    if log_files:
        return max(log_files, key=os.path.getmtime)
    return None

def check_log_for_volumes(log_file, last_position=0):
    """Verifica volumes no log"""
    volumes_found = []
    new_position = last_position
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            f.seek(last_position)
            new_lines = f.readlines()
            new_position = f.tell()
            
        for line in new_lines:
            if 'TRADE VOLUME' in line or 'TRADE_V2' in line:
                # Extrair volume
                if 'Volume:' in line:
                    parts = line.split('Volume:')[1].split('|')[0].strip().split()[0]
                    try:
                        volume = int(parts)
                        volumes_found.append(volume)
                    except:
                        pass
                elif 'Volume=' in line:
                    parts = line.split('Volume=')[1].split(',')[0].strip()
                    try:
                        volume = int(parts)
                        volumes_found.append(volume)
                    except:
                        pass
    except:
        pass
    
    return volumes_found, new_position

def main():
    print("="*60)
    print("MONITOR DE VOLUME EM TEMPO REAL")
    print("="*60)
    print("Pressione Ctrl+C para sair\n")
    
    # Encontrar log atual
    log_file = get_latest_log()
    if not log_file:
        print("ERRO: Nenhum log encontrado!")
        return
    
    print(f"Monitorando: {os.path.basename(log_file)}\n")
    
    # Estado
    last_log_pos = 0
    total_trades = 0
    valid_volumes = []
    invalid_volumes = []
    last_update = None
    
    try:
        while True:
            clear_screen()
            
            # Header
            print("="*60)
            print("MONITOR DE VOLUME - QUANTUM TRADER")
            print(f"Hora: {datetime.now().strftime('%H:%M:%S')}")
            print("="*60)
            
            # Verificar monitor files
            try:
                with open("data/monitor/hmarl_status.json", 'r') as f:
                    hmarl_data = json.load(f)
                    market = hmarl_data.get('market_data', {})
                    timestamp = hmarl_data.get('timestamp', '')
                    
                print(f"\n[MONITOR STATUS]")
                print(f"  Última atualização: {timestamp}")
                print(f"  Preço atual: R$ {market.get('price', 0):.2f}")
                print(f"  Volume no monitor: {market.get('volume', 0)} contratos")
                
                if market.get('volume', 0) > 0:
                    print(f"  >>> VOLUME CAPTURADO COM SUCESSO! <<<")
            except:
                pass
            
            # Verificar novos trades no log
            new_volumes, last_log_pos = check_log_for_volumes(log_file, last_log_pos)
            
            for vol in new_volumes:
                total_trades += 1
                if vol == 2290083475312:
                    invalid_volumes.append(vol)
                    print(f"\n[TRADE #{total_trades}] Volume INCORRETO: {vol}")
                    print("  >>> BUG NAO CORRIGIDO - PRECISA REINICIAR!")
                elif 0 < vol < 1000:
                    valid_volumes.append(vol)
                    print(f"\n[TRADE #{total_trades}] Volume CORRETO: {vol} contratos")
                    print("  >>> CORRECAO FUNCIONANDO!")
                elif vol == 0:
                    print(f"\n[TRADE #{total_trades}] Volume zero (mercado parado?)")
                else:
                    invalid_volumes.append(vol)
                    print(f"\n[TRADE #{total_trades}] Volume suspeito: {vol}")
            
            # Estatísticas
            print(f"\n[ESTATÍSTICAS]")
            print(f"  Total de trades: {total_trades}")
            print(f"  Volumes válidos: {len(valid_volumes)}")
            print(f"  Volumes inválidos: {len(invalid_volumes)}")
            
            if valid_volumes:
                print(f"\n  Volumes válidos capturados:")
                print(f"    Média: {sum(valid_volumes)/len(valid_volumes):.1f} contratos")
                print(f"    Mínimo: {min(valid_volumes)} contratos")
                print(f"    Máximo: {max(valid_volumes)} contratos")
                print(f"    Últimos 5: {valid_volumes[-5:]}")
            
            # Diagnóstico
            print(f"\n[DIAGNÓSTICO]")
            if invalid_volumes and 2290083475312 in invalid_volumes:
                print("  PROBLEMA: Sistema ainda com bug de decodificação")
                print("  SOLUÇÃO: Reiniciar o sistema para aplicar correção")
                print("  COMANDO: python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
            elif valid_volumes:
                print("  SUCESSO: Sistema capturando volumes corretamente!")
                print(f"  {len(valid_volumes)} volumes válidos processados")
            elif total_trades == 0:
                print("  AGUARDANDO: Nenhum trade capturado ainda")
                print("  Possíveis causas:")
                print("    - Mercado em leilão")
                print("    - Baixa liquidez")
                print("    - Sistema ainda inicializando")
            else:
                print("  VERIFICANDO: Trades capturados mas sem volume válido")
            
            time.sleep(2)  # Atualizar a cada 2 segundos
            
    except KeyboardInterrupt:
        print("\n\nMonitor encerrado pelo usuário")
        
        # Resumo final
        if valid_volumes:
            print(f"\nRESUMO FINAL:")
            print(f"  Total de volumes válidos: {len(valid_volumes)}")
            print(f"  Média geral: {sum(valid_volumes)/len(valid_volumes):.1f} contratos")
            print(f"  >>> SISTEMA FUNCIONANDO CORRETAMENTE!")
        elif invalid_volumes:
            print(f"\nRESUMO FINAL:")
            print(f"  Total de volumes inválidos: {len(invalid_volumes)}")
            print(f"  >>> SISTEMA PRECISA SER REINICIADO!")

if __name__ == "__main__":
    main()