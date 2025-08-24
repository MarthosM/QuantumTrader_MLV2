#!/usr/bin/env python3
"""
Script para verificar e exibir o estado real da posição
Mostra se há grupos OCO ativos e o que isso significa
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Carregar configurações
load_dotenv('.env.production')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def check_system_state():
    """Verifica estado do sistema através dos arquivos de status"""
    
    print("\n" + "="*70)
    print("VERIFICAÇÃO DE ESTADO DO SISTEMA")
    print("="*70)
    
    # 1. Verificar arquivos de status
    print("\n1. ARQUIVOS DE STATUS:")
    print("-" * 40)
    
    status_files = {
        'ml_status.json': 'Status ML',
        'hmarl_status.json': 'Status HMARL',
        'data/monitor/ml_status.json': 'Monitor ML',
        'data/monitor/hmarl_status.json': 'Monitor HMARL',
        'data/monitor/regime_status.json': 'Status Regime'
    }
    
    for file, desc in status_files.items():
        if Path(file).exists():
            mod_time = datetime.fromtimestamp(Path(file).stat().st_mtime)
            age = (datetime.now() - mod_time).total_seconds()
            
            if age < 60:
                status = "[ATIVO]"
                color = "[OK]"
            elif age < 300:
                status = "[RECENTE]"
                color = "[~]"
            else:
                status = "[ANTIGO]"
                color = "[X]"
            
            print(f"  {color} {desc:20} - {status:10} (atualizado há {age:.0f}s)")
        else:
            print(f"  [X] {desc:20} - [NAO EXISTE]")
    
    # 2. Analisar interpretação de OCO
    print("\n2. INTERPRETAÇÃO DE GRUPOS OCO:")
    print("-" * 40)
    
    print("""
  IMPORTANTE: Grupos OCO ativos podem significar:
  
  [OK] COM POSIÇÃO ABERTA:
    - 1 grupo OCO = 1 posição com stop + take pendentes
    - Ordens protegem a posição existente
    - Sistema deve BLOQUEAR novos trades
    
  [X] SEM POSIÇÃO (órfãs):
    - Posição foi fechada mas ordens não foram canceladas
    - Sistema errou ao abrir ordens
    - Necessário cancelar manualmente
    
  Como identificar:
  1. Se GetPosition() retorna TRUE = TEM posição
  2. Se GetPosition() retorna FALSE:
     - Aguardar 60s para confirmar
     - Se persiste = São órfãs, cancelar
  """)
    
    # 3. Recomendações
    print("\n3. RECOMENDAÇÕES:")
    print("-" * 40)
    
    print("""
  Se o sistema está com "grupos OCO ativos":
  
  1. VERIFICAR no ProfitChart:
     - Há posição aberta? (ver aba Posições)
     - Há ordens pendentes? (ver aba Ordens)
  
  2. SE HÁ POSIÇÃO:
     - Sistema está CORRETO em bloquear novos trades
     - Aguardar stop ou take ser executado
  
  3. SE NÃO HÁ POSIÇÃO:
     - Cancelar ordens manualmente no ProfitChart
     - OU executar: python fix_clear_pending_orders.py
     - Reiniciar sistema após limpar
  
  4. PREVENÇÃO:
     - Sistema agora sincroniza melhor com OCO Monitor
     - Aguarda 60s antes de considerar órfãs
     - Marca posição baseada em grupos OCO ativos
  """)
    
    print("\n" + "="*70)
    print("FIM DA VERIFICAÇÃO")
    print("="*70)

if __name__ == "__main__":
    check_system_state()