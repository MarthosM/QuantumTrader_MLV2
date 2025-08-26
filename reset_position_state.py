#!/usr/bin/env python3
"""
Script para resetar estado de posição travado
Usar quando o sistema acha que tem posição mas não tem
"""

import json
from pathlib import Path
from datetime import datetime

def reset_position_state():
    """Reseta arquivos de estado de posição"""
    
    print("[RESET] Iniciando reset de estado de posição...")
    
    # 1. Limpar arquivo de status de posição
    position_status_file = Path("data/monitor/position_status.json")
    if position_status_file.exists():
        try:
            # Criar backup primeiro
            backup_file = position_status_file.with_suffix('.json.backup')
            position_status_file.rename(backup_file)
            print(f"[OK] Backup criado: {backup_file}")
            
            # Criar novo arquivo limpo
            clean_status = {
                'timestamp': datetime.now().isoformat(),
                'has_position': False,
                'positions': []
            }
            
            with open(position_status_file, 'w') as f:
                json.dump(clean_status, f, indent=2)
            
            print(f"[OK] {position_status_file} resetado")
        except Exception as e:
            print(f"[ERRO] Falha ao resetar position_status.json: {e}")
    else:
        print(f"[INFO] {position_status_file} não existe")
    
    # 2. Verificar e limpar grupos OCO ativos
    oco_groups_file = Path("data/monitor/oco_groups.json")
    if oco_groups_file.exists():
        try:
            with open(oco_groups_file, 'r') as f:
                oco_data = json.load(f)
            
            active_groups = [g for g in oco_data.get('groups', []) if g.get('active')]
            
            if active_groups:
                print(f"[AVISO] Encontrados {len(active_groups)} grupos OCO ativos")
                
                # Desativar todos os grupos
                for group in oco_data.get('groups', []):
                    group['active'] = False
                
                # Salvar arquivo atualizado
                with open(oco_groups_file, 'w') as f:
                    json.dump(oco_data, f, indent=2)
                
                print(f"[OK] Grupos OCO desativados")
            else:
                print("[OK] Nenhum grupo OCO ativo encontrado")
                
        except Exception as e:
            print(f"[ERRO] Falha ao processar oco_groups.json: {e}")
    
    # 3. Criar arquivo de flag para forçar reset no sistema
    reset_flag_file = Path("data/monitor/force_position_reset.flag")
    reset_flag_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(reset_flag_file, 'w') as f:
        f.write(datetime.now().isoformat())
    
    print(f"[OK] Flag de reset criado: {reset_flag_file}")
    
    print("\n" + "="*60)
    print("[SUCESSO] Estado de posição resetado!")
    print("="*60)
    print("\nPróximos passos:")
    print("1. Reinicie o sistema: python stop_production.py")
    print("2. Aguarde 5 segundos")
    print("3. Inicie novamente: python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
    print("\nO sistema deve agora aceitar novos trades com OCO.")
    
if __name__ == "__main__":
    reset_position_state()