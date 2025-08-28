"""
Teste de conexão com a chave correta
"""
import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv('.env.production')

# Adicionar diretório ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print("="*60)
print("TESTE DE CONEXÃO COM CHAVE CORRETA")
print("="*60)

# Mostrar credenciais
print("\nCredenciais carregadas:")
print(f"  KEY: {os.getenv('PROFIT_KEY')}")
print(f"  USERNAME: {os.getenv('PROFIT_USERNAME')}")
print(f"  ACCOUNT_ID: {os.getenv('PROFIT_ACCOUNT_ID')}")
print(f"  BROKER_ID: {os.getenv('PROFIT_BROKER_ID')}")

# Testar conexão básica
from src.connection_manager_v4 import ConnectionManagerV4

print("\n[1] Criando conexão...")
dll_path = os.getenv('PROFIT_DLL_PATH', r'C:\Profit\ProfitDLL.dll')
conn = ConnectionManagerV4(dll_path=dll_path)

print("\n[2] Inicializando com credenciais...")
key = os.getenv('PROFIT_KEY')
username = os.getenv('PROFIT_USERNAME')
password = os.getenv('PROFIT_PASSWORD')

if conn.initialize(key=key, username=username, password=password):
    print("  [OK] Conexão inicializada com sucesso!")
    
    # Verificar estados
    print("\n[3] Estados da conexão:")
    print(f"  Connected: {conn.connected}")
    print(f"  Login State: {conn.login_state}")
    print(f"  Market State: {conn.market_state}")
    print(f"  Routing State: {conn.routing_state}")
    
    # Desconectar
    conn.disconnect()
    print("\n[4] Desconectado")
else:
    print("  [ERRO] Falha ao inicializar conexão")
    print("  Verifique se o ProfitChart está aberto")