"""
Sistema de Produção V3 - Integração Gradual com Callbacks V2
Baseado no sistema mínimo que funciona, adicionando componentes gradualmente
"""

import os
import sys
import time
import logging
import threading
from ctypes import *
from datetime import datetime
from collections import deque
from dotenv import load_dotenv
import numpy as np

# Adicionar diretório ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Carregar configurações
load_dotenv('.env.production')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SystemV3')

# ==============================================================================
# ESTRUTURAS CTYPES
# ==============================================================================

class TAssetID(Structure):
    _fields_ = [
        ("pwcTicker", c_wchar_p),
        ("pwcBolsa", c_wchar_p),
        ("nFeed", c_int)
    ]

# ==============================================================================
# SISTEMA PRINCIPAL
# ==============================================================================

class ProductionSystemV3:
    def __init__(self):
        """Inicializa o sistema de produção V3"""
        self.logger = logging.getLogger('ProductionSystemV3')
        
        # Estado do sistema
        self.running = False
        self.dll = None
        self.callbacks_refs = []  # Manter referências aos callbacks
        
        # Buffers de dados
        self.book_buffer = deque(maxlen=500)
        self.book_lock = threading.RLock()
        self.tick_buffer = deque(maxlen=500)
        self.tick_lock = threading.RLock()
        
        # Estado de conexão
        self.states = {
            'market_connected': False,
            'book_count': 0,
            'tick_count': 0,
            'last_price': 0.0
        }
        
        # Monitoramento de posição
        self.position = {
            'has_position': False,
            'side': None,
            'quantity': 0,
            'entry_price': 0.0,
            'current_pnl': 0.0
        }
        
        # Trading
        self.enable_trading = os.getenv('ENABLE_TRADING', 'false').lower() == 'true'
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE', '0.60'))
        
        self.logger.info("=" * 80)
        self.logger.info("SISTEMA DE PRODUÇÃO V3 - CALLBACKS V2 INTEGRADOS")
        self.logger.info("=" * 80)
        self.logger.info(f"Trading: {'ATIVO' if self.enable_trading else 'SIMULADO'}")
        self.logger.info(f"Confiança mínima: {self.min_confidence*100:.0f}%")
        
    def initialize_dll(self):
        """Inicializa a DLL e conexão"""
        try:
            # Carregar DLL
            dll_path = r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
            self.dll = WinDLL(dll_path)
            self.logger.info("[OK] DLL carregada")
            
            # Configurar servidor
            self.dll.SetServerAndPort(
                c_wchar_p("producao.nelogica.com.br"),
                c_wchar_p("8184")
            )
            self.logger.info("[OK] Servidor configurado")
            
            # Configurar callbacks
            self._setup_callbacks()
            
            # Inicializar login
            username = os.getenv('PROFIT_USERNAME', '')
            password = os.getenv('PROFIT_PASSWORD', '')
            key = os.getenv('PROFIT_KEY', '')
            
            # Callbacks vazios
            empty = WINFUNCTYPE(None)()
            
            result = self.dll.DLLInitializeLogin(
                c_wchar_p(key), c_wchar_p(username), c_wchar_p(password),
                self.callbacks_refs[0],  # state_callback
                empty, empty, empty,
                empty, empty, empty, empty,
                empty, empty, empty
            )
            
            self.logger.info(f"[OK] DLL inicializada: {result}")
            
            # Aguardar conexão
            for i in range(15):
                if self.states['market_connected']:
                    self.logger.info("[OK] Market Data conectado!")
                    break
                time.sleep(1)
                if i % 3 == 0:
                    self.logger.info(f"Aguardando conexão... ({i}/15s)")
            
            # Registrar callbacks V2
            self._register_v2_callbacks()
            
            # Subscrever ao book
            self.dll.SubscribeOfferBook(c_wchar_p("WDOU25"), c_wchar_p("F"))
            self.logger.info("[OK] Subscrito ao book de WDOU25")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro na inicialização: {e}")
            return False
    
    def _setup_callbacks(self):
        """Configura callbacks básicos"""
        
        # Callback de estado
        @WINFUNCTYPE(None, c_int, c_int)
        def state_callback(conn_type, result):
            if conn_type == 2 and result == 4:
                self.states['market_connected'] = True
                self.logger.info("[STATE] Market Data conectado")
        
        # Callback de tick/trade
        @WINFUNCTYPE(None, TAssetID, c_wchar_p, c_double, c_longlong, 
                    c_int, c_int, c_int, c_int)
        def trade_callback(asset_id, date, price, volume, 
                          qtd_trades, side, buyer, seller):
            try:
                if price > 0:
                    self.states['last_price'] = price
                    self.states['tick_count'] += 1
                    
                    tick_data = {
                        'timestamp': datetime.now(),
                        'price': price,
                        'volume': volume,
                        'side': side
                    }
                    
                    with self.tick_lock:
                        self.tick_buffer.append(tick_data)
                    
                    # Atualizar P&L se tiver posição
                    if self.position['has_position']:
                        self._update_pnl(price)
                        
            except Exception as e:
                self.logger.error(f"Erro no trade callback: {e}")
        
        # Adicionar às referências
        self.callbacks_refs.append(state_callback)
        self.callbacks_refs.append(trade_callback)
        
        self.logger.info("[OK] Callbacks básicos configurados")
    
    def _register_v2_callbacks(self):
        """Registra callbacks V2 (CFUNCTYPE)"""
        
        # Callback V2 para book de ofertas
        @CFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
                  c_longlong, c_double, c_char, c_char, c_char, c_char,
                  c_char, c_wchar_p, c_void_p, c_void_p)
        def offer_book_v2(asset_id, action, position, side, qtd, agent,
                         offer_id, price, has_price, has_qtd, has_date,
                         has_offer_id, has_agent, date_ptr, array_sell, array_buy):
            try:
                # Processar apenas dados com preço válido
                if has_price and price > 0:
                    book_data = {
                        'timestamp': datetime.now(),
                        'side': 'BUY' if side == 0 else 'SELL',
                        'price': price,
                        'quantity': qtd,
                        'action': action,
                        'position': position
                    }
                    
                    with self.book_lock:
                        self.book_buffer.append(book_data)
                        self.states['book_count'] += 1
                    
                    # Atualizar último preço
                    if self.states['book_count'] <= 5:
                        self.logger.info(f"[BOOK] {book_data['side']}: {price:.2f} x {qtd}")
                
                return 0
            except Exception as e:
                self.logger.error(f"Erro no book callback v2: {e}")
                return 0
        
        # Adicionar à lista de referências
        self.callbacks_refs.append(offer_book_v2)
        
        # Registrar na DLL
        self.dll.SetOfferBookCallbackV2.restype = c_int
        result = self.dll.SetOfferBookCallbackV2(offer_book_v2)
        
        if result == 0:
            self.logger.info("[OK] SetOfferBookCallbackV2 registrado")
        else:
            self.logger.warning(f"[WARN] SetOfferBookCallbackV2 retornou: {result}")
    
    def _update_pnl(self, current_price):
        """Atualiza P&L da posição"""
        if self.position['has_position']:
            entry = self.position['entry_price']
            qty = self.position['quantity']
            
            if self.position['side'] == 'LONG':
                pnl = (current_price - entry) * qty
            else:
                pnl = (entry - current_price) * qty
            
            self.position['current_pnl'] = pnl
    
    def _calculate_features(self):
        """Calcula features básicas do book"""
        try:
            with self.book_lock:
                if len(self.book_buffer) < 20:
                    return None
                
                # Separar bids e asks
                recent_data = list(self.book_buffer)[-100:]
                bids = [d for d in recent_data if d['side'] == 'BUY']
                asks = [d for d in recent_data if d['side'] == 'SELL']
                
                if not bids or not asks:
                    return None
                
                # Features básicas
                best_bid = max([b['price'] for b in bids]) if bids else 0
                best_ask = min([a['price'] for a in asks]) if asks else 0
                spread = best_ask - best_bid if best_bid > 0 and best_ask > 0 else 0
                
                bid_volume = sum([b['quantity'] for b in bids])
                ask_volume = sum([a['quantity'] for a in asks])
                imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0
                
                return {
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'spread': spread,
                    'imbalance': imbalance,
                    'bid_volume': bid_volume,
                    'ask_volume': ask_volume
                }
                
        except Exception as e:
            self.logger.error(f"Erro calculando features: {e}")
            return None
    
    def _make_prediction(self, features):
        """Faz predição simples baseada em imbalance"""
        if not features:
            return 0, 0.0
        
        # Estratégia simples: seguir o imbalance forte
        imbalance = features['imbalance']
        
        if abs(imbalance) > 0.3:  # Imbalance significativo
            signal = 1 if imbalance > 0 else -1
            confidence = min(abs(imbalance) * 1.5, 0.8)  # Confiança baseada no imbalance
            return signal, confidence
        
        return 0, 0.0
    
    def run(self):
        """Loop principal do sistema"""
        self.running = True
        
        # Threads de monitoramento
        def metrics_thread():
            """Thread para mostrar métricas"""
            while self.running:
                time.sleep(10)
                
                with self.book_lock:
                    book_size = len(self.book_buffer)
                    book_count = self.states['book_count']
                
                with self.tick_lock:
                    tick_size = len(self.tick_buffer)
                    tick_count = self.states['tick_count']
                
                last_price = self.states['last_price']
                
                self.logger.info(f"[METRICS] Book: {book_size}/500 ({book_count} total) | "
                               f"Ticks: {tick_size}/500 ({tick_count} total) | "
                               f"Preço: {last_price:.2f}")
                
                # Mostrar posição se houver
                if self.position['has_position']:
                    self.logger.info(f"[POSITION] {self.position['side']} {self.position['quantity']} @ "
                                   f"{self.position['entry_price']:.2f} | P&L: {self.position['current_pnl']:.2f}")
        
        # Iniciar thread de métricas
        t_metrics = threading.Thread(target=metrics_thread, daemon=True)
        t_metrics.start()
        
        # Loop principal de trading
        self.logger.info("\n[SISTEMA] Iniciando loop principal...")
        self.logger.info("Pressione Ctrl+C para parar\n")
        
        try:
            iteration = 0
            while self.running:
                iteration += 1
                
                # Calcular features a cada 5 segundos
                if iteration % 50 == 0:  # 5 segundos (0.1s * 50)
                    features = self._calculate_features()
                    
                    if features:
                        signal, confidence = self._make_prediction(features)
                        
                        if signal != 0 and confidence >= self.min_confidence:
                            side = "BUY" if signal > 0 else "SELL"
                            self.logger.info(f"[SIGNAL] {side} com confiança {confidence*100:.1f}%")
                            
                            # Simular entrada na posição
                            if not self.position['has_position']:
                                self.position['has_position'] = True
                                self.position['side'] = 'LONG' if signal > 0 else 'SHORT'
                                self.position['quantity'] = 1
                                self.position['entry_price'] = features['best_ask'] if signal > 0 else features['best_bid']
                                
                                self.logger.info(f"[TRADE] {'COMPRA' if signal > 0 else 'VENDA'} simulada @ "
                                               f"{self.position['entry_price']:.2f}")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            self.logger.info("\n[INFO] Parando sistema...")
        finally:
            self.stop()
    
    def stop(self):
        """Para o sistema"""
        self.running = False
        
        if self.dll:
            self.logger.info("Finalizando DLL...")
            self.dll.DLLFinalize()
        
        self.logger.info(f"\n[FINAL] Book msgs: {self.states['book_count']} | "
                        f"Tick msgs: {self.states['tick_count']}")
        self.logger.info("Sistema finalizado com sucesso!")

# ==============================================================================
# MAIN
# ==============================================================================

def main():
    """Função principal"""
    system = ProductionSystemV3()
    
    if system.initialize_dll():
        system.run()
    else:
        logger.error("Falha na inicialização do sistema")
        sys.exit(1)

if __name__ == "__main__":
    main()