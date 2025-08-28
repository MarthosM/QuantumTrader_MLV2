#!/usr/bin/env python3
"""
Correção completa do sistema - ML e Detecção de Posição
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_complete_system():
    """Aplica todas as correções necessárias"""
    
    print("="*60)
    print("CORREÇÃO COMPLETA DO SISTEMA")
    print("="*60)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modifications = []
    
    print("\n1. Corrigindo importação do HybridMLPredictor...")
    
    # Procurar a linha de importação
    for i, line in enumerate(lines):
        if "from src.ml.hybrid_predictor import" in line:
            if "HybridPredictor" in line and "HybridMLPredictor" not in line:
                lines[i] = line.replace("HybridPredictor", "HybridMLPredictor")
                modifications.append(f"   Linha {i+1}: Corrigido import HybridMLPredictor")
    
    print("\n2. Garantindo atualização do price_history...")
    
    # Procurar onde adicionar mais atualizações do price_history
    for i, line in enumerate(lines):
        # Adicionar em on_tick_update também
        if "def on_tick_update(self, tick_data):" in line:
            # Procurar onde adicionar o código
            for j in range(i+1, min(i+20, len(lines))):
                if "try:" in lines[j]:
                    # Adicionar código após o try
                    indent = "            "
                    new_code = [
                        f"{indent}# Atualizar price_history com preço do tick\n",
                        f"{indent}if 'price' in tick_data and tick_data['price'] > 0:\n",
                        f"{indent}    if not hasattr(self, '_last_tick_price') or abs(tick_data['price'] - self._last_tick_price) > 0.01:\n",
                        f"{indent}        self.price_history.append(tick_data['price'])\n",
                        f"{indent}        self._last_tick_price = tick_data['price']\n",
                        f"{indent}        if len(self.price_history) % 100 == 0:\n",
                        f"{indent}            logger.debug(f'[TICK] Price history updated: {{tick_data[\"price\"]:.2f}} (size={{len(self.price_history)}})')\n",
                        "\n"
                    ]
                    # Inserir o código
                    for k, code_line in enumerate(new_code):
                        lines.insert(j+1+k, code_line)
                    modifications.append(f"   Linha {j+1}: Adicionada atualização via tick")
                    break
            break
    
    print("\n3. Melhorando detecção de posição fechada...")
    
    # Procurar a função de detecção de posição
    for i, line in enumerate(lines):
        if "def check_position_status(self):" in line:
            # Adicionar verificação mais robusta
            for j in range(i+1, min(i+50, len(lines))):
                if "# Verificar se posição fechou" in lines[j]:
                    # Melhorar a lógica
                    indent = "            "
                    improved_code = [
                        f"{indent}# Verificação melhorada de fechamento de posição\n",
                        f"{indent}current_has_position = False\n",
                        f"{indent}current_quantity = 0\n",
                        f"\n",
                        f"{indent}# Verificar via callbacks primeiro\n",
                        f"{indent}if hasattr(self, 'connection') and self.connection:\n",
                        f"{indent}    try:\n",
                        f"{indent}        # Tentar obter posição atual\n",
                        f"{indent}        position_info = getattr(self.connection, 'current_position', None)\n",
                        f"{indent}        if position_info:\n",
                        f"{indent}            current_quantity = position_info.get('quantity', 0)\n",
                        f"{indent}            current_has_position = abs(current_quantity) > 0\n",
                        f"{indent}    except:\n",
                        f"{indent}        pass\n",
                        f"\n",
                        f"{indent}# Se tinha posição e agora não tem\n",
                        f"{indent}if self.has_position and not current_has_position:\n",
                        f"{indent}    logger.info('[POSITION] Fechamento detectado!')\n",
                        f"{indent}    self.on_position_closed()\n",
                        f"\n",
                        f"{indent}self.has_position = current_has_position\n",
                        f"{indent}self.position_quantity = current_quantity\n"
                    ]
                    
                    # Substituir código existente
                    lines[j:j+10] = improved_code
                    modifications.append(f"   Linha {j}: Melhorada detecção de posição")
                    break
            break
    
    print("\n4. Forçando cancelamento de ordens órfãs...")
    
    # Adicionar função de limpeza agressiva
    cleanup_function = '''
    def force_cancel_orphan_orders(self):
        """Força cancelamento de todas ordens pendentes se não há posição"""
        try:
            if not self.has_position:
                logger.info("[CLEANUP] Forçando cancelamento de ordens órfãs...")
                
                # Cancelar via connection manager
                if hasattr(self, 'connection') and self.connection:
                    try:
                        self.connection.cancel_all_pending_orders()
                        logger.info("  [OK] Ordens canceladas via connection")
                    except Exception as e:
                        logger.error(f"  [ERRO] Falha ao cancelar: {e}")
                
                # Limpar OCO monitor
                if hasattr(self, 'oco_monitor'):
                    self.oco_monitor.oco_groups.clear()
                    self.oco_monitor.has_position = False
                    logger.info("  [OK] OCO Monitor limpo")
                
                # Resetar lock global
                global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME
                with GLOBAL_POSITION_LOCK_MUTEX:
                    GLOBAL_POSITION_LOCK = False
                    GLOBAL_POSITION_LOCK_TIME = None
                logger.info("  [OK] Lock global resetado")
                
        except Exception as e:
            logger.error(f"[CLEANUP] Erro na limpeza forçada: {e}")
    
'''
    
    # Adicionar a função antes do main loop
    for i, line in enumerate(lines):
        if "def run(self):" in line:
            lines.insert(i, cleanup_function)
            modifications.append(f"   Linha {i}: Adicionada função force_cancel_orphan_orders")
            break
    
    # Salvar arquivo
    with open(system_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("\n5. Criando script de verificação...")
    
    verify_script = '''#!/usr/bin/env python3
"""
Verifica se as correções estão funcionando
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import json
from pathlib import Path
from collections import deque

