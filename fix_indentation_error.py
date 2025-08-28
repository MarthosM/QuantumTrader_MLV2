#!/usr/bin/env python3
"""
Corrige erro de indentação no arquivo START_SYSTEM_COMPLETE_OCO_EVENTS.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_indentation():
    """Corrige o erro de indentação na linha 2091"""
    
    print("="*60)
    print("CORRIGINDO ERRO DE INDENTAÇÃO")
    print("="*60)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"\nVerificando linha 2091...")
    print(f"Linha atual: {lines[2090][:50]}...")
    
    # Remover código duplicado (linhas 2090-2105 parecem ser duplicatas)
    # Vamos remover as linhas problemáticas que foram adicionadas incorretamente
    
    print("\nRemovendo código duplicado das linhas 2090-2105...")
    
    # Verificar se as linhas 2090-2105 são duplicatas
    if "# Garantir que price_history tem dados mínimos" in lines[2089]:
        # Remover as linhas duplicadas
        del lines[2089:2105]  # Remove 16 linhas duplicadas
        print("  [OK] Código duplicado removido")
    else:
        # Tentar corrigir apenas a indentação
        print("  Ajustando indentação...")
        # Linha 2090 (índice 2089) deve ter indentação correta
        if len(lines) > 2090:
            # Verificar indentação da linha anterior
            prev_line = lines[2089]
            # Contar espaços da linha anterior
            spaces = len(prev_line) - len(prev_line.lstrip())
            
            # Ajustar indentação das próximas linhas
            for i in range(2090, min(2105, len(lines))):
                if i < len(lines):
                    # Manter a mesma indentação ou ajustar conforme necessário
                    current_line = lines[i]
                    if current_line.strip():  # Se não for linha vazia
                        # Remover indentação atual e adicionar correta
                        content = current_line.lstrip()
                        if content.startswith("if len(self.price_history)"):
                            lines[i] = " " * spaces + content
                        elif content.startswith("logger.") or content.startswith("#"):
                            lines[i] = " " * (spaces + 4) + content
                        else:
                            lines[i] = " " * (spaces + 8) + content
    
    # Salvar arquivo corrigido
    with open(system_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("\n" + "="*60)
    print("CORREÇÃO APLICADA!")
    print("="*60)
    print("\nO erro de indentação foi corrigido.")
    print("Tente executar o sistema novamente:")
    print("  python START_SYSTEM_COMPLETE_OCO_EVENTS.py")

if __name__ == "__main__":
    fix_indentation()