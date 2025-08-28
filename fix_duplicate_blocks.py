#!/usr/bin/env python3
"""
Remove blocos de código duplicados que estão causando o erro
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_duplicate_blocks():
    """Remove blocos duplicados de verificação de órfãs"""
    
    print("="*70)
    print("CORREÇÃO - REMOVENDO BLOCOS DUPLICADOS")
    print("="*70)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"\nArquivo tem {len(lines)} linhas")
    
    # Procurar e remover blocos duplicados de verificação de órfãs
    # que estão incorretamente inseridos em lugares errados
    
    lines_to_remove = []
    
    # Identificar blocos duplicados pela sequência específica
    for i in range(len(lines)):
        # Procurar pelo padrão de erro duplicado
        if i < len(lines) - 10:
            if ("[ORPHAN] Erro na verificação" in lines[i] and 
                "except Exception as e:" in lines[i-1] and
                i > 2700):  # Apenas remover os duplicados após linha 2700
                
                # Marcar bloco para remoção (de except até o próximo código válido)
                start = i - 1
                end = i + 10  # Remover cerca de 10 linhas do bloco duplicado
                
                print(f"   Encontrado bloco duplicado na linha {i+1}")
                
                # Verificar se é realmente um bloco duplicado mal colocado
                block_text = ''.join(lines[start:end])
                if "now = datetime.now()" in block_text or "loop_count +=" in block_text:
                    # É um bloco que está no lugar errado
                    for j in range(start, min(end, len(lines))):
                        lines_to_remove.append(j)
    
    if lines_to_remove:
        print(f"\n   Removendo {len(lines_to_remove)} linhas de código duplicado...")
        
        # Remover linhas de trás para frente para não afetar índices
        for idx in sorted(lines_to_remove, reverse=True):
            if idx < len(lines):
                del lines[idx]
        
        print("   [OK] Blocos duplicados removidos")
    else:
        print("\n   Nenhum bloco duplicado encontrado para remover")
    
    # Agora garantir que a função cleanup_orphan_orders_loop está correta
    print("\n[2] Verificando função cleanup_orphan_orders_loop...")
    
    # Procurar a função
    func_start = -1
    for i, line in enumerate(lines):
        if "def cleanup_orphan_orders_loop(self):" in line:
            func_start = i
            break
    
    if func_start != -1:
        print(f"   Função encontrada na linha {func_start+1}")
        
        # Verificar se tem o bloco try/except correto
        has_correct_structure = False
        for i in range(func_start + 1, min(func_start + 50, len(lines))):
            if "while self.running:" in lines[i]:
                # Verificar se tem try dentro do while
                for j in range(i + 1, min(i + 5, len(lines))):
                    if "try:" in lines[j]:
                        has_correct_structure = True
                        break
                break
        
        if has_correct_structure:
            print("   [OK] Estrutura da função está correta")
        else:
            print("   [AVISO] Estrutura da função pode precisar ajuste")
    
    # Salvar arquivo corrigido
    print("\n[3] Salvando arquivo corrigido...")
    
    with open(system_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("   [OK] Arquivo salvo")
    
    print("\n" + "="*70)
    print("CORREÇÃO APLICADA!")
    print("="*70)
    
    print("\nBlocos duplicados removidos.")
    print("\nREINICIE O SISTEMA:")
    print("1. Pare o sistema atual (Ctrl+C)")
    print("2. Execute: python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
    print("\nO erro '[ORPHAN] Erro na verificação' deve parar de aparecer.")

if __name__ == "__main__":
    fix_duplicate_blocks()