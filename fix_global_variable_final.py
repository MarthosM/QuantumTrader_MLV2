#!/usr/bin/env python3
"""
Correção FINAL do erro de variável global GLOBAL_POSITION_LOCK
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_global_variable_final():
    """Corrige definitivamente o erro de acesso à variável global"""
    
    print("="*70)
    print("CORREÇÃO DEFINITIVA - VARIÁVEL GLOBAL")
    print("="*70)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n[1] Procurando função cleanup_orphan_orders_loop...")
    
    # Procurar a função que está causando o erro
    search_str = "def cleanup_orphan_orders_loop(self):"
    if search_str in content:
        print("   Função encontrada!")
        
        # Encontrar o início da função
        func_start = content.find(search_str)
        func_end = content.find("\n    def ", func_start + 10)
        if func_end == -1:
            func_end = len(content)
        
        # Extrair a função
        func_content = content[func_start:func_end]
        
        # Verificar se já tem global declaration
        if "global GLOBAL_POSITION_LOCK" not in func_content:
            print("   Adicionando declaração global...")
            
            # Encontrar onde inserir (após o def e docstring se houver)
            lines = func_content.split('\n')
            insert_line = 1  # Após a linha def
            
            # Pular docstring se existir
            for i in range(1, len(lines)):
                if '"""' in lines[i]:
                    # Encontrar fim da docstring
                    for j in range(i+1, len(lines)):
                        if '"""' in lines[j]:
                            insert_line = j + 1
                            break
                    break
                elif lines[i].strip() and not lines[i].strip().startswith('#'):
                    insert_line = i
                    break
            
            # Inserir a declaração global
            global_declaration = "        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX\n"
            lines.insert(insert_line, global_declaration)
            
            # Reconstruir a função
            new_func = '\n'.join(lines)
            
            # Substituir no conteúdo
            content = content[:func_start] + new_func + content[func_end:]
            
            print("   [OK] Declaração global adicionada")
        else:
            print("   [INFO] Função já tem declaração global")
    
    print("\n[2] Verificando outras funções que precisam de global...")
    
    # Lista de funções que precisam da declaração global
    functions_need_global = [
        "cleanup_orphan_orders_loop",
        "position_consistency_check", 
        "monitor_oco_executions",
        "check_position_and_unlock",
        "on_position_closed_detected"
    ]
    
    for func_name in functions_need_global:
        search = f"def {func_name}(self"
        if search in content:
            # Encontrar a função
            func_start = content.find(search)
            # Procurar o próximo def ou fim do arquivo
            func_end = content.find("\n    def ", func_start + 10)
            if func_end == -1:
                func_end = len(content)
            
            func_content = content[func_start:func_end]
            
            # Verificar se precisa adicionar global
            if "GLOBAL_POSITION_LOCK" in func_content and "global GLOBAL_POSITION_LOCK" not in func_content:
                print(f"   Adicionando global em {func_name}...")
                
                # Encontrar onde inserir
                lines = func_content.split('\n')
                
                # Encontrar primeira linha não vazia após def
                insert_at = 1
                for i in range(1, min(10, len(lines))):
                    if '"""' in lines[i]:
                        # Pular docstring
                        for j in range(i+1, len(lines)):
                            if '"""' in lines[j]:
                                insert_at = j + 1
                                break
                        break
                    elif lines[i].strip() and not lines[i].strip().startswith('#'):
                        insert_at = i
                        break
                
                # Inserir declaração global
                indent = "        "  # 8 espaços para métodos
                global_line = f"{indent}global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX"
                lines.insert(insert_at, global_line)
                
                # Reconstruir função
                new_func = '\n'.join(lines)
                content = content[:func_start] + new_func + content[func_end:]
                
                print(f"      [OK] Global adicionado em {func_name}")
    
    print("\n[3] Salvando arquivo corrigido...")
    
    # Salvar arquivo
    with open(system_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("   [OK] Arquivo salvo com sucesso")
    
    print("\n" + "="*70)
    print("CORREÇÃO APLICADA COM SUCESSO!")
    print("="*70)
    
    print("\nO erro 'cannot access local variable GLOBAL_POSITION_LOCK' foi corrigido.")
    print("\nPRÓXIMOS PASSOS:")
    print("1. Pare o sistema atual (Ctrl+C)")
    print("2. Reinicie o sistema:")
    print("   python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
    print("\n3. Verifique se o erro parou de aparecer nos logs")

if __name__ == "__main__":
    fix_global_variable_final()