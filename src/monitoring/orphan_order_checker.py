"""
Verificador de ordens órfãs
"""

import logging
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger('OrderChecker')

class OrphanOrderChecker:
    """Detecta e cancela ordens órfãs automaticamente"""
    
    def __init__(self, connection_manager):
        self.connection = connection_manager
        self.checking = False
        self.check_thread = None
        
    def start(self):
        """Inicia verificação contínua"""
        if self.checking:
            return
            
        self.checking = True
        self.check_thread = threading.Thread(target=self._check_loop, daemon=True)
        self.check_thread.start()
        logger.info("[OrderChecker] Iniciado")
        
    def stop(self):
        """Para verificação"""
        self.checking = False
        if self.check_thread:
            self.check_thread.join(timeout=5)
        logger.info("[OrderChecker] Parado")
        
    def _check_loop(self):
        """Loop de verificação"""
        while self.checking:
            try:
                time.sleep(10)  # Verificar a cada 10 segundos
                
                # Verificar consistência
                if not self._has_position() and self._has_pending_orders():
                    logger.warning("[OrderChecker] Ordens órfãs detectadas!")
                    self._cancel_orphan_orders()
                    
            except Exception as e:
                logger.error(f"[OrderChecker] Erro: {e}")
                
    def _has_position(self):
        """Verifica se há posição aberta"""
        try:
            import START_SYSTEM_COMPLETE_OCO_EVENTS as main
            return main.GLOBAL_POSITION_LOCK
        except:
            return False
            
    def _has_pending_orders(self):
        """Verifica se há ordens pendentes"""
        # Implementar verificação específica
        return False
        
    def _cancel_orphan_orders(self):
        """Cancela ordens órfãs"""
        try:
            self.connection.cancel_all_pending_orders(force=True)
            logger.info("[OrderChecker] Ordens órfãs canceladas")
        except Exception as e:
            logger.error(f"[OrderChecker] Erro ao cancelar: {e}")
