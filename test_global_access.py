# -*- coding: utf-8 -*-
"""
Teste para verificar se as globais estao acessiveis
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import START_SYSTEM_COMPLETE_OCO_EVENTS as main
    
    print("Verificando variaveis globais...")
    print(f"GLOBAL_POSITION_LOCK: {main.GLOBAL_POSITION_LOCK}")
    print(f"GLOBAL_POSITION_LOCK_TIME: {main.GLOBAL_POSITION_LOCK_TIME}")
    print(f"GLOBAL_POSITION_LOCK_MUTEX: {main.GLOBAL_POSITION_LOCK_MUTEX}")
    
    print("\n[OK] Variaveis globais acessiveis")
    
except Exception as e:
    print(f"[ERRO] {e}")