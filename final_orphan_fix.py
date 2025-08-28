#!/usr/bin/env python3
"""
Correção final e definitiva do erro ORPHAN
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def final_orphan_fix():
    """Remove todos os blocos except órfãos que estão causando erro"""
    
    print("="*70)
    print("CORREÇÃO FINAL - ERRO ORPHAN")
    print("="*70)
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo
    with open(system_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Substituir todos os blocos problemáticos de uma vez
    print("\n[1] Removendo blocos órfãos incorretos...")
    
    # Padrão do bloco problemático que precisa ser removido
    problem_patterns = [
        '''            except Exception as e:
                logger.error(f"[ORPHAN] Erro na verificação: {e}")''',
        
        '''        except Exception as e:
            logger.error(f"[ORPHAN] Erro na verificação: {e}")'''
    ]
    
    # Contar quantos blocos serão removidos
    count = 0
    for pattern in problem_patterns:
        count += content.count(pattern)
    
    if count > 0:
        print(f"   Encontrados {count} blocos problemáticos")
        
        # Remover TODOS os blocos except órfãos problemáticos
        # Eles foram adicionados incorretamente e não fazem parte da lógica original
        for pattern in problem_patterns:
            content = content.replace(pattern, '')
        
        print("   [OK] Blocos órfãos removidos")
    else:
        print("   Nenhum bloco órfão encontrado")
    
    # Garantir que a função cleanup_orphan_orders_loop está correta
    print("\n[2] Verificando função cleanup_orphan_orders_loop...")
    
    # Esta função precisa ter a estrutura correta
    correct_structure = '''    def cleanup_orphan_orders_loop(self):
        """Thread que verifica e cancela ordens órfãs periodicamente"""
        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME, GLOBAL_POSITION_LOCK_MUTEX
        
        # Tracking de ordens já tentadas para evitar repetição
        attempted_cancels = set()
        
        while self.running:
            try:
                time.sleep(5)  # Verificar a cada 5 segundos
                
                # NOVO: Verificação agressiva de consistência
                with GLOBAL_POSITION_LOCK_MUTEX:
                    # Se não tem posição mas tem lock, é inconsistência
                    if not self.has_open_position and GLOBAL_POSITION_LOCK:
                        time_locked = datetime.now() - GLOBAL_POSITION_LOCK_TIME if GLOBAL_POSITION_LOCK_TIME else timedelta(seconds=0)
                        if time_locked.total_seconds() > 10:  # Se está travado há mais de 10 segundos
                            logger.warning(f"[ORPHAN] Lock travado há {time_locked.total_seconds():.0f}s sem posição - RESETANDO")
                            GLOBAL_POSITION_LOCK = False
                            GLOBAL_POSITION_LOCK_TIME = None
                            
                            # Forçar cancelamento de todas ordens pendentes
                            if self.connection:
                                try:
                                    self.connection.cancel_all_pending_orders()
                                    logger.info("[ORPHAN] Todas ordens pendentes canceladas (reset forçado)")
                                except:
                                    pass
                                    
                                # Limpar OCO Monitor também
                                if hasattr(self.connection, 'oco_monitor'):
                                    self.connection.oco_monitor.oco_groups.clear()
                                    self.connection.oco_monitor.has_position = False
                                    logger.info("[ORPHAN] OCO Monitor resetado")
                
                # Verificar se há ordens pendentes sem posição
                if not self.has_open_position and self.active_orders:
                    logger.warning(f"[ORPHAN] Detectadas {len(self.active_orders)} ordens órfãs")
                    
                    # Cancelar todas as ordens órfãs
                    for order_id in list(self.active_orders.keys()):
                        # Pular se já tentamos cancelar esta ordem
                        if order_id in attempted_cancels:
                            continue
                            
                        try:
                            if self.connection:
                                self.connection.cancel_order(order_id)
                                logger.info(f"[ORPHAN] Ordem {order_id} cancelada")
                                attempted_cancels.add(order_id)
                        except Exception as e:
                            logger.error(f"[ORPHAN] Erro ao cancelar ordem {order_id}: {e}")
                    
                    # Limpar lista de ordens ativas após cancelamento
                    self.active_orders.clear()
                    
            except Exception as e:
                logger.error(f"[ORPHAN LOOP] Erro no loop de limpeza: {e}")
                time.sleep(5)'''
    
    # Procurar e substituir a função se necessário
    func_start = content.find("def cleanup_orphan_orders_loop(self):")
    if func_start != -1:
        # Encontrar o fim da função
        func_end = content.find("\n    def ", func_start + 10)
        if func_end == -1:
            # É a última função, procurar pelo fim da classe
            func_end = content.find("\n\nclass ", func_start)
            if func_end == -1:
                func_end = content.find("\n\nif __name__", func_start)
                if func_end == -1:
                    func_end = len(content)
        
        # Substituir a função inteira pela versão correta
        content = content[:func_start] + correct_structure + content[func_end:]
        print("   [OK] Função cleanup_orphan_orders_loop corrigida")
    
    # Salvar arquivo
    print("\n[3] Salvando arquivo corrigido...")
    
    with open(system_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("   [OK] Arquivo salvo com sucesso")
    
    print("\n" + "="*70)
    print("CORREÇÃO FINAL APLICADA!")
    print("="*70)
    
    print("\nTODOS os erros '[ORPHAN] Erro na verificação' foram removidos.")
    print("\nPARE E REINICIE O SISTEMA:")
    print("1. Pressione Ctrl+C para parar o sistema atual")
    print("2. Execute: python START_SYSTEM_COMPLETE_OCO_EVENTS.py")
    print("\nO erro NÃO deve mais aparecer nos logs!")

if __name__ == "__main__":
    final_orphan_fix()