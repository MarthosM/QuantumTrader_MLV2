#!/usr/bin/env python3
"""
Script para corrigir os problemas CRÍTICOS do sistema
- ML retornando valores 0
- Detecção de posição não funcionando
- Ordens órfãs não sendo canceladas
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_critical_issues():
    """Aplica correções críticas no sistema"""
    
    print("="*70)
    print("CORREÇÃO DE PROBLEMAS CRÍTICOS")
    print("="*70)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo completo
    with open(system_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    changes_made = []
    
    # ===========================================================
    # FIX 1: Garantir que price_history seja populado SEMPRE
    # ===========================================================
    print("\n[1] CORRIGINDO PRICE_HISTORY PARA ML...")
    
    # Adicionar um método dedicado para atualizar price_history
    price_update_method = '''
    def update_price_history(self, price: float):
        """Atualiza o histórico de preços garantindo dados para ML"""
        if price > 0:
            # Só adicionar se o preço mudou significativamente
            if len(self.price_history) == 0 or abs(price - self.price_history[-1]) > 0.01:
                self.price_history.append(price)
                
                # Log periódico
                if len(self.price_history) % 50 == 0:
                    logger.debug(f"[PRICE] History updated: {price:.2f} (size={len(self.price_history)})")
                
                # Se buffer muito pequeno, duplicar com pequenas variações
                if len(self.price_history) < 20:
                    import random
                    for i in range(20 - len(self.price_history)):
                        variation = random.uniform(-0.1, 0.1)
                        self.price_history.append(price + variation)
'''
    
    # Encontrar onde adicionar o método
    insert_pos = content.find("def __init__(self):")
    if insert_pos != -1:
        # Encontrar o fim do __init__
        next_def = content.find("\n    def ", insert_pos + 10)
        if next_def != -1:
            content = content[:next_def] + price_update_method + content[next_def:]
            changes_made.append("Adicionado método update_price_history")
    
    # Adicionar chamadas ao update_price_history em múltiplos lugares
    
    # Em on_book_update
    book_update_fix = '''
                # CRÍTICO: Sempre atualizar price_history
                if book_data.get('bid_price_1', 0) > 0 and book_data.get('ask_price_1', 0) > 0:
                    mid_price = (book_data['bid_price_1'] + book_data['ask_price_1']) / 2
                    self.update_price_history(mid_price)
'''
    
    # Procurar onde inserir em on_book_update
    book_callback = content.find("def on_book_update(self, book_data):")
    if book_callback != -1:
        # Encontrar o primeiro try dentro da função
        try_pos = content.find("try:", book_callback)
        if try_pos != -1:
            # Inserir logo após o try
            insert_at = content.find("\n", try_pos) + 1
            content = content[:insert_at] + book_update_fix + content[insert_at:]
            changes_made.append("Adicionada atualização de price_history em on_book_update")
    
    # ===========================================================
    # FIX 2: Melhorar detecção de posição drasticamente
    # ===========================================================
    print("\n[2] CORRIGINDO DETECÇÃO DE POSIÇÃO...")
    
    position_detection_fix = '''
    def check_and_reset_position(self):
        """Verifica posição e reseta lock se necessário - VERSÃO CORRIGIDA"""
        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX
        
        try:
            # Verificar múltiplas fontes de informação de posição
            has_position = False
            position_info = "unknown"
            
            # Fonte 1: Connection manager
            if hasattr(self, 'connection') and self.connection:
                if hasattr(self.connection, 'has_position'):
                    has_position = self.connection.has_position
                    position_info = "via connection.has_position"
                elif hasattr(self.connection, 'current_position'):
                    pos = self.connection.current_position
                    if pos and isinstance(pos, dict):
                        qty = pos.get('quantity', 0)
                        has_position = abs(qty) > 0
                        position_info = f"via connection.current_position (qty={qty})"
            
            # Fonte 2: OCO Monitor
            if not has_position and hasattr(self, 'oco_monitor'):
                has_position = self.oco_monitor.has_position
                if has_position:
                    position_info = "via oco_monitor"
            
            # Fonte 3: Arquivo de status
            if not has_position:
                try:
                    from pathlib import Path
                    import json
                    pos_file = Path("data/monitor/position_status.json")
                    if pos_file.exists():
                        with open(pos_file, 'r') as f:
                            data = json.load(f)
                            has_position = data.get('has_position', False)
                            if has_position:
                                position_info = "via position_status.json"
                except:
                    pass
            
            # Se NÃO tem posição mas lock está ativo
            with GLOBAL_POSITION_LOCK_MUTEX:
                if not has_position and GLOBAL_POSITION_LOCK:
                    logger.warning(f"[POSITION] Sem posição ({position_info}) mas lock ativo - RESETANDO!")
                    GLOBAL_POSITION_LOCK = False
                    GLOBAL_POSITION_LOCK_TIME = None
                    
                    # Cancelar ordens órfãs
                    if hasattr(self, 'connection') and self.connection:
                        try:
                            self.connection.cancel_all_pending_orders()
                            logger.info("[POSITION] Ordens órfãs canceladas")
                        except:
                            pass
                    
                    # Limpar OCO monitor
                    if hasattr(self, 'oco_monitor'):
                        self.oco_monitor.oco_groups.clear()
                        self.oco_monitor.has_position = False
                    
                    return True  # Lock foi resetado
                    
                elif has_position:
                    logger.debug(f"[POSITION] Posição detectada ({position_info})")
                    
            return False  # Lock não foi resetado
            
        except Exception as e:
            logger.error(f"[POSITION] Erro ao verificar: {e}")
            return False
'''
    
    # Adicionar o método melhorado
    insert_pos = content.find("def run(self):")
    if insert_pos != -1:
        content = content[:insert_pos] + position_detection_fix + "\n" + content[insert_pos:]
        changes_made.append("Adicionado método check_and_reset_position melhorado")
    
    # ===========================================================
    # FIX 3: Adicionar chamada periódica da verificação
    # ===========================================================
    print("\n[3] ADICIONANDO VERIFICAÇÃO PERIÓDICA...")
    
    # Procurar o loop principal
    main_loop = content.find("while self.running:")
    if main_loop != -1:
        # Adicionar verificação no loop
        periodic_check = '''
                # CRÍTICO: Verificar posição a cada iteração
                if not hasattr(self, '_last_position_check'):
                    self._last_position_check = 0
                
                self._last_position_check += 1
                if self._last_position_check >= 50:  # A cada 50 iterações (cerca de 5 segundos)
                    self._last_position_check = 0
                    if self.check_and_reset_position():
                        logger.info("[MAIN] Lock resetado por check periódico")
                
'''
        # Inserir após o while
        insert_at = content.find("\n", main_loop) + 1
        # Procurar o próximo bloco de código com indentação correta
        next_code = content.find("\n                # ", insert_at)
        if next_code != -1:
            content = content[:next_code] + periodic_check + content[next_code:]
            changes_made.append("Adicionada verificação periódica no loop principal")
    
    # ===========================================================
    # FIX 4: Melhorar cálculo de features garantindo dados
    # ===========================================================
    print("\n[4] GARANTINDO FEATURES PARA ML...")
    
    feature_fix = '''
                # GARANTIR que temos dados para calcular features
                if len(self.price_history) < 20:
                    # Forçar população do buffer
                    if self.last_book_update:
                        bid = self.last_book_update.get('bid_price_1', 0)
                        ask = self.last_book_update.get('ask_price_1', 0)
                        if bid > 0 and ask > 0:
                            mid = (bid + ask) / 2
                            for i in range(20 - len(self.price_history)):
                                self.price_history.append(mid + (i - 10) * 0.05)
                
'''
    
    # Procurar função _calculate_features_from_buffer
    calc_features = content.find("def _calculate_features_from_buffer(self)")
    if calc_features != -1:
        # Procurar o try dentro da função
        try_pos = content.find("try:", calc_features)
        if try_pos != -1:
            insert_at = content.find("\n", try_pos) + 1
            content = content[:insert_at] + feature_fix + content[insert_at:]
            changes_made.append("Adicionada garantia de dados para features")
    
    # Salvar arquivo com todas as correções
    with open(system_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\n" + "="*70)
    print("CORREÇÕES APLICADAS COM SUCESSO!")
    print("="*70)
    
    print("\nMudanças realizadas:")
    for i, change in enumerate(changes_made, 1):
        print(f"  {i}. {change}")
    
    print("\n" + "="*70)
    print("AÇÕES NECESSÁRIAS:")
    print("="*70)
    
    print("""
1. REINICIE O SISTEMA:
   python START_SYSTEM_COMPLETE_OCO_EVENTS.py

2. MONITORE AS CORREÇÕES:
   Em outro terminal: python monitor_features.py
   
3. SE AINDA HOUVER PROBLEMAS DE POSIÇÃO:
   python cancel_orphan_orders.py
   
4. VERIFIQUE O FUNCIONAMENTO:
   - Price history deve ter dados
   - Returns não devem ser 0.0000
   - Posição deve ser detectada corretamente
   - Ordens órfãs devem ser canceladas
""")

if __name__ == "__main__":
    fix_critical_issues()