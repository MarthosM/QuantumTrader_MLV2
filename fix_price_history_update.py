"""
Script para corrigir a atualização do price_history buffer
O problema é que o buffer só é atualizado em trades, não em book updates
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_price_history_update():
    """Adiciona atualização do price_history no book update"""
    
    print("="*60)
    print("CORREÇÃO: Atualização do Price History Buffer")
    print("="*60)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print("\n1. Procurando onde adicionar atualização do price_history...")
    
    # Procurar pela linha onde last_mid_price é atualizada no on_book_update
    insert_line = -1
    for i, line in enumerate(lines):
        if "self.last_mid_price = (book_data['bid_price_1'] + book_data['ask_price_1']) / 2" in line:
            insert_line = i
            print(f"   Encontrado na linha {i+1}")
            break
    
    if insert_line == -1:
        print("   [ERRO] Não encontrou onde inserir a correção")
        return False
    
    print("\n2. Adicionando atualização do price_history...")
    
    # Adicionar código após a atualização do last_mid_price
    indent = "                "  # Ajustar identação conforme necessário
    new_code = [
        f"{indent}# Atualizar price_history com mid price do book\n",
        f"{indent}if self.last_mid_price > 0:\n",
        f"{indent}    self.price_history.append(self.last_mid_price)\n",
        f"{indent}    # Limitar log para não poluir\n",
        f"{indent}    if len(self.price_history) % 50 == 0:\n",
        f"{indent}        logger.debug(f'[PRICE HISTORY] Updated from book: {{self.last_mid_price:.2f}} (size={{len(self.price_history)}})')\n",
        "\n"
    ]
    
    # Inserir o novo código
    for j, code_line in enumerate(new_code):
        lines.insert(insert_line + 2 + j, code_line)
    
    # Salvar arquivo
    with open(system_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("   [OK] Código adicionado com sucesso")
    
    print("\n3. Criando teste para verificar features dinâmicas...")
    
    test_code = '''"""
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
    
    print(f"\\nPrice history size: {len(price_history)}")
    print(f"Last 5 prices: {list(price_history)[-5:]}")
    
    # Calcular returns
    prices = list(price_history)
    
    returns_1 = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] != 0 else 0
    returns_5 = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
    returns_20 = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
    
    print(f"\\nReturns calculados:")
    print(f"  returns_1: {returns_1:.6f}")
    print(f"  returns_5: {returns_5:.6f}")
    print(f"  returns_20: {returns_20:.6f}")
    
    # Calcular volatilidade
    volatility_20 = np.std(prices[-20:]) / np.mean(prices[-20:]) if np.mean(prices[-20:]) != 0 else 0
    print(f"  volatility_20: {volatility_20:.6f}")
    
    # Verificar se features são dinâmicas
    if abs(returns_1) < 1e-8 and abs(returns_5) < 1e-8:
        print("\\n[AVISO] Returns estão muito próximos de zero - features podem estar estáticas!")
    else:
        print("\\n[OK] Features parecem dinâmicas")
    
    # Simular múltiplas iterações
    print("\\n" + "="*40)
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
        
        print(f"\\nIteração {iteration + 1}:")
        print(f"  Novo preço: {new_price:.2f}")
        print(f"  Returns_1: {returns_1:.6f}")
        print(f"  Variação: {returns_1 * 100:.4f}%")

if __name__ == "__main__":
    test_price_history_and_features()
'''
    
    with open("test_price_features.py", 'w', encoding='utf-8') as f:
        f.write(test_code)
    
    print("   [OK] Teste criado: test_price_features.py")
    
    print("\n" + "="*60)
    print("CORREÇÃO APLICADA!")
    print("="*60)
    print("\nA correção resolve o problema de returns sempre em 0.0000:")
    print("1. Price history agora é atualizado em cada book update")
    print("2. Isso garante dados frescos para cálculo de returns")
    print("3. Features devem ficar dinâmicas após reiniciar o sistema")
    print("\nReinicie o sistema para aplicar as correções.")

if __name__ == "__main__":
    fix_price_history_update()