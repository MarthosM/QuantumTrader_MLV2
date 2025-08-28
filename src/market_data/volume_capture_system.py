"""
Sistema de Captura de Volume para WDO
Baseado nas análises da pasta analises_claude
"""

import ctypes
from ctypes import WINFUNCTYPE, c_int, c_void_p, c_char_p, c_double, c_uint32, c_char, POINTER, cast
import threading
import time
from datetime import datetime
import logging
from collections import deque
import struct

logger = logging.getLogger(__name__)

class VolumeTracker:
    """Rastreador de volume com análise de fluxo"""
    
    def __init__(self):
        self.lock = threading.Lock()
        
        # Dados de volume
        self.current_volume = 0
        self.cumulative_volume = 0
        self.buy_volume = 0
        self.sell_volume = 0
        self.delta_volume = 0  # Buy - Sell
        
        # Volume por preço
        self.volume_profile = {}
        
        # Buffer circular para trades
        self.trade_buffer = deque(maxlen=1000)
        
        # Estatísticas por minuto
        self.minute_stats = {}
        
        # Último trade processado
        self.last_trade = None
        
    def process_trade(self, trade_data):
        """Processa um trade individual"""
        with self.lock:
            volume = trade_data.get('volume', 0)
            price = trade_data.get('price', 0)
            trade_type = trade_data.get('trade_type', 0)
            
            if volume > 0 and volume < 10000:  # Validar volume razoável
                # Atualizar volumes
                self.current_volume = volume
                self.cumulative_volume += volume
                
                # Determinar direção (compra/venda agressora)
                if trade_type == 2:  # Compra agressora
                    self.buy_volume += volume
                    self.delta_volume += volume
                elif trade_type == 3:  # Venda agressora
                    self.sell_volume += volume
                    self.delta_volume -= volume
                
                # Atualizar volume profile
                price_level = round(price, 1)
                if price_level not in self.volume_profile:
                    self.volume_profile[price_level] = {
                        'total': 0, 'buy': 0, 'sell': 0
                    }
                
                self.volume_profile[price_level]['total'] += volume
                if trade_type == 2:
                    self.volume_profile[price_level]['buy'] += volume
                else:
                    self.volume_profile[price_level]['sell'] += volume
                
                # Adicionar ao buffer
                self.trade_buffer.append(trade_data)
                self.last_trade = trade_data
                
                # Estatísticas por minuto
                minute = datetime.now().strftime('%H:%M')
                if minute not in self.minute_stats:
                    self.minute_stats[minute] = {
                        'volume': 0, 'trades': 0, 'buy': 0, 'sell': 0
                    }
                
                self.minute_stats[minute]['volume'] += volume
                self.minute_stats[minute]['trades'] += 1
                if trade_type == 2:
                    self.minute_stats[minute]['buy'] += volume
                else:
                    self.minute_stats[minute]['sell'] += volume
                
                logger.debug(f"Volume processado: {volume} contratos @ {price}")
                return True
        
        return False
    
    def get_current_stats(self):
        """Retorna estatísticas atuais de volume"""
        with self.lock:
            return {
                'current_volume': self.current_volume,
                'cumulative_volume': self.cumulative_volume,
                'buy_volume': self.buy_volume,
                'sell_volume': self.sell_volume,
                'delta_volume': self.delta_volume,
                'volume_ratio': self.buy_volume / self.sell_volume if self.sell_volume > 0 else 0,
                'last_trade': self.last_trade
            }


