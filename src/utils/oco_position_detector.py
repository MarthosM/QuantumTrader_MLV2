"""
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
