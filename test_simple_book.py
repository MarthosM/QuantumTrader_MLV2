"""
Teste simples para verificar se estamos recebendo dados do book
"""
import os
import sys
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv('.env.production')

# Setup logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Adicionar diretório ao path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_simple():
    """Teste simplificado"""
    
    print("\n" + "="*60)
    print("TESTE SIMPLES DE BOOK DATA")
    print("="*60)
    
    # Verificar horário do mercado
    now = datetime.now()
    print(f"\nHorário atual: {now.strftime('%H:%M:%S')}")
    
    # Horário do mercado: 9h às 18h (horário de Brasília)
    market_open = now.hour >= 9 and now.hour < 18 and now.weekday() < 5
    
    if market_open:
        print("[OK] Mercado está ABERTO (9h-18h, seg-sex)")
    else:
        print("[AVISO] Mercado está FECHADO")
        print("  Horário de funcionamento: 9h-18h (seg-sex)")
        if now.weekday() >= 5:
            print("  Hoje é fim de semana")
    
    # Verificar conexão básica sem usar a DLL para evitar crash
    print("\n[*] Verificando configurações...")
    
    # Verificar variáveis de ambiente
    has_key = bool(os.getenv('PROFIT_KEY'))
    has_user = bool(os.getenv('PROFIT_USERNAME'))
    has_pass = bool(os.getenv('PROFIT_PASSWORD'))
    
    print(f"  PROFIT_KEY: {'[OK]' if has_key else '[FALTA]'}")
    print(f"  PROFIT_USERNAME: {'[OK]' if has_user else '[FALTA]'}")
    print(f"  PROFIT_PASSWORD: {'[OK]' if has_pass else '[FALTA]'}")
    
    if not (has_key and has_user and has_pass):
        print("\n[ERRO] Configuração incompleta. Verifique o arquivo .env.production")
        return
    
    # Verificar se o sistema principal está rodando
    print("\n[*] Verificando se o sistema principal está rodando...")
    
    pid_file = "quantum_trader.pid"
    if os.path.exists(pid_file):
        print("  [OK] Sistema principal está RODANDO")
        with open(pid_file, 'r') as f:
            pid = f.read().strip()
            print(f"  PID: {pid}")
    else:
        print("  [INFO] Sistema principal NÃO está rodando")
        print("  Para iniciar: python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
    
    # Verificar arquivos de status
    print("\n[*] Verificando arquivos de monitoramento...")
    
    files_to_check = [
        "data/monitor/hmarl_status.json",
        "data/monitor/position_status.json", 
        "data/monitor/ml_status.json",
        "data/monitor/regime_status.json"
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            # Verificar última modificação
            mtime = os.path.getmtime(file_path)
            last_modified = datetime.fromtimestamp(mtime)
            seconds_ago = (datetime.now() - last_modified).total_seconds()
            
            if seconds_ago < 60:
                print(f"  {os.path.basename(file_path)}: [OK] Atualizado há {seconds_ago:.0f}s")
            else:
                print(f"  {os.path.basename(file_path)}: [AVISO] Última atualização há {seconds_ago:.0f}s")
        else:
            print(f"  {os.path.basename(file_path)}: [NÃO EXISTE]")
    
    # Verificar logs recentes
    print("\n[*] Verificando logs recentes...")
    
    log_dir = "logs"
    if os.path.exists(log_dir):
        log_files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')], 
                          key=lambda x: os.path.getmtime(os.path.join(log_dir, x)),
                          reverse=True)
        
        if log_files:
            latest_log = log_files[0]
            log_path = os.path.join(log_dir, latest_log)
            
            # Ler últimas linhas do log
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            # Procurar por mensagens relacionadas a book data
            book_lines = [l for l in lines[-100:] if 'book' in l.lower() or 'subscription' in l.upper()]
            
            if book_lines:
                print(f"  Mensagens de book no log {latest_log}:")
                for line in book_lines[-5:]:  # Últimas 5 mensagens
                    print(f"    {line.strip()}")
            else:
                print(f"  Nenhuma mensagem de book encontrada em {latest_log}")
    
    print("\n" + "="*60)
    print("DIAGNÓSTICO")
    print("="*60)
    
    if not market_open:
        print("\n[PROBLEMA] Mercado fechado")
        print("  Solução: Aguarde o mercado abrir (9h-18h, seg-sex)")
    elif not os.path.exists(pid_file):
        print("\n[PROBLEMA] Sistema principal não está rodando")
        print("  Solução: Execute 'python START_SYSTEM_COMPLETE_OCO_EVENTS.py'")
    else:
        print("\n[INFO] Sistema parece estar configurado corretamente")
        print("  Se não está recebendo dados do book:")
        print("  1. Verifique se o ProfitChart está aberto e conectado")
        print("  2. Verifique se o símbolo WDOU25 está correto para este mês")
        print("  3. Verifique os logs para mensagens de erro")
        print("  4. Tente reiniciar o sistema")

if __name__ == "__main__":
    test_simple()