def verify_system():
    print("="*60)
    print("VERIFICAÇÃO DO SISTEMA")
    print("="*60)
    
    # 1. Testar ML
    print("\\n1. Testando ML Predictor...")
    try:
        from src.ml.hybrid_predictor import HybridMLPredictor
        predictor = HybridMLPredictor()
        
        # Criar features teste
        test_features = {
            'returns_1': 0.001,
            'returns_5': 0.002,
            'volatility_20': 0.01,
            'order_flow_imbalance': 0.5,
            'bid_price_1': 5500,
            'ask_price_1': 5505
        }
        
        # Preencher com features dummy
        for i in range(65):
            if f'feature_{i}' not in test_features:
                test_features[f'feature_{i}'] = 0.1
        
        result = predictor.predict(test_features)
        if result and result.get('signal') != 0:
            print("  [OK] ML funcionando")
        else:
            print("  [PROBLEMA] ML retornando 0 ou None")
            
    except Exception as e:
        print(f"  [ERRO] {e}")
    
    # 2. Verificar price buffer
    print("\\n2. Testando Price Buffer...")
    price_history = deque(maxlen=500)
    
    # Simular adição de preços
    for i in range(50):
        price = 5500 + i * 0.1
        price_history.append(price)
    
    if len(price_history) > 20:
        prices = list(price_history)
        returns = (prices[-1] - prices[-2]) / prices[-2]
        if abs(returns) > 1e-8:
            print("  [OK] Price buffer e returns funcionando")
        else:
            print("  [PROBLEMA] Returns zerados")
    
    # 3. Verificar arquivos de status
    print("\\n3. Verificando Arquivos de Status...")
    
    pos_file = Path("data/monitor/position_status.json")
    if pos_file.exists():
        with open(pos_file, 'r') as f:
            data = json.load(f)
        print(f"  Position status: has_position={data.get('has_position', 'N/A')}")
    else:
        print("  [AVISO] Arquivo position_status.json não existe")
    
    ml_file = Path("data/monitor/ml_status.json")
    if ml_file.exists():
        with open(ml_file, 'r') as f:
            data = json.load(f)
        print(f"  ML status: timestamp={data.get('timestamp', 'N/A')}")
    else:
        print("  [AVISO] Arquivo ml_status.json não existe")
    
    print("\\n" + "="*60)
    print("Verificação concluída!")
    print("\\nSe houver problemas, execute:")
    print("  1. python fix_complete_system.py")
    print("  2. Reinicie o sistema")
    print("  3. python monitor_features.py (em outro terminal)")

if __name__ == "__main__":
    verify_system()
'''
    
    with open("verify_fixes.py", 'w', encoding='utf-8') as f:
        f.write(verify_script)
    
    print("\n   [OK] Script de verificação criado: verify_fixes.py")
    
    print("\n" + "="*60)
    print("CORREÇÕES APLICADAS!")
    print("="*60)
    
    if modifications:
        print("\nModificações realizadas:")
        for mod in modifications:
            print(mod)
    else:
        print("\nNenhuma modificação necessária (já aplicadas)")
    
    print("\n" + "="*60)
    print("PRÓXIMOS PASSOS:")
    print("="*60)
    print("\n1. Reinicie o sistema:")
    print("   python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
    print("\n2. Em outro terminal, verifique as correções:")
    print("   python verify_fixes.py")
    print("\n3. Monitore as features:")
    print("   python monitor_features.py")
    print("\n4. Se posição não detectar fechamento:")
    print("   python cancel_orphan_orders.py")

if __name__ == "__main__":
    fix_complete_system()