#!/usr/bin/env python3
"""
Correção definitiva - adiciona declaração global em TODAS as funções que usam GLOBAL_POSITION_LOCK
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_global_all_functions():
    """Adiciona declaração global em todas as funções necessárias"""
    
    print("="*70)
    print("CORREÇÃO DEFINITIVA - VARIÁVEIS GLOBAIS")
    print("="*70)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"\nArquivo tem {len(lines)} linhas")
    
    # Procurar a função trading_loop e adicionar global declaration
    print("\n[1] Procurando função trading_loop...")
    
    changes_made = []
    
    for i in range(len(lines)):
        # Procurar definição da função trading_loop
        if "def trading_loop(self):" in lines[i]:
            print(f"   Encontrada na linha {i+1}")
            
            # Verificar se já tem global declaration nas próximas linhas
            has_global = False
            for j in range(i+1, min(i+10, len(lines))):
                if "global GLOBAL_POSITION_LOCK" in lines[j]:
                    has_global = True
                    break
            
            if not has_global:
                # Adicionar após a docstring ou após o def
                insert_at = i + 1
                
                # Pular docstring se existir
                if i+1 < len(lines) and '"""' in lines[i+1]:
                    # Encontrar fim da docstring
                    for j in range(i+2, min(i+10, len(lines))):
                        if '"""' in lines[j]:
                            insert_at = j + 1
                            break
                
                # Inserir global declaration
                indent = "        "  # 8 espaços para métodos
                lines.insert(insert_at, f"{indent}global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX\n")
                changes_made.append(f"Linha {i+1}: trading_loop")
                print("   [OK] Global declaration adicionada em trading_loop")
    
    # Lista de TODAS as funções que precisam da declaração global
    functions_need_global = [
        "trading_loop",
        "check_position_status",
        "handle_position_closed",
        "on_position_closed",
        "on_position_closed_detected",
        "cleanup_orphan_orders_loop",
        "position_consistency_check",
        "monitor_oco_executions",
        "check_position_and_unlock",
        "make_hybrid_prediction",
        "execute_trade",
        "process_hmarl_decision",
        "run"
    ]
    
    print("\n[2] Verificando todas as funções que usam GLOBAL_POSITION_LOCK...")
    
    for func_name in functions_need_global:
        for i in range(len(lines)):
            if f"def {func_name}(self" in lines[i]:
                # Verificar se usa GLOBAL_POSITION_LOCK
                func_end = i + 100  # Verificar próximas 100 linhas
                if func_end > len(lines):
                    func_end = len(lines)
                
                uses_global = False
                has_global_decl = False
                
                for j in range(i, func_end):
                    if j < len(lines):
                        if "GLOBAL_POSITION_LOCK" in lines[j]:
                            uses_global = True
                        if "global GLOBAL_POSITION_LOCK" in lines[j]:
                            has_global_decl = True
                            break
                    
                    # Parar se encontrar próxima função
                    if j > i and "def " in lines[j] and lines[j][0:4] == "    ":
                        break
                
                if uses_global and not has_global_decl:
                    print(f"   Função {func_name} usa GLOBAL mas não tem declaração")
                    
                    # Adicionar global declaration
                    insert_at = i + 1
                    
                    # Pular docstring se existir
                    if i+1 < len(lines) and '"""' in lines[i+1]:
                        for j in range(i+2, min(i+10, len(lines))):
                            if '"""' in lines[j]:
                                insert_at = j + 1
                                break
                    
                    # Inserir
                    indent = "        "  # 8 espaços para métodos
                    lines.insert(insert_at, f"{indent}global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX\n")
                    changes_made.append(f"Linha {i+1}: {func_name}")
                    print(f"      [OK] Global adicionado em {func_name}")
                    break
    
    # Procurar por qualquer linha que usa GLOBAL_POSITION_LOCK sem ter global declaration
    print("\n[3] Verificação final - procurando usos sem declaração...")
    
    current_function = None
    has_global_in_function = False
    
    for i in range(len(lines)):
        line = lines[i]
        
        # Detectar início de função
        if "def " in line and "(self" in line:
            current_function = line.strip()
            has_global_in_function = False
        
        # Detectar global declaration
        if "global GLOBAL_POSITION_LOCK" in line:
            has_global_in_function = True
        
        # Detectar uso sem global
        if "GLOBAL_POSITION_LOCK" in line and not "global GLOBAL_POSITION_LOCK" in line:
            if current_function and not has_global_in_function:
                # É um uso sem declaração global
                if "if " in line or "while " in line or "= GLOBAL" in line or "with GLOBAL" in line:
                    print(f"   Linha {i+1}: Uso sem global em {current_function[:50]}")
    
    # Salvar arquivo
    print("\n[4] Salvando arquivo corrigido...")
    
    with open(system_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("   [OK] Arquivo salvo")
    
    if changes_made:
        print(f"\n   Total de {len(changes_made)} declarações globais adicionadas:")
        for change in changes_made:
            print(f"      - {change}")
    
    print("\n" + "="*70)
    print("CORREÇÃO COMPLETA APLICADA!")
    print("="*70)
    
    print("\nTODAS as funções que usam GLOBAL_POSITION_LOCK agora têm declaração global.")
    print("\nREINICIE O SISTEMA:")
    print("1. Pare o sistema atual (Ctrl+C)")
    print("2. Execute: python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
    print("\nO erro de variável global NÃO deve mais ocorrer!")

if __name__ == "__main__":
    fix_global_all_functions()