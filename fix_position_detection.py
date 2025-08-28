"""
Script para corrigir detecção de fechamento de posição
Adiciona verificação ativa e callbacks melhorados
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def apply_position_detection_fix():
    """Aplica correções no sistema de detecção de posição"""
    
    print("="*60)
    print("CORREÇÃO: Sistema de Detecção de Fechamento de Posição")
    print("="*60)
    
    # 1. Modificar START_SYSTEM_COMPLETE_OCO_EVENTS.py
    print("\n1. Atualizando sistema principal...")
    
    system_file = "START_SYSTEM_COMPLETE_OCO_EVENTS.py"
    
    # Ler arquivo atual
    with open(system_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Adicionar import do PositionChecker
    if "from src.monitoring.position_checker import" not in content:
        # Adicionar após os imports
        import_line = "from src.monitoring.position_checker import get_position_checker, PositionChecker"
        content = content.replace(
            "# Importações opcionais",
            f"# Importações opcionais\ntry:\n    {import_line}\n    position_checker_available = True\nexcept:\n    position_checker_available = False\n    logger.warning('PositionChecker não disponível')\n"
        )
    
    # Adicionar inicialização do PositionChecker no __init__
    if "self.position_checker = None" not in content:
        init_addition = """
        # Sistema de verificação ativa de posições
        self.position_checker = None
        if position_checker_available:
            try:
                self.position_checker = get_position_checker()
                self.position_checker.register_callbacks(
                    on_closed=self.on_position_closed_detected,
                    on_opened=self.on_position_opened_detected,
                    on_changed=self.on_position_changed_detected
                )
                logger.info("[INIT] PositionChecker inicializado")
            except Exception as e:
                logger.error(f"[INIT] Erro ao inicializar PositionChecker: {e}")
        """
        
        # Adicionar após a inicialização do monitor_bridge
        content = content.replace(
            "self.monitor_bridge = get_bridge() if get_bridge else None",
            f"self.monitor_bridge = get_bridge() if get_bridge else None\n{init_addition}"
        )
    
    # Adicionar método de callback para posição fechada
    if "def on_position_closed_detected" not in content:
        callback_methods = '''
    def on_position_closed_detected(self, position_info):
        """Callback quando PositionChecker detecta fechamento de posição"""
        logger.info(f"[POSITION CLOSED] Detectado fechamento de posição: {position_info}")
        
        # Resetar lock global
        global GLOBAL_POSITION_LOCK, GLOBAL_POSITION_LOCK_TIME
        with GLOBAL_POSITION_LOCK_MUTEX:
            if GLOBAL_POSITION_LOCK:
                GLOBAL_POSITION_LOCK = False
                GLOBAL_POSITION_LOCK_TIME = None
                logger.info("[POSITION CLOSED] Lock global resetado!")
        
        # Limpar estado interno
        self.has_open_position = False
        self.position_open_time = None
        self.current_position = 0
        self.current_position_side = None
        self.current_position_id = None
        
        # Notificar OCO Monitor se disponível
        if self.connection and hasattr(self.connection, 'oco_monitor'):
            try:
                self.connection.oco_monitor.handle_position_closed()
            except:
                pass
        
        logger.info("[POSITION CLOSED] Sistema limpo e pronto para novo trade")
    
    def on_position_opened_detected(self, position_info):
        """Callback quando PositionChecker detecta abertura de posição"""
        logger.info(f"[POSITION OPENED] Detectada abertura de posição: {position_info}")
        
        # Atualizar estado interno
        self.has_open_position = True
        self.position_open_time = datetime.now()
        self.current_position = position_info.get('quantity', 0)
        self.current_position_side = position_info.get('side', 'UNKNOWN')
    
    def on_position_changed_detected(self, position_info):
        """Callback quando PositionChecker detecta mudança na posição"""
        logger.info(f"[POSITION CHANGED] Detectada mudança na posição: {position_info}")
        
        # Atualizar quantidade
        self.current_position = position_info.get('quantity', 0)
        '''
        
        # Adicionar antes do método run
        content = content.replace(
            "    def run(self):",
            f"{callback_methods}\n    def run(self):"
        )
    
    # Adicionar início do PositionChecker no método run
    if "self.position_checker.start_checking" not in content:
        checker_start = """
            # Iniciar verificação ativa de posições
            if self.position_checker:
                try:
                    self.position_checker.start_checking(self.symbol)
                    logger.info(f"[RUN] PositionChecker iniciado para {self.symbol}")
                except Exception as e:
                    logger.error(f"[RUN] Erro ao iniciar PositionChecker: {e}")
        """
        
        # Adicionar após conectar
        content = content.replace(
            "print(\"  [OK] Sistema pronto para operar!\")",
            f"print(\"  [OK] Sistema pronto para operar!\")\n{checker_start}"
        )
    
    # Adicionar parada do PositionChecker no cleanup
    if "self.position_checker.stop_checking" not in content:
        checker_stop = """
            # Parar PositionChecker
            if self.position_checker:
                try:
                    self.position_checker.stop_checking()
                    logger.info("[CLEANUP] PositionChecker parado")
                except:
                    pass
        """
        
        # Adicionar no método cleanup
        content = content.replace(
            "def cleanup(self):",
            f"def cleanup(self):\n        {checker_stop}"
        )
    
    # Salvar arquivo modificado
    with open(system_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  [OK] {system_file} atualizado")
    
    # 2. Criar fallback para detectar fechamento via OCO
    print("\n2. Criando detecção alternativa via status de ordens...")
    
    oco_detection = '''"""
