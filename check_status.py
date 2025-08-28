#!/usr/bin/env python3
"""
Verifica o status do sistema Quantum Trader
"""

import json
import time
from pathlib import Path
from datetime import datetime

def check_status():
    """Verifica status do sistema"""
    
    print("\n" + "=" * 80)
    print(" QUANTUM TRADER V3 - STATUS CHECK")
    print("=" * 80)
    print(f" Horário: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 80 + "\n")
    
    # Verificar métricas principais
    metrics_file = Path("metrics/current_metrics.json")
    if metrics_file.exists():
        with open(metrics_file, 'r') as f:
            metrics = json.load(f)
        
        print("[SISTEMA]")
        print(f"  Status: {'RODANDO' if metrics.get('running', False) else 'PARADO'}")
        print(f"  Símbolo: {metrics.get('symbol', 'N/A')}")
        print(f"  Modo: {metrics.get('trading_mode', 'N/A')}")
        print(f"  Book count: {metrics.get('book_count', 0):,}")
        print(f"  Tick count: {metrics.get('tick_count', 0):,}")
        
        print("\n[PREÇOS]")
        print(f"  Último: {metrics.get('last_price', 0):.2f}")
        print(f"  Bid: {metrics.get('best_bid', 0):.2f}")
        print(f"  Ask: {metrics.get('best_ask', 0):.2f}")
        print(f"  Spread: {metrics.get('spread', 0):.2f}")
        
        position = metrics.get('position', {})
        if position.get('has_position'):
            print("\n[POSIÇÃO ABERTA]")
            print(f"  Side: {position.get('side', 'N/A')}")
            print(f"  Qtd: {position.get('quantity', 0)}")
            print(f"  Entry: {position.get('entry_price', 0):.2f}")
            print(f"  P&L: R$ {position.get('current_pnl', 0):.2f}")
        else:
            print("\n[POSIÇÃO]")
            print("  Sem posição aberta")
        
        stats = metrics.get('stats', {})
        print("\n[ESTATÍSTICAS]")
        print(f"  Trades hoje: {stats.get('trades_today', 0)}/{stats.get('max_trades', 10)}")
        print(f"  Sinais gerados: {stats.get('signals_generated', 0)}")
        print(f"  Win Rate: {stats.get('win_rate', 0):.1f}%")
        print(f"  P&L Total: R$ {stats.get('total_pnl', 0):.2f}")
        
        # Calcular idade dos dados
        try:
            timestamp = datetime.fromisoformat(metrics['timestamp'])
            age = (datetime.now() - timestamp).total_seconds()
            print(f"\n  Última atualização: {age:.1f}s atrás")
            if age > 30:
                print("  ⚠️ AVISO: Dados desatualizados!")
        except:
            pass
    else:
        print("❌ Arquivo de métricas não encontrado!")
    
    # Verificar ML status
    print("\n" + "-" * 80)
    ml_file = Path("metrics/ml_status.json")
    if ml_file.exists():
        with open(ml_file, 'r') as f:
            ml_status = json.load(f)
        
        print("\n[ML/HMARL STATUS]")
        print(f"  Sinal ML: {ml_status.get('ml_signal', 0)}")
        print(f"  Confiança ML: {ml_status.get('ml_confidence', 0)*100:.1f}%")
        print(f"  Features calculadas: {ml_status.get('features_calculated', 0)}")
        print(f"  Buffer size: {ml_status.get('buffer_size', 0)}")
        print(f"  Predictions count: {ml_status.get('predictions_count', 0)}")
        
        # HMARL
        if 'hmarl_consensus' in ml_status:
            print(f"\n  HMARL Consensus: {ml_status.get('hmarl_consensus', 0):.3f}")
            print(f"  HMARL Confidence: {ml_status.get('hmarl_confidence', 0.5)*100:.1f}%")
        
        if 'orderflow_action' in ml_status:
            print(f"\n  [AGENTS]")
            print(f"    OrderFlow: {ml_status.get('orderflow_action', 0):.3f}")
            print(f"    Liquidity: {ml_status.get('liquidity_action', 0):.3f}")
            print(f"    TapeReading: {ml_status.get('tapereading_action', 0):.3f}")
            print(f"    Footprint: {ml_status.get('footprint_action', 0):.3f}")
        
        # Idade dos dados ML
        try:
            timestamp = datetime.fromisoformat(ml_status['timestamp'])
            age = (datetime.now() - timestamp).total_seconds()
            print(f"\n  Última predição: {age:.1f}s atrás")
        except:
            pass
    else:
        print("\n❌ Arquivo ML status não encontrado!")
    
    print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    check_status()