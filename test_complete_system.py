#!/usr/bin/env python3
"""
Teste completo do sistema com todas as correções
"""

import time
import json
from pathlib import Path
from datetime import datetime

def check_system():
    """Verifica se o sistema está funcionando corretamente"""
    
    print("\n" + "=" * 80)
    print(" QUANTUM TRADER V3 - TESTE COMPLETO")
    print("=" * 80)
    print(f" Horário: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 80 + "\n")
    
    issues = []
    successes = []
    
    # 1. Verificar arquivos de métricas
    print("[1] Verificando arquivos de métricas...")
    
    metrics_file = Path("metrics/current_metrics.json")
    if metrics_file.exists():
        with open(metrics_file, 'r') as f:
            metrics = json.load(f)
        
        # Verificar idade dos dados
        try:
            timestamp = datetime.fromisoformat(metrics['timestamp'])
            age = (datetime.now() - timestamp).total_seconds()
            
            if age < 30:
                successes.append(f"[OK] Métricas atualizadas ({age:.1f}s)")
            else:
                issues.append(f"[WARN] Métricas desatualizadas ({age:.1f}s)")
        except:
            issues.append("[ERRO] Timestamp inválido nas métricas")
        
        # Verificar dados
        if metrics.get('book_count', 0) > 0:
            successes.append(f"[OK] Book data: {metrics['book_count']} mensagens")
        else:
            issues.append("[ERRO] Sem dados de book")
            
        if metrics.get('tick_count', 0) > 0:
            successes.append(f"[OK] Tick data: {metrics['tick_count']} trades")
        else:
            issues.append("[WARN] Sem dados de tick/trade")
    else:
        issues.append("[ERRO] Arquivo de métricas não encontrado")
    
    # 2. Verificar ML/HMARL
    print("\n[2] Verificando ML/HMARL...")
    
    ml_file = Path("metrics/ml_status.json")
    if ml_file.exists():
        with open(ml_file, 'r') as f:
            ml_status = json.load(f)
        
        # Verificar predições
        if ml_status.get('predictions_count', 0) > 0:
            successes.append(f"[OK] ML predictions: {ml_status['predictions_count']}")
        else:
            issues.append("[WARN] ML sem predições")
        
        # Verificar HMARL
        if 'orderflow_action' in ml_status:
            successes.append("[OK] HMARL agents ativos")
        elif 'hmarl_consensus' in ml_status:
            successes.append("[OK] HMARL consensus disponível")
        else:
            issues.append("[WARN] HMARL não integrado")
        
        # Verificar features
        features_count = ml_status.get('features_calculated', 0)
        if features_count > 5:
            successes.append(f"[OK] Features calculadas: {features_count}")
        else:
            issues.append(f"[WARN] Poucas features: {features_count}")
    else:
        issues.append("[ERRO] ML status não encontrado")
    
    # 3. Verificar HMARL status específico
    print("\n[3] Verificando HMARL status...")
    
    hmarl_file = Path("hmarl_status.json")
    if hmarl_file.exists():
        with open(hmarl_file, 'r') as f:
            hmarl = json.load(f)
        
        if 'consensus' in hmarl:
            action = hmarl['consensus'].get('action', 'HOLD')
            confidence = hmarl['consensus'].get('confidence', 0) * 100
            successes.append(f"[OK] HMARL: {action} ({confidence:.1f}%)")
        else:
            issues.append("[WARN] HMARL sem consensus")
    else:
        issues.append("[WARN] HMARL status file não encontrado")
    
    # 4. Verificar processos
    print("\n[4] Verificando processos...")
    
    import subprocess
    try:
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], 
                              capture_output=True, text=True, timeout=2)
        python_count = result.stdout.count('python.exe')
        if python_count > 0:
            successes.append(f"[OK] {python_count} processos Python ativos")
        else:
            issues.append("[ERRO] Nenhum processo Python ativo")
    except:
        issues.append("[WARN] Não foi possível verificar processos")
    
    # 5. Resumo
    print("\n" + "=" * 80)
    print(" RESUMO DO TESTE")
    print("=" * 80)
    
    print("\nSUCESSOS:")
    for success in successes:
        print(f"  {success}")
    
    if issues:
        print("\nPROBLEMAS ENCONTRADOS:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n*** SISTEMA FUNCIONANDO PERFEITAMENTE! ***")
    
    # Score
    total = len(successes) + len(issues)
    if total > 0:
        score = (len(successes) / total) * 100
        print(f"\nSCORE: {score:.1f}% ({len(successes)}/{total})")
        
        if score >= 80:
            print("[OK] Sistema operacional")
        elif score >= 60:
            print("[WARN] Sistema parcialmente operacional")
        else:
            print("[ERRO] Sistema com problemas críticos")
    
    print("\n" + "=" * 80)
    
    return len(issues) == 0

if __name__ == "__main__":
    # Executar teste
    all_ok = check_system()
    
    if not all_ok:
        print("\nSUGESTOES:")
        print("  1. Verifique se o sistema está rodando: python START_SYSTEM_PRODUCTION_FINAL.py")
        print("  2. Aguarde 30 segundos para o sistema inicializar completamente")
        print("  3. Verifique se o mercado está aberto (9:00-18:00)")
        print("  4. Confirme as credenciais em .env.production")
    
    print("\nPressione Enter para sair...")
    input()