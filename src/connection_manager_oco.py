"""
Connection Manager com suporte a ordens OCO (One-Cancels-Other)
Baseado no connection_manager_working.py com adição de stop/take automático
"""

import os
import time
import logging
from ctypes import *
from .profit_dll_structures import (
    TConnectorCancelOrder,
    TConnectorAccountIdentifier, 
    TConnectorOrderIdentifier,
    POINTER
)
from datetime import datetime
from .connection_manager_working import ConnectionManagerWorking
from .oco_monitor import OCOMonitor

logger = logging.getLogger('ConnectionOCO')

class ConnectionManagerOCO(ConnectionManagerWorking):
    """Extensão do ConnectionManagerWorking com suporte a ordens OCO"""
    
    def __init__(self, dll_path=None):
        super().__init__(dll_path)
        self.active_orders = {}  # Rastrear ordens ativas
        self.oco_pairs = {}  # Mapear ordens OCO (stop_id -> take_id e vice-versa)
        self.executed_orders = set()  # Ordens já executadas
        
        # Configurar referência bidirecional para callbacks
        if hasattr(self, 'parent_connection'):
            self.parent_connection = self
        
        # Inicializar monitor OCO
        self.oco_monitor = OCOMonitor(self)
        self.oco_monitor.start()
        
    def send_order_with_bracket(self, symbol, side, quantity, entry_price,
                               stop_price, take_price, 
                               account_id=None, broker_id=None, password=None):
        """
        Envia ordem principal com ordens bracket (stop loss e take profit)
        
        Args:
            symbol: Símbolo do ativo (ex: "WDOU25")
            side: "BUY" ou "SELL"
            quantity: Quantidade
            entry_price: Preço de entrada (0 para mercado)
            stop_price: Preço do stop loss
            take_price: Preço do take profit
            account_id: ID da conta (opcional)
            broker_id: ID da corretora (opcional)
            password: Senha da conta (opcional)
            
        Returns:
            dict: {'main_order': id, 'stop_order': id, 'take_order': id}
        """
        if not self.dll:
            self.logger.error("DLL não inicializada")
            return None
            
        try:
            # Configurar parâmetros
            if not account_id:
                account_id = os.getenv('PROFIT_ACCOUNT_ID', '70562000')
            if not broker_id:
                broker_id = os.getenv('PROFIT_BROKER_ID', '33005')
            if not password:
                password = os.getenv('PROFIT_ROUTING_PASSWORD', 'Ultra3376!')
            
            # Configurar tipos de retorno
            # Usando apenas SendBuyOrder e SendSellOrder para todas as ordens
            self.dll.SendBuyOrder.restype = c_longlong
            self.dll.SendSellOrder.restype = c_longlong
            
            # Preparar parâmetros
            c_account = c_wchar_p(str(account_id))
            c_broker = c_wchar_p(str(broker_id))
            c_password = c_wchar_p(password)
            c_symbol = c_wchar_p(symbol)
            c_exchange = c_wchar_p("F")  # F = Futuros BMF
            c_quantity = c_int(quantity)
            
            order_ids = {}
            
            # ========== 1. ENVIAR ORDEM PRINCIPAL ==========
            self.logger.info(f"[OCO] Enviando ordem principal:")
            self.logger.info(f"  Symbol: {symbol}")
            self.logger.info(f"  Side: {side}")
            self.logger.info(f"  Quantity: {quantity}")
            self.logger.info(f"  Entry: A MERCADO (execução imediata)")
            self.logger.info(f"  Stop Loss: {stop_price}")
            self.logger.info(f"  Take Profit: {take_price}")
            
            # Enviar ordem principal
            # IMPORTANTE: Para garantir execução, vamos enviar ordem a MERCADO
            # Preço 0 ou -1 geralmente indica ordem a mercado
            
            # Verificar se devemos usar ordem a mercado ou limite
            use_market_order = True  # Sempre usar mercado para garantir execução
            
            if use_market_order:
                # Usar funções de mercado se disponíveis
                if side.upper() == "BUY":
                    if hasattr(self.dll, 'SendMarketBuyOrder'):
                        self.dll.SendMarketBuyOrder.restype = c_longlong
                        main_order_id = self.dll.SendMarketBuyOrder(
                            c_account, c_broker, c_password,
                            c_symbol, c_exchange, c_quantity
                        )
                    else:
                        # Fallback: ordem com preço 0 (mercado)
                        main_order_id = self.dll.SendBuyOrder(
                            c_account, c_broker, c_password,
                            c_symbol, c_exchange, c_double(0.0), c_quantity
                        )
                else:  # SELL
                    if hasattr(self.dll, 'SendMarketSellOrder'):
                        self.dll.SendMarketSellOrder.restype = c_longlong
                        main_order_id = self.dll.SendMarketSellOrder(
                            c_account, c_broker, c_password,
                            c_symbol, c_exchange, c_quantity
                        )
                    else:
                        # Fallback: ordem com preço 0 (mercado)
                        main_order_id = self.dll.SendSellOrder(
                            c_account, c_broker, c_password,
                            c_symbol, c_exchange, c_double(0.0), c_quantity
                        )
            else:
                # Ordem limite (original)
                c_entry_price = c_double(entry_price if entry_price > 0 else 0.0)
                if side.upper() == "BUY":
                    main_order_id = self.dll.SendBuyOrder(
                        c_account, c_broker, c_password,
                        c_symbol, c_exchange, c_entry_price, c_quantity
                    )
                else:  # SELL
                    main_order_id = self.dll.SendSellOrder(
                        c_account, c_broker, c_password,
                        c_symbol, c_exchange, c_entry_price, c_quantity
                    )
            
            if main_order_id > 0:
                self.logger.info(f"[OK] Ordem principal enviada! ID: {main_order_id}")
                order_ids['main_order'] = main_order_id
                
                # Aguardar um pouco para ordem ser processada
                time.sleep(0.5)
                
                # ========== 2. ENVIAR STOP LOSS ==========
                # IMPORTANTE: Para Stop Loss em posições SELL, não podemos usar ordem limite BUY
                # acima do mercado pois seria executada imediatamente.
                # Solução: Usar SendStopBuyOrder para SELL e SendStopSellOrder para BUY
                
                c_stop_price = c_double(stop_price)
                
                if side.upper() == "BUY":
                    # Para posição comprada, stop loss é venda abaixo
                    # Vamos usar SendStopSellOrder para garantir que funcione como stop
                    if hasattr(self.dll, 'SendStopSellOrder'):
                        # Configurar SendStopSellOrder
                        self.dll.SendStopSellOrder.argtypes = [c_wchar_p, c_wchar_p, c_wchar_p, 
                                                               c_wchar_p, c_wchar_p, 
                                                               c_double, c_double, c_int]
                        self.dll.SendStopSellOrder.restype = c_longlong
                        
                        # Para STOP LOSS de BUY: quando preço cair para stop_price, vender com slippage
                        # Preço limite = stop_price - 20 pontos (slippage máximo aceitável)
                        # Preço de disparo = stop_price (trigger)
                        stop_limit_price = stop_price - 20  # 20 pontos de slippage
                        
                        self.logger.info(f"[DEBUG] Enviando SendStopSellOrder:")
                        self.logger.info(f"  Stop Trigger: {stop_price}")
                        self.logger.info(f"  Stop Limit: {stop_limit_price}")
                        
                        stop_order_id = self.dll.SendStopSellOrder(
                            c_account, c_broker, c_password,
                            c_symbol, c_exchange,
                            c_double(stop_limit_price),  # Preço limite (com slippage)
                            c_stop_price,                # Preço de disparo (trigger)
                            c_quantity
                        )
                    else:
                        # Fallback: ordem limite (funciona para BUY pois stop está abaixo)
                        stop_order_id = self.dll.SendSellOrder(
                            c_account, c_broker, c_password,
                            c_symbol, c_exchange, c_stop_price, c_quantity
                        )
                else:  # SELL
                    # Para posição vendida, stop loss é compra acima
                    # NÃO podemos usar ordem limite BUY acima do mercado!
                    # Vamos usar SendStopBuyOrder com parâmetros corretos
                    if hasattr(self.dll, 'SendStopBuyOrder'):
                        # Configurar SendStopBuyOrder
                        self.dll.SendStopBuyOrder.argtypes = [c_wchar_p, c_wchar_p, c_wchar_p, 
                                                              c_wchar_p, c_wchar_p, 
                                                              c_double, c_double, c_int]
                        self.dll.SendStopBuyOrder.restype = c_longlong
                        
                        # Para STOP LOSS de SELL: quando preço subir para stop_price, comprar com slippage
                        # Preço limite = stop_price + 20 pontos (slippage máximo aceitável)
                        # Preço de disparo = stop_price (trigger)
                        stop_limit_price = stop_price + 20  # 20 pontos de slippage
                        
                        self.logger.info(f"[DEBUG] Enviando SendStopBuyOrder:")
                        self.logger.info(f"  Account: {account_id}")
                        self.logger.info(f"  Symbol: {symbol}")
                        self.logger.info(f"  Stop Trigger: {stop_price}")
                        self.logger.info(f"  Stop Limit: {stop_limit_price}")
                        self.logger.info(f"  Quantity: {quantity}")
                        
                        stop_order_id = self.dll.SendStopBuyOrder(
                            c_account, c_broker, c_password,
                            c_symbol, c_exchange, 
                            c_double(stop_limit_price),  # Preço limite (com slippage)
                            c_stop_price,                # Preço de disparo (trigger)
                            c_quantity
                        )
                        
                        self.logger.info(f"[DEBUG] SendStopBuyOrder retornou: {stop_order_id}")
                    else:
                        # Fallback: não enviar stop (evita execução imediata)
                        self.logger.warning("[AVISO] SendStopBuyOrder não disponível - Stop Loss não enviado")
                        stop_order_id = -1
                
                if stop_order_id > 0:
                    self.logger.info(f"[OK] Stop Loss configurado! ID: {stop_order_id}")
                    order_ids['stop_order'] = stop_order_id
                else:
                    self.logger.warning(f"[AVISO] Falha ao configurar Stop Loss: {stop_order_id}")
                
                # ========== 3. ENVIAR TAKE PROFIT ==========
                c_take_price = c_double(take_price)
                
                if side.upper() == "BUY":
                    # Para posição comprada, take profit é venda acima
                    take_order_id = self.dll.SendSellOrder(
                        c_account, c_broker, c_password,
                        c_symbol, c_exchange, c_take_price, c_quantity
                    )
                else:  # SELL
                    # Para posição vendida, take profit é compra abaixo
                    take_order_id = self.dll.SendBuyOrder(
                        c_account, c_broker, c_password,
                        c_symbol, c_exchange, c_take_price, c_quantity
                    )
                
                if take_order_id > 0:
                    self.logger.info(f"[OK] Take Profit configurado! ID: {take_order_id}")
                    order_ids['take_order'] = take_order_id
                else:
                    self.logger.warning(f"[AVISO] Falha ao configurar Take Profit: {take_order_id}")
                
                # ========== 4. CONFIGURAR OCO SE DISPONÍVEL ==========
                if hasattr(self.dll, 'SetOCOOrders') and 'stop_order' in order_ids and 'take_order' in order_ids:
                    # Vincular stop e take como OCO
                    oco_result = self.dll.SetOCOOrders(
                        c_longlong(order_ids['stop_order']),
                        c_longlong(order_ids['take_order'])
                    )
                    if oco_result == 0:
                        self.logger.info("[OK] Ordens OCO configuradas (Stop/Take)")
                    else:
                        self.logger.warning("[AVISO] SetOCOOrders não disponível - ordens independentes")
                
                # Salvar informações da ordem
                self.active_orders[main_order_id] = {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'stop_price': stop_price,
                    'take_price': take_price,
                    'timestamp': datetime.now(),
                    'order_ids': order_ids,
                    'executed': False,  # Será marcado como True quando executar
                    'closed': False     # Será marcado como True quando fechar
                }
                
                # Mapear ordens OCO (stop e take se cancelam mutuamente)
                if 'stop_order' in order_ids and 'take_order' in order_ids:
                    stop_id = order_ids['stop_order']
                    take_id = order_ids['take_order']
                    self.oco_pairs[stop_id] = take_id
                    self.oco_pairs[take_id] = stop_id
                    self.logger.info(f"[OCO] Mapeamento criado: Stop {stop_id} <-> Take {take_id}")
                    
                    # Registrar no monitor OCO
                    self.oco_monitor.register_oco_group(main_order_id, stop_id, take_id)
                
                self.logger.info("=" * 60)
                self.logger.info("ORDEM BRACKET ENVIADA COM SUCESSO")
                self.logger.info("=" * 60)
                self.logger.info(f"Ordem Principal: {main_order_id}")
                if 'stop_order' in order_ids:
                    self.logger.info(f"Stop Loss: {stop_order_id} @ {stop_price:.1f}")
                if 'take_order' in order_ids:
                    self.logger.info(f"Take Profit: {take_order_id} @ {take_price:.1f}")
                self.logger.info("=" * 60)
                
                return order_ids
                
            else:
                self.logger.error(f"[ERRO] Falha ao enviar ordem principal. Codigo: {main_order_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"Erro ao enviar ordem bracket: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def cancel_bracket_orders(self, main_order_id):
        """
        Cancela todas as ordens bracket relacionadas
        
        Args:
            main_order_id: ID da ordem principal
            
        Returns:
            bool: True se cancelou com sucesso
        """
        if main_order_id not in self.active_orders:
            self.logger.warning(f"Ordem {main_order_id} não encontrada")
            return False
        
        order_info = self.active_orders[main_order_id]
        success = True
        
        # Cancelar cada ordem do bracket
        for order_type, order_id in order_info['order_ids'].items():
            if hasattr(self.dll, 'CancelOrder'):
                result = self.dll.CancelOrder(c_longlong(order_id))
                if result == 0:
                    self.logger.info(f"[OK] {order_type} cancelada: {order_id}")
                else:
                    self.logger.warning(f"[AVISO] Falha ao cancelar {order_type}: {order_id}")
                    success = False
        
        # Remover das ordens ativas
        if success:
            del self.active_orders[main_order_id]
        
        return success
    
    def cancel_order_by_id(self, order_id, symbol="WDOU25"):
        """
        Cancela uma ordem específica usando SendCancelOrderV2
        
        Args:
            order_id: ID da ordem a cancelar (ProfitID)
            symbol: Símbolo do ativo
            
        Returns:
            bool: True se cancelou com sucesso
        """
        if not self.dll:
            self.logger.error("DLL não inicializada")
            return False
            
        try:
            # Configurar SendCancelOrderV2 se ainda não configurado
            if not hasattr(self.dll, '_cancel_configured'):
                self.dll.SendCancelOrderV2.argtypes = [POINTER(TConnectorCancelOrder)]
                self.dll.SendCancelOrderV2.restype = c_int
                self.dll._cancel_configured = True
            
            # Preparar estruturas
            account_id = os.getenv('PROFIT_ACCOUNT_ID', '70562000')
            broker_id = int(os.getenv('PROFIT_BROKER_ID', '33005'))
            password = os.getenv('PROFIT_ROUTING_PASSWORD', 'Ultra3376!')
            
            # Criar estruturas separadamente
            account = TConnectorAccountIdentifier()
            account.Version = c_ubyte(0)
            account.BrokerID = c_int(broker_id)
            account.AccountID = c_wchar_p(account_id)
            account.SubAccountID = c_wchar_p("")
            account.Reserved = c_int64(0)
            
            order = TConnectorOrderIdentifier()
            order.Version = c_ubyte(0)
            order.LocalOrderID = c_int64(order_id)
            order.ClOrderID = c_wchar_p("")
            
            # Criar estrutura de cancelamento
            cancel_order = TConnectorCancelOrder()
            cancel_order.Version = c_ubyte(0)
            cancel_order.AccountID = account
            cancel_order.OrderID = order
            cancel_order.Password = c_wchar_p(password)
            
            # Chamar SendCancelOrderV2
            result = self.dll.SendCancelOrderV2(byref(cancel_order))
            
            if result == 0:  # 0 = sucesso (NL_OK)
                self.logger.info(f"[OK] Ordem {order_id} cancelada com sucesso")
                return True
            else:
                self.logger.warning(f"[AVISO] Falha ao cancelar ordem {order_id}. Código: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro ao cancelar ordem {order_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def check_and_cancel_oco_pair(self, executed_order_id):
        """
        Verifica se uma ordem executada tem par OCO e cancela
        
        Args:
            executed_order_id: ID da ordem que foi executada
        """
        if executed_order_id in self.executed_orders:
            return  # Já processada
            
        self.executed_orders.add(executed_order_id)
        
        # Verificar se tem par OCO
        if executed_order_id in self.oco_pairs:
            pair_order_id = self.oco_pairs[executed_order_id]
            
            self.logger.info(f"[OCO] Ordem {executed_order_id} executada")
            self.logger.info(f"[OCO] Cancelando ordem par: {pair_order_id}")
            
            # Cancelar ordem par
            if self.cancel_order_by_id(pair_order_id):
                # Remover do mapeamento
                del self.oco_pairs[executed_order_id]
                del self.oco_pairs[pair_order_id]
                self.logger.info(f"[OCO] Par cancelado com sucesso")
            else:
                self.logger.warning(f"[OCO] Falha ao cancelar par")
        
        # Marcar ordem principal como executada se for uma das ordens bracket
        for main_id, info in self.active_orders.items():
            order_ids = info.get('order_ids', {})
            if executed_order_id == order_ids.get('main_order'):
                info['executed'] = True
                self.logger.info(f"[POSIÇÃO] Ordem principal {executed_order_id} executada")
            elif executed_order_id in [order_ids.get('stop_order'), order_ids.get('take_order')]:
                # Stop ou take executado - posição fechada
                info['closed'] = True
                self.logger.info(f"[POSIÇÃO] Posição fechada por {'stop' if executed_order_id == order_ids.get('stop_order') else 'take'}")
    
    def get_position(self, symbol="WDOU25", account_id=None, broker_id=None):
        """
        Obtém a posição atual para um símbolo
        
        Args:
            symbol: Símbolo do ativo
            account_id: ID da conta (opcional)
            broker_id: ID da corretora (opcional)
            
        Returns:
            dict: {'quantity': int, 'side': str, 'avg_price': float} ou None
        """
        if not self.dll:
            self.logger.error("DLL não inicializada")
            return None
            
        try:
            # Por enquanto, desabilitar GetPosition devido ao access violation
            # TODO: Implementar quando tivermos a assinatura correta da função
            
            # Alternativa: rastrear posição internamente
            # Quando enviarmos uma ordem, salvamos o estado
            # Quando recebermos callback de execução, atualizamos
            
            # Por enquanto, retornar None (sem posição)
            # Isso é seguro pois evita o erro e permite o sistema funcionar
            return None
            
        except Exception as e:
            self.logger.error(f"Erro ao obter posição: {e}")
            return None
    
    def get_position_safe(self, symbol="WDOU25"):
        """
        Versão segura que usa rastreamento interno de posição
        
        Returns:
            dict: {'quantity': int, 'side': str} ou None
        """
        # Usar rastreamento interno baseado em ordens enviadas
        # Este é um fallback seguro enquanto não temos GetPosition funcionando
        
        # Se temos ordens ativas com ordem principal executada
        for order_id, info in self.active_orders.items():
            if info.get('executed', False):
                return {
                    'quantity': info['quantity'],
                    'side': info['side'],
                    'avg_price': info.get('entry_price', 0)
                }
        
        return None
    
    def get_order_status(self, order_id):
        """
        Verifica o status de uma ordem específica
        
        Args:
            order_id: ID da ordem a verificar
            
        Returns:
            str: Status da ordem ("PENDING", "FILLED", "CANCELLED", "REJECTED", "UNKNOWN")
        """
        if not self.dll:
            self.logger.error("DLL não inicializada")
            return "UNKNOWN"
        
        try:
            # Verificar primeiro no tracking interno
            if order_id in self.executed_orders:
                return "FILLED"
            
            # Tentar obter status via DLL
            if hasattr(self.dll, 'GetOrderStatus'):
                # Configurar GetOrderStatus
                self.dll.GetOrderStatus.argtypes = [c_longlong]
                self.dll.GetOrderStatus.restype = c_int
                
                status_code = self.dll.GetOrderStatus(c_longlong(order_id))
                
                # Mapear códigos de status
                status_map = {
                    0: "PENDING",
                    1: "FILLED",
                    2: "CANCELLED",
                    3: "REJECTED",
                    4: "PARTIALLY_FILLED"
                }
                
                return status_map.get(status_code, "UNKNOWN")
            
            # Método alternativo: verificar em active_orders
            if order_id in self.active_orders:
                order_info = self.active_orders[order_id]
                if order_info.get('executed', False):
                    return "FILLED"
                elif order_info.get('closed', False):
                    return "CANCELLED"
                else:
                    return "PENDING"
            
            # Verificar no OCO Monitor se ele tem informação
            if hasattr(self, 'oco_monitor') and self.oco_monitor:
                if order_id in self.oco_monitor.executed_orders:
                    return "FILLED"
                elif order_id in self.oco_monitor.pending_cancellations:
                    return "CANCELLED"
            
            # Status padrão se não encontrado
            return "UNKNOWN"
            
        except Exception as e:
            self.logger.error(f"Erro ao obter status da ordem {order_id}: {e}")
            return "UNKNOWN"
    
    def mark_order_as_executed(self, order_id):
        """
        Marca uma ordem como executada
        
        Args:
            order_id: ID da ordem executada
        """
        self.executed_orders.add(order_id)
        
        # Atualizar active_orders se existe
        if order_id in self.active_orders:
            self.active_orders[order_id]['executed'] = True
        
        # Notificar OCO Monitor
        if hasattr(self, 'oco_monitor') and self.oco_monitor:
            self.oco_monitor.mark_order_executed(order_id)
        
        self.logger.info(f"[ORDER STATUS] Ordem {order_id} marcada como EXECUTADA")
    
    def check_position_exists(self, symbol="WDOU25"):
        """
        Verifica se existe posição aberta para o símbolo
        
        Args:
            symbol: Símbolo do ativo
            
        Returns:
            tuple: (has_position: bool, quantity: int, side: str)
        """
        if not self.dll:
            self.logger.error("DLL não inicializada")
            return (False, 0, "")
        
        try:
            # CORREÇÃO: Implementação correta de GetPosition conforme manual ProfitDLL v4.0.0.30
            if hasattr(self.dll, 'GetPosition'):
                try:
                    # Criar estrutura TAssetIDRec para o ativo
                    class TAssetIDRec(Structure):
                        _fields_ = [
                            ("ticker", c_wchar * 35),
                            ("bolsa", c_wchar * 15),
                        ]
                    
                    # Preparar estrutura do ativo
                    asset = TAssetIDRec()
                    asset.ticker = symbol
                    asset.bolsa = "F"  # F para futuros
                    
                    self.logger.debug(f"[GETPOSITION DEBUG] Chamando GetPosition para {symbol} bolsa={asset.bolsa}")
                    
                    # Variáveis para receber resultado
                    quantity = c_int(0)
                    avg_price = c_double(0.0)
                    
                    # Configurar assinatura CORRETA da função
                    self.dll.GetPosition.argtypes = [
                        POINTER(TAssetIDRec),  # asset structure pointer
                        POINTER(c_int),         # quantity pointer
                        POINTER(c_double)       # average price pointer
                    ]
                    self.dll.GetPosition.restype = c_int
                    
                    # Chamar GetPosition com assinatura correta
                    result = self.dll.GetPosition(
                        byref(asset),
                        byref(quantity),
                        byref(avg_price)
                    )
                    
                    self.logger.debug(f"[GETPOSITION DEBUG] Resultado: {result}, Quantity: {quantity.value}, AvgPrice: {avg_price.value}")
                    
                    if result == 0:  # NL_OK - sucesso
                        if quantity.value != 0:
                            side = "BUY" if quantity.value > 0 else "SELL"
                            self.logger.info(f"[POSITION CHECK] GetPosition OK: {symbol}: {abs(quantity.value)} {side} @ {avg_price.value:.2f}")
                            return (True, abs(quantity.value), side)
                        else:
                            self.logger.debug(f"[POSITION CHECK] GetPosition OK mas quantity=0: Sem posição")
                            return (False, 0, "")
                    elif result == -2147483637:  # NL_NO_POSITION
                        self.logger.debug(f"[POSITION CHECK] GetPosition retornou NL_NO_POSITION (-2147483637)")
                        return (False, 0, "")
                    else:
                        self.logger.warning(f"[POSITION CHECK] GetPosition retornou erro código: {result}")
                        self.logger.warning(f"[POSITION CHECK] Possíveis causas: símbolo incorreto, DLL não inicializada, ou assinatura incorreta")
                        # Usar fallback
                        raise Exception(f"GetPosition error: {result}")
                        
                except Exception as e:
                    self.logger.warning(f"[POSITION CHECK] Erro ao usar GetPosition: {e}, usando fallback")
                    # Continuar para método alternativo
                    pass
            
            # Método alternativo: verificar se há ordens ativas de stop/take
            # Se não há ordens ativas, provavelmente posição foi fechada
            active_oco_count = sum(1 for g in self.oco_monitor.oco_groups.values() if g.get('active', False))
            
            self.logger.info(f"[POSITION CHECK FALLBACK] Grupos OCO ativos: {active_oco_count}")
            
            if active_oco_count == 0:
                self.logger.info("[POSITION CHECK FALLBACK] Sem ordens OCO ativas - posição provavelmente fechada")
                return (False, 0, "")
            else:
                # Tentar obter mais detalhes do grupo OCO ativo
                for main_id, group in self.oco_monitor.oco_groups.items():
                    if group.get('active', False):
                        self.logger.info(f"[POSITION CHECK FALLBACK] Grupo OCO ativo encontrado: Main={main_id}, Stop={group.get('stop')}, Take={group.get('take')}")
                        break
                
                self.logger.info("[POSITION CHECK FALLBACK] Há ordens OCO ativas, assumindo que posição existe")
                return (True, 1, "UNKNOWN")
            
        except Exception as e:
            self.logger.error(f"Erro ao verificar posição: {e}")
            return (False, 0, "")
    
    def cancel_all_pending_orders(self, symbol="WDOU25", account_id=None, broker_id=None, password=None):
        """
        Cancela todas as ordens pendentes para um símbolo
        
        Args:
            symbol: Símbolo do ativo
            account_id: ID da conta (opcional)
            broker_id: ID da corretora (opcional)
            password: Senha da conta (opcional)
            
        Returns:
            bool: True se cancelou com sucesso
        """
        if not self.dll:
            self.logger.error("DLL não inicializada")
            return False
            
        try:
            # Configurar parâmetros
            if not account_id:
                account_id = os.getenv('PROFIT_ACCOUNT_ID', '70562000')
            if not broker_id:
                broker_id = os.getenv('PROFIT_BROKER_ID', '33005')
            if not password:
                password = os.getenv('PROFIT_ROUTING_PASSWORD', 'Ultra3376!')
            
            # Verificar se existe CancelAllOrders
            if hasattr(self.dll, 'CancelAllOrders'):
                # Configurar CancelAllOrders
                self.dll.CancelAllOrders.argtypes = [c_wchar_p, c_wchar_p, c_wchar_p, c_wchar_p, c_wchar_p]
                self.dll.CancelAllOrders.restype = c_int
                
                result = self.dll.CancelAllOrders(
                    c_wchar_p(str(account_id)),
                    c_wchar_p(str(broker_id)),
                    c_wchar_p(password),
                    c_wchar_p(symbol),
                    c_wchar_p("F")  # Exchange
                )
                
                if result == 0:
                    self.logger.info(f"[OK] Todas as ordens pendentes de {symbol} canceladas")
                    return True
                else:
                    self.logger.warning(f"[AVISO] Falha ao cancelar ordens. Código: {result}")
                    return False
                    
            # Método alternativo: usar CancelOrdersV2 se disponível
            elif hasattr(self.dll, 'CancelOrdersV2'):
                from .profit_dll_structures import TConnectorCancelOrders
                
                # Criar estrutura
                cancel_struct = TConnectorCancelOrders()
                
                # Criar account identifier
                account = TConnectorAccountIdentifier()
                account.Version = c_ubyte(0)
                account.BrokerID = c_int(int(broker_id))
                account.AccountID = c_wchar_p(str(account_id))
                account.SubAccountID = c_wchar_p("")
                account.Reserved = c_int64(0)
                
                cancel_struct.AccountID = POINTER(TConnectorAccountIdentifier)(account)
                cancel_struct.Password = c_wchar_p(password)
                cancel_struct.Ticker = c_wchar_p(symbol)
                cancel_struct.Exchange = c_wchar_p("F")
                cancel_struct.Side = c_int(0)  # 0 = Ambos os lados
                
                result = self.dll.CancelOrdersV2(byref(cancel_struct))
                
                if result == 0:
                    self.logger.info(f"[OK] Todas as ordens pendentes de {symbol} canceladas")
                    return True
                else:
                    self.logger.warning(f"[AVISO] Falha ao cancelar ordens. Código: {result}")
                    return False
                    
            else:
                self.logger.warning("CancelAllOrders não disponível na DLL")
                
                # Fallback: cancelar ordens individualmente se temos a lista
                canceled_count = 0
                for order_id in list(self.active_orders.keys()):
                    if self.cancel_order_by_id(order_id):
                        canceled_count += 1
                        
                if canceled_count > 0:
                    self.logger.info(f"[OK] {canceled_count} ordens canceladas manualmente")
                    return True
                    
            return False
            
        except Exception as e:
            self.logger.error(f"Erro ao cancelar todas as ordens: {e}")
            return False
    
    def disconnect(self):
        """Desconecta e para o monitor OCO"""
        if hasattr(self, 'oco_monitor'):
            self.oco_monitor.stop()
        super().disconnect()
    
    def modify_stop_loss(self, main_order_id, new_stop_price):
        """
        Modifica o stop loss de uma ordem bracket (trailing stop)
        
        Args:
            main_order_id: ID da ordem principal
            new_stop_price: Novo preço de stop
            
        Returns:
            bool: True se modificou com sucesso
        """
        if main_order_id not in self.active_orders:
            self.logger.warning(f"Ordem {main_order_id} não encontrada")
            return False
        
        order_info = self.active_orders[main_order_id]
        
        if 'stop_order' not in order_info['order_ids']:
            self.logger.warning("Ordem não tem stop loss configurado")
            return False
        
        stop_order_id = order_info['order_ids']['stop_order']
        
        if hasattr(self.dll, 'ModifyOrder'):
            result = self.dll.ModifyOrder(
                c_longlong(stop_order_id),
                c_double(new_stop_price)
            )
            
            if result == 0:
                old_stop = order_info['stop_price']
                order_info['stop_price'] = new_stop_price
                self.logger.info(f"[OK] Stop modificado: {old_stop:.1f} -> {new_stop_price:.1f}")
                return True
            else:
                self.logger.error(f"[ERRO] Falha ao modificar stop: {result}")
                return False
        else:
            self.logger.warning("ModifyOrder não disponível na DLL")
            return False