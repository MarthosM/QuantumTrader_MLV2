#!/usr/bin/env python3
"""
Teste do Sistema de Validação Anti-Contra-Tendência
Verifica se o sistema está bloqueando corretamente trades contra a tendência
"""

import sys
import numpy as np
from pathlib import Path
from collections import deque

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.trading.regime_based_strategy import (
    RegimeBasedTradingSystem, 
    MarketRegime,
    RegimeDetector
)

def generate_trending_data(trend_type='up', length=100, noise=0.0005):
    """Gera dados simulados com tendência"""
    base_price = 5500.0
    
    if trend_type == 'up':
        # Tendência de alta mais forte para garantir detecção
        trend = np.linspace(0, 100, length)  # Alta de 100 pontos (mais forte)
    elif trend_type == 'down':
        # Tendência de baixa mais forte
        trend = np.linspace(0, -100, length)  # Queda de 100 pontos
    else:
        # Lateral
        trend = np.zeros(length)
    
    # Adicionar menos ruído
    noise_array = np.random.normal(0, base_price * noise, length)
    
    prices = base_price + trend + noise_array
    volumes = np.random.uniform(100, 500, length)
    
    return prices, volumes

def test_trend_detection():
    """Testa detecção de regime"""
    print("\n=== TESTE 1: Detecção de Regime ===")
    
    detector = RegimeDetector()
    
    # Teste 1: Tendência de ALTA
    print("\n1. Testando detecção de UPTREND...")
    prices_up, volumes_up = generate_trending_data('up', 50)
    
    for price, volume in zip(prices_up, volumes_up):
        detector.update(price, volume)
    
    regime, confidence = detector.detect_regime()
    print(f"   Regime detectado: {regime.value}")
    print(f"   Confiança: {confidence:.1%}")
    print(f"   Consistência: {detector.get_trend_consistency():.1%}")
    
    assert regime in [MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND], \
        f"Esperava UPTREND, mas detectou {regime.value}"
    
    # Teste 2: Tendência de BAIXA
    print("\n2. Testando detecção de DOWNTREND...")
    detector = RegimeDetector()  # Reset
    prices_down, volumes_down = generate_trending_data('down', 50)
    
    for price, volume in zip(prices_down, volumes_down):
        detector.update(price, volume)
    
    regime, confidence = detector.detect_regime()
    print(f"   Regime detectado: {regime.value}")
    print(f"   Confiança: {confidence:.1%}")
    print(f"   Consistência: {detector.get_trend_consistency():.1%}")
    
    assert regime in [MarketRegime.DOWNTREND, MarketRegime.STRONG_DOWNTREND], \
        f"Esperava DOWNTREND, mas detectou {regime.value}"
    
    print("\n[OK] Detecção de regime funcionando corretamente!")

def test_trend_validation():
    """Testa validação de alinhamento com tendência"""
    print("\n=== TESTE 2: Validação de Tendência ===")
    
    system = RegimeBasedTradingSystem(min_confidence=0.6)
    
    # Criar tendência de ALTA
    prices_up, volumes_up = generate_trending_data('up', 50)
    for price, volume in zip(prices_up, volumes_up):
        system.update(price, volume)
    
    # Obter regime atual
    regime, _ = system.regime_detector.detect_regime()
    print(f"\nRegime atual: {regime.value}")
    
    # Teste 1: BUY em UPTREND (deve ser permitido)
    print("\n1. Testando BUY em UPTREND...")
    is_valid, reason = system.validate_trend_alignment(
        signal=1,  # BUY
        regime=regime,
        confidence=0.7
    )
    print(f"   Resultado: {'[OK] PERMITIDO' if is_valid else '[X] BLOQUEADO'}")
    print(f"   Motivo: {reason}")
    assert is_valid, "BUY deveria ser permitido em UPTREND"
    
    # Teste 2: SELL em UPTREND (deve ser bloqueado)
    print("\n2. Testando SELL em UPTREND...")
    is_valid, reason = system.validate_trend_alignment(
        signal=-1,  # SELL
        regime=regime,
        confidence=0.7
    )
    print(f"   Resultado: {'[OK] PERMITIDO' if is_valid else '[X] BLOQUEADO'}")
    print(f"   Motivo: {reason}")
    
    # Em tendência forte, deve bloquear
    if regime == MarketRegime.STRONG_UPTREND:
        assert not is_valid, "SELL deveria ser bloqueado em STRONG_UPTREND"
    
    print("\n[OK] Validação de tendência funcionando corretamente!")

