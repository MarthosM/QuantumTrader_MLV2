#!/usr/bin/env python3
"""
Teste de conexão baseado no book_collector funcional
Verifica se conseguimos receber dados reais do mercado
"""

import os
import sys
import time
import ctypes
from ctypes import *
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv('.env.production')

# Estrutura TAssetIDRec simplificada (igual ao book_collector)
class TAssetIDRec(Structure):
    _fields_ = [
        ("ticker", c_wchar * 35),
        ("bolsa", c_wchar * 15),
    ]

class BookConnectionTest:
    def __init__(self):
        self.dll = None
        
        # Flags de controle
        self.bAtivo = False
        self.bMarketConnected = False
        self.bConnectado = False
        self.bBrokerConnected = False
        
        # Contadores
        self.callbacks = {
            'state': 0,
            'trade': 0,
            'tiny_book': 0,
            'offer_book': 0,
            'price_book': 0
        }
        
        # Referências dos callbacks - IMPORTANTE
        self.callback_refs = {}
        
        # Ticker que estamos monitorando
        self.target_ticker = "WDOU25"
        
        # Dados recebidos
        self.last_bid = 0
        self.last_ask = 0
        self.last_trade_price = 0
        
    def initialize(self):
        """Inicializa DLL e callbacks (igual ao book_collector)"""
        try:
            # Carregar DLL
            # Tentar vários caminhos possíveis
            possible_paths = [
                "C:/Users/marth/OneDrive/Programacao/Python/QuantumTrader_Production/ProfitDLL64.dll",
                "C:/Users/marth/Downloads/ProfitDLL/DLLs/ProfitDLL64.dll",
                "./ProfitDLL64.dll",
                "./dll/ProfitDLL64.dll"
            ]
            
            dll_path = None
            for path in possible_paths:
                if Path(path).exists():
                    dll_path = path
                    break
            
            if dll_path is None:
                print("[ERRO] DLL não encontrada em nenhum caminho conhecido")
                return False
            
            print(f"[INIT] Carregando DLL: {os.path.abspath(dll_path)}")
            
            self.dll = WinDLL(dll_path)
            print("[OK] DLL carregada")
            
            # Criar callbacks ANTES do login
            self._create_callbacks()
            
            # Login com callbacks
            key = c_wchar_p(os.getenv('PROFIT_KEY', '16168135121806338936'))
            user = c_wchar_p(os.getenv('PROFIT_USERNAME', '29936354842'))
            pwd = c_wchar_p(os.getenv('PROFIT_PASSWORD', 'Ultra3376!'))
            
            print("[LOGIN] Fazendo login com callbacks...")
            
            # DLLInitializeLogin com callbacks
            result = self.dll.DLLInitializeLogin(
                key, user, pwd,
                self.callback_refs['state'],         # stateCallback
                None,                                # historyCallback
                None,                                # orderChangeCallback
                None,                                # accountCallback
                None,                                # accountInfoCallback
                None,                                # newDailyCallback
                self.callback_refs['price_book'],    # priceBookCallback
                self.callback_refs['offer_book'],    # offerBookCallback
                None,                                # historyTradeCallback
                None,                                # progressCallBack
                self.callback_refs['tiny_book']      # tinyBookCallBack
            )
            
            if result != 0:
                print(f"[ERRO] Erro no login: {result}")
                return False
                
            print(f"[OK] Login bem sucedido: {result}")
            
            # Aguardar conexão completa
            if not self._wait_login():
                print("[ERRO] Timeout aguardando conexão")
                return False
            
            # Configurar callbacks adicionais após login
            self._setup_additional_callbacks()
            
            return True
            
        except Exception as e:
            print(f"[ERRO] Erro na inicialização: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def _create_callbacks(self):
        """Cria callbacks (baseado no book_collector)"""
        
        # State callback - CRÍTICO
        @WINFUNCTYPE(None, c_int32, c_int32)
        def stateCallback(nType, nResult):
            self.callbacks['state'] += 1
            
            states = {0: "Login", 1: "Broker", 2: "Market", 3: "Ativacao"}
            print(f"[STATE] {states.get(nType, f'Type{nType}')}: {nResult}")
            
            if nType == 0:  # Login
                self.bConnectado = (nResult == 0)
            elif nType == 1:  # Broker
                self.bBrokerConnected = (nResult == 5)
            elif nType == 2:  # Market
                self.bMarketConnected = (nResult == 4 or nResult == 3 or nResult == 2)
            elif nType == 3:  # Ativacao
                self.bAtivo = (nResult == 0)
                
            if self.bMarketConnected and self.bAtivo and self.bConnectado:
                print(">>> SISTEMA TOTALMENTE CONECTADO <<<")
                
            return None
            
        self.callback_refs['state'] = stateCallback
        
        # TinyBook callback
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_double, c_int, c_int)
        def tinyBookCallBack(assetId, price, qtd, side):
            self.callbacks['tiny_book'] += 1
            
            ticker = self.target_ticker
            
            # Validar preço
            if price > 0 and price < 10000:
                if side == 0:  # Bid
                    self.last_bid = price
                else:  # Ask
                    self.last_ask = price
                
                # Log apenas primeiros ou a cada 100
                if self.callbacks['tiny_book'] <= 10 or self.callbacks['tiny_book'] % 100 == 0:
                    side_str = "BID" if side == 0 else "ASK"
                    print(f'[TINY_BOOK #{self.callbacks["tiny_book"]}] {ticker} {side_str}: R$ {price:.2f} x {qtd}')
            
            return None
            
        self.callback_refs['tiny_book'] = tinyBookCallBack
        
        # Price Book callback V2
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_int, c_int, c_int, c_double, c_int, c_double, POINTER(c_int), POINTER(c_int))
        def priceBookCallback(assetId, nAction, nPosition, Side, sPrice, nQtd, nCount, pArraySell, pArrayBuy):
            self.callbacks['price_book'] += 1
            
            ticker = self.target_ticker
            
            # Validar dados
            if sPrice > 0 and sPrice < 10000 and nQtd > 0:
                if Side == 0:  # Bid
                    self.last_bid = sPrice
                else:  # Ask
                    self.last_ask = sPrice
                    
                if self.callbacks['price_book'] <= 10 or self.callbacks['price_book'] % 100 == 0:
                    print(f'[PRICE_BOOK #{self.callbacks["price_book"]}] Price={sPrice:.2f} Qty={nQtd}')
            
            return None
            
        self.callback_refs['price_book'] = priceBookCallback
        
        # Offer Book callback V2
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_int, c_int, c_int, c_int, c_int, c_longlong, c_double, c_int, c_int, c_int, c_int, c_int,
                   c_wchar_p, POINTER(c_ubyte), POINTER(c_ubyte))
        def offerBookCallback(assetId, nAction, nPosition, Side, nQtd, nAgent, nOfferID, sPrice, bHasPrice,
                             bHasQtd, bHasDate, bHasOfferID, bHasAgent, date, pArraySell, pArrayBuy):
            self.callbacks['offer_book'] += 1
            
            ticker = self.target_ticker
            
            # Validar dados - NÃO sobrescrever se sPrice for 0
            if bHasPrice and bHasQtd and sPrice > 1000 and sPrice < 10000 and nQtd > 0:
                if Side == 0 and nPosition == 0:  # Bid na posição 0 (melhor bid)
                    self.last_bid = sPrice
                elif Side == 1 and nPosition == 0:  # Ask na posição 0 (melhor ask)
                    self.last_ask = sPrice
                    
                if self.callbacks['offer_book'] <= 10 or self.callbacks['offer_book'] % 100 == 0:
                    side_str = "BID" if Side == 0 else "ASK"
                    print(f'[OFFER_BOOK #{self.callbacks["offer_book"]}] {side_str} @ R$ {sPrice:.2f} x {nQtd}')
            
            return None
            
        self.callback_refs['offer_book'] = offerBookCallback
        
    def _wait_login(self):
        """Aguarda login completo"""
        print("[WAIT] Aguardando conexão completa...")
        
        timeout = 15  # 15 segundos
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            if self.bMarketConnected:
                print("[OK] Market conectado!")
                return True
                
            # Log periódico do status
            if int(time.time() - start_time) % 3 == 0:
                print(f"Status: Market={self.bMarketConnected}, Broker={self.bBrokerConnected}, Login={self.bConnectado}, Ativo={self.bAtivo}")
                
            time.sleep(0.1)
            
        return False
        
    def _setup_additional_callbacks(self):
        """Configura callbacks adicionais após login"""
        
        # SetNewTradeCallback
        if hasattr(self.dll, 'SetNewTradeCallback'):
            @WINFUNCTYPE(None, c_wchar_p, c_double, c_int, c_int, c_int)
            def tradeCallback(ticker, price, qty, buyer, seller):
                self.callbacks['trade'] += 1
                
                ticker_str = self.target_ticker
                
                if price > 0 and price < 10000:
                    self.last_trade_price = price
                    
                    if self.callbacks['trade'] <= 10 or self.callbacks['trade'] % 100 == 0:
                        print(f'[TRADE #{self.callbacks["trade"]}] @ R$ {price:.2f} x {qty}')
                
                return None
                
            self.callback_refs['trade'] = tradeCallback
            self.dll.SetNewTradeCallback(self.callback_refs['trade'])
            print("[OK] Trade callback registrado")
            
        # Re-registrar callbacks de book
        if hasattr(self.dll, 'SetTinyBookCallback'):
            self.dll.SetTinyBookCallback(self.callback_refs['tiny_book'])
            print("[OK] TinyBook callback re-registrado")
            
        if hasattr(self.dll, 'SetOfferBookCallbackV2'):
            self.dll.SetOfferBookCallbackV2(self.callback_refs['offer_book'])
            print("[OK] OfferBook V2 callback registrado")
            
        if hasattr(self.dll, 'SetPriceBookCallback'):
            self.dll.SetPriceBookCallback(self.callback_refs['price_book'])
            print("[OK] PriceBook callback registrado")
            
    def subscribe_wdo(self):
        """Subscreve WDOU25 (baseado no book_collector)"""
        try:
            ticker = self.target_ticker
            exchange = "F"
            
            print(f"\n[SUBSCRIBE] Subscrevendo {ticker} na bolsa {exchange}...")
            
            # SubscribeTicker
            result = self.dll.SubscribeTicker(c_wchar_p(ticker), c_wchar_p(exchange))
            print(f"SubscribeTicker({ticker}, {exchange}) = {result}")
            
            if result == 0:
                print(f"[OK] Subscrito a {ticker}/{exchange}")
                
            # SubscribeOfferBook
            if hasattr(self.dll, 'SubscribeOfferBook'):
                result = self.dll.SubscribeOfferBook(c_wchar_p(ticker), c_wchar_p(exchange))
                print(f"SubscribeOfferBook({ticker}, {exchange}) = {result}")
                
            # SubscribePriceBook
            if hasattr(self.dll, 'SubscribePriceBook'):
                result = self.dll.SubscribePriceBook(c_wchar_p(ticker), c_wchar_p(exchange))
                print(f"SubscribePriceBook({ticker}, {exchange}) = {result}")
                
            return True
                
        except Exception as e:
            print(f"[ERRO] Erro na subscrição: {e}")
            return False
            
    def run_test(self, duration=30):
        """Executa o teste por um período"""
        print(f"\n[TEST] Executando teste por {duration} segundos...")
        print("=" * 60)
        
        start_time = time.time()
        last_status = time.time()
        
        while (time.time() - start_time) < duration:
            # Status a cada 5 segundos
            if (time.time() - last_status) >= 5:
                total_callbacks = sum(self.callbacks.values())
                print(f"\n[STATUS] Total callbacks: {total_callbacks}")
                for key, value in self.callbacks.items():
                    if value > 0:
                        print(f"  {key:12}: {value:6}")
                
                if self.last_bid > 0 or self.last_ask > 0:
                    print(f"\n[PRECOS] Bid: {self.last_bid:.2f} | Ask: {self.last_ask:.2f} | Trade: {self.last_trade_price:.2f}")
                    print("[OK] RECEBENDO DADOS REAIS DO MERCADO!")
                else:
                    print("[AVISO] Ainda aguardando dados...")
                    
                last_status = time.time()
                
            time.sleep(0.1)
        
        # Resultado final
        print("\n" + "=" * 60)
        print("[RESULTADO FINAL]")
        print("=" * 60)
        
        total_callbacks = sum(self.callbacks.values())
        print(f"Total callbacks recebidos: {total_callbacks}")
        
        if self.last_bid > 0 and self.last_ask > 0:
            print(f"\n[SUCESSO] Sistema recebendo dados REAIS:")
            print(f"   Ultimo Bid: {self.last_bid:.2f}")
            print(f"   Ultimo Ask: {self.last_ask:.2f}")
            print(f"   Ultimo Trade: {self.last_trade_price:.2f}")
        else:
            print(f"\n[ERRO] Nao recebeu dados reais.")
            print("Possíveis causas:")
            print("1. Mercado fechado (horário: 9h-18h)")
            print("2. Símbolo incorreto ou expirado")
            print("3. Problema na conexão com a corretora")
            
        print("=" * 60)
        
    def disconnect(self):
        """Desconecta da DLL"""
        if self.dll and hasattr(self.dll, 'DLLFinalize'):
            self.dll.DLLFinalize()
            print("[OK] Desconectado")

def main():
    print("=" * 60)
    print("TESTE DE CONEXÃO - BASEADO NO BOOK_COLLECTOR")
    print("=" * 60)
    
    tester = BookConnectionTest()
    
    # Inicializar
    if tester.initialize():
        # Subscrever
        if tester.subscribe_wdo():
            # Executar teste
            tester.run_test(duration=30)
    
    # Desconectar
    tester.disconnect()
    
    print("\n[FIM] Teste concluído")

if __name__ == "__main__":
    main()