class WDOVolumeCapture:
    """Sistema principal de captura de volume do WDO"""
    
    def __init__(self, dll_path="ProfitDLL64.dll"):
        self.dll_path = dll_path
        self.dll = None
        self.tracker = VolumeTracker()
        self.is_connected = False
        
        # Callbacks
        self.trade_callback = None
        self.daily_callback = None
        
        # Contadores de debug
        self.callbacks_received = 0
        self.volumes_captured = 0
        
    def initialize(self):
        """Inicializa sistema de captura de volume"""
        try:
            logger.info("Inicializando sistema de captura de volume...")
            
            # Carregar DLL
            self.dll = ctypes.CDLL(self.dll_path)
            
            # Configurar callback de trade
            self._setup_trade_callback()
            
            logger.info("Sistema de captura de volume inicializado")
            return True
            
        except Exception as e:
            logger.error(f"Erro inicializando captura de volume: {e}")
            return False
    
    def _setup_trade_callback(self):
        """Configura callback para capturar trades com volume"""
        
        # Definir assinatura do callback TNewTradeCallback
        # Baseado na análise do callbacks.py
        TRADE_CALLBACK_FUNC = WINFUNCTYPE(
            None,           # return void
            c_void_p,       # rAssetID (TAssetIDRec)
            c_char_p,       # pwcDate (timestamp)
            c_uint32,       # nTradeNumber
            c_double,       # dPrice
            c_double,       # dVol (volume financeiro)
            c_int,          # nQtd (QUANTIDADE DE CONTRATOS!)
            c_int,          # nBuyAgent
            c_int,          # nSellAgent
            c_int,          # nTradeType (2=Buy, 3=Sell)
            c_char          # bEdit
        )
        
        @TRADE_CALLBACK_FUNC
        def new_trade_callback(asset_id, date, trade_number, price, 
                              financial_volume, quantity, buy_agent, 
                              sell_agent, trade_type, is_edit):
            """Callback para processar trades com volume"""
            
            try:
                self.callbacks_received += 1
                
                # Extrair ticker do asset_id
                ticker = self._extract_ticker(asset_id)
                
                # Filtrar WDO
                if ticker and b'WDO' in ticker:
                    # QUANTIDADE está no campo nQtd (parâmetro quantity)
                    trade_data = {
                        'timestamp': datetime.now().isoformat(),
                        'trade_number': trade_number,
                        'price': price,
                        'volume': quantity,  # CONTRATOS!
                        'financial_volume': financial_volume,
                        'trade_type': trade_type,
                        'buy_agent': buy_agent,
                        'sell_agent': sell_agent
                    }
                    
                    # Processar no tracker
                    if self.tracker.process_trade(trade_data):
                        self.volumes_captured += 1
                        
                        # Log a cada 100 volumes capturados
                        if self.volumes_captured % 100 == 0:
                            stats = self.tracker.get_current_stats()
                            logger.info(f"Volume capturado: {stats['cumulative_volume']} contratos totais")
                            logger.info(f"Delta: {stats['delta_volume']} | Buy: {stats['buy_volume']} | Sell: {stats['sell_volume']}")
                            
            except Exception as e:
                logger.error(f"Erro no callback de trade: {e}")
        
        self.trade_callback = new_trade_callback
        logger.info("Callback de trade configurado para captura de volume")
        
    def _extract_ticker(self, asset_id_ptr):
        """Extrai ticker da estrutura TAssetIDRec"""
        if not asset_id_ptr:
            return None
            
        try:
            # TAssetIDRec: primeiro campo é ponteiro para ticker (PWideChar)
            ticker_ptr_addr = cast(asset_id_ptr, POINTER(c_void_p))
            if ticker_ptr_addr and ticker_ptr_addr.contents:
                # Ler string wide char
                ticker_wstr = ctypes.wstring_at(ticker_ptr_addr.contents)
                return ticker_wstr.encode('utf-8')
        except:
            pass
            
        return None
    
    def register_callback(self, dll_instance):
        """Registra callback na DLL já inicializada"""
        try:
            # Usar SetNewTradeCallback se disponível
            if hasattr(dll_instance, 'SetNewTradeCallback'):
                result = dll_instance.SetNewTradeCallback(self.trade_callback)
                if result == 0:
                    logger.info("SetNewTradeCallback registrado para captura de volume")
                    self.is_connected = True
                    return True
            
            # Alternativamente, callback pode ser passado no DLLInitializeLogin
            logger.warning("SetNewTradeCallback não disponível - callback deve ser passado no login")
            
        except Exception as e:
            logger.error(f"Erro registrando callback de volume: {e}")
            
        return False
    
    def get_volume_for_features(self):
        """Retorna volume atual para uso nas features"""
        stats = self.tracker.get_current_stats()
        return stats.get('current_volume', 0)
    
    def get_volume_profile(self):
        """Retorna perfil de volume por preço"""
        with self.tracker.lock:
            return dict(self.tracker.volume_profile)
    
    def get_delta_volume(self):
        """Retorna delta volume (buy - sell)"""
        stats = self.tracker.get_current_stats()
        return stats.get('delta_volume', 0)
    
    def get_volume_stats(self):
        """Retorna todas as estatísticas de volume"""
        return self.tracker.get_current_stats()


# Instância global para uso no sistema
volume_capture = None

def initialize_volume_capture(dll_path="ProfitDLL64.dll"):
    """Inicializa sistema global de captura de volume"""
    global volume_capture
    
    if volume_capture is None:
        volume_capture = WDOVolumeCapture(dll_path)
        if volume_capture.initialize():
            logger.info("Sistema de captura de volume inicializado globalmente")
            return volume_capture
    
    return volume_capture

def get_current_volume():
    """Função auxiliar para obter volume atual"""
    if volume_capture:
        return volume_capture.get_volume_for_features()
    return 0

def get_volume_stats():
    """Função auxiliar para obter estatísticas de volume"""
    if volume_capture:
        return volume_capture.get_volume_stats()
    return {
        'current_volume': 0,
        'cumulative_volume': 0,
        'buy_volume': 0,
        'sell_volume': 0,
        'delta_volume': 0,
        'volume_ratio': 0
    }