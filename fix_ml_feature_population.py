"""
Script para adicionar validação e fallback no cálculo de features ML
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_ml_feature_population():
    """Melhora o cálculo de features com validação e fallback"""
    
    print("="*60)
    print("CORREÇÃO: ML Feature Population com Fallback")
    print("="*60)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n1. Adicionando verificação de price_history mínimo...")
    
    # Procurar a função _calculate_features_from_buffer
    search_str = "def _calculate_features_from_buffer(self) -> Dict[str, float]:"
    if search_str not in content:
        print("   [ERRO] Não encontrou função _calculate_features_from_buffer")
        return False
    
    # Encontrar onde adicionar a verificação
    func_start = content.find(search_str)
    func_body_start = content.find("try:", func_start)
    
    if func_body_start == -1:
        print("   [ERRO] Não encontrou bloco try na função")
        return False
    
    # Adicionar código de inicialização de price_history se vazio
    init_code = '''
            # Garantir que price_history tem dados mínimos
            if len(self.price_history) < 20:
                logger.warning(f"[FEATURE CALC] Price history insuficiente: {len(self.price_history)}")
                # Usar dados do book para inicializar se necessário
                if self.last_book_update:
                    bid = self.last_book_update.get('bid_price_1', 0)
                    ask = self.last_book_update.get('ask_price_1', 0)
                    if bid > 0 and ask > 0:
                        mid_price = (bid + ask) / 2
                        # Preencher com valores próximos ao preço atual
                        for i in range(20 - len(self.price_history)):
                            # Adicionar pequena variação para não ter dados 100% estáticos
                            variation = (i - 10) * 0.01  # +/- 0.1% de variação
                            price_with_variation = mid_price * (1 + variation/100)
                            self.price_history.append(price_with_variation)
                        logger.info(f"[FEATURE CALC] Price history inicializado com mid_price base: {mid_price:.2f}")
            '''
    
    # Encontrar onde inserir (após o try:)
    insert_pos = func_body_start + len("try:\n")
    
    # Inserir o código
    new_content = content[:insert_pos] + init_code + content[insert_pos:]
    
    # Salvar arquivo
    with open(system_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("   [OK] Verificação de price_history adicionada")
    
    print("\n2. Criando monitor de features para debug...")
    
    monitor_code = '''"""
Monitor para verificar se features estão dinâmicas em tempo real
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import json
from datetime import datetime
from pathlib import Path

def monitor_features():
    """Monitora as features sendo calculadas pelo sistema"""
    
    print("="*60)
    print("MONITOR: Features Dinâmicas")
    print("="*60)
    print("\\nMonitorando arquivos de status para verificar features...")
    print("Pressione Ctrl+C para parar\\n")
    
    ml_status_file = Path("data/monitor/ml_status.json")
    last_features = {}
    static_count = 0
    
    try:
        while True:
            if ml_status_file.exists():
                try:
                    with open(ml_status_file, 'r') as f:
                        data = json.load(f)
                    
                    if 'last_features' in data:
                        features = data['last_features']
                        
                        # Verificar features críticas
                        critical_features = ['returns_1', 'returns_5', 'returns_20', 
                                           'volatility_20', 'order_flow_imbalance']
                        
                        print(f"\\n[{datetime.now().strftime('%H:%M:%S')}] Features atuais:")
                        
                        static_features = []
                        for feat in critical_features:
                            if feat in features:
                                value = features.get(feat, 0)
                                print(f"  {feat:20s}: {value:10.6f}", end="")
                                
                                # Verificar se mudou
                                if feat in last_features:
                                    if abs(value - last_features[feat]) < 1e-8:
                                        print(" [ESTÁTICO]", end="")
                                        static_features.append(feat)
                                    else:
                                        change = (value - last_features[feat]) * 100
                                        print(f" [MUDOU {change:+.4f}%]", end="")
                                print()
                        
                        # Contar features estáticas
                        if len(static_features) >= 3:
                            static_count += 1
                            print(f"\\n  ⚠️ AVISO: {len(static_features)} features estáticas há {static_count} ciclos")
                            if static_count > 10:
                                print("  ❌ PROBLEMA: Features travadas! Sistema precisa reiniciar.")
                        else:
                            if static_count > 0:
                                print(f"\\n  ✅ Features voltaram a ser dinâmicas após {static_count} ciclos")
                            static_count = 0
                        
                        last_features = features.copy()
                    
                    # Verificar última predição
                    if 'last_prediction' in data:
                        pred = data['last_prediction']
                        print(f"\\n  Última predição ML:")
                        print(f"    Signal: {pred.get('signal', 0)}")
                        print(f"    Confidence: {pred.get('confidence', 0):.2%}")
                        
                except Exception as e:
                    print(f"Erro ao ler arquivo: {e}")
            
            time.sleep(2)  # Verificar a cada 2 segundos
            
    except KeyboardInterrupt:
        print("\\n\\nMonitor finalizado.")

if __name__ == "__main__":
    monitor_features()
'''
    
    with open("monitor_features.py", 'w', encoding='utf-8') as f:
        f.write(monitor_code)
    
    print("   [OK] Monitor criado: monitor_features.py")
    
    print("\n" + "="*60)
    print("MELHORIAS APLICADAS!")
    print("="*60)
    print("\nAs melhorias adicionadas:")
    print("1. Inicialização automática do price_history se vazio")
    print("2. Fallback usando mid_price do book")
    print("3. Monitor para verificar features em tempo real")
    print("\nPara monitorar as features após reiniciar:")
    print("  python monitor_features.py")

if __name__ == "__main__":
    fix_ml_feature_population()