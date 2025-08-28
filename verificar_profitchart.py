"""
Verificação se ProfitChart está rodando e conectado
"""
import psutil
import os
from datetime import datetime

print("="*60)
print("VERIFICAÇÃO DO PROFITCHART")
print(f"Horário: {datetime.now().strftime('%H:%M:%S')}")
print("="*60)

# 1. Verificar processos do Profit
print("\n[1] Procurando processos do Profit...")
profit_found = False

for proc in psutil.process_iter(['pid', 'name']):
    try:
        name = proc.info['name'].lower()
        if 'profit' in name or 'nelogica' in name:
            print(f"  [OK] Encontrado: {proc.info['name']} (PID: {proc.info['pid']})")
            profit_found = True
    except:
        pass

if not profit_found:
    print("  [ERRO] Nenhum processo do Profit encontrado!")
    print("\n[AÇÃO NECESSÁRIA]")
    print("1. Abra o ProfitChart")
    print("2. Faça login com sua conta")
    print("3. Abra um gráfico do WDOU25")
    print("4. Então execute o sistema novamente")
else:
    print("\n[OK] ProfitChart parece estar rodando")
    print("\n[PRÓXIMOS PASSOS]")
    print("1. Verifique se está LOGADO no ProfitChart")
    print("2. Verifique se tem um gráfico do WDOU25 aberto")
    print("3. Verifique se mostra cotações em tempo real")
    print("4. Verifique se o book de ofertas está visível")

# 2. Verificar conexões de rede (porta típica do Profit)
print("\n[2] Verificando conexões de rede...")
profit_ports = [443, 8080, 8184, 9995]  # Portas comuns do Profit
connections_found = False

for conn in psutil.net_connections():
    if conn.status == 'ESTABLISHED' and conn.raddr:
        if conn.raddr.port in profit_ports or conn.laddr.port in profit_ports:
            print(f"  [OK] Conexão ativa: {conn.laddr.ip}:{conn.laddr.port} -> {conn.raddr.ip}:{conn.raddr.port}")
            connections_found = True

if not connections_found:
    print("  [AVISO] Nenhuma conexão típica do Profit detectada")

# 3. Verificar DLL
print("\n[3] Verificando DLL...")
dll_path = r"C:\Users\marth\OneDrive\Programacao\Python\QuantumTrader_Production\ProfitDLL64.dll"
if os.path.exists(dll_path):
    print(f"  [OK] DLL encontrada: {dll_path}")
    size = os.path.getsize(dll_path) / (1024*1024)
    print(f"  Tamanho: {size:.2f} MB")
else:
    print(f"  [ERRO] DLL não encontrada!")

print("\n" + "="*60)
print("DIAGNÓSTICO")
print("="*60)

if profit_found:
    print("\n✅ ProfitChart está rodando")
    print("\nVERIFIQUE NO PROFITCHART:")
    print("1. Status de conexão (deve estar verde/conectado)")
    print("2. Gráfico do WDOU25 aberto")
    print("3. Book de ofertas visível")
    print("4. Cotações atualizando em tempo real")
else:
    print("\n❌ ProfitChart NÃO está rodando!")
    print("\nAÇÃO IMEDIATA:")
    print("1. Abra o ProfitChart")
    print("2. Faça login")
    print("3. Abra gráfico WDOU25")
    print("4. Execute o sistema novamente")

print("\n[INFO] Se o ProfitChart está aberto mas não recebe dados:")
print("  - Verifique se está DENTRO do horário de mercado (9h-18h)")
print("  - Verifique se hoje é dia útil (seg-sex)")
print("  - Tente trocar de símbolo e voltar para WDOU25")
print("  - Verifique com a corretora se tem acesso a dados de mercado")