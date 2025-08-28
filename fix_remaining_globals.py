#!/usr/bin/env python3
"""
Adiciona global declaration nas funções que ainda faltam
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_remaining_globals():
    """Corrige as funções restantes que usam GLOBAL_POSITION_LOCK"""
    
    print("="*70)
    print("CORREÇÃO FINAL - FUNÇÕES RESTANTES")
    print("="*70)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Funções que precisam de global declaration
    functions_to_fix = [
        "_training_scheduler",
        "metrics_loop",
        "data_collection_loop"
    ]
    
    changes = []
    
    for func_name in functions_to_fix:
        print(f"\n[*] Procurando função {func_name}...")
        
        for i in range(len(lines)):
            if f"def {func_name}(self):" in lines[i]:
                print(f"   Encontrada na linha {i+1}")
                
                # Verificar se já tem global
                has_global = False
                for j in range(i+1, min(i+10, len(lines))):
                    if "global GLOBAL_POSITION_LOCK" in lines[j]:
                        has_global = True
                        print(f"   Já tem declaração global")
                        break
                
                if not has_global:
                    # Adicionar global declaration
                    insert_at = i + 1
                    
                    # Pular docstring se houver
                    if i+1 < len(lines) and '"""' in lines[i+1]:
                        for j in range(i+2, min(i+10, len(lines))):
                            if '"""' in lines[j]:
                                insert_at = j + 1
                                break
                    
                    # Inserir
                    indent = "        "  # 8 espaços
                    global_line = f"{indent}global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX\n"
                    lines.insert(insert_at, global_line)
                    changes.append(func_name)
                    print(f"   [OK] Global declaration adicionada")
                
                break
    
    # Salvar arquivo
    print("\n[*] Salvando arquivo...")
    
    with open(system_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("   [OK] Arquivo salvo")
    
    print("\n" + "="*70)
    print("TODAS AS CORREÇÕES APLICADAS!")
    print("="*70)
    
    if changes:
        print(f"\nDeclarações globais adicionadas em {len(changes)} funções:")
        for func in changes:
            print(f"   - {func}")
    else:
        print("\nNenhuma mudança necessária")
    
    print("\nREINICIE O SISTEMA para aplicar as correções:")
    print("1. Ctrl+C para parar")
    print("2. python START_SYSTEM_COMPLETE_OCO_EVENTS.py")

if __name__ == "__main__":
    fix_remaining_globals()