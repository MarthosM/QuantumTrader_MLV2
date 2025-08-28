#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico completo do fluxo de dados HMARL
"""

import sys
import os
import time
import json
import psutil
from datetime import datetime
from pathlib import Path

# Adicionar paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

def check_processes():
    """Verifica processos Python rodando"""
    print("\n[1] VERIFICANDO PROCESSOS")
    print("-" * 50)
    
    python_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'QuantumTrader' in cmdline:
                    python_processes.append({
                        'pid': proc.info['pid'],
                        'cmd': cmdline[:100]
                    })
        except:
            pass
    
    if python_processes:
        print(f"   [OK] {len(python_processes)} processos QuantumTrader rodando:")
        for p in python_processes:
            print(f"      PID {p['pid']}: {p['cmd']}")
    else:
        print("   [X] Nenhum processo QuantumTrader encontrado!")
        print("   [!] O sistema precisa estar rodando!")
    
    return len(python_processes) > 0

def check_hmarl_module():
    """Verifica se módulo HMARL carrega corretamente"""
    print("\n[2] TESTANDO MÓDULO HMARL")
    print("-" * 50)
    
    try:
        from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
        print("   [OK] Módulo importado com sucesso")
        
        # Tentar criar instância
        hmarl = HMARLAgentsRealtime()
        print("   [OK] Instância criada com sucesso")
        
        # Verificar métodos
        methods = ['update_market_data', 'get_consensus', 'analyze_order_flow']
        for method in methods:
            if hasattr(hmarl, method):
                print(f"   [OK] Método {method} existe")
            else:
                print(f"   [X] Método {method} NÃO ENCONTRADO!")
        
        return True
        
    except Exception as e:
        print(f"   [X] Erro ao carregar módulo: {e}")
        return False

def check_file_updates():
    """Verifica atualização dos arquivos"""
    print("\n[3] VERIFICANDO ARQUIVOS DE STATUS")
    print("-" * 50)
    
    files = {
        'ml_status.json': 'data/monitor/ml_status.json',
        'hmarl_status.json': 'data/monitor/hmarl_status.json'
    }
    
    results = {}
    for name, path in files.items():
        if Path(path).exists():
            with open(path, 'r') as f:
                data = json.load(f)
            
            timestamp = data.get('timestamp', '')
            if timestamp:
                file_time = datetime.fromisoformat(timestamp)
                age = (datetime.now() - file_time).total_seconds()
                
                if age < 60:
                    status = "[OK] ATUALIZADO"
                    symbol = "[OK]"
                elif age < 300:
                    status = "[!] RECENTE"
                    symbol = "[!]"
                else:
                    status = "[X] DESATUALIZADO"
                    symbol = "[X]"
                
                print(f"   {symbol} {name}")
                print(f"      Timestamp: {timestamp}")
                print(f"      Idade: {age:.0f} segundos ({status})")
                
                results[name] = {
                    'age': age,
                    'status': status,
                    'data': data
                }
        else:
            print(f"   [X] {name} - NÃO EXISTE!")
            results[name] = None
    
    return results

def test_hmarl_update():
    """Testa se HMARL responde a atualizações"""
    print("\n[4] TESTANDO ATUALIZAÇÃO HMARL")
    print("-" * 50)
    
    try:
        from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
        
        hmarl = HMARLAgentsRealtime()
        print("   [OK] HMARL inicializado")
        
        # Teste 1: Update sem dados
        print("\n   Teste 1: Update vazio")
        hmarl.update_market_data()
        consensus = hmarl.get_consensus()
        print(f"      Resultado: {consensus['action']} ({consensus['confidence']:.1%})")
        
        # Teste 2: Update com preço
        print("\n   Teste 2: Update com preço")
        hmarl.update_market_data(price=5400.0)
        consensus = hmarl.get_consensus()
        print(f"      Resultado: {consensus['action']} ({consensus['confidence']:.1%})")
        
        # Teste 3: Update completo
        print("\n   Teste 3: Update completo")
        features = {
            'order_flow_imbalance_5': 0.5,
            'signed_volume_5': 1000,
            'trade_flow_5': 500
        }
        hmarl.update_market_data(price=5400.0, volume=100, features=features)
        consensus = hmarl.get_consensus(features)
        print(f"      Resultado: {consensus['action']} ({consensus['confidence']:.1%})")
        
        return True
        
    except Exception as e:
        print(f"   [X] Erro no teste: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_system_logs():
    """Verifica logs do sistema por erros HMARL"""
    print("\n[5] VERIFICANDO LOGS DO SISTEMA")
    print("-" * 50)
    
    log_dir = Path("logs")
    if not log_dir.exists():
        print("   [X] Diretório de logs não encontrado")
        return
    
    # Pegar log mais recente
    log_files = list(log_dir.glob("*.log"))
    if not log_files:
        print("   [X] Nenhum arquivo de log encontrado")
        return
    
    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
    print(f"   Analisando: {latest_log.name}")
    
    # Procurar por padrões relevantes
    patterns = {
        'HMARL init': 0,
        'update_market_data': 0,
        'get_consensus': 0,
        'HMARL error': 0,
        '_save_hmarl_status': 0
    }
    
    try:
        with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-1000:]  # Últimas 1000 linhas
            
        for line in lines:
            for pattern in patterns:
                if pattern.lower() in line.lower():
                    patterns[pattern] += 1
        
        print("\n   Ocorrências nos logs:")
        for pattern, count in patterns.items():
            if count > 0:
                print(f"      [OK] {pattern}: {count} vezes")
            else:
                print(f"      [X] {pattern}: NUNCA")
                
    except Exception as e:
        print(f"   [X] Erro ao ler logs: {e}")

def check_main_system_code():
    """Verifica se as correções estão no código"""
    print("\n[6] VERIFICANDO CÓDIGO DO SISTEMA")
    print("-" * 50)
    
    main_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    if not Path(main_file).exists():
        print(f"   [X] {main_file} não encontrado!")
        return False
    
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar se as correções estão presentes
    checks = {
        'update_market_data no make_hybrid_prediction': 'self.hmarl_agents.update_market_data(' in content,
        'update_market_data no process_book_update': 'if self.hmarl_agents and self.current_price > 0:' in content,
        '_save_hmarl_status definido': 'def _save_hmarl_status(self' in content,
        '_save_ml_status definido': 'def _save_ml_status(self' in content,
        'Chamada _save_hmarl_status': 'self._save_hmarl_status(' in content
    }
    
    all_ok = True
    for check, present in checks.items():
        if present:
            print(f"   [OK] {check}")
        else:
            print(f"   [X] {check} - NÃO ENCONTRADO!")
            all_ok = False
    
    return all_ok

def test_direct_save():
    """Testa salvamento direto de arquivo HMARL"""
    print("\n[7] TESTANDO SALVAMENTO DIRETO")
    print("-" * 50)
    
    try:
        from pathlib import Path
        import json
        from datetime import datetime
        
        # Preparar dados de teste
        test_data = {
            'timestamp': datetime.now().isoformat(),
            'market_data': {
                'price': 5400.0,
                'volume': 100,
                'book_data': {'spread': 1.0, 'imbalance': 0.5}
            },
            'consensus': {
                'action': 'TEST',
                'confidence': 0.99,
                'signal': 0.99
            },
            'agents': {
                'OrderFlowSpecialist': {'signal': 1, 'confidence': 0.99, 'weight': 0.3}
            }
        }
        
        # Salvar
        Path("data/monitor").mkdir(parents=True, exist_ok=True)
        test_file = Path("data/monitor/hmarl_test.json")
        
        with open(test_file, 'w') as f:
            json.dump(test_data, f, indent=2)
        
        print("   [OK] Arquivo de teste salvo")
        
        # Verificar
        if test_file.exists():
            with open(test_file, 'r') as f:
                saved_data = json.load(f)
            
            if saved_data['consensus']['action'] == 'TEST':
                print("   [OK] Dados salvos corretamente")
                test_file.unlink()  # Limpar
                return True
        
        print("   [X] Erro ao verificar arquivo salvo")
        return False
        
    except Exception as e:
        print(f"   [X] Erro no teste: {e}")
        return False

def main():
    """Executa diagnóstico completo"""
    print("=" * 60)
    print("DIAGNÓSTICO COMPLETO - FLUXO HMARL")
    print("=" * 60)
    
    results = {
        'processes': check_processes(),
        'module': check_hmarl_module(),
        'files': check_file_updates(),
        'update_test': test_hmarl_update(),
        'logs': check_system_logs(),
        'code': check_main_system_code(),
        'save': test_direct_save()
    }
    
    print("\n" + "=" * 60)
    print("RESUMO DO DIAGNÓSTICO")
    print("=" * 60)
    
    # Análise dos resultados
    if not results['processes']:
        print("\n[ERRO] PROBLEMA PRINCIPAL: Sistema não está rodando!")
        print("   SOLUÇÃO: Execute 'python START_SYSTEM_COMPLETE_OCO_EVENTS.py'")
        
    elif not results['code']:
        print("\n[ERRO] PROBLEMA PRINCIPAL: Correções não estão no código!")
        print("   SOLUÇÃO: As correções não foram aplicadas ou foram sobrescritas.")
        print("   Execute novamente os scripts de correção.")
        
    elif results['files'] and results['files'].get('hmarl_status.json'):
        age = results['files']['hmarl_status.json']['age']
        if age > 300:
            print(f"\n[ERRO] PROBLEMA PRINCIPAL: HMARL não está sendo atualizado!")
            print(f"   Arquivo com {age:.0f} segundos de idade")
            print("   POSSÍVEIS CAUSAS:")
            print("   1. update_market_data() não está sendo chamado")
            print("   2. _save_hmarl_status() não está sendo chamado")
            print("   3. Sistema travado ou em loop infinito")
    else:
        print("\n[OK] Sistema parece estar funcionando corretamente")
    
    print("\n" + "=" * 60)
    print("FIM DO DIAGNÓSTICO")
    print("=" * 60)

if __name__ == "__main__":
    main()