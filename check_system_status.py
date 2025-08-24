#!/usr/bin/env python3
"""
Verifica o status do sistema completo
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Carregar configurações
load_dotenv('.env.production')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def check_status():
    """Verifica status de todos os componentes"""
    
    print("\n" + "=" * 80)
    print(" VERIFICAÇÃO DE STATUS DO SISTEMA")
    print("=" * 80)
    print(f"Horário: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print()
    
    status = {
        'dll': False,
        'connection': False,
        'models': False,
        'hmarl': False,
        'data_files': False,
        'config': False
    }
    
    # 1. Verificar DLL
    print("[1] DLL ProfitChart:")
    dll_paths = [
        Path(os.getcwd()) / 'ProfitDLL64.dll',
        Path('ProfitDLL64.dll')
    ]
    
    for path in dll_paths:
        if path.exists():
            print(f"  ✓ DLL encontrada: {path}")
            status['dll'] = True
            break
    
    if not status['dll']:
        print("  ✗ DLL não encontrada")
    
    # 2. Verificar configurações
    print("\n[2] Configurações:")
    
    username = os.getenv('PROFIT_USERNAME', '')
    password = os.getenv('PROFIT_PASSWORD', '')
    trading = os.getenv('ENABLE_TRADING', 'false')
    symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
    
    if username and password:
        print(f"  ✓ Credenciais configuradas")
        status['config'] = True
    else:
        print(f"  ✗ Credenciais não configuradas")
    
    print(f"  • Trading: {'REAL' if trading.lower() == 'true' else 'SIMULADO'}")
    print(f"  • Símbolo: {symbol}")
    print(f"  • Confiança mínima: {os.getenv('MIN_CONFIDENCE', '0.60')}")
    print(f"  • Stop Loss: {os.getenv('STOP_LOSS', '0.005')}")
    print(f"  • Take Profit: {os.getenv('TAKE_PROFIT', '0.010')}")
    
    # 3. Verificar modelos
    print("\n[3] Modelos ML:")
    models_dir = Path("models/hybrid")
    
    if models_dir.exists():
        model_count = 0
        for subdir in ['context', 'microstructure', 'meta_learner']:
            subpath = models_dir / subdir
            if subpath.exists():
                pkl_files = list(subpath.glob("*.pkl"))
                if pkl_files:
                    print(f"  ✓ {subdir}: {len(pkl_files)} modelos")
                    model_count += len(pkl_files)
        
        if model_count > 0:
            print(f"  Total: {model_count} modelos")
            status['models'] = True
        else:
            print("  ✗ Nenhum modelo encontrado")
    else:
        print("  ✗ Diretório de modelos não existe")
    
    # 4. Verificar HMARL
    print("\n[4] HMARL Agents:")
    try:
        from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
        print("  ✓ HMARL disponível")
        status['hmarl'] = True
    except:
        print("  ✗ HMARL não disponível")
    
    # 5. Verificar arquivos de dados
    print("\n[5] Arquivos de Dados:")
    data_dir = Path("data/book_tick_data")
    
    if data_dir.exists():
        csv_files = list(data_dir.glob("*.csv"))
        if csv_files:
            # Pegar os 3 arquivos mais recentes
            recent_files = sorted(csv_files, key=lambda x: x.stat().st_mtime, reverse=True)[:3]
            print(f"  ✓ {len(csv_files)} arquivos encontrados")
            print("  Arquivos recentes:")
            for f in recent_files:
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"    • {f.name} ({size_mb:.2f} MB)")
            status['data_files'] = True
        else:
            print("  ○ Nenhum arquivo de dados")
    else:
        print("  ○ Diretório de dados não existe")
    
    # 6. Testar conexão
    print("\n[6] Teste de Conexão:")
    if status['dll'] and status['config']:
        try:
            from src.connection_manager_oco import ConnectionManagerOCO
            
            conn = ConnectionManagerOCO(str(dll_paths[0]))
            if conn.initialize(username=username, password=password):
                print("  ✓ Conexão estabelecida")
                
                # Verificar status
                conn_status = conn.get_status()
                print(f"    • Login: {'OK' if conn_status.get('connected') else 'X'}")
                print(f"    • Market: {'OK' if conn_status.get('market') else 'X'}")
                print(f"    • Broker: {'OK' if conn_status.get('broker') else 'X'}")
                
                status['connection'] = True
                
                # Desconectar
                conn.disconnect()
            else:
                print("  ✗ Falha ao conectar")
        except Exception as e:
            print(f"  ✗ Erro: {e}")
    else:
        print("  ○ Pré-requisitos não atendidos")
    
    # 7. Verificar processos
    print("\n[7] Processos Rodando:")
    
    # Verificar logs recentes
    log_dir = Path("logs")
    if log_dir.exists():
        log_files = list(log_dir.glob("*.log"))
        if log_files:
            recent_log = max(log_files, key=lambda x: x.stat().st_mtime)
            
            # Verificar se foi modificado nos últimos 5 minutos
            time_diff = time.time() - recent_log.stat().st_mtime
            if time_diff < 300:  # 5 minutos
                print(f"  ✓ Sistema ativo (log atualizado há {int(time_diff)}s)")
            else:
                print(f"  ○ Sistema inativo (último log há {int(time_diff/60)} minutos)")
    
    # Resumo
    print("\n" + "=" * 80)
    print(" RESUMO")
    print("=" * 80)
    
    ready_count = sum(status.values())
    total_count = len(status)
    
    print(f"\nComponentes prontos: {ready_count}/{total_count}")
    
    if ready_count == total_count:
        print("\n✅ SISTEMA PRONTO PARA OPERAR!")
    else:
        print("\n⚠️  Componentes faltando:")
        for component, ready in status.items():
            if not ready:
                print(f"  • {component}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    check_status()