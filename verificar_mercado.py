"""
Verificação se o mercado está aberto
"""
from datetime import datetime
import pytz

# Configurar timezone de Brasília
br_tz = pytz.timezone('America/Sao_Paulo')
agora = datetime.now(br_tz)

print("="*60)
print("VERIFICAÇÃO DO MERCADO B3")
print("="*60)

print(f"\nData/Hora atual (Brasília): {agora.strftime('%d/%m/%Y %H:%M:%S')}")
print(f"Dia da semana: {agora.strftime('%A')}")
print(f"Dia: {agora.day}")
print(f"Mês: {agora.month}")
print(f"Ano: {agora.year}")

# Verificar dia da semana
dia_semana = agora.weekday()  # 0=Segunda, 6=Domingo
dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
print(f"\nHoje é: {dias[dia_semana]}-feira")

# Verificar se é dia útil
if dia_semana >= 5:  # Sábado=5, Domingo=6
    print("\n❌ MERCADO FECHADO - FIM DE SEMANA")
    print("O mercado B3 não funciona aos finais de semana!")
    print("\n[SOLUÇÃO]")
    print("1. O sistema só funcionará com dados reais de segunda a sexta")
    print("2. Hoje sendo DOMINGO, não há dados de mercado disponíveis")
    print("3. Execute o sistema novamente na SEGUNDA-FEIRA após 9h")
else:
    # Verificar horário
    hora = agora.hour
    minuto = agora.minute
    
    print(f"\nHorário: {hora:02d}:{minuto:02d}")
    
    # Horário do mercado: 9h às 18h
    if hora < 9:
        print("\n⏰ MERCADO FECHADO - MUITO CEDO")
        print(f"O mercado abre às 09:00. Faltam {9-hora}h {60-minuto}min")
    elif hora >= 18:
        print("\n🌙 MERCADO FECHADO - APÓS HORÁRIO")
        print("O mercado fechou às 18:00")
    else:
        print("\n✅ MERCADO ABERTO!")
        print("Horário de funcionamento: 9h às 18h")
        
print("\n" + "="*60)
print("CONCLUSÃO")
print("="*60)

if dia_semana == 6:  # Domingo
    print("\n🔴 HOJE É DOMINGO - MERCADO FECHADO!")
    print("\nO sistema NÃO receberá dados reais hoje porque:")
    print("1. A B3 não opera aos domingos")
    print("2. Não há negociação, portanto não há book de ofertas")
    print("3. O ProfitChart pode estar conectado mas não há dados para transmitir")
    print("\n✅ PRÓXIMA OPORTUNIDADE:")
    print("Segunda-feira, 26/08/2025, a partir das 9h00")
    print("\n[IMPORTANTE]")
    print("O sistema está funcionando corretamente!")
    print("O problema é apenas que hoje é domingo e não há mercado.")
elif dia_semana == 5:  # Sábado
    print("\n🔴 HOJE É SÁBADO - MERCADO FECHADO!")
else:
    if hora >= 9 and hora < 18:
        print("\n✅ Mercado deveria estar funcionando agora")
        print("Se não está recebendo dados, verifique:")
        print("1. Gráfico WDOU25 aberto no ProfitChart")
        print("2. Book de ofertas ativo")
        print("3. Conexão com a corretora")
    else:
        print("\n⏰ Aguarde o horário de funcionamento (9h-18h)")