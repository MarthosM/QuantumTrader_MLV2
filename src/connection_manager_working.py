"""
Connection Manager Working - Baseado no book_collector funcional
Sistema de conexão que realmente recebe dados do mercado
"""

import os
import sys
import time
import ctypes
from ctypes import *
from ctypes import c_longlong  # Adicionar importação explícita
from ctypes import c_uint32  # Para trade callback
from datetime import datetime
from pathlib import Path
import logging
from typing import Optional, Callable, Dict, Any
from dotenv import load_dotenv
import threading
from src.market_data.volume_capture_system import VolumeTracker

# Carregar variáveis de ambiente
load_dotenv('.env.production')

# Estrutura TAssetIDRec simplificada (funciona!)
class TAssetIDRec(Structure):
    _fields_ = [
        ("ticker", c_wchar * 35),
        ("bolsa", c_wchar * 15),
    ]

class ConnectionManagerWorking:
    """Connection Manager que funciona com dados reais"""
    
    def __init__(self, dll_path: Optional[str] = None):
        self.logger = logging.getLogger('ConnectionManagerWorking')
        self.dll = None
        self.volume_tracker = VolumeTracker()
        
        # Caminho da DLL
        if dll_path:
            self.dll_path = dll_path
        else:
            # Tentar vários caminhos
            possible_paths = [
                "C:/Users/marth/OneDrive/Programacao/Python/QuantumTrader_Production/ProfitDLL64.dll",
                os.path.abspath("ProfitDLL64.dll"),
                "./ProfitDLL64.dll",
                "ProfitDLL64.dll"
            ]
            for path in possible_paths:
                if Path(path).exists():
                    self.dll_path = path
                    break
            else:
                raise FileNotFoundError("ProfitDLL64.dll não encontrada")
        
        # Flags de controle
        self.bAtivo = False
        self.bMarketConnected = False
        self.bConnectado = False
        self.bBrokerConnected = False
        self.connected = False
        
        # Estados para compatibilidade
        self.market_connected = False
        self.broker_connected = False
        self.login_state = -1
        self.market_state = -1
        self.routing_state = -1
        
        # Contadores
        self.callbacks = {
            'state': 0,
            'trade': 0,
            'tiny_book': 0,
            'offer_book': 0,
            'price_book': 0,
            'daily': 0
        }
        
        # Referências dos callbacks - IMPORTANTE: manter referências
        self.callback_refs = {}
        
        # Ticker que estamos monitorando
        self.target_ticker = os.getenv('TRADING_SYMBOL', 'WDOU25')
        
        # Dados de mercado atuais
        self.last_bid = 0
        self.last_ask = 0
        self.last_trade_price = 0
        self.last_book_update = {}
        
        # Callbacks externos
        self._offer_book_callback = None
        self._trade_callback = None
        
        # Lock para thread safety
        self._lock = threading.RLock()
        
        # Estruturas para ordens
        self.active_orders = {}  # Ordens ativas
        self.oco_pairs = {}      # Mapeamento de pares OCO
        
        self.logger.info(f"ConnectionManagerWorking criado - DLL: {self.dll_path}")
        
    def connect(self) -> bool:
        """Conecta ao ProfitChart usando o método que funciona"""
        try:
            # Carregar DLL
            self.logger.info(f"Carregando DLL: {os.path.abspath(self.dll_path)}")
            self.dll = WinDLL(self.dll_path)
            self.logger.info("[OK] DLL carregada")
            
            # Criar callbacks ANTES do login (CRÍTICO!)
            self._create_all_callbacks()
            
            # Pegar credenciais
            key = c_wchar_p(os.getenv('PROFIT_KEY', '16168135121806338936'))
            user = c_wchar_p(os.getenv('PROFIT_USERNAME', '29936354842'))
            pwd = c_wchar_p(os.getenv('PROFIT_PASSWORD', 'Ultra3376!'))
            
            self.logger.info("Fazendo login com callbacks...")
            
            # DLLInitializeLogin com callbacks (método que funciona!)
            # Agora passando NewTradeCallback no 8º parâmetro!
            result = self.dll.DLLInitializeLogin(
                key, user, pwd,
                self.callback_refs['state'],         # stateCallback
                None,                                # historyCallback
                None,                                # orderChangeCallback
                None,                                # accountCallback
                self.callback_refs.get('new_trade'), # newTradeCallback <- AQUI! (8º parâmetro)
                self.callback_refs.get('daily'),     # newDailyCallback
                self.callback_refs['price_book'],    # priceBookCallback
                self.callback_refs['offer_book'],    # offerBookCallback
                None,                                # historyTradeCallback
                None,                                # progressCallBack
                self.callback_refs['tiny_book']      # tinyBookCallBack
            )
            
            if result != 0:
                self.logger.error(f"Erro no login: {result}")
                return False
                
            self.logger.info(f"[OK] Login bem sucedido: {result}")
            
            # Aguardar conexão completa
            if not self._wait_login():
                self.logger.error("Timeout aguardando conexão")
                return False
            
            # Configurar callbacks adicionais após login
            self._setup_additional_callbacks()
            
            self.connected = True
            return True
            
        except Exception as e:
            self.logger.error(f"Erro na conexão: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_all_callbacks(self):
        """Cria TODOS os callbacks necessários (baseado no book_collector)"""
        
        # State callback - CRÍTICO para conexão
        @WINFUNCTYPE(None, c_int32, c_int32)
        def stateCallback(nType, nResult):
            with self._lock:
                self.callbacks['state'] += 1
                
                states = {0: "Login", 1: "Broker", 2: "Market", 3: "Ativacao"}
                self.logger.debug(f"[STATE] {states.get(nType, f'Type{nType}')}: {nResult}")
                
                if nType == 0:  # Login
                    self.bConnectado = (nResult == 0)
                    self.login_state = nResult
                elif nType == 1:  # Broker  
                    self.bBrokerConnected = (nResult == 5)
                    self.broker_connected = self.bBrokerConnected
                    self.routing_state = nResult
                elif nType == 2:  # Market
                    self.bMarketConnected = (nResult == 4 or nResult == 3 or nResult == 2)
                    self.market_connected = self.bMarketConnected
                    self.market_state = nResult
                elif nType == 3:  # Ativacao
                    self.bAtivo = (nResult == 0)
                    
                if self.bMarketConnected and self.bAtivo and self.bConnectado:
                    self.logger.info(">>> SISTEMA TOTALMENTE CONECTADO <<<")
                    
            return None
            
        self.callback_refs['state'] = stateCallback
        
        # TinyBook callback - Recebe bid/ask básico
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_double, c_int, c_int)
        def tinyBookCallBack(assetId, price, qtd, side):
            with self._lock:
                self.callbacks['tiny_book'] += 1
                
                # LOG DEBUG: Sempre logar primeiros callbacks para verificar se está funcionando
                if self.callbacks['tiny_book'] <= 3:
                    side_str = "BID" if side == 0 else "ASK"
                    self.logger.info(f'[TINY_BOOK DEBUG] #{self.callbacks["tiny_book"]} {side_str}: Price={price}, Qtd={qtd}')
                
                # Validar preço
                if price > 1000 and price < 10000:  # Faixa válida para WDO
                    if side == 0:  # Bid
                        self.last_bid = price
                    else:  # Ask
                        self.last_ask = price
                    
                    # Atualizar last_book_update
                    if side == 0:
                        self.last_book_update['bid_price_1'] = price
                        self.last_book_update['bid_volume_1'] = qtd
                    else:
                        self.last_book_update['ask_price_1'] = price
                        self.last_book_update['ask_volume_1'] = qtd
                    
                    # Log apenas primeiros ou a cada 500
                    if self.callbacks['tiny_book'] <= 5 or self.callbacks['tiny_book'] % 500 == 0:
                        side_str = "BID" if side == 0 else "ASK"
                        self.logger.info(f'[TINY_BOOK] {self.target_ticker} {side_str}: R$ {price:.2f} x {qtd}')
                    
                    # IMPORTANTE: Chamar callback externo também do TinyBook
                    if self._offer_book_callback and self.last_bid > 0 and self.last_ask > 0:
                        book_data = {
                            'bid_price_1': self.last_bid,
                            'bid_volume_1': self.last_book_update.get('bid_volume_1', 100),
                            'ask_price_1': self.last_ask,
                            'ask_volume_1': self.last_book_update.get('ask_volume_1', 100),
                            'timestamp': datetime.now().isoformat()
                        }
                        try:
                            self._offer_book_callback(self.target_ticker, book_data)
                        except Exception as e:
                            if self.callbacks['tiny_book'] <= 5:
                                self.logger.error(f"Erro no callback externo (tiny): {e}")
                        
            return None
            
        self.callback_refs['tiny_book'] = tinyBookCallBack
        
        # Price Book callback V2
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_int, c_int, c_int, c_double, c_int, c_double, POINTER(c_int), POINTER(c_int))
        def priceBookCallback(assetId, nAction, nPosition, Side, sPrice, nQtd, nCount, pArraySell, pArrayBuy):
            with self._lock:
                self.callbacks['price_book'] += 1
                
                # Validar e salvar dados
                if sPrice > 1000 and sPrice < 10000 and nQtd > 0:
                    if Side == 0 and nPosition == 0:  # Melhor bid
                        self.last_bid = sPrice
                        self.last_book_update['bid_price_1'] = sPrice
                        self.last_book_update['bid_volume_1'] = nQtd
                    elif Side == 1 and nPosition == 0:  # Melhor ask
                        self.last_ask = sPrice
                        self.last_book_update['ask_price_1'] = sPrice
                        self.last_book_update['ask_volume_1'] = nQtd
                        
            return None
            
        self.callback_refs['price_book'] = priceBookCallback
        
        # Offer Book callback V2 - Mais detalhado
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_int, c_int, c_int, c_int, c_int, c_longlong, c_double, c_int, c_int, c_int, c_int, c_int,
                   c_wchar_p, POINTER(c_ubyte), POINTER(c_ubyte))
        def offerBookCallback(assetId, nAction, nPosition, Side, nQtd, nAgent, nOfferID, sPrice, bHasPrice,
                             bHasQtd, bHasDate, bHasOfferID, bHasAgent, date, pArraySell, pArrayBuy):
            with self._lock:
                self.callbacks['offer_book'] += 1
                
                # Validar e processar dados
                if bHasPrice and bHasQtd and sPrice > 1000 and sPrice < 10000 and nQtd > 0:
                    # Atualizar preços se for melhor bid/ask
                    if Side == 0 and nPosition == 0:  # Melhor bid
                        self.last_bid = sPrice
                        self.last_book_update['bid_price_1'] = sPrice
                        self.last_book_update['bid_volume_1'] = nQtd
                    elif Side == 1 and nPosition == 0:  # Melhor ask
                        self.last_ask = sPrice
                        self.last_book_update['ask_price_1'] = sPrice
                        self.last_book_update['ask_volume_1'] = nQtd
                    
                    # Criar estrutura de book para callback externo
                    book_data = {
                        'bid_price_1': self.last_book_update.get('bid_price_1', 0),
                        'bid_volume_1': self.last_book_update.get('bid_volume_1', 0),
                        'ask_price_1': self.last_book_update.get('ask_price_1', 0),
                        'ask_volume_1': self.last_book_update.get('ask_volume_1', 0),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Chamar callback externo SEMPRE (não só a cada 10)
                    if self._offer_book_callback:
                        try:
                            self._offer_book_callback(self.target_ticker, book_data)
                        except Exception as e:
                            self.logger.error(f"Erro no callback externo: {e}")
                    
                    # Log ocasional
                    if self.callbacks['offer_book'] <= 5 or self.callbacks['offer_book'] % 1000 == 0:
                        side_str = "BID" if Side == 0 else "ASK"
                        self.logger.info(f'[OFFER_BOOK] {side_str} @ R$ {sPrice:.2f} x {nQtd}')
                        
            return None
            
        self.callback_refs['offer_book'] = offerBookCallback
        
        # Daily callback (opcional)
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_wchar_p, c_double, c_double, c_double, c_double, c_double, c_double, c_double, c_double, c_double,
                   c_double, c_int, c_int, c_int, c_int, c_int, c_int, c_int)
        def dailyCallback(assetId, date, sOpen, sHigh, sLow, sClose, sVol, sAjuste, sMaxLimit, sMinLimit, sVolBuyer,
                         sVolSeller, nQtd, nNegocios, nContratosOpen, nQtdBuyer, nQtdSeller, nNegBuyer, nNegSeller):
            with self._lock:
                self.callbacks['daily'] += 1
                
                if self.callbacks['daily'] <= 2:
                    self.logger.info(f'[DAILY] O={sOpen:.2f} H={sHigh:.2f} L={sLow:.2f} C={sClose:.2f}')
                    
            return None
            
        self.callback_refs['daily'] = dailyCallback
        
        # NewTradeCallback com estrutura correta (10 parâmetros diretos)
        # Baseado na solução descoberta em analises_claude
        @WINFUNCTYPE(None, c_void_p, c_char_p, c_uint32, c_double, c_double, c_int, c_int, c_int, c_int, c_char)
        def newTradeCallback(asset_id, date, trade_number, price, financial_volume, quantity, buy_agent, sell_agent, trade_type, is_edit):
            """Callback de trade com volume REAL em 'quantity' (nQtd)"""
            with self._lock:
                self.callbacks['trade'] += 1
                
                # VOLUME REAL está no parâmetro quantity (nQtd - 6º parâmetro)
                volume_contratos = quantity
                
                # Validar valores razoáveis
                if price > 1000 and price < 10000 and 0 < volume_contratos < 10000:
                    self.last_trade_price = price
                    
                    # Processar no VolumeTracker
                    trade_data = {
                        'volume': volume_contratos,
                        'price': price,
                        'trade_type': trade_type,  # 2=Buy, 3=Sell
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Processar com VolumeTracker
                    self.volume_tracker.process_trade(trade_data)
                    
                    # Log dos primeiros trades para verificar
                    if self.callbacks['trade'] <= 5:
                        direction = 'BUY' if trade_type == 2 else 'SELL' if trade_type == 3 else 'UNK'
                        self.logger.info(f'[TRADE] #{self.callbacks["trade"]}: {direction} {volume_contratos} @ R$ {price:.2f}')
                    elif self.callbacks['trade'] % 100 == 0:
                        stats = self.volume_tracker.get_current_stats()
                        self.logger.info(f'[VOLUME STATS] Total: {stats["cumulative_volume"]} | Delta: {stats["delta_volume"]}')
                    
                    # Chamar callback externo se configurado
                    if self._trade_callback:
                        try:
                            self._trade_callback(self.target_ticker, trade_data)
                        except Exception as e:
                            self.logger.error(f"Erro no trade callback externo: {e}")
                            
            return None
            
        self.callback_refs['new_trade'] = newTradeCallback
    
    def _wait_login(self):
        """Aguarda login completo"""
        self.logger.info("Aguardando conexão completa...")
        
        timeout = 15  # 15 segundos
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            if self.bMarketConnected:
                self.logger.info("[OK] Market conectado!")
                return True
                
            # Log periódico do status
            elapsed = int(time.time() - start_time)
            if elapsed > 0 and elapsed % 3 == 0 and elapsed == int(time.time() - start_time):
                self.logger.debug(f"Status: Market={self.bMarketConnected}, Broker={self.bBrokerConnected}, Login={self.bConnectado}")
                
            time.sleep(0.1)
            
        return False
    
    def _setup_additional_callbacks(self):
        """Configura callbacks adicionais após login"""
        
        # Importar estruturas de trade
        try:
            from src.profit_trade_structures import decode_trade_v2
        except ImportError:
            from profit_trade_structures import decode_trade_v2
        
        # DESABILITADO - Usando newTradeCallback no DLLInitializeLogin
        # O novo callback com volume real já foi registrado no login
        if False and hasattr(self.dll, 'SetTradeCallbackV2'):
            # TConnectorTradeCallback para V2
            @WINFUNCTYPE(None, POINTER(c_byte))
            def tradeCallbackV2(trade_ptr):
                with self._lock:
                    self.callbacks['trade'] += 1
                    
                    # Decodificar estrutura TConnectorTrade
                    try:
                        # Debug DETALHADO: Capturar e analisar bytes
                        if self.callbacks['trade'] <= 10:  # Primeiros 10 trades
                            import struct
                            raw_bytes = cast(trade_ptr, POINTER(c_byte * 200))
                            raw_data = bytes(raw_bytes.contents[:100])
                            
                            # Log hex dump
                            self.logger.info(f"[TRADE_V2 RAW #{self.callbacks['trade']}] First 100 bytes:")
                            for offset in range(0, min(len(raw_data), 64), 16):
                                hex_part = raw_data[offset:offset+16].hex()
                                self.logger.info(f"  {offset:04x}: {hex_part}")
                            
                            # Procurar padrões de volume (int32 ou int64)
                            self.logger.info(f"[TRADE_V2 ANALYSIS] Searching for volume patterns:")
                            for offset in range(0, min(len(raw_data)-7, 80), 4):
                                try:
                                    # Tentar int32
                                    val32 = struct.unpack_from('<i', raw_data, offset)[0]
                                    if 1 <= val32 <= 500:  # Volume típico: 1-500 contratos
                                        self.logger.info(f"  Possible volume (int32) at offset {offset}: {val32} contracts")
                                    
                                    # Tentar int64
                                    if offset <= len(raw_data)-8:
                                        val64 = struct.unpack_from('<q', raw_data, offset)[0]
                                        if 1 <= val64 <= 500:
                                            self.logger.info(f"  Possible volume (int64) at offset {offset}: {val64} contracts")
                                    
                                    # Tentar double (preço)
                                    if offset <= len(raw_data)-8:
                                        val_double = struct.unpack_from('<d', raw_data, offset)[0]
                                        if 5000 < val_double < 6000:  # Preço típico WDO
                                            self.logger.info(f"  Possible price at offset {offset}: {val_double:.2f}")
                                except:
                                    pass
                        
                        trade_data = decode_trade_v2(trade_ptr)
                        
                        # Extrair dados importantes
                        price = trade_data.get('price', 0)
                        quantity = trade_data.get('quantity', 0)  # VOLUME!
                        
                        # Atualizar preço e volume
                        if price > 1000 and price < 10000:
                            self.last_trade_price = price
                            
                            # Log dos primeiros trades para verificar
                            if self.callbacks['trade'] <= 5:
                                self.logger.info(f'[TRADE_V2] Trade #{self.callbacks["trade"]}: Price={price:.2f}, Volume={quantity}, Aggressor={trade_data.get("aggressor", "?")}')
                            elif self.callbacks['trade'] % 100 == 0:
                                self.logger.info(f'[TRADE_V2] Trade #{self.callbacks["trade"]}: Price={price:.2f}, Volume={quantity}')
                        
                        # Chamar callback externo se configurado
                        if self._trade_callback and quantity > 0:
                            try:
                                self._trade_callback(self.target_ticker, trade_data)
                            except Exception as e:
                                self.logger.error(f"Erro no trade callback externo: {e}")
                                
                    except Exception as e:
                        if self.callbacks['trade'] <= 3:
                            self.logger.error(f"Erro decodificando trade V2: {e}")
                    
                return None
                
            self.callback_refs['trade_v2'] = tradeCallbackV2
            result = self.dll.SetTradeCallbackV2(self.callback_refs['trade_v2'])
            self.logger.info(f"[OK] SetTradeCallbackV2 registrado: {result}")
            
        # Fallback para SetTradeCallback (sem 'New')
        # DESABILITADO - Usando newTradeCallback no DLLInitializeLogin
        elif False and hasattr(self.dll, 'SetTradeCallback'):
            @WINFUNCTYPE(None, c_wchar_p, c_double, c_int, c_int, c_int)
            def tradeCallback(ticker, price, qty, buyer, seller):
                with self._lock:
                    self.callbacks['trade'] += 1
                    
                    if price > 1000 and price < 10000:
                        self.last_trade_price = price
                        
                        # Criar estrutura de trade
                        trade_data = {
                            'price': float(price),
                            'quantity': int(qty),
                            'buyer': int(buyer),
                            'seller': int(seller),
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        # Chamar callback externo se configurado
                        if self._trade_callback:
                            try:
                                self._trade_callback(self.target_ticker, trade_data)
                            except Exception as e:
                                self.logger.error(f"Erro no trade callback: {e}")
                        
                        if self.callbacks['trade'] <= 5 or self.callbacks['trade'] % 500 == 0:
                            self.logger.info(f'[TRADE] @ R$ {price:.2f} x {qty}')
                    
                return None
                
            self.callback_refs['trade'] = tradeCallback
            self.dll.SetTradeCallback(self.callback_refs['trade'])
            self.logger.info("[OK] SetTradeCallback registrado")
            
        # Log do status do callback de trade
        if 'new_trade' in self.callback_refs:
            self.logger.info("[OK] NewTradeCallback registrado no DLLInitializeLogin")
            self.logger.info("  Aguardando trades para captura de VOLUME REAL...")
        else:
            self.logger.warning("[!] NewTradeCallback não foi registrado!")
            
        # Re-registrar callbacks de book para garantir
        if hasattr(self.dll, 'SetTinyBookCallback'):
            self.dll.SetTinyBookCallback(self.callback_refs['tiny_book'])
            self.logger.info("[OK] TinyBook callback re-registrado")
            
        if hasattr(self.dll, 'SetOfferBookCallbackV2'):
            self.dll.SetOfferBookCallbackV2(self.callback_refs['offer_book'])
            self.logger.info("[OK] OfferBook V2 callback registrado")
            
        if hasattr(self.dll, 'SetPriceBookCallback'):
            self.dll.SetPriceBookCallback(self.callback_refs['price_book'])
            self.logger.info("[OK] PriceBook callback registrado")
    
    def subscribe_symbol(self, symbol: str) -> bool:
        """Subscreve ao símbolo (método que funciona!)"""
        try:
            self.target_ticker = symbol
            exchange = "F"  # Futuros
            
            self.logger.info(f"Subscrevendo {symbol} na bolsa {exchange}...")
            
            # SubscribeTicker - principal
            result = self.dll.SubscribeTicker(c_wchar_p(symbol), c_wchar_p(exchange))
            self.logger.info(f"SubscribeTicker({symbol}, {exchange}) = {result}")
            
            if result != 0:
                self.logger.warning(f"SubscribeTicker retornou {result}")
                
            # SubscribeOfferBook - book detalhado
            if hasattr(self.dll, 'SubscribeOfferBook'):
                result = self.dll.SubscribeOfferBook(c_wchar_p(symbol), c_wchar_p(exchange))
                self.logger.info(f"SubscribeOfferBook({symbol}, {exchange}) = {result}")
                
            # SubscribePriceBook - agregado por preço
            if hasattr(self.dll, 'SubscribePriceBook'):
                result = self.dll.SubscribePriceBook(c_wchar_p(symbol), c_wchar_p(exchange))
                self.logger.info(f"SubscribePriceBook({symbol}, {exchange}) = {result}")
            
            # Tentar SubscribeAggregatedBook também (pode incluir volume)
            if hasattr(self.dll, 'SubscribeAggregatedBook'):
                result = self.dll.SubscribeAggregatedBook(c_wchar_p(symbol), c_wchar_p(exchange))
                self.logger.info(f"SubscribeAggregatedBook({symbol}, {exchange}) = {result}")
            
            # Verificar se existe método específico para Times & Trades
            if hasattr(self.dll, 'SubscribeTimesAndTrades'):
                result = self.dll.SubscribeTimesAndTrades(c_wchar_p(symbol), c_wchar_p(exchange))
                self.logger.info(f"SubscribeTimesAndTrades({symbol}, {exchange}) = {result}")
            elif hasattr(self.dll, 'SubscribeTrades'):
                result = self.dll.SubscribeTrades(c_wchar_p(symbol), c_wchar_p(exchange))
                self.logger.info(f"SubscribeTrades({symbol}, {exchange}) = {result}")
            elif hasattr(self.dll, 'SubscribeMarketData'):
                # Alguns sistemas usam SubscribeMarketData para todos os dados
                result = self.dll.SubscribeMarketData(c_wchar_p(symbol), c_wchar_p(exchange), c_int(3))  # 3 = Book + Trades
                self.logger.info(f"SubscribeMarketData({symbol}, {exchange}, 3) = {result}")
                
            self.logger.info(f"[OK] Subscrito a {symbol} com todas as subscrições disponíveis")
            return True
                
        except Exception as e:
            self.logger.error(f"Erro na subscrição: {e}")
            return False
    
    def set_offer_book_callback(self, callback: Callable):
        """Define callback para book updates"""
        self._offer_book_callback = callback
        self.logger.info("Offer book callback configurado")
    
    def set_trade_callback(self, callback: Callable):
        """Define callback para trades"""
        self._trade_callback = callback
        self.logger.info("Trade callback configurado")
    
    def get_volume_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de volume do VolumeTracker"""
        return self.volume_tracker.get_current_stats()
    
    def get_current_prices(self) -> Dict[str, float]:
        """Retorna preços atuais"""
        with self._lock:
            return {
                'bid': self.last_bid,
                'ask': self.last_ask,
                'last': self.last_trade_price,
                'mid': (self.last_bid + self.last_ask) / 2 if self.last_bid > 0 and self.last_ask > 0 else 0
            }
    
    def is_receiving_data(self) -> bool:
        """Verifica se está recebendo dados"""
        with self._lock:
            return self.last_bid > 0 and self.last_ask > 0
    
    def disconnect(self):
        """Desconecta da DLL"""
        try:
            if self.dll and hasattr(self.dll, 'DLLFinalize'):
                self.dll.DLLFinalize()
                self.logger.info("[OK] Desconectado")
            self.connected = False
        except Exception as e:
            self.logger.error(f"Erro ao desconectar: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da conexão"""
        with self._lock:
            return {
                'connected': self.connected,
                'market_connected': self.bMarketConnected,
                'broker_connected': self.bBrokerConnected,
                'receiving_data': self.is_receiving_data(),
                'callbacks': dict(self.callbacks),
                'last_bid': self.last_bid,
                'last_ask': self.last_ask,
                'last_trade': self.last_trade_price
            }
    
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
            
            # Enviar ordem principal a MERCADO (preço 0 para garantir execução)
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
            
            if main_order_id > 0:
                self.logger.info(f"[OK] Ordem principal enviada! ID: {main_order_id}")
                order_ids['main_order'] = main_order_id
                
                # Aguardar um pouco para ordem ser processada
                time.sleep(0.5)
                
                # ========== 2. ENVIAR STOP LOSS ==========
                c_stop_price = c_double(stop_price)
                
                if side.upper() == "BUY":
                    # Para posição comprada, stop loss é venda abaixo
                    if hasattr(self.dll, 'SendStopSellOrder'):
                        # Configurar SendStopSellOrder
                        self.dll.SendStopSellOrder.argtypes = [c_wchar_p, c_wchar_p, c_wchar_p, 
                                                               c_wchar_p, c_wchar_p, 
                                                               c_double, c_double, c_int]
                        self.dll.SendStopSellOrder.restype = c_longlong
                        
                        # Preço limite com slippage
                        stop_limit_price = stop_price - 20  # 20 pontos de slippage
                        
                        stop_order_id = self.dll.SendStopSellOrder(
                            c_account, c_broker, c_password,
                            c_symbol, c_exchange,
                            c_double(stop_limit_price),  # Preço limite
                            c_stop_price,                # Preço de disparo
                            c_quantity
                        )
                    else:
                        # Fallback: ordem limite
                        stop_order_id = self.dll.SendSellOrder(
                            c_account, c_broker, c_password,
                            c_symbol, c_exchange, c_stop_price, c_quantity
                        )
                else:  # SELL
                    # Para posição vendida, stop loss é compra acima
                    if hasattr(self.dll, 'SendStopBuyOrder'):
                        # Configurar SendStopBuyOrder
                        self.dll.SendStopBuyOrder.argtypes = [c_wchar_p, c_wchar_p, c_wchar_p, 
                                                              c_wchar_p, c_wchar_p, 
                                                              c_double, c_double, c_int]
                        self.dll.SendStopBuyOrder.restype = c_longlong
                        
                        # Preço limite com slippage
                        stop_limit_price = stop_price + 20  # 20 pontos de slippage
                        
                        stop_order_id = self.dll.SendStopBuyOrder(
                            c_account, c_broker, c_password,
                            c_symbol, c_exchange, 
                            c_double(stop_limit_price),  # Preço limite
                            c_stop_price,                # Preço de disparo
                            c_quantity
                        )
                    else:
                        # Sem SendStopBuyOrder, não enviar (evita execução imediata)
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
                    'executed': False,
                    'closed': False
                }
                
                # Mapear ordens OCO
                if 'stop_order' in order_ids and 'take_order' in order_ids:
                    stop_id = order_ids['stop_order']
                    take_id = order_ids['take_order']
                    self.oco_pairs[stop_id] = take_id
                    self.oco_pairs[take_id] = stop_id
                    self.logger.info(f"[OCO] Mapeamento criado: Stop {stop_id} <-> Take {take_id}")
                
                self.logger.info("=" * 60)
                self.logger.info("ORDEM BRACKET ENVIADA COM SUCESSO")
                self.logger.info("=" * 60)
                self.logger.info(f"Ordem Principal: {main_order_id}")
                if 'stop_order' in order_ids:
                    self.logger.info(f"Stop Loss: {order_ids['stop_order']} @ {stop_price:.1f}")
                if 'take_order' in order_ids:
                    self.logger.info(f"Take Profit: {order_ids['take_order']} @ {take_price:.1f}")
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
                    self.logger.error(f"[ERRO] Falha ao cancelar {order_type}: {order_id}")
                    success = False
        
        # Marcar como fechada
        if success:
            order_info['closed'] = True
        
        return success