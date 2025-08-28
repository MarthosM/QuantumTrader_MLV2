"""
Connection Manager v4.0.0.30 - Gerencia conexão com ProfitDLL e callbacks
Versão atualizada com assinaturas corretas para API v4.0.0.30
"""

import logging
import time
import os
import traceback
from typing import Dict, Optional, Callable, Any, List
from ctypes import WINFUNCTYPE, WinDLL, c_int, c_int32, c_wchar_p, c_double, c_uint, c_char, c_longlong, c_void_p, POINTER, byref
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Importar estruturas da API v4.0.0.30
from src.profit_dll_structures import (
    TAssetID, TConnectorOrderOut, TConnectorAccountIdentifier,
    TConnectorTradeCallback, TConnectorOrderCallback, TConnectorAccountCallback,
    TStateCallback, TNewTradeCallback, THistoryTradeCallback, TProgressCallback,
    TPriceBookCallback, TOfferBookCallback, TAccountCallback,
    TOfferBookCallbackV2, TPriceBookCallbackV2, TTradeCallbackV2,
    NResult, ConnectionState
)

class ConnectionManagerV4:
    """Gerencia conexão com Profit e callbacks essenciais - v4.0.0.30"""
    
    def __init__(self, dll_path: str):
        self.dll_path = dll_path if dll_path else r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
        self.dll = None
        self.connected = False
        self.callbacks = {}
        self.v2_callbacks = {}  # Store V2 callbacks to prevent garbage collection
        self.logger = logging.getLogger('ConnectionManagerV4')
        
        # Detectar modo de desenvolvimento
        self.dev_mode = os.getenv('DEV_MODE', 'false').lower() == 'true'
        if self.dev_mode:
            self.logger.info("[DEV] MODO DESENVOLVIMENTO ATIVADO - Lógica adaptada para mercado fechado")
        
        # OTIMIZAÇÃO: Configurar logging para reduzir spam no terminal
        self._configure_optimal_logging()
        
        # Estados de conexão (baseado na API v4.0.0.30)
        self.market_connected = False
        self.broker_connected = False
        self.routing_connected = False
        self.login_state = -1
        self.routing_state = -1
        self.market_state = -1

        # Constantes de estado do manual v4.0.0.30
        self.CONNECTION_STATE_LOGIN = ConnectionState.LOGIN
        self.CONNECTION_STATE_ROTEAMENTO = ConnectionState.ROTEAMENTO
        self.CONNECTION_STATE_MARKET_DATA = ConnectionState.MARKET_DATA
        self.CONNECTION_STATE_MARKET_LOGIN = ConnectionState.MARKET_LOGIN

        self.LOGIN_CONNECTED = 0
        self.MARKET_CONNECTED = 4
        self.ROTEAMENTO_BROKER_CONNECTED = 5
                
        # Configurações do servidor
        self.server_address = os.getenv("SERVER_ADDRESS", "producao.nelogica.com.br")
        self.server_port = os.getenv("SERVER_PORT", "8184")
        
        # Callbacks registrados
        self.trade_callbacks = []
        self.state_callbacks = []
        self.order_callbacks = []
        self.account_callbacks = []
        
        # Callbacks de book em tempo real
        self._offer_book_callback = None
        self._price_book_callback = None
        
        # Contadores para debug
        self._historical_data_count = 0
        self._last_historical_timestamp = None
        
        self.logger.info("ConnectionManagerV4 criado - Compatível com ProfitDLL v4.0.0.30")
    
    def _configure_optimal_logging(self):
        """
        Configura logging otimizado para evitar spam no terminal
        Especialmente importante durante carregamento de dados históricos
        """
        try:
            # Configurar nível ROOT como WARNING para reduzir spam geral
            root_logger = logging.getLogger()
            if not root_logger.handlers:
                root_logger.setLevel(logging.WARNING)
            
            # Componentes que podem gerar muito spam - configurar como ERROR apenas
            spam_components = [
                'FeatureEngine',
                'ProductionDataValidator',
                'TechnicalIndicators',
                'MLFeatures',
                'RealTimeProcessor',
                'DataPipeline'
            ]
            
            for component in spam_components:
                spam_logger = logging.getLogger(component)
                spam_logger.setLevel(logging.ERROR)
            
            # ConnectionManager e componentes essenciais mantêm INFO
            essential_components = [
                'ConnectionManagerV4',
                'TradingSystem',
                'DataIntegration'
            ]
            
            for component in essential_components:
                essential_logger = logging.getLogger(component)
                essential_logger.setLevel(logging.INFO)
            
            self.logger.info("[DEV] Logging otimizado configurado - redução de spam ativada")
            
        except Exception as e:
            # Não falhar se houver problema com logging
            print(f"Aviso: Erro configurando logging otimizado: {e}")
        
    def initialize(self, key: str, username: str, password: str, 
                  account_id: Optional[str] = None, broker_id: Optional[str] = None, 
                  trading_password: Optional[str] = None) -> bool:
        """
        Inicializa conexão com Profit usando API v4.0.0.30
        
        Args:
            key: Chave de acesso do Profit
            username: Nome de usuário
            password: Senha de login
            account_id: ID da conta (para simulador)
            broker_id: ID da corretora (para simulador)
            trading_password: Senha de trading (se necessária)
        """
        try:
            # Log dos parâmetros (sem senhas por segurança)
            self.logger.info(f"Inicializando conexão v4.0.0.30 com usuário: {username}")
            if account_id:
                self.logger.info(f"Conta: {account_id}")
            if broker_id:
                self.logger.info(f"Corretora: {broker_id}")
            
            # Carregar DLL
            self.dll = self._load_dll()
            if not self.dll:
                return False
            
            # Configurar servidor
            self.logger.info(f"Configurando servidor: {self.server_address}:{self.server_port}")
            server_result = self.dll.SetServerAndPort(
                c_wchar_p(self.server_address),
                c_wchar_p(self.server_port)
            )
            self.logger.info(f"Resultado da configuração do servidor: {server_result}")
            
            # Configurar callbacks v4.0.0.30
            self._setup_callbacks_v4()
            
            # Conectar usando DLLInitializeLogin (inclui market data e routing)
            self.logger.info("Inicializando conexão completa com Profit v4.0.0.30...")
            init_result = self.dll.DLLInitializeLogin(
                c_wchar_p(key),
                c_wchar_p(username),
                c_wchar_p(password),
                self.callbacks['state'],           # StateCallback
                self.callbacks['order_history'],   # HistoryCallback (deprecated mas ainda necessário)
                self.callbacks['order_change'],    # OrderChangeCallback (deprecated mas ainda necessário)
                self.callbacks['account'],         # AccountCallback
                self.callbacks['trade'],           # NewTradeCallback
                None,                             # NewDailyCallback
                self.callbacks['price_book'],      # PriceBookCallback
                self.callbacks['offer_book'],      # OfferBookCallback
                self.callbacks['history'],         # HistoryTradeCallback
                self.callbacks['progress'],        # ProgressCallback
                None                              # TinyBookCallback
            )
            
            if init_result == NResult.NL_OK:
                self.logger.info("DLL v4.0.0.30 inicializada com sucesso")
                
                # Configurar callbacks V2 após inicialização
                self._setup_v2_callbacks()
                
                # Aguardar conexões
                if self._wait_for_connections(timeout=30):
                    self.connected = True
                    self.logger.info("[OK] Conexão v4.0.0.30 estabelecida com sucesso!")
                    return True
                else:
                    self.logger.error("[ERRO] Falha ao estabelecer conexões necessárias")
                    return False
                    
            else:
                self.logger.error(f"Falha na inicialização da DLL: código {init_result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro na inicialização: {e}", exc_info=True)
            return False
    
    def _load_dll(self) -> Optional[WinDLL]:
        """Carrega a DLL do Profit usando WinDLL (stdcall)"""
        try:
            if not os.path.exists(self.dll_path):
                self.logger.error(f"DLL não encontrada em: {self.dll_path}")
                return None
                
            # IMPORTANTE: Usar WinDLL para convenção stdcall
            dll = WinDLL(self.dll_path)
            self.logger.info("[OK] DLL carregada com WinDLL (stdcall)")
            
            # Configurar argtypes (não definir globalmente)
            dll.argtypes = None
            
            return dll
            
        except Exception as e:
            self.logger.error(f"Erro carregando DLL: {e}")
            return None
    
    def _setup_callbacks_v4(self):
        """
        Configura callbacks básicos com assinaturas v4.0.0.30
        """
        
        # State callback - assinatura correta
        @TStateCallback
        def state_callback(nConnStateType, nResult):
            try:
                self.logger.info(f"State callback v4: Type={nConnStateType}, Result={nResult}")
                
                # Atualizar estados baseado no tipo
                if nConnStateType == self.CONNECTION_STATE_LOGIN:
                    self.login_state = nResult
                    if nResult == self.LOGIN_CONNECTED:
                        self.logger.info("[OK] LOGIN conectado")
                    else:
                        self.logger.warning(f"[ERRO] LOGIN erro: {nResult}")
                        
                elif nConnStateType == self.CONNECTION_STATE_ROTEAMENTO:
                    self.routing_state = nResult
                    self.routing_connected = (nResult == self.ROTEAMENTO_BROKER_CONNECTED)
                    if self.routing_connected:
                        self.logger.info("[OK] ROTEAMENTO conectado")
                    else:
                        self.logger.warning(f"[WARN] ROTEAMENTO: {nResult}")
                        
                elif nConnStateType == self.CONNECTION_STATE_MARKET_DATA:
                    self.market_state = nResult
                    self.market_connected = (nResult == self.MARKET_CONNECTED)
                    if self.market_connected:
                        self.logger.info("[OK] MARKET DATA conectado")
                    else:
                        self.logger.warning(f"[WARN] MARKET DATA: {nResult}")
                
                # Notificar callbacks registrados
                for callback in self.state_callbacks:
                    callback(nConnStateType, nResult)
                    
                return 0
            except Exception as e:
                self.logger.error(f"Erro no state callback: {e}")
                return 0
        
        # Trade callback (tempo real) - assinatura v4.0.0.30
        @TNewTradeCallback
        def trade_callback(asset_id, date, trade_number, price, vol, qtd, 
                          buy_agent, sell_agent, trade_type, b_edit):
            try:
                timestamp = datetime.strptime(str(date), '%d/%m/%Y %H:%M:%S.%f')
                
                trade_data = {
                    'timestamp': timestamp,
                    'ticker': asset_id.pwcTicker,
                    'price': float(price),
                    'volume': float(vol),
                    'quantity': int(qtd),
                    'trade_type': int(trade_type),
                    'trade_number': int(trade_number)
                }
                
                # Notificar callbacks registrados
                for callback in self.trade_callbacks:
                    callback(trade_data)
                    
                return 0
            except Exception as e:
                self.logger.error(f"Erro no trade callback: {e}")
                return 0
        
        # History trade callback - assinatura v4.0.0.30
        @THistoryTradeCallback
        def history_callback(asset_id, date, trade_number, price, vol, qtd,
                           buy_agent, sell_agent, trade_type):
            try:
                # Este callback recebe os dados históricos!
                ticker_name = asset_id.pwcTicker if asset_id and asset_id.pwcTicker else 'N/A'
                
                # Fazer parsing correto do timestamp
                try:
                    date_str = str(date) if date else ""
                    
                    if date_str:
                        # Formatos possíveis da ProfitDLL
                        for fmt in ['%d/%m/%Y %H:%M:%S.%f', '%d/%m/%Y %H:%M:%S', 
                                   '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']:
                            try:
                                timestamp = datetime.strptime(date_str, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            timestamp = datetime.now()
                    else:
                        timestamp = datetime.now()
                except Exception as e:
                    timestamp = datetime.now()
                
                # Criar dicionário com dados do trade
                trade_data = {
                    'ticker': ticker_name,
                    'date': date_str,
                    'timestamp': timestamp,
                    'trade_number': trade_number,
                    'price': price,
                    'volume': vol,
                    'quantity': qtd,
                    'buy_agent': buy_agent,
                    'sell_agent': sell_agent,
                    'trade_type': trade_type
                }
                
                # Chamar callback registrado se existir
                if hasattr(self, 'history_trade_callback') and self.history_trade_callback:
                    self.history_trade_callback(trade_data)
                
                # LOG OTIMIZADO
                if self._historical_data_count == 0:
                    self.logger.info(f"[TICK] PRIMEIRO DADO HISTÓRICO: {ticker_name}")
                elif self._historical_data_count in [100, 500, 1000, 5000, 10000, 50000, 100000]:
                    self.logger.info(f"[DATA] {self._historical_data_count} dados recebidos...")
                
                # Incrementar contador
                self._historical_data_count += 1
                self._last_historical_timestamp = timestamp
                
                # Notificar callbacks registrados
                for callback in self.trade_callbacks:
                    callback({
                        'timestamp': timestamp,
                        'ticker': ticker_name,
                        'price': float(price),
                        'volume': float(vol),
                        'quantity': int(qtd),
                        'trade_type': int(trade_type),
                        'trade_number': int(trade_number),
                        'is_historical': True
                    })
                
                return 0
            except Exception as e:
                self.logger.error(f"Erro no history callback: {e}")
                return 0
        
        # Progress callback - assinatura v4.0.0.30
        @TProgressCallback
        def progress_callback(asset_id, progress):
            try:
                ticker_name = asset_id.pwcTicker if asset_id and asset_id.pwcTicker else 'N/A'
                if progress % 10 == 0 or progress >= 95:
                    self.logger.info(f"[DATA] Progresso {ticker_name}: {progress}%")
                
                if progress >= 100:
                    self.logger.info(f"[OK] Download de {ticker_name} completo!")
                    
                return 0
            except Exception as e:
                self.logger.error(f"Erro no progress callback: {e}")
                return 0
        
        # Book callbacks - assinaturas v4.0.0.30
        @TOfferBookCallback
        def offer_book_callback(asset_id, broker_id, position, side, volume, 
                               quantity, offer_id, price, has_price, has_quantity,
                               has_date, has_offer_id, is_edit, date, book_array, reserved):
            """Callback para book de ofertas em tempo real"""
            try:
                if self._offer_book_callback:
                    book_data = {
                        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S.%f')[:-3],
                        'ticker': asset_id.pwcTicker if hasattr(asset_id, 'pwcTicker') else '',
                        'broker_id': broker_id,
                        'position': position,
                        'side': side,  # 0=Buy, 1=Sell
                        'volume': volume,
                        'quantity': quantity,
                        'offer_id': offer_id,
                        'price': price,
                        'has_price': bool(has_price),
                        'has_quantity': bool(has_quantity),
                        'has_date': bool(has_date),
                        'has_offer_id': bool(has_offer_id),
                        'is_edit': bool(is_edit),
                        'date': date if has_date else ''
                    }
                    self._offer_book_callback(book_data)
                return 0
            except Exception as e:
                self.logger.error(f"Erro no callback de offer book: {e}")
                return 0
        
        @TPriceBookCallback
        def price_book_callback(asset_id, position, side, order_count, quantity,
                               display_quantity, price, book_array, reserved):
            """Callback para book de preços agregado em tempo real"""
            try:
                if self._price_book_callback:
                    book_data = {
                        'timestamp': datetime.now().strftime('%d/%m/%Y %H:%M:%S.%f')[:-3],
                        'ticker': asset_id.pwcTicker if hasattr(asset_id, 'pwcTicker') else '',
                        'position': position,
                        'side': side,  # 0=Buy, 1=Sell
                        'order_count': order_count,
                        'quantity': quantity,
                        'display_quantity': display_quantity,
                        'price': price
                    }
                    self._price_book_callback(book_data)
                return 0
            except Exception as e:
                self.logger.error(f"Erro no callback de price book: {e}")
                return 0
        
        # Order callbacks (versão antiga para compatibilidade na inicialização)
        # Serão substituídos pelos V2 após inicialização
        @WINFUNCTYPE(None, TAssetID, c_int, c_int, c_int, c_int, c_int, c_double,
                    c_double, c_double, c_longlong, c_wchar_p, c_wchar_p, c_wchar_p,
                    c_wchar_p, c_wchar_p, c_wchar_p, c_wchar_p)
        def order_change_callback(asset_id, corretora, qtd, traded_qtd, leaves_qtd,
                                side, price, stop_price, avg_price, profit_id,
                                tipo_ordem, conta, titular, cl_ord_id, status,
                                date, text_message):
            # Callback temporário para compatibilidade
            pass

        @WINFUNCTYPE(None, TAssetID, c_int, c_int, c_int, c_int, c_int, c_double,
                    c_double, c_double, c_longlong, c_wchar_p, c_wchar_p, c_wchar_p,
                    c_wchar_p, c_wchar_p, c_wchar_p)
        def order_history_callback(asset_id, corretora, qtd, traded_qtd, leaves_qtd,
                                side, price, stop_price, avg_price, profit_id,
                                tipo_ordem, conta, titular, cl_ord_id, status, date):
            # Callback temporário para compatibilidade
            pass
        
        @TAccountCallback
        def account_callback(broker_id, account_id, account_name, titular):
            # SAFE VERSION: Account callback desabilitado
            return 0
        
        # Armazenar callbacks
        self.callbacks = {
            'state': state_callback,
            'trade': trade_callback,
            'history': history_callback,
            'progress': progress_callback,
            'offer_book': offer_book_callback,
            'price_book': price_book_callback,
            'order_change': order_change_callback,
            'order_history': order_history_callback,
            'account': account_callback
        }
        
        self.logger.info("Callbacks v4.0.0.30 configurados")
    
    def _setup_v2_callbacks(self):
        """
        Configura callbacks V2 após inicialização da DLL
        """
        try:
            # SetOrderCallback - substitui OrderChangeCallback para v4.0.0.30
            @TConnectorOrderCallback
            def order_callback_v2(order_ptr):
                try:
                    if order_ptr:
                        order = order_ptr.contents
                        
                        order_data = {
                            'version': order.Version,
                            'broker_id': order.AccountID.BrokerID,
                            'account_id': order.AccountID.AccountID,
                            'profit_id': order.ProfitID,
                            'client_order_id': str(order.ClientOrderID),
                            'ticker': str(order.AssetID.pwcTicker),
                            'side': order.Side,
                            'order_type': order.OrderType,
                            'status': order.Status,
                            'quantity': order.Quantity,
                            'executed_quantity': order.ExecutedQuantity,
                            'remaining_quantity': order.RemainingQuantity,
                            'price': order.Price,
                            'stop_price': order.StopPrice,
                            'average_price': order.AveragePrice,
                            'status_message': str(order.StatusMessage) if order.StatusMessage else ''
                        }
                        
                        self.logger.debug(f"Order callback v2: {order_data}")
                        
                        # Notificar callbacks registrados
                        for callback in self.order_callbacks:
                            callback(order_data)
                    
                    return 0  # IMPORTANTE: Retornar 0 para sucesso
                            
                except Exception as e:
                    self.logger.error(f"Erro no order callback v2: {e}")
                    return -1  # Retornar -1 para erro
            
            # SetOrderHistoryCallback - para histórico de ordens
            @TConnectorAccountCallback
            def order_history_callback_v2(account_id_ptr):
                try:
                    if account_id_ptr:
                        account_id = account_id_ptr.contents
                        self.logger.info(f"Order history loaded for account: "
                                       f"Broker={account_id.BrokerID}, "
                                       f"Account={account_id.AccountID}")
                except Exception as e:
                    self.logger.error(f"Erro no order history callback v2: {e}")
                # IMPORTANTE: Sempre retornar 0 para sucesso
                return 0
            
            # Configurar callbacks V2 na DLL
            if hasattr(self.dll, 'SetOrderCallback'):
                result = self.dll.SetOrderCallback(order_callback_v2)
                if result == NResult.NL_OK:
                    self.logger.info("[OK] SetOrderCallback configurado com sucesso")
                else:
                    self.logger.warning(f"[WARN] SetOrderCallback retornou: {result}")
            
            if hasattr(self.dll, 'SetOrderHistoryCallback'):
                result = self.dll.SetOrderHistoryCallback(order_history_callback_v2)
                if result == NResult.NL_OK:
                    self.logger.info("[OK] SetOrderHistoryCallback configurado com sucesso")
                else:
                    self.logger.warning(f"[WARN] SetOrderHistoryCallback retornou: {result}")
            
            # SetTradeCallbackV2 se disponível
            if hasattr(self.dll, 'SetTradeCallbackV2'):
                @TTradeCallbackV2
                def trade_callback_v2(trade_ptr):
                    try:
                        # Log para debug
                        self.logger.debug("Trade V2 callback recebido")
                        
                        # Por enquanto apenas log, pois precisamos descobrir a estrutura correta
                        # ou usar TranslateTrade se disponível
                        if trade_ptr:
                            self.logger.debug("Trade V2 pointer recebido")
                        
                        return 0  # Success
                    except Exception as e:
                        self.logger.error(f"Erro no trade callback v2: {e}")
                        return -1
                
                result = self.dll.SetTradeCallbackV2(trade_callback_v2)
                if result == NResult.NL_OK:
                    self.logger.info("[OK] SetTradeCallbackV2 configurado com TTradeCallbackV2")
            
            # SetOfferBookCallbackV2 - versão mais recente do callback
            if hasattr(self.dll, 'SetOfferBookCallbackV2'):
                @TOfferBookCallbackV2
                def offer_book_callback_v2(asset_id, action, position, side, qtd, agent,
                                          offer_id, price, has_price, has_qtd, has_date,
                                          has_offer_id, has_agent, date_ptr, array_sell, array_buy):
                    """Callback V2 para book de ofertas com melhor suporte"""
                    try:
                        ticker_name = asset_id.pwcTicker if asset_id and hasattr(asset_id, 'pwcTicker') else 'N/A'
                        
                        # Processar dados do book
                        book_data = {
                            'timestamp': datetime.now(),
                            'ticker': ticker_name,
                            'action': action,  # 0=Adicionar, 1=Atualizar, 2=Remover
                            'position': position,
                            'side': side,  # 0=Buy, 1=Sell
                            'quantity': qtd,
                            'agent': agent,
                            'offer_id': offer_id,
                            'price': price,
                            'has_price': bool(has_price),
                            'has_quantity': bool(has_qtd)
                        }
                        
                        # Notificar callback registrado
                        if self._offer_book_callback:
                            self._offer_book_callback(book_data)
                        
                        # Notificar book_update_callback se existir
                        if hasattr(self, 'book_update_callback') and self.book_update_callback:
                            self.book_update_callback(book_data)
                        
                        # Log apenas primeiras mensagens para debug
                        if not hasattr(self, '_book_count'):
                            self._book_count = 0
                        self._book_count += 1
                        
                        if self._book_count <= 5:
                            self.logger.info(f"[BOOK V2] {ticker_name} - Side: {side}, Price: {price}, Qty: {qtd}")
                        elif self._book_count == 100:
                            self.logger.info(f"[BOOK V2] Recebendo dados de book... ({self._book_count} mensagens)")
                        
                        return 0
                    except Exception as e:
                        self.logger.error(f"Erro no offer book callback v2: {e}")
                        return 0
                
                result = self.dll.SetOfferBookCallbackV2(offer_book_callback_v2)
                if result == NResult.NL_OK:
                    self.logger.info("[OK] SetOfferBookCallbackV2 configurado")
                else:
                    self.logger.warning(f"[WARN] SetOfferBookCallbackV2 retornou: {result}")
            
            # SetPriceBookCallbackV2 - versão mais recente
            if hasattr(self.dll, 'SetPriceBookCallbackV2'):
                @TPriceBookCallbackV2
                def price_book_callback_v2(asset_id, action, position, side, order_count,
                                          qtd, display_qtd, price, array_sell, array_buy):
                    """Callback V2 para book de preços agregado"""
                    try:
                        ticker_name = asset_id.pwcTicker if asset_id and hasattr(asset_id, 'pwcTicker') else 'N/A'
                        
                        book_data = {
                            'timestamp': datetime.now(),
                            'ticker': ticker_name,
                            'action': action,
                            'position': position,
                            'side': side,
                            'order_count': order_count,
                            'quantity': qtd,
                            'display_quantity': display_qtd,
                            'price': price
                        }
                        
                        if self._price_book_callback:
                            self._price_book_callback(book_data)
                        
                        return 0
                    except Exception as e:
                        self.logger.error(f"Erro no price book callback v2: {e}")
                        return 0
                
                result = self.dll.SetPriceBookCallbackV2(price_book_callback_v2)
                if result == NResult.NL_OK:
                    self.logger.info("[OK] SetPriceBookCallbackV2 configurado")
            
            # IMPORTANTE: Armazenar V2 callbacks para evitar garbage collection
            self.v2_callbacks = {
                'order': order_callback_v2,
                'order_history': order_history_callback_v2,
                'trade': trade_callback_v2,
                'offer_book': offer_book_callback_v2,
                'price_book': price_book_callback_v2
            }
            
            self.logger.info("Callbacks V2 configurados e armazenados com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro configurando callbacks V2: {e}")
    
    def _wait_for_connections(self, timeout: int = 30) -> bool:
        """Aguarda conexões serem estabelecidas"""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            # Aguardar especificamente market data para dados históricos
            if self.market_connected and self.market_state == self.MARKET_CONNECTED:
                self.logger.info("[OK] Market Data conectado - dados históricos disponíveis")
                return True
                
            # Log periódico mais detalhado
            elapsed = time.time() - start_time
            if int(elapsed) % 3 == 0 and int(elapsed) > 0:
                self.logger.info(f"Aguardando market data ({int(elapsed)}/{timeout}s)...")
                self._log_connection_states()
                
                # Verificar se pelo menos login funcionou
                if self.login_state != self.LOGIN_CONNECTED:
                    self.logger.warning("Login ainda não conectado - pode impedir market data")
                
            time.sleep(1)
            
        # Se chegou aqui, timeout ocorreu
        self.logger.error("TIMEOUT: Market data não conectou no tempo esperado")
        self._log_connection_states()
        return False
    
    def _log_connection_states(self):
        """Log dos estados de conexão com interpretação detalhada"""
        self.logger.info("=== Estados de Conexão v4.0.0.30 ===")
        self.logger.info(f"Login: {self.login_state} {'[OK]' if self.login_state == self.LOGIN_CONNECTED else '[ERRO]'}")
        self.logger.info(f"Roteamento: {self.routing_state} (conectado: {self.routing_connected}) {'[OK]' if self.routing_connected else '[WARN]'}")
        self.logger.info(f"Market Data: {self.market_state} (conectado: {self.market_connected}) {'[OK]' if self.market_connected else '[WARN]'}")
        self.logger.info(f"Geral: {self.connected}")
        self.logger.info("===================================")
    
    def register_trade_callback(self, callback: Callable):
        """Registra callback para trades em tempo real"""
        self.trade_callbacks.append(callback)
        
    def register_state_callback(self, callback: Callable):
        """Registra callback para mudanças de estado"""
        self.state_callbacks.append(callback)
        
    def register_order_callback(self, callback: Callable):
        """Registra callback para atualizações de ordens"""
        self.order_callbacks.append(callback)
        
    def register_account_callback(self, callback: Callable):
        """Registra callback para informações da conta"""
        self.account_callbacks.append(callback)
    
    def register_history_trade_callback(self, callback):
        """Registra callback para dados históricos"""
        self.history_trade_callback = callback
        self.logger.info("History trade callback registrado")
    
    def get_history_trades(self, ticker: str, exchange: str, date_start: str, date_end: str) -> bool:
        """
        Solicita dados históricos de trades
        
        Args:
            ticker: Símbolo (ex: WDOQ25)
            exchange: Bolsa (ex: BMF)
            date_start: Data inicial (formato: dd/mm/yyyy)
            date_end: Data final (formato: dd/mm/yyyy)
            
        Returns:
            True se solicitação foi enviada com sucesso
        """
        try:
            if not self.dll:
                self.logger.error("DLL não carregada")
                return False
            
            # Configurar função GetHistoryTrades se existir
            if hasattr(self.dll, 'GetHistoryTrades'):
                self.dll.GetHistoryTrades.argtypes = [c_wchar_p, c_wchar_p, 
                                                      c_wchar_p, c_wchar_p]
                self.dll.GetHistoryTrades.restype = c_int
                
                result = self.dll.GetHistoryTrades(ticker, exchange, date_start, date_end)
                
                if result == 0:
                    self.logger.info(f"Solicitação de histórico enviada: {ticker} de {date_start} até {date_end}")
                    return True
                else:
                    self.logger.error(f"Erro ao solicitar histórico: código {result}")
                    return False
            else:
                self.logger.warning("GetHistoryTrades não disponível nesta versão da DLL")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro em get_history_trades: {e}")
            return False
    
    def subscribe_ticker(self, ticker: str, exchange: str = "F") -> bool:
        """Subscreve para receber dados de um ticker"""
        try:
            if self.dll is None:
                self.logger.error("DLL não está carregada. Inicialize antes de subscrever ticker.")
                return False
            if not hasattr(self.dll, "SubscribeTicker"):
                self.logger.error("Método SubscribeTicker não encontrado na DLL.")
                return False
            result = self.dll.SubscribeTicker(c_wchar_p(ticker), c_wchar_p(exchange))
            if result == NResult.NL_OK:
                self.logger.info(f"Subscrito para {ticker} em {exchange}")
                return True
            else:
                self.logger.error(f"Falha ao subscrever {ticker}: código {result}")
                return False
        except Exception as e:
            self.logger.error(f"Erro ao subscrever ticker: {e}")
            return False

    def _get_current_wdo_contract(self, reference_date: Optional[datetime] = None) -> str:
        """
        Detecta o contrato WDO correto baseado na data atual e regras de virada
        """
        if reference_date is None:
            reference_date = datetime.now()
        
        # Códigos de mês para futuros
        month_codes = {
            1: 'F',   # Janeiro
            2: 'G',   # Fevereiro  
            3: 'H',   # Março
            4: 'J',   # Abril
            5: 'K',   # Maio
            6: 'M',   # Junho
            7: 'N',   # Julho
            8: 'Q',   # Agosto
            9: 'U',   # Setembro
            10: 'V',  # Outubro
            11: 'X',  # Novembro
            12: 'Z'   # Dezembro
        }
        
        current_month = reference_date.month
        current_year = str(reference_date.year)[-2:]  # Últimos 2 dígitos
        current_day = reference_date.day
        
        # REGRA WDO: SEMPRE usar contrato do PRÓXIMO mês
        # Exemplo: TODO mês de julho (01/07 a 31/07) usa WDOQ25 (agosto)
        
        # Calcular próximo mês
        if current_month == 12:
            next_month = 1
            next_year = str(reference_date.year + 1)[-2:]
        else:
            next_month = current_month + 1
            next_year = current_year
            
        contract_month_code = month_codes[next_month]
        contract_year = next_year
        
        self.logger.info(f"[*] Mês {current_month} usa contrato do mês {next_month} (sempre próximo mês)")
        
        contract = f"WDO{contract_month_code}{contract_year}"
        self.logger.info(f"[DART] Contrato WDO detectado: {contract}")
        self.logger.info(f"[DATA] Data referência: {reference_date.strftime('%d/%m/%Y')}")
        
        return contract
    
    def _get_smart_ticker_variations(self, ticker: str) -> List[str]:
        """
        Gera variações inteligentes do ticker considerando viradas de mês
        """
        variations = []
        
        if ticker.startswith("WDO"):
            self.logger.info(f"[DEBUG] Detectado ticker WDO - aplicando lógica de contratos futuros")
            
            # 1. Contrato atual detectado automaticamente (MAIS PROVÁVEL)
            current_contract = self._get_current_wdo_contract()
            variations.append(current_contract)
            
            # 2. Ticker original fornecido
            if ticker != current_contract:
                variations.append(ticker)
            
            # 3. WDO genérico (funciona em algumas APIs)
            if "WDO" not in variations:
                variations.append("WDO")
                
        else:
            # Para outros tickers, apenas usar o original
            variations.append(ticker)
        
        # Remover duplicatas mantendo ordem
        unique_variations = []
        for var in variations:
            if var not in unique_variations:
                unique_variations.append(var)
        
        self.logger.info(f"[BOARD] Variações de ticker a serem testadas: {unique_variations}")
        return unique_variations
    
    def request_historical_data(self, ticker: str, start_date: datetime, 
                               end_date: datetime) -> int:
        """Solicita dados históricos - compatível com v4.0.0.30"""
        try:
            if self.dll is None:
                self.logger.error("DLL não está carregada. Inicialize antes de solicitar dados históricos.")
                return -1

            # Dados históricos só precisam de login, não de market data
            if self.login_state != self.LOGIN_CONNECTED:
                self.logger.error("Login não conectado - dados históricos não disponíveis")
                self._log_connection_states()
                return -1
            
            self.logger.info("[OK] Login conectado - prosseguindo com dados históricos")
            
            # VALIDAÇÃO: LIMITE OTIMIZADO DE 3 DIAS
            days_requested = (end_date - start_date).days
            if days_requested > 3:
                self.logger.warning(f"Período solicitado muito longo ({days_requested} dias). API otimizada para máximo de 3 dias.")
                start_date = end_date - timedelta(days=3)
            
            # RESET: Limpar contadores antes de nova requisição
            self._historical_data_count = 0
            self._last_historical_timestamp = None
            
            # Usar sistema inteligente de detecção de ticker
            tickers_to_try = self._get_smart_ticker_variations(ticker)

            # Formatos de data para WDO na B3
            start_str = start_date.strftime('%d/%m/%Y %H:%M:%S')
            end_str = end_date.strftime('%d/%m/%Y %H:%M:%S')
            
            self.logger.info(f"Período: {start_str} até {end_str}")
            
            # Usar GetHistoryTrades com parâmetros corretos
            if hasattr(self.dll, "GetHistoryTrades"):
                
                for test_ticker in tickers_to_try:
                    self.logger.info(f"Testando ticker: {test_ticker}")
                    
                    try:
                        # Usar bolsa/exchange correta para WDO
                        exchange = "F" if test_ticker.startswith("WDO") else ""
                        
                        self.logger.info(f"Tentando {test_ticker} na bolsa '{exchange}'")
                        
                        result = self.dll.GetHistoryTrades(
                            c_wchar_p(test_ticker),
                            c_wchar_p(exchange),
                            c_wchar_p(start_str),
                            c_wchar_p(end_str)
                        )
                        
                        self.logger.info(f"Resultado GetHistoryTrades para {test_ticker}: {result}")
                        
                        # Interpretar códigos de retorno
                        if result >= 0:
                            self.logger.info(f"[OK] Solicitação aceita para ticker {test_ticker}!")
                            return result
                        elif result == NResult.NL_INVALID_ARGS:
                            self.logger.warning(f"Erro de parâmetros para {test_ticker}")
                            
                    except Exception as e:
                        self.logger.error(f"Erro ao testar ticker {test_ticker}: {e}")
            
            self.logger.error("Falha ao solicitar dados históricos")
            return -1
            
        except Exception as e:
            self.logger.error(f"Erro solicitando dados históricos: {e}")
            self.logger.error(f"Stack trace: {traceback.format_exc()}")
            return -1
    
    def wait_for_historical_data(self, timeout_seconds: int = 60) -> bool:
        """
        Aguarda os dados históricos chegarem via callback
        """
        try:
            start_time = time.time()
            last_count = self._historical_data_count
            stable_count = 0
            no_data_count = 0
            last_log_time = 0
            
            self.logger.info(f"[HOUR] Aguardando dados históricos (timeout: {timeout_seconds}s)...")
            self.logger.info(f"[DATA] Contador inicial: {self._historical_data_count}")
            
            while (time.time() - start_time) < timeout_seconds:
                current_count = self._historical_data_count
                elapsed = time.time() - start_time
                
                # Se há dados chegando
                if current_count > last_count:
                    last_count = current_count
                    stable_count = 0
                    no_data_count = 0
                    
                    # Log apenas a cada 5 segundos para evitar spam
                    if elapsed - last_log_time >= 5:
                        rate = (current_count / elapsed) if elapsed > 0 else 0
                        self.logger.info(f"[TICK] {current_count} dados recebidos... ({elapsed:.1f}s, {rate:.0f} trades/s)")
                        last_log_time = elapsed
                        
                else:
                    # Dados estáveis, contar tempo
                    stable_count += 1
                    no_data_count += 1
                    
                    # Se estável por 5 segundos e temos dados
                    if stable_count >= 10 and current_count > 0:  # 10 * 0.5s = 5s
                        if self._is_historical_data_complete():
                            self.logger.info(f"[OK] Dados históricos carregados: {current_count} registros em {elapsed:.1f}s")
                            self._notify_historical_data_complete()
                            return True
                        else:
                            # Em dev mode, ser mais tolerante
                            if self.dev_mode and stable_count >= 20:
                                self.logger.warning(f"[WARN] DEV MODE: Forçando conclusão após 10s de estabilidade com {current_count} registros")
                                self._notify_historical_data_complete()
                                return True
                    
                    # Se passou 90 segundos sem dados, desistir
                    if no_data_count >= 180 and current_count == 0:  # 180 * 0.5s = 90s
                        self.logger.warning(f"[WARN] 90 segundos sem dados - assumindo que não há dados disponíveis")
                        return False
                    
                    # Log periódico menos frequente
                    if int(elapsed) % 10 == 0 and int(elapsed) > 0 and elapsed - last_log_time >= 10:
                        self.logger.info(f"[HOUR] Aguardando... {current_count} dados recebidos em {elapsed:.0f}s")
                        last_log_time = elapsed
                
                time.sleep(0.5)
            
            # Timeout atingido
            final_count = self._historical_data_count
            elapsed_final = time.time() - start_time
            
            if final_count > 0:
                self.logger.warning(f"[WARN] Timeout após {elapsed_final:.1f}s, mas {final_count} dados foram recebidos")
                
                if self._is_historical_data_complete():
                    self.logger.info("[OK] Timeout mas dados históricos estão completos")
                    self._notify_historical_data_complete()
                    return True
                else:
                    self.logger.error("[ERRO] Timeout e dados históricos incompletos")
                    return False
            else:
                self.logger.error(f"[ERRO] Timeout após {elapsed_final:.1f}s sem nenhum dado recebido")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro aguardando dados históricos: {e}")
            return False
    
    def _is_historical_data_complete(self) -> bool:
        """
        Verifica se os dados históricos chegaram até próximo da hora atual
        """
        try:
            if self._last_historical_timestamp is None:
                self.logger.warning("Nenhum timestamp de dados históricos registrado ainda")
                return False
                
            current_time = datetime.now()
            
            # Em modo dev, considerar dados completos se chegaram até o fechamento do mercado
            if self.dev_mode:
                # Verificar se é fim de semana ou fora do horário de pregão
                weekday = current_time.weekday()
                hour = current_time.hour
                
                # Se é fim de semana (sábado=5, domingo=6)
                if weekday >= 5:
                    self.logger.info("[DEV] DEV MODE: Fim de semana detectado")
                    # Considerar completo se dados chegaram até sexta-feira
                    friday_close = self._last_historical_timestamp.replace(hour=18, minute=0, second=0)
                    if self._last_historical_timestamp >= friday_close:
                        self.logger.info("[OK] DEV MODE: Dados históricos completos até fechamento de sexta")
                        return True
                    else:
                        time_to_close = (friday_close - self._last_historical_timestamp).total_seconds() / 60
                        self.logger.info(f"[HOUR] DEV MODE: Dados ainda {time_to_close:.1f} min antes do fechamento")
                        return time_to_close <= 30  # Tolerar 30 min antes do fechamento
                
                # Se é dia útil mas fora do horário de pregão
                elif hour < 9 or hour >= 18:
                    self.logger.info(f"[DEV] DEV MODE: Fora do horário de pregão ({hour}h)")
                    # Considerar completo se dados chegaram até o fechamento
                    if hour < 9:  # Antes da abertura
                        yesterday_close = (current_time - timedelta(days=1)).replace(hour=18, minute=0, second=0)
                        if self._last_historical_timestamp >= yesterday_close:
                            self.logger.info("[OK] DEV MODE: Dados completos até fechamento do dia anterior")
                            return True
                    else:  # Depois do fechamento
                        today_close = current_time.replace(hour=18, minute=0, second=0)
                        if self._last_historical_timestamp >= today_close:
                            self.logger.info("[OK] DEV MODE: Dados completos até fechamento de hoje")
                            return True
                        else:
                            time_to_close = (today_close - self._last_historical_timestamp).total_seconds() / 60
                            self.logger.info(f"[HOUR] DEV MODE: Dados ainda {time_to_close:.1f} min antes do fechamento")
                            return time_to_close <= 30
                
                # Durante o pregão em dev mode
                else:
                    time_diff = (current_time - self._last_historical_timestamp).total_seconds() / 60
                    self.logger.info(f"[DATA] DEV MODE: Último dado: {self._last_historical_timestamp.strftime('%H:%M')} | Diff: {time_diff:.1f} min")
                    # Em dev mode, tolerar até 30 minutos de atraso
                    if time_diff <= 30:
                        self.logger.info("[OK] DEV MODE: Dados históricos considerados completos (tolerância 30 min)")
                        return True
                    else:
                        self.logger.info(f"[HOUR] DEV MODE: Dados ainda defasados em {time_diff:.1f} minutos")
                        return False
            
            # Modo normal (produção)
            else:
                # Calcular diferença em minutos
                time_diff = (current_time - self._last_historical_timestamp).total_seconds() / 60
                
                self.logger.info(f"[DATA] Último dado histórico: {self._last_historical_timestamp.strftime('%H:%M')} | "
                               f"Atual: {current_time.strftime('%H:%M')} | Diff: {time_diff:.1f} min")
                
                # Se diferença é menor que 10 minutos, considerar completo
                if time_diff <= 10:
                    self.logger.info("[OK] Dados históricos chegaram até próximo da hora atual")
                    return True
                else:
                    self.logger.info(f"[HOUR] Dados ainda defasados em {time_diff:.1f} minutos")
                    return False
                
        except Exception as e:
            self.logger.error(f"Erro verificando completude dos dados históricos: {e}")
            return True  # Em caso de erro, assumir completo para não travar
    
    def _notify_historical_data_complete(self):
        """
        Notifica que o carregamento de dados históricos foi completado
        """
        try:
            self.logger.info("[*] Carregamento de dados históricos FINALIZADO!")
            
            # Notificar todos os callbacks registrados sobre conclusão
            for callback in self.trade_callbacks:
                # Enviar sinal especial de conclusão
                try:
                    callback({
                        'event_type': 'historical_data_complete',
                        'total_records': self._historical_data_count,
                        'timestamp': datetime.now()
                    })
                except Exception as e:
                    self.logger.debug(f"Callback não suporta evento de conclusão: {e}")
                    
        except Exception as e:
            self.logger.error(f"Erro notificando fim dos dados históricos: {e}")
    
    def unsubscribe_ticker(self, ticker: str) -> bool:
        """
        Cancela subscrição de um ticker
        """
        try:
            if not self.dll:
                return False
                
            exchange = "F" if ticker.startswith("WDO") else ""
            result = self.dll.UnsubscribeTicker(c_wchar_p(ticker), c_wchar_p(exchange))
            
            if result == NResult.NL_OK:
                self.logger.info(f"Subscrição cancelada para {ticker}")
                return True
            else:
                self.logger.error(f"Erro ao cancelar subscrição: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro ao cancelar subscrição: {e}")
            return False
        
    def disconnect(self):
        """Desconecta e limpa recursos"""
        try:
            if self.dll:
                result = self.dll.DLLFinalize()
                if result == NResult.NL_OK:
                    self.logger.info("DLL finalizada com sucesso")
                else:
                    self.logger.warning(f"DLL finalizada com código: {result}")
            self.connected = False
        except Exception as e:
            self.logger.error(f"Erro ao desconectar: {e}")

    def get_account_info(self) -> bool:
        """
        Solicita informações das contas disponíveis
        """
        try:
            if not self.dll or not self.connected:
                self.logger.error("DLL não está conectada")
                return False
                
            result = self.dll.GetAccount()
            if result == NResult.NL_OK:
                self.logger.info("Solicitação de contas enviada")
                return True
            else:
                self.logger.error(f"Erro ao solicitar contas: código {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro ao obter informações de conta: {e}")
            return False
    
    def register_offer_book_callback(self, callback):
        """
        Registra callback para receber dados de book de ofertas em tempo real
        
        Args:
            callback: Função que recebe dict com dados do book
        """
        self._offer_book_callback = callback
        self.logger.info("Callback de offer book registrado")
    
    def register_price_book_callback(self, callback):
        """
        Registra callback para receber dados de book de preços agregado em tempo real
        
        Args:
            callback: Função que recebe dict com dados do book
        """
        self._price_book_callback = callback
        self.logger.info("Callback de price book registrado")
    
    def subscribe_offer_book(self, ticker: str) -> bool:
        """
        Subscreve ao book de ofertas de um ticker
        
        Args:
            ticker: Ticker do ativo
            
        Returns:
            bool: True se subscrição bem-sucedida
        """
        try:
            if not self.dll or not self.connected:
                self.logger.error("DLL não está conectada")
                return False
            
            # Verificar se market data está conectado
            if self.market_state != self.MARKET_CONNECTED:
                self.logger.error("Market data não conectado - necessário para book")
                return False
            
            # SubscribeOfferBook(pwcTicker, pwcBolsa) - apenas 2 parâmetros conforme manual
            result = self.dll.SubscribeOfferBook(
                c_wchar_p(ticker),  # Ticker
                c_wchar_p("F")      # Bolsa (F=Futuros)
            )
            
            if result == NResult.NL_OK:
                self.logger.info(f"[OK] Subscrito ao offer book de {ticker}")
                return True
            else:
                self.logger.error(f"Erro ao subscrever offer book: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro ao subscrever offer book: {e}")
            return False
    
    def subscribe_price_book(self, ticker: str) -> bool:
        """
        Subscreve ao book de preços agregado de um ticker
        
        Args:
            ticker: Ticker do ativo
            
        Returns:
            bool: True se subscrição bem-sucedida
        """
        try:
            if not self.dll or not self.connected:
                self.logger.error("DLL não está conectada")
                return False
            
            # Verificar se market data está conectado
            if self.market_state != self.MARKET_CONNECTED:
                self.logger.error("Market data não conectado - necessário para book")
                return False
            
            # SubscribePriceBook(pwcTicker, pwcBolsa)
            result = self.dll.SubscribePriceBook(
                c_wchar_p(ticker),  # Ticker
                c_wchar_p("F")      # Bolsa (F=Futuros)
            )
            
            if result == NResult.NL_OK:
                self.logger.info(f"[OK] Subscrito ao price book de {ticker}")
                return True
            else:
                self.logger.error(f"Erro ao subscrever price book: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro ao subscrever price book: {e}")
            return False
    
    def unsubscribe_offer_book(self, ticker: str) -> bool:
        """
        Cancela subscrição do book de ofertas
        """
        try:
            result = self.dll.UnsubscribeOfferBook(
                c_wchar_p(ticker),
                c_wchar_p("F")
            )
            return result == NResult.NL_OK
        except Exception as e:
            self.logger.error(f"Erro ao cancelar offer book: {e}")
            return False
    
    def unsubscribe_price_book(self, ticker: str) -> bool:
        """
        Cancela subscrição do book de preços
        """
        try:
            result = self.dll.UnsubscribePriceBook(
                c_wchar_p(ticker),
                c_wchar_p("F")
            )
            return result == NResult.NL_OK
        except Exception as e:
            self.logger.error(f"Erro ao cancelar price book: {e}")
            return False
        
    def _validate_market_data(self, data: Dict) -> bool:
        """
        Valida que dados são reais e não dummy
        """
        # Em produção, validação rigorosa
        if os.getenv('TRADING_ENV') == 'PRODUCTION':
            # Verificar fonte
            if not self.market_connected:
                self.logger.error("Dados recebidos sem conexão de market data")
                return False
                
            # Verificar timestamp
            if 'timestamp' in data:
                data_age = (datetime.now() - data['timestamp']).total_seconds()
                if data_age > 5:  # Mais de 5 segundos
                    self.logger.error(f"Dados muito antigos: {data_age}s")
                    return False
            
            # Verificar valores suspeitos
            if 'price' in data:
                # WDO tem preços típicos entre 4000-6000
                if data['price'] < 3000 or data['price'] > 10000:
                    self.logger.error(f"Preço suspeito para WDO: {data['price']}")
                    return False
        
        return True