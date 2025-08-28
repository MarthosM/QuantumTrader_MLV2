#!/usr/bin/env python3
"""
Verificação visual do Book no ProfitChart
"""

import os
import time
from datetime import datetime
from colorama import init, Fore, Back, Style

# Initialize colorama for Windows
init()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    while True:
        clear_screen()
        
        print(Fore.CYAN + "="*80)
        print(" "*20 + "VERIFICAÇÃO DO BOOK NO PROFITCHART")
        print("="*80 + Style.RESET_ALL)
        
        print(f"\nHorário: {datetime.now().strftime('%H:%M:%S')}")
        
        print(Fore.YELLOW + "\n📊 CHECKLIST DO PROFITCHART:" + Style.RESET_ALL)
        print("\n1. " + Fore.GREEN + "✓" + Style.RESET_ALL + " ProfitChart está aberto?")
        print("2. " + Fore.GREEN + "✓" + Style.RESET_ALL + " Está conectado (botão verde)?")
        print("3. " + Fore.RED + "?" + Style.RESET_ALL + " Tem um gráfico do WDOU25 aberto?")
        print("4. " + Fore.RED + "?" + Style.RESET_ALL + " O Book de Ofertas está visível?")
        
        print(Fore.YELLOW + "\n📋 COMO ATIVAR O BOOK:" + Style.RESET_ALL)
        
        print("\n" + Fore.CYAN + "MÉTODO 1 - Book na Janela do Gráfico:" + Style.RESET_ALL)
        print("  1. Clique com " + Fore.GREEN + "BOTÃO DIREITO" + Style.RESET_ALL + " no gráfico")
        print("  2. Procure por: " + Fore.YELLOW + "'Book de Ofertas'" + Style.RESET_ALL + " ou " + Fore.YELLOW + "'Livro de Ofertas'" + Style.RESET_ALL)
        print("  3. " + Fore.GREEN + "MARQUE" + Style.RESET_ALL + " a opção")
        print("  4. Deve aparecer uma tabela com preços e quantidades")
        
        print("\n" + Fore.CYAN + "MÉTODO 2 - Book em Janela Separada:" + Style.RESET_ALL)
        print("  1. No menu: " + Fore.YELLOW + "Janela → Nova Janela → Book de Ofertas" + Style.RESET_ALL)
        print("  2. Digite: " + Fore.GREEN + "WDOU25" + Style.RESET_ALL)
        print("  3. Clique OK")
        
        print("\n" + Fore.CYAN + "MÉTODO 3 - Painel Lateral:" + Style.RESET_ALL)
        print("  1. Menu: " + Fore.YELLOW + "Exibir → Painéis → Book" + Style.RESET_ALL)
        print("  2. Selecione " + Fore.GREEN + "WDOU25" + Style.RESET_ALL + " no painel")
        
        print(Fore.YELLOW + "\n🔍 O QUE VOCÊ DEVE VER:" + Style.RESET_ALL)
        print("\n┌─────────────────────────────┐")
        print("│   COMPRA     │    VENDA     │")
        print("├──────────────┼──────────────┤")
        print("│ 5480.5 (10)  │ 5481.0 (15)  │")
        print("│ 5480.0 (25)  │ 5481.5 (20)  │")
        print("│ 5479.5 (30)  │ 5482.0 (10)  │")
        print("└─────────────────────────────┘")
        
        print(Fore.GREEN + "\n✅ SE VOCÊ VÊ ALGO ASSIM:" + Style.RESET_ALL)
        print("   - Os números estão " + Fore.CYAN + "MUDANDO" + Style.RESET_ALL + "?")
        print("   - Aparecem " + Fore.YELLOW + "PREÇOS" + Style.RESET_ALL + " e " + Fore.YELLOW + "QUANTIDADES" + Style.RESET_ALL + "?")
        print("   → Então o book está " + Fore.GREEN + "FUNCIONANDO!" + Style.RESET_ALL)
        
        print(Fore.RED + "\n❌ SE NÃO VÊ O BOOK:" + Style.RESET_ALL)
        print("   - Verifique se tem " + Fore.YELLOW + "permissão Level 2" + Style.RESET_ALL + " na conta")
        print("   - Tente " + Fore.CYAN + "reconectar" + Style.RESET_ALL + " (desconectar e conectar)")
        print("   - Verifique se o " + Fore.GREEN + "símbolo está correto (WDOU25)" + Style.RESET_ALL)
        
        print(Fore.MAGENTA + "\n💡 DICA IMPORTANTE:" + Style.RESET_ALL)
        print("O book DEVE estar " + Fore.YELLOW + "VISÍVEL e ATIVO" + Style.RESET_ALL + " no ProfitChart")
        print("Se minimizar ou fechar a janela do book, os dados " + Fore.RED + "PARAM!" + Style.RESET_ALL)
        
        print("\n" + Fore.CYAN + "="*80 + Style.RESET_ALL)
        print("Pressione " + Fore.GREEN + "CTRL+C" + Style.RESET_ALL + " para sair")
        print("Esta tela atualiza a cada 5 segundos...")
        
        time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSaindo...")