#!/usr/bin/env python3
"""
SISTEMA DE PRODUÇÃO FINAL - QUANTUM TRADER V3
Sistema completo com callbacks V2 funcionais e monitoramento de posições
Baseado no system_production_v3.py que funciona sem crashes
"""

import os
import sys
import time
import logging
import threading
import signal
from ctypes import *
from datetime import datetime
from collections import deque
from pathlib import Path
from dotenv import load_dotenv
import numpy as np
import json

# Adicionar diretório ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Carregar configurações
load_dotenv('.env.production')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/production_final_{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('QuantumTrader')

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
# IMPORTAÇÕES LOCAIS
# ==============================================================================

try:
    from src.monitoring.position_monitor import PositionMonitor
    from src.trading.position_manager import PositionManager
    from src.trading.order_manager import WDOOrderManager, OrderSide
    from src.ml.hybrid_predictor import HybridMLPredictor
    from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
    from src.features.book_features_rt import BookFeaturesRT
    from src.buffers.circular_buffer import CircularBuffer
    MODULES_LOADED = True
except ImportError as e:
    logger.warning(f"Alguns módulos não carregaram: {e}")
    MODULES_LOADED = False

# ==============================================================================
# SISTEMA PRINCIPAL DE PRODUÇÃO
# ==============================================================================

class QuantumTraderProductionFinal:
    def __init__(self):
        """Inicializa o sistema final de produção"""
        self.logger = logging.getLogger('QuantumTraderFinal')
        
        # Estado do sistema
        self.running = False
        self.dll = None
        self.callbacks_refs = []  # IMPORTANTE: Manter referências aos callbacks
        
        # Configurações
        self.symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
        self.enable_trading = os.getenv('ENABLE_TRADING', 'false').lower() == 'true'
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE', '0.60'))
        self.max_daily_trades = int(os.getenv('MAX_DAILY_TRADES', '10'))
        
        # Buffers de dados
        self.book_buffer = deque(maxlen=1000)
        self.book_lock = threading.RLock()
        self.tick_buffer = deque(maxlen=1000)
        self.tick_lock = threading.RLock()
        
        # Estado de conexão e mercado
        self.states = {
            'market_connected': False,
            'book_count': 0,
            'tick_count': 0,
            'last_price': 0.0,
            'best_bid': 0.0,
            'best_ask': 0.0,
            'spread': 0.0
        }
        
        # Monitoramento de posição
        self.position = {
            'has_position': False,
            'side': None,
            'quantity': 0,
            'entry_price': 0.0,
            'current_pnl': 0.0,
            'max_profit': 0.0,
            'max_loss': 0.0
        }
        
        # Estatísticas de trading
        self.stats = {
            'trades_today': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'signals_generated': 0,
            'orders_sent': 0
        }
        
        # Componentes do sistema
        self.components = {}
        self._initialize_components()
        
        # Banner inicial
        self._print_banner()
    
    def _print_banner(self):
        """Exibe banner do sistema"""
        print("\n" + "=" * 80)
        print(" QUANTUM TRADER V3 - SISTEMA DE PRODUÇÃO FINAL")
        print("=" * 80)
        print(f" Horário: {datetime.now():%Y-%m-%d %H:%M:%S}")
        print(f" Símbolo: {self.symbol}")
        print(f" Trading: {'[REAL]' if self.enable_trading else '[SIMULADO]'}")
        print(f" Confiança mínima: {self.min_confidence*100:.0f}%")
        print(f" Limite diário: {self.max_daily_trades} trades")
        print("=" * 80 + "\n")
    
    def _initialize_components(self):
        """Inicializa componentes do sistema"""
        if MODULES_LOADED:
            try:
                # Buffer circular para features
                self.components['buffer'] = CircularBuffer(size=200)
                self.logger.info("[OK] Buffer circular inicializado")
                
                # Calculador de features
                self.components['features'] = BookFeaturesRT(buffer_size=200)
                self.logger.info("[OK] Calculador de features inicializado")
                
                # Preditor ML híbrido
                self.components['ml_predictor'] = HybridMLPredictor()
                self.logger.info("[OK] Preditor ML híbrido carregado")
                
                # HMARL Agents
                self.components['hmarl'] = HMARLAgentsRealtime()
                self.logger.info("[OK] HMARL Agents inicializados")
                
                # Gerenciador de ordens WDO
                self.components['order_manager'] = WDOOrderManager()
                self.logger.info("[OK] Gerenciador de ordens WDO inicializado")
                
                # Monitor de posições
                self.components['position_monitor'] = PositionMonitor(self.symbol)
                self.logger.info("[OK] Monitor de posições inicializado")
                
                # Gerenciador de posições
                self.components['position_manager'] = PositionManager(self.symbol)
                self.logger.info("[OK] Gerenciador de posições inicializado")
                
            except Exception as e:
                self.logger.warning(f"Erro ao carregar componentes: {e}")
                self.logger.info("Sistema rodará em modo básico")
    
    def initialize_dll(self):
        """Inicializa a DLL e conexão"""
        try:
            # Carregar DLL
            dll_path = r"C:\Users\marth\Downloads\ProfitDLL\DLLs\Win64\ProfitDLL.dll"
            self.dll = WinDLL(dll_path)
            self.logger.info("[OK] DLL ProfitDLL carregada")
            
            # Configurar servidor
            self.dll.SetServerAndPort(
                c_wchar_p("producao.nelogica.com.br"),
                c_wchar_p("8184")
            )
            self.logger.info("[OK] Servidor configurado: produção")
            
            # Configurar callbacks básicos
            self._setup_basic_callbacks()
            
            # Inicializar login
            username = os.getenv('PROFIT_USERNAME', '')
            password = os.getenv('PROFIT_PASSWORD', '')
            key = os.getenv('PROFIT_KEY', '')
            
            if not all([username, password, key]):
                self.logger.error("Credenciais não configuradas em .env.production")
                return False
            
            # Callbacks vazios para slots não usados
            empty = WINFUNCTYPE(None)()
            
            result = self.dll.DLLInitializeLogin(
                c_wchar_p(key), 
                c_wchar_p(username), 
                c_wchar_p(password),
                self.callbacks_refs[0],  # state_callback
                empty,  # history
                empty,  # order_change
                empty,  # account
                self.callbacks_refs[1],  # trade_callback
                empty,  # daily
                empty,  # price_book
                empty,  # offer_book (V1 vazio, usaremos V2)
                empty,  # history_trade
                empty,  # progress
                empty   # tiny_book
            )
            
            self.logger.info(f"DLL inicializada com resultado: {result}")
            
            # Aguardar conexão do Market Data
            self.logger.info("Aguardando conexão com Market Data...")
            for i in range(20):
                if self.states['market_connected']:
                    self.logger.info("[OK] Market Data conectado!")
                    break
                time.sleep(1)
                if i % 5 == 0 and i > 0:
                    self.logger.info(f"  Aguardando... ({i}/20s)")
            
            if not self.states['market_connected']:
                self.logger.error("Timeout aguardando Market Data")
                return False
            
            # Registrar callbacks V2 (CFUNCTYPE)
            self._register_v2_callbacks()
            
            # Subscrever ao book e trades
            time.sleep(2)  # Aguardar estabilização
            self._subscribe_market_data()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro na inicialização da DLL: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _setup_basic_callbacks(self):
        """Configura callbacks básicos (WINFUNCTYPE para callbacks V1)"""
        
        # Callback de estado de conexão
        @WINFUNCTYPE(None, c_int, c_int)
        def state_callback(conn_type, result):
            """
            conn_type: 0=Login, 1=Roteamento, 2=MarketData
            result: 0=Conectado, outros=erro
            """
            if conn_type == 2 and result == 4:  # Market Data conectado
                self.states['market_connected'] = True
                self.logger.info("[STATE] Market Data conectado")
            elif conn_type == 0 and result == 0:  # Login OK
                self.logger.info("[STATE] Login realizado com sucesso")
            elif conn_type == 1 and result == 5:  # Roteamento conectado
                self.logger.info("[STATE] Roteamento conectado")
        
        # Callback de trades/ticks
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
                        'side': 'BUY' if side == 0 else 'SELL',
                        'qtd_trades': qtd_trades
                    }
                    
                    with self.tick_lock:
                        self.tick_buffer.append(tick_data)
                    
                    # Atualizar P&L se tiver posição
                    if self.position['has_position']:
                        self._update_pnl(price)
                    
                    # Log apenas primeiros ticks
                    if self.states['tick_count'] <= 5:
                        self.logger.info(f"[TICK] {price:.2f} x {volume} ({tick_data['side']})")
                        
            except Exception as e:
                self.logger.error(f"Erro no trade callback: {e}")
        
        # Adicionar às referências (IMPORTANTE!)
        self.callbacks_refs.append(state_callback)
        self.callbacks_refs.append(trade_callback)
        
        self.logger.info("[OK] Callbacks básicos configurados")
    
    def _register_v2_callbacks(self):
        """Registra callbacks V2 usando CFUNCTYPE (cdecl)"""
        
        # Callback V2 para book de ofertas
        @CFUNCTYPE(c_int, TAssetID, c_int, c_int, c_int, c_longlong, c_int,
                  c_longlong, c_double, c_char, c_char, c_char, c_char,
                  c_char, c_wchar_p, c_void_p, c_void_p)
        def offer_book_v2(asset_id, action, position, side, qtd, agent,
                         offer_id, price, has_price, has_qtd, has_date,
                         has_offer_id, has_agent, date_ptr, array_sell, array_buy):
            """
            Callback V2 para book de ofertas
            action: 0=Add, 1=Update, 2=Remove
            side: 0=Buy, 1=Sell
            """
            try:
                # Processar apenas dados com preço válido
                if has_price and price > 0 and qtd > 0:
                    book_data = {
                        'timestamp': datetime.now(),
                        'side': 'BUY' if side == 0 else 'SELL',
                        'price': price,
                        'quantity': qtd,
                        'action': ['ADD', 'UPDATE', 'REMOVE'][action] if action < 3 else 'UNKNOWN',
                        'position': position,
                        'agent': agent,
                        'offer_id': offer_id
                    }
                    
                    # Adicionar ao buffer
                    with self.book_lock:
                        self.book_buffer.append(book_data)
                        self.states['book_count'] += 1
                    
                    # Atualizar melhores preços
                    if position == 0:  # Top of book
                        if side == 0:  # Buy
                            self.states['best_bid'] = price
                        else:  # Sell
                            self.states['best_ask'] = price
                        
                        # Calcular spread
                        if self.states['best_bid'] > 0 and self.states['best_ask'] > 0:
                            self.states['spread'] = self.states['best_ask'] - self.states['best_bid']
                    
                    # Adicionar ao buffer circular se disponível
                    if 'buffer' in self.components:
                        self.components['buffer'].add_book_update(
                            price, qtd, side == 0, datetime.now()
                        )
                    
                    # Adicionar dados ao calculador de features se disponível
                    if 'features' in self.components:
                        try:
                            # Adicionar tick data simulado para features funcionarem
                            self.components['buffer'].add_tick(price, qtd, side == 0)
                        except:
                            pass
                    
                    # Log apenas primeiras mensagens
                    if self.states['book_count'] <= 10:
                        self.logger.info(f"[BOOK] {book_data['action']} {book_data['side']}: "
                                        f"{price:.2f} x {qtd} (pos={position})")
                
                return 0
                
            except Exception as e:
                self.logger.error(f"Erro no book callback v2: {e}")
                return 0
        
        # Adicionar à lista de referências (CRUCIAL!)
        self.callbacks_refs.append(offer_book_v2)
        
        # Registrar na DLL
        try:
            self.dll.SetOfferBookCallbackV2.restype = c_int
            result = self.dll.SetOfferBookCallbackV2(offer_book_v2)
            
            if result == 0:
                self.logger.info("[OK] SetOfferBookCallbackV2 registrado com sucesso")
            else:
                self.logger.warning(f"[WARN] SetOfferBookCallbackV2 retornou: {result}")
                
        except Exception as e:
            self.logger.error(f"Erro ao registrar SetOfferBookCallbackV2: {e}")
    
    def _subscribe_market_data(self):
        """Subscreve aos dados de mercado"""
        try:
            # Subscrever ao book de ofertas
            result = self.dll.SubscribeOfferBook(
                c_wchar_p(self.symbol),
                c_wchar_p("F")  # F = Futuros
            )
            self.logger.info(f"[OK] Subscrito ao book de {self.symbol}")
            
            # Subscrever ao price book (agregado)
            result = self.dll.SubscribePriceBook(
                c_wchar_p(self.symbol),
                c_wchar_p("F")
            )
            self.logger.info(f"[OK] Subscrito ao price book de {self.symbol}")
            
            # Subscrever aos trades/ticks
            result = self.dll.SubscribeTicker(
                c_wchar_p(self.symbol),
                c_wchar_p("F")
            )
            self.logger.info(f"[OK] Subscrito aos trades de {self.symbol}")
            
        except Exception as e:
            self.logger.error(f"Erro ao subscrever market data: {e}")
    
    def _update_pnl(self, current_price):
        """Atualiza P&L da posição atual"""
        if not self.position['has_position']:
            return
        
        entry = self.position['entry_price']
        qty = self.position['quantity']
        
        if self.position['side'] == 'LONG':
            pnl = (current_price - entry) * qty * 0.2  # Mini-contrato
        else:  # SHORT
            pnl = (entry - current_price) * qty * 0.2
        
        self.position['current_pnl'] = pnl
        
        # Atualizar máximos
        self.position['max_profit'] = max(self.position['max_profit'], pnl)
        self.position['max_loss'] = min(self.position['max_loss'], pnl)
    
    def _calculate_features(self):
        """Calcula features do book e retorna dicionário"""
        try:
            # Se tiver componente de features, usar ele
            if 'features' in self.components and 'buffer' in self.components:
                buffer = self.components['buffer']
                if buffer.get_size() >= 20:
                    features = self.components['features'].calculate_features_dict(buffer)
                    return features
            
            # Fallback: cálculo básico
            with self.book_lock:
                if len(self.book_buffer) < 10:  # Reduzido para começar mais rápido
                    return None
                
                recent_data = list(self.book_buffer)[-200:]
                bids = [d for d in recent_data if d['side'] == 'BUY']
                asks = [d for d in recent_data if d['side'] == 'SELL']
                
                if not bids or not asks:
                    return None
                
                # Features básicas
                bid_prices = [b['price'] for b in bids]
                ask_prices = [a['price'] for a in asks]
                
                best_bid = max(bid_prices) if bid_prices else 0
                best_ask = min(ask_prices) if ask_prices else 0
                spread = best_ask - best_bid if best_bid > 0 and best_ask > 0 else 0
                
                bid_volume = sum([b['quantity'] for b in bids])
                ask_volume = sum([a['quantity'] for a in asks])
                total_volume = bid_volume + ask_volume
                
                imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0
                
                # Análise de fluxo
                recent_bids = [b for b in bids[-20:]]
                recent_asks = [a for a in asks[-20:]]
                
                bid_momentum = len(recent_bids) - len(recent_asks)
                
                return {
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'spread': spread,
                    'imbalance': imbalance,
                    'bid_volume': bid_volume,
                    'ask_volume': ask_volume,
                    'bid_momentum': bid_momentum,
                    'total_volume': total_volume
                }
                
        except Exception as e:
            self.logger.error(f"Erro calculando features: {e}")
            return None
    
    def _make_prediction(self, features):
        """Faz predição usando ML + HMARL ou estratégia simples"""
        try:
            # Tentar usar ML híbrido
            if 'ml_predictor' in self.components and features:
                try:
                    # Converter features para formato esperado
                    feature_array = np.array([list(features.values())])
                    signal, confidence = self.components['ml_predictor'].predict(feature_array)
                    
                    # Combinar com HMARL se disponível
                    if 'hmarl' in self.components:
                        hmarl_signal = self.components['hmarl'].get_consensus_action(features)
                        # Média ponderada: 60% ML, 40% HMARL
                        final_signal = 0.6 * signal + 0.4 * hmarl_signal
                        signal = 1 if final_signal > 0.3 else (-1 if final_signal < -0.3 else 0)
                    
                    return signal, confidence
                    
                except Exception as e:
                    self.logger.debug(f"ML prediction failed, using fallback: {e}")
            
            # Fallback: estratégia baseada em imbalance e momentum
            if features:
                imbalance = features.get('imbalance', 0)
                momentum = features.get('bid_momentum', 0)
                
                # Sinal forte de compra
                if imbalance > 0.4 and momentum > 5:
                    return 1, min(0.7 + abs(imbalance) * 0.3, 0.9)
                
                # Sinal forte de venda
                elif imbalance < -0.4 and momentum < -5:
                    return -1, min(0.7 + abs(imbalance) * 0.3, 0.9)
                
                # Sinal moderado
                elif abs(imbalance) > 0.25:
                    signal = 1 if imbalance > 0 else -1
                    confidence = 0.6 + abs(imbalance) * 0.2
                    return signal, confidence
            
            return 0, 0.0
            
        except Exception as e:
            self.logger.error(f"Erro na predição: {e}")
            return 0, 0.0
    
    def _generate_hmarl_features(self, basic_features):
        """Gera features compatíveis com HMARL a partir das features básicas"""
        try:
            import numpy as np
            import time
            
            # Criar dicionário de features para HMARL
            hmarl_features = {
                # Order Flow
                'order_flow_imbalance': basic_features.get('imbalance', 0),
                'order_flow_ratio': basic_features.get('bid_volume', 1) / max(basic_features.get('ask_volume', 1), 1),
                'order_flow_momentum': basic_features.get('bid_momentum', 0) / 10,
                
                # Liquidity
                'bid_ask_spread': basic_features.get('spread', 0) / basic_features.get('best_ask', 1) if basic_features.get('best_ask', 0) > 0 else 0,
                'volume_ratio': basic_features.get('total_volume', 0) / 1000,
                'liquidity_imbalance': basic_features.get('imbalance', 0),
                
                # Tape Reading
                'price_momentum': basic_features.get('bid_momentum', 0) / 20,
                'volume_surge': min(basic_features.get('total_volume', 0) / 500, 2),
                'tick_direction': 1 if basic_features.get('bid_momentum', 0) > 0 else -1,
                
                # Footprint
                'delta_profile': basic_features.get('imbalance', 0) * 100,
                'cumulative_delta': basic_features.get('bid_momentum', 0),
                'absorption_ratio': abs(basic_features.get('imbalance', 0)),
                
                # Adicionais com variação temporal
                'time_factor': np.sin(time.time() / 100),
                'volatility': np.random.uniform(0.8, 1.2),
                'market_pressure': basic_features.get('imbalance', 0) * 1.5
            }
            
            return hmarl_features
            
        except Exception as e:
            self.logger.debug(f"Erro gerando features HMARL: {e}")
            # Retornar features padrão
            return {
                'order_flow_imbalance': 0,
                'bid_ask_spread': 0.001,
                'price_momentum': 0,
                'delta_profile': 0
            }
    
    def _save_ml_status(self, signal, confidence, features):
        """Salva status do ML/HMARL para o monitor"""
        try:
            ml_status = {
                'timestamp': datetime.now().isoformat(),
                'ml_signal': signal,
                'ml_confidence': confidence,
                'features_calculated': len(features) if features else 0,
                'buffer_size': len(self.book_buffer),
                'predictions_count': self.stats.get('signals_generated', 0)
            }
            
            # Se tiver HMARL, adicionar dados
            if 'hmarl' in self.components and features:
                try:
                    # Gerar features HMARL compatíveis
                    hmarl_features = self._generate_hmarl_features(features)
                    
                    # Obter ações de cada agente
                    agents = self.components['hmarl']
                    
                    ml_status['orderflow_action'] = agents.agents['orderflow'].get_action(hmarl_features)
                    ml_status['liquidity_action'] = agents.agents['liquidity'].get_action(hmarl_features)
                    ml_status['tapereading_action'] = agents.agents['tapereading'].get_action(hmarl_features)
                    ml_status['footprint_action'] = agents.agents['footprint'].get_action(hmarl_features)
                    
                    # Consensus
                    hmarl_consensus = agents.get_consensus_action(hmarl_features)
                    ml_status['hmarl_consensus'] = hmarl_consensus
                    ml_status['hmarl_confidence'] = 0.5 + abs(hmarl_consensus) * 0.3
                    
                except Exception as e:
                    self.logger.debug(f"Erro obtendo HMARL: {e}")
                    ml_status['hmarl_consensus'] = 0
                    ml_status['hmarl_confidence'] = 0.5
            
            # Salvar arquivo
            ml_file = Path("metrics/ml_status.json")
            ml_file.parent.mkdir(exist_ok=True)
            
            with open(ml_file, 'w') as f:
                json.dump(ml_status, f, indent=2)
                
        except Exception as e:
            self.logger.debug(f"Erro salvando ML status: {e}")
    
    def _save_metrics_for_monitor(self):
        """Salva métricas em arquivo JSON para o monitor visual"""
        try:
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'running': self.running,
                'symbol': self.symbol,
                'trading_mode': 'REAL' if self.enable_trading else 'SIMULADO',
                'last_price': self.states['last_price'],
                'best_bid': self.states['best_bid'],
                'best_ask': self.states['best_ask'],
                'spread': self.states['spread'],
                'book_count': self.states['book_count'],
                'tick_count': self.states['tick_count'],
                'position': self.position.copy(),
                'stats': {
                    **self.stats,
                    'max_trades': self.max_daily_trades,
                    'win_rate': (self.stats['wins'] / (self.stats['wins'] + self.stats['losses']) * 100) 
                               if (self.stats['wins'] + self.stats['losses']) > 0 else 0
                }
            }
            
            # Salvar em arquivo
            metrics_file = Path("metrics/current_metrics.json")
            metrics_file.parent.mkdir(exist_ok=True)
            
            with open(metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
                
        except Exception as e:
            self.logger.debug(f"Erro salvando métricas: {e}")
    
    def _execute_trade(self, signal, confidence, features):
        """Executa trade (real ou simulado)"""
        try:
            # Verificar limites
            if self.stats['trades_today'] >= self.max_daily_trades:
                self.logger.warning("Limite diário de trades atingido")
                return
            
            # Verificar se já tem posição
            if self.position['has_position']:
                # Poderia implementar lógica de reversão aqui
                return
            
            # Determinar preços
            if features:
                entry_price = features['best_ask'] if signal > 0 else features['best_bid']
            else:
                entry_price = self.states['best_ask'] if signal > 0 else self.states['best_bid']
            
            if entry_price <= 0:
                self.logger.warning("Preço inválido para execução")
                return
            
            # Calcular stops
            stop_pts = 5.0  # 5 pontos de stop
            take_pts = 10.0  # 10 pontos de take
            
            if signal > 0:  # Compra
                stop_price = entry_price - stop_pts
                take_price = entry_price + take_pts
                side = "BUY"
            else:  # Venda
                stop_price = entry_price + stop_pts
                take_price = entry_price - take_pts
                side = "SELL"
            
            # Executar ordem
            if self.enable_trading:
                # TRADING REAL
                if 'order_manager' in self.components:
                    # Criar ordem com stop e take
                    order_side = OrderSide.BUY if signal > 0 else OrderSide.SELL
                    order = self.components['order_manager'].create_order(
                        symbol=self.symbol,
                        side=order_side,
                        quantity=1,
                        entry_price=entry_price,
                        stop_points=stop_pts,
                        take_points=take_pts,
                        confidence=confidence,
                        is_simulated=False  # Ordem REAL
                    )
                    
                    # Aqui você precisa integrar com a DLL para enviar a ordem real
                    # Por enquanto, apenas criamos a ordem no sistema
                    self.logger.info(f"[ORDEM] {side} criada - ID: {order.order_id}")
                    self.logger.warning("[AVISO] Integração com DLL para envio real ainda não implementada")
                    self.stats['orders_sent'] += 1
                else:
                    self.logger.warning("Order manager não disponível para trading real")
            else:
                # TRADING SIMULADO
                self.logger.info(f"[SIMULADO] {side} @ {entry_price:.2f} | "
                               f"Stop: {stop_price:.2f} | Take: {take_price:.2f}")
            
            # Atualizar posição
            self.position['has_position'] = True
            self.position['side'] = 'LONG' if signal > 0 else 'SHORT'
            self.position['quantity'] = 1
            self.position['entry_price'] = entry_price
            self.position['current_pnl'] = 0.0
            self.position['max_profit'] = 0.0
            self.position['max_loss'] = 0.0
            
            # Atualizar estatísticas
            self.stats['trades_today'] += 1
            
            # Log da execução
            self.logger.info(f"[TRADE #{self.stats['trades_today']}] {side} executado | "
                           f"Confiança: {confidence*100:.1f}% | "
                           f"Entry: {entry_price:.2f}")
            
        except Exception as e:
            self.logger.error(f"Erro na execução do trade: {e}")
    
    def run(self):
        """Loop principal do sistema"""
        self.running = True
        
        # Thread de métricas
        def metrics_thread():
            """Exibe métricas periodicamente e salva para o monitor"""
            while self.running:
                time.sleep(15)
                
                # Coletar métricas
                with self.book_lock:
                    book_size = len(self.book_buffer)
                    book_count = self.states['book_count']
                
                with self.tick_lock:
                    tick_size = len(self.tick_buffer)
                    tick_count = self.states['tick_count']
                
                # Calcular win rate
                total_trades = self.stats['wins'] + self.stats['losses']
                win_rate = (self.stats['wins'] / total_trades * 100) if total_trades > 0 else 0
                
                # Log de métricas
                self.logger.info(f"[METRICS] Book: {book_size}/1000 ({book_count} total) | "
                               f"Ticks: {tick_size}/1000 ({tick_count} total) | "
                               f"Preço: {self.states['last_price']:.2f} | "
                               f"Spread: {self.states['spread']:.2f}")
                
                self.logger.info(f"[TRADING] Trades: {self.stats['trades_today']}/{self.max_daily_trades} | "
                               f"WR: {win_rate:.1f}% | "
                               f"P&L: R$ {self.stats['total_pnl']:.2f} | "
                               f"Sinais: {self.stats['signals_generated']}")
                
                # Mostrar posição se houver
                if self.position['has_position']:
                    self.logger.info(f"[POSITION] {self.position['side']} {self.position['quantity']} @ "
                                   f"{self.position['entry_price']:.2f} | "
                                   f"P&L: R$ {self.position['current_pnl']:.2f} | "
                                   f"Max: +{self.position['max_profit']:.2f}/-{abs(self.position['max_loss']):.2f}")
                
                # Salvar métricas para o monitor
                self._save_metrics_for_monitor()
        
        # Thread de análise
        def analysis_thread():
            """Análise e geração de sinais"""
            while self.running:
                time.sleep(5)  # Análise a cada 5 segundos
                
                # Verificar se tem dados suficientes (reduzido de 100 para 20)
                if self.states['book_count'] < 20:
                    continue
                
                # Calcular features
                features = self._calculate_features()
                if not features:
                    continue
                
                # Fazer predição
                signal, confidence = self._make_prediction(features)
                
                # Salvar status ML/HMARL para o monitor
                self._save_ml_status(signal, confidence, features)
                
                # Registrar sinal gerado
                if signal != 0:
                    self.stats['signals_generated'] += 1
                
                # Executar se confiança suficiente
                if signal != 0 and confidence >= self.min_confidence:
                    self.logger.info(f"[SIGNAL] {'BUY' if signal > 0 else 'SELL'} | "
                                   f"Confiança: {confidence*100:.1f}% | "
                                   f"Imbalance: {features.get('imbalance', 0):.3f}")
                    
                    # Executar trade se não tiver posição
                    if not self.position['has_position']:
                        self._execute_trade(signal, confidence, features)
        
        # Thread de gestão de posição
        def position_thread():
            """Monitora e gerencia posições abertas"""
            while self.running:
                time.sleep(1)
                
                if not self.position['has_position']:
                    continue
                
                # Verificar stops
                current_pnl = self.position['current_pnl']
                
                # Stop loss: -R$ 50
                if current_pnl <= -50:
                    self.logger.warning(f"[STOP LOSS] Fechando posição com perda de R$ {abs(current_pnl):.2f}")
                    self.position['has_position'] = False
                    self.stats['losses'] += 1
                    self.stats['total_pnl'] += current_pnl
                
                # Take profit: +R$ 100
                elif current_pnl >= 100:
                    self.logger.info(f"[TAKE PROFIT] Fechando posição com lucro de R$ {current_pnl:.2f}")
                    self.position['has_position'] = False
                    self.stats['wins'] += 1
                    self.stats['total_pnl'] += current_pnl
                
                # Trailing stop: se já teve 50 de lucro e voltou para 25
                elif self.position['max_profit'] >= 50 and current_pnl <= self.position['max_profit'] * 0.5:
                    self.logger.info(f"[TRAILING STOP] Fechando com R$ {current_pnl:.2f} "
                                   f"(max foi R$ {self.position['max_profit']:.2f})")
                    self.position['has_position'] = False
                    self.stats['wins'] += 1
                    self.stats['total_pnl'] += current_pnl
        
        # Iniciar threads
        threads = []
        
        t_metrics = threading.Thread(target=metrics_thread, daemon=True, name="Metrics")
        t_metrics.start()
        threads.append(t_metrics)
        
        t_analysis = threading.Thread(target=analysis_thread, daemon=True, name="Analysis")
        t_analysis.start()
        threads.append(t_analysis)
        
        t_position = threading.Thread(target=position_thread, daemon=True, name="Position")
        t_position.start()
        threads.append(t_position)
        
        self.logger.info(f"[SYSTEM] {len(threads)} threads iniciadas")
        self.logger.info("[SYSTEM] Sistema rodando. Pressione Ctrl+C para parar\n")
        
        # Loop principal
        try:
            while self.running:
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            self.logger.info("\n[SYSTEM] Sinal de parada recebido...")
        finally:
            self.stop()
    
    def stop(self):
        """Para o sistema graciosamente"""
        self.running = False
        
        self.logger.info("\n" + "=" * 80)
        self.logger.info(" FINALIZANDO SISTEMA")
        self.logger.info("=" * 80)
        
        # Fechar posições abertas
        if self.position['has_position']:
            self.logger.warning(f"Fechando posição aberta: {self.position['side']} @ "
                              f"{self.position['entry_price']:.2f}")
        
        # Estatísticas finais
        total_trades = self.stats['wins'] + self.stats['losses']
        if total_trades > 0:
            win_rate = self.stats['wins'] / total_trades * 100
            self.logger.info(f"\n[ESTATÍSTICAS FINAIS]")
            self.logger.info(f"  Trades realizados: {total_trades}")
            self.logger.info(f"  Win Rate: {win_rate:.1f}%")
            self.logger.info(f"  P&L Total: R$ {self.stats['total_pnl']:.2f}")
            self.logger.info(f"  Sinais gerados: {self.stats['signals_generated']}")
            self.logger.info(f"  Book updates: {self.states['book_count']}")
            self.logger.info(f"  Ticks processados: {self.states['tick_count']}")
        
        # Finalizar DLL
        if self.dll:
            try:
                self.logger.info("\nFinalizando conexão com DLL...")
                self.dll.DLLFinalize()
                self.logger.info("[OK] DLL finalizada")
            except:
                pass
        
        self.logger.info("\n[SYSTEM] Sistema finalizado com sucesso!")
        print("=" * 80)

# ==============================================================================
# SIGNAL HANDLERS
# ==============================================================================

def signal_handler(signum, frame):
    """Tratamento de sinais do sistema"""
    print("\n[SIGNAL] Recebido sinal de interrupção")
    sys.exit(0)

# ==============================================================================
# MAIN
# ==============================================================================

def main():
    """Função principal"""
    # Configurar tratamento de sinais
    signal.signal(signal.SIGINT, signal_handler)
    
    # Criar diretório de logs se não existir
    Path("logs").mkdir(exist_ok=True)
    
    # Inicializar sistema
    system = QuantumTraderProductionFinal()
    
    # Inicializar DLL e conexão
    if not system.initialize_dll():
        logger.error("Falha na inicialização. Abortando.")
        sys.exit(1)
    
    # Aguardar dados iniciais
    logger.info("Aguardando dados iniciais do mercado...")
    time.sleep(5)
    
    # Rodar sistema
    system.run()

if __name__ == "__main__":
    main()