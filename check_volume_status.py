"""
Verifica status do volume no sistema em produção
"""
import json
import os
from datetime import datetime

print("=" * 60)
print("STATUS DE VOLUME - QUANTUM TRADER")
print("=" * 60)

# Verificar ML status
ml_file = "data/monitor/ml_status.json"
if os.path.exists(ml_file):
    with open(ml_file, 'r') as f:
        ml_data = json.load(f)
        print(f"\n[ML STATUS]")
        print(f"  Timestamp: {ml_data.get('timestamp', 'N/A')}")
        print(f"  Signal: {ml_data.get('signal', 0)}")
        print(f"  Confidence: {ml_data.get('ml_confidence', 0):.2%}")

# Verificar HMARL status
hmarl_file = "data/monitor/hmarl_status.json"
if os.path.exists(hmarl_file):
    with open(hmarl_file, 'r') as f:
        hmarl_data = json.load(f)
        market = hmarl_data.get('market_data', {})
        print(f"\n[MARKET DATA]")
        print(f"  Price: R$ {market.get('price', 0):.2f}")
        print(f"  Volume: {market.get('volume', 0)} contratos")
        
        if market.get('volume', 0) == 0:
            print(f"  ⚠️ VOLUME AINDA ZERADO!")
        else:
            print(f"  ✅ VOLUME CAPTURADO COM SUCESSO!")

# Verificar último log
import glob
log_files = glob.glob("logs/system_complete_oco_events_*.log")
if log_files:
    latest_log = max(log_files, key=os.path.getmtime)
    
    # Procurar últimos volumes nos logs
    print(f"\n[ÚLTIMOS TRADES NO LOG]")
    print(f"  Arquivo: {os.path.basename(latest_log)}")
    
    with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    # Procurar últimos TRADE VOLUME
    trade_lines = [l for l in lines if 'TRADE VOLUME' in l]
    if trade_lines:
        for line in trade_lines[-3:]:
            # Extrair volume do log
            if 'Volume:' in line:
                parts = line.split('Volume:')[1].split('|')[0].strip()
                print(f"  Volume encontrado: {parts}")
                
                # Verificar se é o valor errado
                if '2290083475312' in parts:
                    print(f"    ❌ VALOR INCORRETO (bug não corrigido)")
                elif parts != '0':
                    print(f"    ✅ POSSÍVEL CORREÇÃO APLICADA")
    else:
        print(f"  Nenhum trade encontrado no log")

print("\n" + "=" * 60)
print("DIAGNÓSTICO:")

if market.get('volume', 0) == 0:
    print("❌ Sistema ainda não está capturando volume corretamente")
    print("\nPRÓXIMOS PASSOS:")
    print("1. Reiniciar o sistema para aplicar correção")
    print("2. Verificar se mercado está ativo (não em leilão)")
    print("3. Aguardar trades serem executados")
else:
    print("✅ Sistema capturando volume com sucesso!")
    print(f"Volume atual: {market.get('volume', 0)} contratos")