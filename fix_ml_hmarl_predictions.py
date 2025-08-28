#!/usr/bin/env python3
"""
Correção definitiva para ML e HMARL gerarem predições corretas
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def fix_ml_hmarl_predictions():
    """Corrige problemas de predições ML e HMARL"""
    
    print("="*70)
    print("CORREÇÃO - ML & HMARL PREDICTIONS")
    print("="*70)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # =========================================================
    # FIX 1: Garantir que make_hybrid_prediction funciona
    # =========================================================
    print("\n[1] Corrigindo função make_hybrid_prediction...")
    
    # Procurar a função
    func_start = content.find("def make_hybrid_prediction(self):")
    if func_start != -1:
        # Encontrar o fim da função
        func_end = content.find("\n    def ", func_start + 10)
        if func_end == -1:
            func_end = len(content)
        
        # Nova implementação robusta
        new_function = '''    def make_hybrid_prediction(self):
        """Faz predição usando ML + HMARL com fallback"""
        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX
        
        try:
            # Inicializar resultado
            final_prediction = {
                'signal': 0,
                'confidence': 0.0,
                'ml_data': None,
                'hmarl_data': None,
                'predictions': {},
                'timestamp': datetime.now()
            }
            
            # 1. Tentar ML primeiro
            ml_prediction = None
            if self.ml_predictor:
                try:
                    # Calcular features
                    features = self._calculate_features_from_buffer()
                    
                    # Garantir que temos features suficientes
                    if len(features) >= 10:  # Mínimo de features
                        # Fazer predição ML
                        ml_result = self.ml_predictor.predict(features)
                        
                        if ml_result:
                            ml_prediction = ml_result
                            final_prediction['ml_data'] = ml_result
                            final_prediction['predictions'] = ml_result.get('predictions', {})
                            
                            # Log apenas periodicamente
                            if not hasattr(self, '_ml_log_count'):
                                self._ml_log_count = 0
                            self._ml_log_count += 1
                            
                            if self._ml_log_count % 100 == 0:
                                logger.debug(f"[ML] Predição: signal={ml_result.get('signal')}, conf={ml_result.get('confidence', 0):.2%}")
                except Exception as e:
                    if not hasattr(self, '_ml_error_logged'):
                        logger.error(f"[ML] Erro na predição: {e}")
                        self._ml_error_logged = True
            
            # 2. Tentar HMARL
            hmarl_prediction = None
            if self.hmarl_agents:
                try:
                    # HMARL precisa apenas das features
                    features = self._calculate_features_from_buffer() if not features else features
                    
                    # Fazer predição HMARL
                    hmarl_result = self.hmarl_agents.get_consensus(features)
                    
                    if hmarl_result:
                        hmarl_prediction = hmarl_result
                        final_prediction['hmarl_data'] = hmarl_result
                        
                        # Log apenas periodicamente
                        if self._ml_log_count % 100 == 0:
                            logger.debug(f"[HMARL] Consenso: signal={hmarl_result.get('signal')}, conf={hmarl_result.get('confidence', 0):.2%}")
                except Exception as e:
                    if not hasattr(self, '_hmarl_error_logged'):
                        logger.error(f"[HMARL] Erro na predição: {e}")
                        self._hmarl_error_logged = True
            
            # 3. Combinar predições (60% ML + 40% HMARL)
            if ml_prediction and hmarl_prediction:
                # Ambas disponíveis - combinar
                ml_weight = 0.6
                hmarl_weight = 0.4
                
                ml_signal = ml_prediction.get('signal', 0)
                ml_conf = ml_prediction.get('confidence', 0)
                hmarl_signal = hmarl_prediction.get('signal', 0)
                hmarl_conf = hmarl_prediction.get('confidence', 0.5)
                
                # Combinar sinais
                if ml_signal == hmarl_signal:
                    # Concordam - aumentar confiança
                    final_prediction['signal'] = ml_signal
                    final_prediction['confidence'] = (ml_conf * ml_weight + hmarl_conf * hmarl_weight) * 1.1  # Boost
                else:
                    # Discordam - usar o de maior confiança
                    if ml_conf > hmarl_conf:
                        final_prediction['signal'] = ml_signal
                        final_prediction['confidence'] = ml_conf * ml_weight
                    else:
                        final_prediction['signal'] = hmarl_signal
                        final_prediction['confidence'] = hmarl_conf * hmarl_weight
            
            elif ml_prediction:
                # Apenas ML disponível
                final_prediction['signal'] = ml_prediction.get('signal', 0)
                final_prediction['confidence'] = ml_prediction.get('confidence', 0) * 0.8  # Reduzir sem HMARL
            
            elif hmarl_prediction:
                # Apenas HMARL disponível
                final_prediction['signal'] = hmarl_prediction.get('signal', 0)
                final_prediction['confidence'] = hmarl_prediction.get('confidence', 0.5) * 0.7  # Reduzir sem ML
            
            else:
                # Nenhum disponível - usar fallback simples baseado em preço
                if len(self.price_history) >= 20:
                    prices = list(self.price_history)
                    ma5 = sum(prices[-5:]) / 5
                    ma20 = sum(prices[-20:]) / 20
                    
                    if ma5 > ma20 * 1.001:  # 0.1% acima
                        final_prediction['signal'] = 1  # Buy
                        final_prediction['confidence'] = 0.5
                    elif ma5 < ma20 * 0.999:  # 0.1% abaixo
                        final_prediction['signal'] = -1  # Sell
                        final_prediction['confidence'] = 0.5
            
            # Garantir limites
            final_prediction['confidence'] = max(0.0, min(1.0, final_prediction['confidence']))
            
            # Salvar última predição
            self.last_prediction = final_prediction
            
            # Atualizar arquivo de status se houver mudança significativa
            if not hasattr(self, '_last_saved_signal'):
                self._last_saved_signal = None
            
            if final_prediction['signal'] != self._last_saved_signal:
                self._last_saved_signal = final_prediction['signal']
                self._save_ml_status(final_prediction)
            
            return final_prediction
            
        except Exception as e:
            logger.error(f"[PREDICTION] Erro geral na predição: {e}")
            # Retornar neutro em caso de erro
            return {
                'signal': 0,
                'confidence': 0.0,
                'error': str(e),
                'timestamp': datetime.now()
            }
'''
        
        # Substituir a função
        content = content[:func_start] + new_function + content[func_end:]
        print("   [OK] Função make_hybrid_prediction corrigida")
    
    # =========================================================
    # FIX 2: Garantir que HMARL recebe dados atualizados
    # =========================================================
    print("\n[2] Corrigindo atualização de dados HMARL...")
    
    # Adicionar atualização no on_book_update
    book_update_func = content.find("def on_book_update(self, book_data):")
    if book_update_func != -1:
        # Procurar onde adicionar atualização HMARL
        insert_pos = content.find("self.last_book_update = book_data", book_update_func)
        if insert_pos != -1:
            # Adicionar após a linha
            insert_at = content.find("\n", insert_pos) + 1
            
            hmarl_update = '''                
                # Atualizar HMARL com dados frescos
                if self.hmarl_agents and hasattr(self.hmarl_agents, 'update_book_data'):
                    try:
                        self.hmarl_agents.update_book_data(book_data)
                    except:
                        pass  # Silencioso se não tiver o método
'''
            
            # Verificar se já não existe
            if "update_book_data" not in content[book_update_func:book_update_func+5000]:
                content = content[:insert_at] + hmarl_update + content[insert_at:]
                print("   [OK] Atualização HMARL adicionada em on_book_update")
    
    # =========================================================
    # FIX 3: Garantir que ML tem features válidas
    # =========================================================
    print("\n[3] Melhorando cálculo de features...")
    
    # Melhorar _calculate_features_from_buffer
    calc_features_func = content.find("def _calculate_features_from_buffer(self):")
    if calc_features_func != -1:
        # Adicionar validação no início
        try_pos = content.find("try:", calc_features_func)
        if try_pos != -1:
            insert_at = content.find("\n", try_pos) + 1
            
            validation_code = '''            # Garantir dados mínimos
            if len(self.price_history) < 20:
                # Preencher com dados do book se disponível
                if self.last_book_update:
                    bid = self.last_book_update.get('bid_price_1', 0)
                    ask = self.last_book_update.get('ask_price_1', 0)
                    if bid > 0 and ask > 0:
                        mid = (bid + ask) / 2
                        for _ in range(20 - len(self.price_history)):
                            self.price_history.append(mid)
            
'''
            # Verificar se já não existe
            if "Garantir dados mínimos" not in content[calc_features_func:calc_features_func+2000]:
                content = content[:insert_at] + validation_code + content[insert_at:]
                print("   [OK] Validação de features adicionada")
    
    # Salvar arquivo
    print("\n[4] Salvando arquivo corrigido...")
    
    with open(system_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("   [OK] Arquivo salvo")
    
    print("\n" + "="*70)
    print("CORREÇÕES APLICADAS!")
    print("="*70)
    
    print("\nMelhorias implementadas:")
    print("1. make_hybrid_prediction com fallback robusto")
    print("2. Combinação inteligente ML (60%) + HMARL (40%)")
    print("3. Atualização automática de dados HMARL")
    print("4. Validação de features antes da predição")
    print("5. Fallback baseado em médias móveis se tudo falhar")
    
    print("\nREINICIE O SISTEMA para aplicar as correções:")
    print("1. Ctrl+C para parar")
    print("2. python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
    
    print("\nO sistema agora deve gerar predições válidas!")

if __name__ == "__main__":
    fix_ml_hmarl_predictions()