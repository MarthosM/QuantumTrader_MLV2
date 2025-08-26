#!/usr/bin/env python3
"""
Teste do sistema de atualização automática de símbolo
"""

import sys
from pathlib import Path
from datetime import datetime

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils.symbol_manager import SymbolManager, update_symbol_if_needed

def test_symbol_manager():
    """Testa o gerenciador de símbolos"""
    
    print("\n" + "="*70)
    print("TESTE DO GERENCIADOR DE SÍMBOLOS WDO")
    print("="*70)
    
    # Data/hora atual
    now = datetime.now()
    print(f"\nData/Hora atual: {now.strftime('%d/%m/%Y %H:%M')}")
    print(f"Mês atual: {now.strftime('%B')}")
    
    # Símbolo atual
    current = SymbolManager.get_current_wdo_symbol()
    print(f"\n✅ Símbolo atual do WDO: {current}")
    
    # Próximo símbolo
    next_sym = SymbolManager.get_next_wdo_symbol()
    print(f"📅 Próximo símbolo: {next_sym}")
    
    # Informações detalhadas
    info = SymbolManager.get_symbol_info()
    print(f"\n📊 Informações do símbolo {current}:")
    print(f"  - Código do mês: {info['month_code']}")
    print(f"  - Mês de vencimento: {info['expiry_month_name']}")
    print(f"  - Ano: {info['year']}")
    print(f"  - É o contrato atual? {info['is_current']}")
    print(f"  - Próximo do vencimento? {info['near_expiry']}")
    
    # Teste de vencimento
    if SymbolManager.is_near_expiry():
        print("\n⚠️  ALERTA: Contrato próximo do vencimento!")
        print(f"   Considere rolar para: {next_sym}")
    else:
        print("\n✅ Contrato ainda longe do vencimento")
    
    # Teste de atualização
    print("\n" + "-"*50)
    print("TESTE DE ATUALIZAÇÃO DE SÍMBOLO")
    print("-"*50)
    
    # Testar com símbolos antigos
    test_symbols = [
        'WDOU25',  # Setembro 2025
        'WDOQ25',  # Outubro 2025
        'WDOV25',  # Dezembro 2025
        'WDOG26',  # Fevereiro 2026
        'WDOJ24',  # Abril 2024 (passado)
    ]
    
    for test_sym in test_symbols:
        updated_sym, changed = update_symbol_if_needed(test_sym)
        
        if changed:
            print(f"  ❌ {test_sym} -> {updated_sym} (DESATUALIZADO)")
        else:
            if test_sym == current:
                print(f"  ✅ {test_sym} (CORRETO)")
            else:
                print(f"  ⚠️  {test_sym} (não é o atual mas foi aceito)")
    
    # Teste de mapeamento de meses
    print("\n" + "-"*50)
    print("MAPEAMENTO DE MESES PARA CÓDIGOS WDO")
    print("-"*50)
    
    months = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    
    print("\nMês Trading -> Código Vencimento:")
    for month_num, month_name in months.items():
        code = SymbolManager.MONTH_CODES.get(month_num, '?')
        expiry_month = SymbolManager.EXPIRY_MONTHS.get(code, 0)
        expiry_name = months.get(expiry_month, "???")
        print(f"  {month_name:10s} -> {code} (vence em {expiry_name})")
    
    # Simular diferentes datas
    print("\n" + "-"*50)
    print("SIMULAÇÃO DE SÍMBOLOS EM DIFERENTES MESES")
    print("-"*50)
    
    from datetime import datetime
    import calendar
    
    # Simular para cada mês de 2025
    for month in range(1, 13):
        # Criar data fictícia (dia 10 de cada mês)
        fake_date = datetime(2025, month, 10)
        
        # Temporariamente modificar datetime.now() para teste
        # Nota: Em produção real, isso não seria feito
        old_month = datetime.now().month
        old_year = datetime.now().year
        
        # Simular mudança de mês (hack para teste)
        SymbolManager_test = SymbolManager()
        current_month = month
        current_year = 2025
        
        # Calcular símbolo para o mês simulado
        month_code = SymbolManager.MONTH_CODES.get(month, 'U')
        year_code = current_year % 100
        simulated_symbol = f"WDO{month_code}{year_code:02d}"
        
        month_name = calendar.month_name[month]
        print(f"  {month_name:10s} 2025: {simulated_symbol}")
    
    # Resultado final
    print("\n" + "="*70)
    print("RESULTADO DO TESTE")
    print("="*70)
    
    print(f"\n✅ Símbolo recomendado para uso hoje: {current}")
    
    if SymbolManager.should_roll_contract():
        print(f"⚠️  ATENÇÃO: Deve rolar para próximo contrato: {next_sym}")
    else:
        print("✅ Não é necessário rolar contrato ainda")
    
    # Verificar se estamos no mês correto
    expected_month_code = SymbolManager.MONTH_CODES.get(now.month)
    if expected_month_code in current:
        print("✅ Código do mês está correto para o período atual")
    else:
        print("⚠️  Código do mês pode precisar de verificação")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    try:
        test_symbol_manager()
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)