Detecção de fechamento via status de ordens OCO
"""

def detect_position_closed_by_oco(connection_manager, symbol):
    """
    Detecta se posição foi fechada verificando status das ordens OCO
    
    Returns:
        bool: True se detectou fechamento
    """
    try:
        if not hasattr(connection_manager, 'oco_monitor'):
            return False
        
        oco_monitor = connection_manager.oco_monitor
        
        # Verificar se há grupos OCO ativos
        active_groups = []
        for group_id, group_info in oco_monitor.oco_groups.items():
            if group_info.get('active'):
                active_groups.append(group_id)
        
        # Se não há grupos ativos mas havia posição, provavelmente fechou
        if not active_groups and oco_monitor.has_position:
            logger.info("[OCO DETECTION] Posição fechada detectada (sem grupos OCO ativos)")
            oco_monitor.has_position = False
            return True
        
        # Verificar se alguma ordem de saída foi executada
        for group_id in active_groups:
            group = oco_monitor.oco_groups[group_id]
            
            # Verificar stop loss
            if group.get('stop_order_id'):
                status = oco_monitor._check_order_status(group['stop_order_id'])
                if status in ['Filled', 'Executed']:
                    logger.info(f"[OCO DETECTION] Stop Loss executado: {group['stop_order_id']}")
                    return True
            
            # Verificar take profit
            if group.get('take_order_id'):
                status = oco_monitor._check_order_status(group['take_order_id'])
                if status in ['Filled', 'Executed']:
                    logger.info(f"[OCO DETECTION] Take Profit executado: {group['take_order_id']}")
                    return True
        
        return False
        
    except Exception as e:
        logger.error(f"[OCO DETECTION] Erro: {e}")
        return False
'''
    
    with open("src/utils/oco_position_detector.py", 'w', encoding='utf-8') as f:
        f.write(oco_detection)
    
    print("  [OK] Detector OCO criado em src/utils/oco_position_detector.py")
    
    print("\n" + "="*60)
    print("CORREÇÕES APLICADAS COM SUCESSO!")
    print("="*60)
    print("\nMelhorias implementadas:")
    print("1. [OK] PositionChecker - Verificação ativa a cada 2 segundos")
    print("2. [OK] Callbacks automáticos quando posição fecha")
    print("3. [OK] Reset automático do GLOBAL_POSITION_LOCK")
    print("4. [OK] Detecção alternativa via status de ordens OCO")
    print("\nO sistema agora detectará automaticamente quando a posição")
    print("for fechada e liberará o lock para permitir novos trades.")
    print("\nReinicie o sistema para aplicar as correções.")

if __name__ == "__main__":
    apply_position_detection_fix()