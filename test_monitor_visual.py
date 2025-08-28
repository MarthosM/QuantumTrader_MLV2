#!/usr/bin/env python3
"""
Teste do Monitor Visual Integrado
Simula dados para visualização
"""

import json
import time
import random
import threading
from datetime import datetime
from pathlib import Path

# Criar diretórios necessários
Path('data/monitor').mkdir(parents=True, exist_ok=True)
Path('metrics').mkdir(parents=True, exist_ok=True)

def simulate_position_data():
    """Simula dados de posição para teste"""
    
    # Simular posição aberta
    has_position = random.random() > 0.3  # 70% chance de ter posição
    
    if has_position:
        side = random.choice(['BUY', 'SELL'])
        entry_price = 5500 + random.uniform(-50, 50)
        current_price = entry_price + random.uniform(-30, 30)
        
        if side == 'BUY':
            pnl = current_price - entry_price
            stop_price = entry_price - 15
            take_price = entry_price + 30
        else:
            pnl = entry_price - current_price
            stop_price = entry_price + 15
            take_price = entry_price - 30
        
        pnl_percentage = (pnl / entry_price) * 100
        
        position_data = {
            'timestamp': datetime.now().isoformat(),
            'has_position': True,
            'positions': [{
                'symbol': 'WDOQ25',
                'side': side,
                'quantity': random.randint(1, 3),
                'entry_price': entry_price,
                'current_price': current_price,
                'stop_price': stop_price,
                'take_price': take_price,
                'pnl': pnl,
                'pnl_percentage': pnl_percentage,
                'status': 'open',
                'position_id': f"POS_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'open_time': datetime.now().isoformat()
            }]
        }
    else:
        position_data = {
            'timestamp': datetime.now().isoformat(),
            'has_position': False,
            'positions': []
        }
    
    # Salvar no arquivo
    with open('data/monitor/position_status.json', 'w') as f:
        json.dump(position_data, f, indent=2)
    
    return position_data

def simulate_ml_status():
    """Simula status dos modelos ML"""
    
    # Gerar predições aleatórias
    def random_prediction():
        r = random.random()
        if r < 0.33:
            return 'BUY'
        elif r < 0.66:
            return 'SELL'
        else:
            return 'HOLD'
    
    ml_status = {
        'timestamp': datetime.now().isoformat(),
        'context_pred': random_prediction(),
        'context_conf': random.uniform(0.4, 0.9),
        'micro_pred': random_prediction(),
        'micro_conf': random.uniform(0.5, 0.95),
        'meta_pred': random_prediction(),
        'meta_conf': random.uniform(0.5, 0.85),
        'ml_status': 'ACTIVE',
        'ml_confidence': random.uniform(0.5, 0.8)
    }
    
    # Salvar no arquivo
    with open('data/monitor/ml_status.json', 'w') as f:
        json.dump(ml_status, f, indent=2)
    
    return ml_status

def simulate_metrics():
    """Simula métricas do sistema"""
    
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'metrics': {
            'gauges': {
                'trades.executed': random.randint(0, 100),
                'trades.wins': random.randint(0, 60),
                'trades.losses': random.randint(0, 40),
                'ml.predictions': random.randint(100, 1000),
                'hmarl.predictions': random.randint(100, 1000),
                'features.calculated': random.randint(1000, 10000),
                'system.uptime': time.time(),
                'position.pnl': random.uniform(-500, 1000),
                'position.open': random.choice([0, 1])
            }
        }
    }
    
    # Salvar no arquivo
    with open('metrics/current_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)
    
    return metrics

def data_simulator():
    """Thread para simular dados continuamente"""
    print("Iniciando simulador de dados...")
    
    while True:
        try:
            # Simular dados a cada intervalo
            simulate_position_data()
            simulate_ml_status()
            simulate_metrics()
            
            # Aguardar antes da próxima atualização
            time.sleep(random.uniform(1, 3))
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Erro no simulador: {e}")
            time.sleep(1)

def main():
    """Função principal"""
    print("=" * 60)
    print(" TESTE DO MONITOR VISUAL INTEGRADO")
    print("=" * 60)
    
    # Iniciar simulador em thread separada
    simulator_thread = threading.Thread(target=data_simulator, daemon=True)
    simulator_thread.start()
    
    print("\n[OK] Simulador de dados iniciado")
    print("[*] Gerando dados de teste...")
    
    # Aguardar um pouco para gerar alguns dados
    time.sleep(2)
    
    print("\n[OK] Dados iniciais gerados:")
    print("  - data/monitor/position_status.json")
    print("  - data/monitor/ml_status.json") 
    print("  - metrics/current_metrics.json")
    
    print("\n[*] Iniciando Monitor Visual Integrado...")
    print("-" * 60)
    
    # Importar e executar o monitor
    try:
        from core.monitor_visual_integrated import IntegratedVisualMonitor
        
        monitor = IntegratedVisualMonitor()
        print("\n[OK] Monitor inicializado com sucesso!")
        print("[*] Iniciando visualização...")
        print("\nPressione Ctrl+C para parar\n")
        
        time.sleep(2)
        monitor.run()
        
    except ImportError as e:
        print(f"\n[ERRO] Não foi possível importar o monitor: {e}")
        print("\nExecute o monitor diretamente:")
        print("  python core/monitor_visual_integrated.py")
    except KeyboardInterrupt:
        print("\n\n[*] Monitor interrompido pelo usuário")
    except Exception as e:
        print(f"\n[ERRO] Erro ao executar monitor: {e}")
    
    print("\n" + "=" * 60)
    print(" TESTE FINALIZADO")
    print("=" * 60)

if __name__ == "__main__":
    main()