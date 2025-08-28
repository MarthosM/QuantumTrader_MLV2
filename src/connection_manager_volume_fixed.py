"""
Connection Manager com Captura de Volume Corrigida
Baseado na análise dos arquivos analises_claude
"""

import ctypes
from ctypes import (c_char, c_char_p, c_void_p, c_int, c_double, c_uint32, 
                    WINFUNCTYPE, POINTER, cast, byref, create_string_buffer)
import logging
import os
import time
import threading
from datetime import datetime
from collections import deque
import struct

logger = logging.getLogger(__name__)

# Importar sistema de captura de volume
from src.market_data.volume_capture_system import VolumeTracker

class ConnectionManagerVolumeFixed:
    """Connection Manager com captura de volume corrigida"""
    
    def __init__(self, dll_path="ProfitDLL64.dll"):
        self.dll_path = dll_path
        self.dll = None
        self.connected = False
        
        # Sistema de captura de volume
        self.volume_tracker = VolumeTracker()
        
        # Buffers
        self.book_buffer = deque(maxlen=1000)
        self.trade_buffer = deque(maxlen=1000)
        
        # Callbacks
        self.callbacks = {
            'state': None,
            'trade': None,
            'daily': None,
            'book': None,
            'tiny_book': None
        }
        
        # Contadores de debug
        self.trade_callbacks = 0
        self.volumes_captured = 0
        self.last_volume = 0
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Último book
        self.last_book = {'bid': 0, 'ask': 0}
        
    def initialize(self):
        """Inicializa conexão com captura de volume"""
        try:
            logger.info("=" * 60)
            logger.info("Inicializando Connection Manager com Volume Fix")
            logger.info("=" * 60)
            
            # Carregar DLL
            logger.info(f"Carregando DLL: {self.dll_path}")
            self.dll = ctypes.CDLL(self.dll_path)
            
            # Configurar tipos
            self._setup_dll_types()
            
            # Criar callbacks
            self._create_callbacks()
            
            # Login com callbacks
            activation_key = os.getenv('PROFIT_KEY', '')
            
            logger.info("Fazendo login com callbacks de volume...")
            result = self.dll.DLLInitializeLogin(
                activation_key.encode('utf-16-le'),
                b'',  # Username
                b'',  # Password
                self.callbacks['state'],       # StateCallback
                None,                          # HistoryCallback
                None,                          # OrderChangeCallback
                None,                          # AccountCallback
                self.callbacks['trade'],       # NewTradeCallback <- IMPORTANTE!
                self.callbacks['daily'],       # NewDailyCallback
                None,                          # PriceBookCallback
                self.callbacks['book'],        # OfferBookCallback
                None,                          # HistoryTradeCallback
                None,                          # ProgressCallback
                self.callbacks['tiny_book']    # TinyBookCallback
            )
            
            if result == 0:
                logger.info("✅ Login bem-sucedido com callbacks de volume!")
                self.connected = True
                
                # Subscribe no WDO
                self._subscribe_wdo()
                
                return True
            else:
                logger.error(f"❌ Falha no login: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Erro na inicialização: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _setup_dll_types(self):
        """Configura tipos das funções da DLL"""
        
        # DLLInitializeLogin com 14 parâmetros
        self.dll.DLLInitializeLogin.argtypes = [
            c_char_p,  # Key
            c_char_p,  # User
            c_char_p,  # Pass
            c_void_p,  # StateCallback
            c_void_p,  # HistoryCallback
            c_void_p,  # OrderChangeCallback
            c_void_p,  # AccountCallback
            c_void_p,  # NewTradeCallback <- VOLUME AQUI!
            c_void_p,  # NewDailyCallback
            c_void_p,  # PriceBookCallback
            c_void_p,  # OfferBookCallback
            c_void_p,  # HistoryTradeCallback
            c_void_p,  # ProgressCallback
            c_void_p   # TinyBookCallback
        ]
        self.dll.DLLInitializeLogin.restype = c_int
        
        # SubscribeTicker
        self.dll.SubscribeTicker.argtypes = [c_char_p, c_char_p]
        self.dll.SubscribeTicker.restype = c_int
        
    def _create_callbacks(self):
        """Cria callbacks com assinaturas corretas"""
        
        # STATE CALLBACK
        STATE_FUNC = WINFUNCTYPE(None, c_int)
        
        @STATE_FUNC
        def state_callback(state):
            if state == 3:  # Connected
                logger.info(">>> SISTEMA CONECTADO <<<")
        
        self.callbacks['state'] = state_callback
        
        # TRADE CALLBACK - CRÍTICO PARA VOLUME!
        # Baseado na análise de callbacks.py
        TRADE_FUNC = WINFUNCTYPE(
            None,           # return void
            c_void_p,       # rAssetID (TAssetIDRec)
            c_char_p,       # pwcDate (timestamp)
            c_uint32,       # nTradeNumber
            c_double,       # dPrice
            c_double,       # dVol (volume financeiro em R$)
            c_int,          # nQtd <- QUANTIDADE DE CONTRATOS!!!
            c_int,          # nBuyAgent
            c_int,          # nSellAgent
            c_int,          # nTradeType (2=Buy, 3=Sell)
            c_char          # bEdit
        )
        
        @TRADE_FUNC
        def trade_callback(asset_id, date, trade_number, price, 
                          financial_volume, quantity, buy_agent, 
                          sell_agent, trade_type, is_edit):
            """Callback para capturar volume em contratos"""
            
            try:
                self.trade_callbacks += 1
                
                # Extrair ticker
                ticker = self._extract_ticker(asset_id)
                
                # Filtrar WDO
                if ticker and b'WDO' in ticker:
                    
                    # VOLUME EM CONTRATOS ESTÁ EM 'quantity' (nQtd)!
                    volume_contratos = quantity
                    
                    # Validar volume razoável (1-10000 contratos)
                    if 0 < volume_contratos < 10000:
                        
                        trade_data = {
                            'timestamp': datetime.now().isoformat(),
                            'trade_number': trade_number,
                            'price': price,
                            'volume': volume_contratos,  # CONTRATOS!
                            'financial_volume': financial_volume,
                            'trade_type': trade_type,  # 2=Buy, 3=Sell
                            'buy_agent': buy_agent,
                            'sell_agent': sell_agent
                        }
                        
                        # Processar no tracker
                        if self.volume_tracker.process_trade(trade_data):
                            self.volumes_captured += 1
                            self.last_volume = volume_contratos
                            
                            # Log a cada 10 volumes
                            if self.volumes_captured % 10 == 0:
                                stats = self.volume_tracker.get_current_stats()
                                logger.info(f"✅ VOLUME CAPTURADO: {volume_contratos} contratos @ R$ {price:.2f}")
                                logger.info(f"   Total: {stats['cumulative_volume']} | Delta: {stats['delta_volume']}")
                                
                    else:
                        if volume_contratos != 0:
                            logger.warning(f"Volume suspeito ignorado: {volume_contratos}")
                            
            except Exception as e:
                logger.error(f"Erro no callback de trade: {e}")
        
        self.callbacks['trade'] = trade_callback
        
        # DAILY CALLBACK
        DAILY_FUNC = WINFUNCTYPE(
            None,           # return
            c_void_p,       # rAssetID
            c_char_p,       # pwcDate
            c_double,       # dOpen
            c_double,       # dHigh
            c_double,       # dLow
            c_double,       # dClose
            c_double,       # dVol
            c_double,       # dAjuste
            c_double,       # dMaxLimit
            c_double,       # dMinLimit
            c_double,       # dVolBuyer
            c_double,       # dVolSeller
            c_int,          # nQtd <- TOTAL DE CONTRATOS DO DIA
            c_int,          # nNegocios
            c_int,          # nContratosOpen
            c_int,          # nQtdBuyer
            c_int,          # nQtdSeller
            c_int,          # nNegBuyer
            c_int           # nNegSeller
        )
        
        @DAILY_FUNC
        def daily_callback(asset_id, date, open_price, high, low, close,
                          financial_volume, ajuste, max_limit, min_limit,
                          vol_buyer, vol_seller, total_contracts,
                          total_trades, open_contracts, qtd_buyer,
                          qtd_seller, neg_buyer, neg_seller):
            """Callback para dados diários agregados"""
            
            try:
                ticker = self._extract_ticker(asset_id)
                
                if ticker and b'WDO' in ticker:
                    logger.info(f"[DAILY] OHLC: {open_price}/{high}/{low}/{close}")
                    logger.info(f"[DAILY] Volume Total: {total_contracts} contratos")
                    logger.info(f"[DAILY] Buy: {qtd_buyer} | Sell: {qtd_seller}")
                    
            except Exception as e:
                logger.error(f"Erro no daily callback: {e}")
        
        self.callbacks['daily'] = daily_callback
        
        # BOOK CALLBACK (Offer Book V2)
        BOOK_FUNC = WINFUNCTYPE(
            None,
            c_void_p,   # AssetID
            c_int,      # Side (0=Buy, 1=Sell)
            c_char,     # Action
            c_int,      # Position
            c_int,      # Qtd
            c_int,      # QtdOrders
            c_double    # Price
        )
        
        @BOOK_FUNC
        def book_callback(asset_id, side, action, position, qtd, qtd_orders, price):
            """Callback do book"""
            try:
                ticker = self._extract_ticker(asset_id)
                
                if ticker and b'WDO' in ticker:
                    with self.lock:
                        book_data = {
                            'timestamp': datetime.now().isoformat(),
                            'side': 'BID' if side == 0 else 'ASK',
                            'price': price,
                            'qtd': qtd,
                            'orders': qtd_orders
                        }
                        self.book_buffer.append(book_data)
                        
            except Exception as e:
                logger.error(f"Erro no book callback: {e}")
        
        self.callbacks['book'] = book_callback
        
        # TINY BOOK CALLBACK
        TINY_FUNC = WINFUNCTYPE(
            None,
            c_void_p,    # AssetID
            c_double,    # BidPrice
            c_int,       # BidQtd
            c_double,    # AskPrice
            c_int        # AskQtd
        )
        
        @TINY_FUNC
        def tiny_book_callback(asset_id, bid_price, bid_qtd, ask_price, ask_qtd):
            """Callback do tiny book (resumido)"""
            try:
                ticker = self._extract_ticker(asset_id)
                
                if ticker and b'WDO' in ticker:
                    with self.lock:
                        self.last_book = {
                            'bid': bid_price,
                            'bid_qtd': bid_qtd,
                            'ask': ask_price,
                            'ask_qtd': ask_qtd,
                            'spread': ask_price - bid_price
                        }
                        
                        # Log ocasional
                        if self.trade_callbacks % 100 == 0:
                            logger.info(f"[BOOK] Bid: {bid_price} x {bid_qtd} | Ask: {ask_price} x {ask_qtd}")
                            
            except Exception as e:
                logger.error(f"Erro no tiny book callback: {e}")
        
        self.callbacks['tiny_book'] = tiny_book_callback
    
    def _extract_ticker(self, asset_id_ptr):
        """Extrai ticker da estrutura TAssetIDRec"""
        if not asset_id_ptr:
            return None
            
        try:
            # TAssetIDRec tem PWideChar como primeiro campo
            ticker_ptr_addr = cast(asset_id_ptr, POINTER(c_void_p))
            if ticker_ptr_addr and ticker_ptr_addr.contents:
                ticker_wstr = ctypes.wstring_at(ticker_ptr_addr.contents)
                return ticker_wstr.encode('utf-8')
        except:
            pass
            
        return None
    
    def _subscribe_wdo(self):
        """Subscribe no contrato WDO atual"""
        try:
            contract = "WDOU25"  # Agosto 2025
            logger.info(f"Subscribing no contrato: {contract}")
            
            result = self.dll.SubscribeTicker(
                contract.encode('utf-16-le'),
                b'F\x00'  # Bolsa BMF
            )
            
            if result == 0:
                logger.info(f"✅ Subscribe bem-sucedido em {contract}")
            else:
                logger.warning(f"⚠️ Erro no subscribe: {result}")
                
        except Exception as e:
            logger.error(f"Erro no subscribe: {e}")
    
    def get_current_book(self):
        """Retorna book atual"""
        with self.lock:
            return dict(self.last_book)
    
    def get_volume_stats(self):
        """Retorna estatísticas de volume"""
        stats = self.volume_tracker.get_current_stats()
        stats['callbacks_received'] = self.trade_callbacks
        stats['volumes_captured'] = self.volumes_captured
        return stats
    
    def get_current_volume(self):
        """Retorna volume atual para features"""
        stats = self.volume_tracker.get_current_stats()
        return stats.get('current_volume', 0)
    
    def get_delta_volume(self):
        """Retorna delta volume"""
        stats = self.volume_tracker.get_current_stats()
        return stats.get('delta_volume', 0)
    
    def finalize(self):
        """Finaliza conexão"""
        try:
            if self.dll and hasattr(self.dll, 'DLLFinalize'):
                self.dll.DLLFinalize()
                logger.info("DLL finalizada")
        except:
            pass