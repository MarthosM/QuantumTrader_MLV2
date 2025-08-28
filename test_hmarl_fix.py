#!/usr/bin/env python3
"""
Teste do HMARL após correções
Verifica se o HMARL está recebendo dados reais e atualizando
"""

import json
import time
from pathlib import Path
from datetime import datetime

def check_hmarl_status():
    """Verifica status do HMARL"""
    print("=" * 60)
    print(" TESTE DO HMARL - VERIFICACAO DE DADOS REAIS")
    print("=" * 60)
    
    # Verificar arquivo de status do HMARL
    hmarl_file = Path("data/monitor/hmarl_status.json")
    
    print("\n[1] Verificando arquivo hmarl_status.json...")
    
    if not hmarl_file.exists():
        print("  [X] Arquivo nao existe ainda")
        print("  [!] Sistema precisa ser reiniciado com as correcoes")
        return False
    
    try:
        with open(hmarl_file, 'r') as f:
            data = json.load(f)
        
        # Verificar timestamp
        timestamp = datetime.fromisoformat(data['timestamp'])
        age = (datetime.now() - timestamp).total_seconds()
        
        print(f"  Ultima atualizacao: {timestamp.strftime('%H:%M:%S')}")
        print(f"  Idade: {age:.0f} segundos")
        
        if age < 60:  # Menos de 1 minuto
            print("  [OK] HMARL ATIVO E ATUALIZADO!")
            
            # Mostrar dados do mercado
            if 'market_data' in data:
                md = data['market_data']
                print(f"\n  Dados do Mercado:")
                print(f"    Preco: {md.get('price', 0):.2f}")
                print(f"    Volume: {md.get('volume', 0)}")
                if 'book_data' in md:
                    bd = md['book_data']
                    print(f"    Spread: {bd.get('spread', 0):.2f}")
                    print(f"    Imbalance: {bd.get('imbalance', 0):.2f}")
            
            # Mostrar consensus
            if 'consensus' in data:
                cons = data['consensus']
                print(f"\n  Consensus HMARL:")
                print(f"    Acao: {cons.get('action', 'N/A')}")
                print(f"    Confianca: {cons.get('confidence', 0):.1%}")
            
            # Mostrar agentes
            if 'agents' in data and data['agents']:
                print(f"\n  Agentes:")
                for agent, info in data['agents'].items():
                    if isinstance(info, dict):
                        print(f"    {agent}: {info.get('action', 'N/A')} ({info.get('confidence', 0):.1%})")
            
            return True
            
        else:
            print(f"  [!] HMARL INATIVO (dados com {age:.0f} segundos)")
            print("  [!] Sistema precisa ser reiniciado")
            return False
            
    except Exception as e:
        print(f"  [X] Erro ao ler arquivo: {e}")
        return False

def main():
    """Funcao principal"""
    success = check_hmarl_status()
    
    print("\n" + "=" * 60)
    
    if success:
        print(" [OK] HMARL FUNCIONANDO COM DADOS REAIS!")
        print("=" * 60)
        print("\nO HMARL esta ativo e recebendo dados do mercado.")
        print("Monitor visual deve mostrar valores atualizados.")
    else:
        print(" [X] HMARL NAO ESTA FUNCIONANDO")
        print("=" * 60)
        print("\nAcoes necessarias:")
        print("1. Parar o sistema atual (Ctrl+C)")
        print("2. Reiniciar com as correcoes:")
        print("   python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
        print("3. Aguardar 30 segundos")
        print("4. Executar este teste novamente")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())