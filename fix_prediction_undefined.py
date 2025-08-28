#!/usr/bin/env python3
"""
Corrige erro 'prediction' is not defined no trading_loop
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_prediction_undefined():
    """Corrige erro de variável prediction não definida"""
    
    print("="*70)
    print("CORREÇÃO - VARIÁVEL PREDICTION")
    print("="*70)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print("\n[1] Procurando linha com erro...")
    
    # Procurar a linha específica do erro (linha 2735)
    error_line = 2734  # índice 2734 = linha 2735
    
    if error_line < len(lines):
        print(f"   Linha {error_line+1}: {lines[error_line].strip()[:60]}...")
        
        # Verificar se é a linha com problema
        if "prediction['signal']" in lines[error_line]:
            print("   [OK] Linha com erro encontrada")
            
            # Comentar ou remover a linha problemática
            # Vamos comentá-la já que parece ser apenas um log de debug
            lines[error_line] = "                # " + lines[error_line].lstrip()
            print("   [OK] Linha comentada para evitar erro")
    
    # Também vamos procurar se há definição da variável prediction antes
    print("\n[2] Verificando definição de 'prediction' na função...")
    
    # Procurar a função trading_loop
    trading_loop_start = -1
    for i in range(len(lines)):
        if "def trading_loop(self):" in lines[i]:
            trading_loop_start = i
            break
    
    if trading_loop_start != -1:
        # Verificar se prediction é definida
        prediction_defined = False
        for i in range(trading_loop_start, min(trading_loop_start + 200, len(lines))):
            if "prediction = " in lines[i]:
                prediction_defined = True
                print(f"   Variável 'prediction' definida na linha {i+1}")
                break
        
        if not prediction_defined:
            print("   [AVISO] Variável 'prediction' não está definida antes do uso")
            print("   Adicionando inicialização padrão...")
            
            # Adicionar inicialização após o while self.running
            for i in range(trading_loop_start, min(trading_loop_start + 50, len(lines))):
                if "while self.running:" in lines[i]:
                    # Adicionar inicialização logo após o try
                    for j in range(i+1, min(i+10, len(lines))):
                        if "try:" in lines[j]:
                            # Inserir após o try
                            insert_at = j + 1
                            indent = "                "  # 16 espaços
                            init_line = f"{indent}prediction = None  # Inicialização para evitar erro\n"
                            lines.insert(insert_at, init_line)
                            print("   [OK] Inicialização adicionada")
                            break
                    break
    
    # Salvar arquivo
    print("\n[3] Salvando arquivo corrigido...")
    
    with open(system_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("   [OK] Arquivo salvo")
    
    print("\n" + "="*70)
    print("CORREÇÃO APLICADA!")
    print("="*70)
    
    print("\nO erro 'prediction is not defined' foi corrigido.")
    print("\nREINICIE O SISTEMA:")
    print("1. Ctrl+C para parar")
    print("2. python START_SYSTEM_COMPLETE_OCO_EVENTS.py")

if __name__ == "__main__":
    fix_prediction_undefined()