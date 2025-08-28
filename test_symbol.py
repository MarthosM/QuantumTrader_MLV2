"""Teste rápido do símbolo WDO"""
from datetime import datetime
from src.utils.symbol_manager import SymbolManager

print(f"Data atual: {datetime.now().strftime('%d/%m/%Y')}")
print(f"Mês: {datetime.now().month}")
print(f"Símbolo calculado: {SymbolManager.get_current_wdo_symbol()}")
print(f"Símbolo correto: WDOU25")

# Verificar se está correto
if SymbolManager.get_current_wdo_symbol() == "WDOU25":
    print("\n[OK] Símbolo está CORRETO!")
else:
    print(f"\n[ERRO] Símbolo incorreto!")