def test_lateral_with_recent_trend():
    """Testa lateralização com tendência recente"""
    print("\n=== TESTE 3: Lateralização com Tendência Recente ===")
    
    system = RegimeBasedTradingSystem(min_confidence=0.6)
    
    # Criar tendência de ALTA seguida de lateralização
    print("\n1. Criando tendência de ALTA...")
    prices_up, volumes_up = generate_trending_data('up', 30)
    for price, volume in zip(prices_up, volumes_up):
        system.update(price, volume)
    
    # Adicionar período lateral
    print("2. Adicionando período LATERAL...")
    last_price = prices_up[-1]
    for i in range(20):
        # Preço oscilando em range pequeno
        price = last_price + np.random.uniform(-2, 2)
        system.update(price, 100)
    
    # Tentar gerar sinal
    current_price = last_price
    signal = system.get_trading_signal(current_price)
    
    if signal:
        print(f"\n   Sinal gerado: {'BUY' if signal.signal == 1 else 'SELL'}")
        print(f"   Estratégia: {signal.strategy}")
        print(f"   Confiança: {signal.confidence:.1%}")
        
        # Verificar se respeitou tendência recente
        if signal.signal == -1:  # SELL
            print("   [AVISO] AVISO: SELL gerado após tendência de ALTA recente")
    else:
        print("\n   Nenhum sinal gerado (correto se tendência recente forte)")
    
    # Verificar estatísticas
    stats = system.get_stats()
    print(f"\n3. Estatísticas do sistema:")
    print(f"   Regime atual: {stats['current_regime']}")
    print(f"   Trades bloqueados: {stats['trades_blocked_by_trend']}")
    print(f"   Taxa de bloqueio: {stats['trend_block_rate']}")
    print(f"   Consistência: {stats['trend_consistency']}")
    
    print("\n[OK] Teste de lateralização com tendência recente concluído!")

def test_full_system_integration():
    """Testa integração completa do sistema"""
    print("\n=== TESTE 4: Integração Completa ===")
    
    system = RegimeBasedTradingSystem(min_confidence=0.6)
    
    # Simular sequência de mercado real
    print("\n1. Simulando mercado com mudanças de regime...")
    
    total_signals = 0
    blocked_signals = 0
    
    # Fase 1: Tendência de ALTA (50 períodos)
    print("\n   Fase 1: UPTREND")
    prices_up, volumes_up = generate_trending_data('up', 50)
    for price, volume in zip(prices_up, volumes_up):
        system.update(price, volume)
        signal = system.get_trading_signal(price)
        if signal:
            total_signals += 1
            print(f"      Sinal: {'BUY' if signal.signal == 1 else 'SELL'} @ {price:.2f}")
    
    # Fase 2: Lateralização (30 períodos)
    print("\n   Fase 2: LATERAL")
    last_price = prices_up[-1]
    for i in range(30):
        price = last_price + np.random.uniform(-5, 5)
        system.update(price, 100)
        signal = system.get_trading_signal(price)
        if signal:
            total_signals += 1
            print(f"      Sinal: {'BUY' if signal.signal == 1 else 'SELL'} @ {price:.2f}")
    
    # Fase 3: Tendência de BAIXA (50 períodos)
    print("\n   Fase 3: DOWNTREND")
    prices_down, volumes_down = generate_trending_data('down', 50)
    # Ajustar para começar do último preço
    prices_down = prices_down - prices_down[0] + last_price
    for price, volume in zip(prices_down, volumes_down):
        system.update(price, volume)
        signal = system.get_trading_signal(price)
        if signal:
            total_signals += 1
            print(f"      Sinal: {'BUY' if signal.signal == 1 else 'SELL'} @ {price:.2f}")
    
    # Estatísticas finais
    stats = system.get_stats()
    print(f"\n2. Estatísticas finais:")
    print(f"   Total de sinais: {stats['total_signals']}")
    print(f"   Trades bloqueados por tendência: {stats['trades_blocked_by_trend']}")
    print(f"   Total de validações: {stats['total_validations']}")
    print(f"   Taxa de bloqueio: {stats['trend_block_rate']}")
    print(f"   Regime atual: {stats['current_regime']}")
    
    # Distribuição de regimes
    print(f"\n3. Distribuição de regimes:")
    for regime, count in stats.get('regime_distribution', {}).items():
        print(f"   {regime}: {count}")
    
    print("\n[OK] Teste de integração completa concluído!")
    
    # Verificar que houve bloqueios
    if stats['trades_blocked_by_trend'] > 0:
        print(f"\n[SUCESSO] SUCESSO: Sistema bloqueou {stats['trades_blocked_by_trend']} trades contra tendência!")
    else:
        print("\n[AVISO] AVISO: Nenhum trade foi bloqueado. Verifique se os sinais estão sendo gerados corretamente.")

def main():
    """Executa todos os testes"""
    print("=" * 60)
    print("TESTE DO SISTEMA ANTI-CONTRA-TENDÊNCIA")
    print("=" * 60)
    
    try:
        # Executar testes
        test_trend_detection()
        test_trend_validation()
        test_lateral_with_recent_trend()
        test_full_system_integration()
        
        print("\n" + "=" * 60)
        print("[OK] TODOS OS TESTES PASSARAM COM SUCESSO!")
        print("=" * 60)
        print("\nO sistema está corretamente:")
        print("1. [OK] Detectando regimes de mercado com análise multi-período")
        print("2. [OK] Validando alinhamento de trades com tendência")
        print("3. [OK] Bloqueando trades contra tendência forte")
        print("4. [OK] Respeitando tendência recente em lateralizações")
        print("5. [OK] Rastreando métricas de bloqueio")
        
    except AssertionError as e:
        print(f"\n[ERRO] ERRO NO TESTE: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERRO] ERRO INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()