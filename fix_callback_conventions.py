#!/usr/bin/env python3
"""
Fix para problema de convenção de chamada nos callbacks V2
Detecta e corrige automaticamente CFUNCTYPE vs WINFUNCTYPE
"""

import sys
import platform
from pathlib import Path

def fix_callbacks():
    """Corrige convenção de callbacks baseado no sistema operacional"""
    
    structures_file = Path("src/profit_dll_structures.py")
    
    if not structures_file.exists():
        print("[ERRO] Arquivo profit_dll_structures.py não encontrado!")
        return False
    
    # Ler arquivo
    with open(structures_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Backup
    backup_file = structures_file.with_suffix('.py.bak')
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[OK] Backup salvo em: {backup_file}")
    
    # Detectar sistema
    is_windows = platform.system() == 'Windows'
    
    if is_windows:
        print("[INFO] Sistema Windows detectado - usando WINFUNCTYPE para callbacks V2")
        
        # Substituir CFUNCTYPE por WINFUNCTYPE nos callbacks V2
        replacements = [
            ('TPriceBookCallbackV2 = CFUNCTYPE', 'TPriceBookCallbackV2 = WINFUNCTYPE'),
            ('TOfferBookCallbackV2 = CFUNCTYPE', 'TOfferBookCallbackV2 = WINFUNCTYPE'),
        ]
        
        for old, new in replacements:
            if old in content:
                content = content.replace(old, new)
                print(f"  [OK] Substituido: {old} -> {new}")
            else:
                print(f"  [AVISO] Não encontrado: {old}")
    else:
        print("[INFO] Sistema Unix/Linux detectado - mantendo CFUNCTYPE")
    
    # Salvar correções
    with open(structures_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\n[OK] Correções aplicadas com sucesso!")
    print("\nPróximos passos:")
    print("  1. Execute o sistema novamente")
    print("  2. Se ainda crashar, reverta com: copy src\\profit_dll_structures.py.bak src\\profit_dll_structures.py")
    
    return True

if __name__ == "__main__":
    print("="*80)
    print(" FIX PARA CALLBACKS V2 - CONVENÇÃO DE CHAMADA")
    print("="*80)
    print()
    
    if fix_callbacks():
        print("\n[OK] Fix aplicado com sucesso!")
    else:
        print("\n[ERRO] Falha ao aplicar fix!")