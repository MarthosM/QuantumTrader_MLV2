"""
Teste para verificar se as features estão sendo calculadas corretamente
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
from collections import deque
import numpy as np

def test_price_history_and_features():
    """Testa se o price_history está sendo atualizado e features calculadas"""
    
    print("="*60)
    print("TESTE: Price History e Features Dinâmicas")
    print("="*60)
    
    # Simular price history
    price_history = deque(maxlen=500)
    
    # Adicionar preços simulados (simulando book updates)
    base_price = 5500
    for i in range(100):
        # Adicionar variação aleatória para simular mercado real
        variation = np.random.randn() * 5  # Variação de +/- 5 pontos
        price = base_price + variation + (i * 0.1)  # Tendência leve de alta
        price_history.append(price)
    
    print(f"\nPrice history size: {len(price_history)}")
    print(f"Last 5 prices: {list(price_history)[-5:]}")
    
    # Calcular returns
    prices = list(price_history)
    
    returns_1 = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] != 0 else 0
    returns_5 = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
    returns_20 = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
    
    print(f"\nReturns calculados:")
    print(f"  returns_1: {returns_1:.6f}")
    print(f"  returns_5: {returns_5:.6f}")
    print(f"  returns_20: {returns_20:.6f}")
    
    # Calcular volatilidade
    volatility_20 = np.std(prices[-20:]) / np.mean(prices[-20:]) if np.mean(prices[-20:]) != 0 else 0
    print(f"  volatility_20: {volatility_20:.6f}")
    
    # Verificar se features são dinâmicas
    if abs(returns_1) < 1e-8 and abs(returns_5) < 1e-8:
        print("\n[AVISO] Returns estão muito próximos de zero - features podem estar estáticas!")
    else:
        print("\n[OK] Features parecem dinâmicas")
    
    # Simular múltiplas iterações
    print("\n" + "="*40)
    print("Simulando múltiplas atualizações de book...")
    print("="*40)
    
    for iteration in range(5):
        time.sleep(0.1)
        
        # Adicionar novo preço
        new_price = prices[-1] + np.random.randn() * 5
        price_history.append(new_price)
        
        # Recalcular returns
        prices = list(price_history)
        returns_1 = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] != 0 else 0
        
        print(f"\nIteração {iteration + 1}:")
        print(f"  Novo preço: {new_price:.2f}")
        print(f"  Returns_1: {returns_1:.6f}")
        print(f"  Variação: {returns_1 * 100:.4f}%")

if __name__ == "__main__":
    test_price_history_and_features()
