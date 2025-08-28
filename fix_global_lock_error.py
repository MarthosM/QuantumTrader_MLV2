"""
Script para corrigir erro de acesso à variável GLOBAL_POSITION_LOCK
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_global_lock_error():
    """Corrige erro de acesso à variável global"""
    
    print("="*60)
    print("CORREÇÃO: Erro de acesso GLOBAL_POSITION_LOCK")
    print("="*60)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n1. Corrigindo declarações de global em funções...")
    
    # Funções que precisam acessar GLOBAL_POSITION_LOCK
    functions_needing_global = [
        "def cleanup_orphan_orders_loop",
        "def position_consistency_check",
        "def monitor_oco_executions"
    ]
    
    for func in functions_needing_global:
        # Procurar a função e adicionar global declaration se não existir
        if func in content:
            # Encontrar o início da função
            func_start = content.find(func)
            if func_start != -1:
                # Encontrar o próximo ':' após def
                colon_pos = content.find(':', func_start)
                # Encontrar a próxima linha
                next_line_pos = content.find('\n', colon_pos) + 1
                
                # Verificar se já tem global declaration
                check_area = content[next_line_pos:next_line_pos + 500]
                
                # Se a função tem docstring, pular ela
                if '"""' in check_area[:100]:
                    # Encontrar fim da docstring
                    docstring_end = check_area.find('"""', 3)
                    if docstring_end != -1:
                        docstring_end = check_area.find('\n', docstring_end) + 1
                        insert_pos = next_line_pos + docstring_end
                    else:
                        continue
                else:
                    insert_pos = next_line_pos
                
                # Verificar se já tem global declaration nesta função
                func_end = content.find('\n    def ', func_start + 1)
                if func_end == -1:
                    func_end = len(content)
                
                func_content = content[func_start:func_end]
                
                if 'global GLOBAL_POSITION_LOCK' not in func_content:
                    print(f"  Adicionando global declaration em {func.split('(')[0]}...")
                    
                    # Adicionar global declaration
                    indent = "        "  # 8 espaços para métodos de classe
                    global_decl = f"{indent}global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX\n{indent}\n"
                    
                    # Inserir após a docstring ou após o def
                    content = content[:insert_pos] + global_decl + content[insert_pos:]
                else:
                    print(f"  {func.split('(')[0]} já tem global declaration")
    
    # Salvar arquivo corrigido
    with open(system_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("  [OK] Arquivo atualizado com declarações globais")
    
    print("\n2. Criando teste de verificação...")
    
    test_code = '''"""
Teste para verificar se as globais estão acessíveis
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import START_SYSTEM_COMPLETE_OCO_EVENTS as main
    
    print("Verificando variáveis globais...")
    print(f"GLOBAL_POSITION_LOCK: {main.GLOBAL_POSITION_LOCK}")
    print(f"GLOBAL_POSITION_LOCK_TIME: {main.GLOBAL_POSITION_LOCK_TIME}")
    print(f"GLOBAL_POSITION_LOCK_MUTEX: {main.GLOBAL_POSITION_LOCK_MUTEX}")
    
    print("\\n[OK] Variáveis globais acessíveis")
    
except Exception as e:
    print(f"[ERRO] {e}")
'''
    
    with open("test_global_access.py", 'w') as f:
        f.write(test_code)
    
    print("  [OK] Teste criado: test_global_access.py")
    
    print("\n" + "="*60)
    print("CORREÇÃO APLICADA!")
    print("="*60)
    print("\nO erro 'cannot access local variable GLOBAL_POSITION_LOCK'")
    print("foi corrigido adicionando declarações 'global' nas funções.")
    print("\nReinicie o sistema para aplicar as correções.")

if __name__ == "__main__":
    fix_global_lock_error()