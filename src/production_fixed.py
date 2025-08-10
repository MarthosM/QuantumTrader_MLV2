"""
Sistema de Produção Corrigido - QuantumTrader ML
Baseado no book_collector_continuous.py com estrutura completa de callbacks
"""

import os
import sys
import time
import ctypes
from ctypes import *
from datetime import datetime
from pathlib import Path
import logging
import threading
import signal
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import joblib
import json
import subprocess

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
log_file = f'logs/production/final_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
Path("logs/production").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('ProductionFixed')

# Estruturas ProfitDLL (copiadas do book_collector)
class TAssetIDRec(Structure):
    _fields_ = [
        ("ticker", c_wchar * 35),
        ("bolsa", c_wchar * 15),
    ]

class TAssetListInfoRec(Structure):
    _fields_ = [
        ("ticker", c_wchar * 35),
        ("bolsa", c_wchar * 15),
        ("descricao", c_wchar * 255),
        ("tipo", c_int),
        ("lote_padrao", c_int),
        ("decimais", c_int),
    ]

class TOfferBookInfo(Structure):
    _fields_ = [
        ("price", c_double),
        ("qtd", c_int32),
        ("nOrders", c_int32),
        ("side", c_int32),
        ("datetime", c_wchar * 25),
        ("position", c_int32),
        ("sinalPr", c_int32)
    ]

class ProductionFixedSystem:
    def __init__(self):
        self.dll = None
        self.logger = logger
        
        # Flags de controle IDÊNTICAS ao book_collector
        self.bAtivo = False
        self.bMarketConnected = False
        self.bConnectado = False
        self.bBrokerConnected = False
        self.is_running = False
        
        # Callbacks
        self.callback_refs = {}
        self.callbacks = {
            'state': 0,
            'history': 0,
            'daily': 0,
            'price_book': 0,
            'offer_book': 0,
            'progress': 0,
            'tiny_book': 0
        }
        
        # Market data
        self.current_price = 0
        self.last_price_update = 0
        self.candles = []
        self.target_ticker = "WDOU25"  # Setembro 2025 - ticker correto
        
        # Trading
        self.position = 0
        self.entry_price = 0
        self.daily_pnl = 0
        self.max_daily_loss = -500
        
        # ML
        self.models = {}
        self.features_lists = {}
        
        # Risk
        self.max_position = 1
        self.stop_loss_pct = 0.005
        self.take_profit_pct = 0.01
        
        # Stats
        self.stats = {
            'start_time': time.time(),
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'predictions': 0,
            'total_pnl': 0,
            'last_price': 0
        }
        
        # Path para dados compartilhados
        self.shared_data_file = Path('data/monitor_data.json')
        self.shared_data_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Monitor
        self.monitor_process = None
        
        # Last prediction for monitor
        self._last_prediction = None
        
    def initialize(self):
        """Inicializa sistema com estrutura IDÊNTICA ao book_collector"""
        try:
            # Carregar modelos ML
            self._load_ml_models()
            
            # Carregar DLL
            dll_path = os.getenv('PROFIT_DLL_PATH', './ProfitDLL64.dll')
            if not os.path.exists(dll_path):
                dll_path = './ProfitDLL64.dll'
                
            self.logger.info(f"Carregando DLL: {os.path.abspath(dll_path)}")
            
            print(f"[DEBUG] Verificando se DLL existe: {os.path.exists(dll_path)}")
            
            self.dll = WinDLL(dll_path)
            self.logger.info("[OK] DLL carregada")
            print("[DEBUG] DLL carregada com sucesso")
            
            # Criar TODOS os callbacks ANTES do login
            self._create_all_callbacks()
            
            # Login com callbacks
            key = c_wchar_p("HMARL")
            user = c_wchar_p(os.getenv('PROFIT_USERNAME', '29936354842'))
            pwd = c_wchar_p(os.getenv('PROFIT_PASSWORD', 'Ultra3376!'))
            
            self.logger.info("Fazendo login com callbacks...")
            
            # DLLInitializeLogin com TODOS os callbacks possíveis (IDÊNTICO ao book_collector)
            result = self.dll.DLLInitializeLogin(
                key, user, pwd,
                self.callback_refs['state'],         # stateCallback
                self.callback_refs['history'],       # historyCallback
                None,                                # orderChangeCallback
                None,                                # accountCallback
                None,                                # accountInfoCallback
                self.callback_refs['daily'],         # newDailyCallback
                self.callback_refs['price_book'],    # priceBookCallback
                self.callback_refs['offer_book'],    # offerBookCallback
                None,                                # historyTradeCallback
                self.callback_refs['progress'],      # progressCallBack
                self.callback_refs['tiny_book']      # tinyBookCallBack
            )
            
            print(f"[DEBUG] DLLInitializeLogin retornou: {result}")
            
            if result != 0:
                self.logger.error(f"Erro no login: {result}")
                return False
                
            self.logger.info(f"[OK] Login bem sucedido: {result}")
            
            # Aguardar conexão completa
            if not self._wait_login():
                self.logger.error("Timeout aguardando conexão")
                return False
                
            # Monitor desabilitado - usando Enhanced Monitor no sistema HMARL
            # self._start_monitor()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro na inicialização: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    def _wait_login(self):
        """Aguarda conexão completa como no book_collector"""
        timeout = 30
        start = time.time()
        
        while (time.time() - start) < timeout:
            if self.bMarketConnected and self.bAtivo and self.bConnectado:
                self.logger.info(">>> SISTEMA TOTALMENTE CONECTADO <<<")
                return True
                
            # Log progresso
            if int(time.time() - start) % 5 == 0:
                self.logger.info(f"Aguardando... Market: {self.bMarketConnected}, Ativo: {self.bAtivo}, Login: {self.bConnectado}")
                
            time.sleep(0.1)
            
        return False
            
    def _create_all_callbacks(self):
        """Cria TODOS os callbacks possíveis ANTES do login"""
        
        # State callback - CRÍTICO
        @WINFUNCTYPE(None, c_int32, c_int32)
        def stateCallback(nType, nResult):
            self.callbacks['state'] += 1
            
            states = {0: "Login", 1: "Broker", 2: "Market", 3: "Ativacao"}
            self.logger.info(f"[STATE] {states.get(nType, f'Type{nType}')}: {nResult}")
            
            if nType == 0:  # Login
                self.bConnectado = (nResult == 0)
            elif nType == 1:  # Broker
                self.bBrokerConnected = (nResult == 5)
            elif nType == 2:  # Market
                self.bMarketConnected = (nResult == 4 or nResult == 3 or nResult == 2)
            elif nType == 3:  # Ativacao
                self.bAtivo = (nResult == 0)
                
            if self.bMarketConnected and self.bAtivo and self.bConnectado:
                self.logger.info(">>> SISTEMA TOTALMENTE CONECTADO <<<")
                
            return None
            
        self.callback_refs['state'] = stateCallback
        
        # TinyBook callback - Principal para preços
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_double, c_int, c_int)
        def tinyBookCallBack(assetId, price, qtd, side):
            self.callbacks['tiny_book'] += 1
            
            # Validar preço
            if price > 0 and price < 10000:
                self.current_price = float(price)
                self.last_price_update = time.time()
                
                # Log a cada 1000 ou mudança significativa de preço
                if self.callbacks['tiny_book'] % 1000 == 0 or abs(price - self.stats['last_price']) > 1:
                    side_str = "BID" if side == 0 else "ASK"
                    self.logger.info(f'[TINY #{self.callbacks["tiny_book"]:,}] {self.target_ticker} {side_str}: R$ {price:.2f} x {qtd}')
                    self.stats['last_price'] = price
                        
            return None
            
        self.callback_refs['tiny_book'] = tinyBookCallBack
        
        # PriceBook callback - Para book detalhado
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_int32, c_int32, c_int32, POINTER(TOfferBookInfo))
        def priceBookCallback(assetId, side, nAction, nPosition, pBook):
            self.callbacks['price_book'] += 1
            
            try:
                if self.callbacks['price_book'] == 1:
                    self.logger.info("[PRICE_BOOK] Primeiro callback recebido!")
                    
            except Exception as e:
                self.logger.error(f"Erro no priceBookCallback: {e}")
                
            return None
            
        self.callback_refs['price_book'] = priceBookCallback
        
        # OfferBook callback - Para ofertas agregadas
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_int32, c_wchar_p)
        def offerBookCallback(assetId, side, strJson):
            self.callbacks['offer_book'] += 1
            
            try:
                if self.callbacks['offer_book'] == 1:
                    self.logger.info(f"[OFFER_BOOK] Primeiro callback recebido!")
                    
            except Exception as e:
                self.logger.error(f"Erro no offerBookCallback: {e}")
                
            return None
            
        self.callback_refs['offer_book'] = offerBookCallback
        
        # Daily callback - Dados agregados
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_wchar_p, c_double, c_double, 
                    c_double, c_double, c_double, c_double, c_double, c_double, 
                    c_double, c_double, c_int, c_int, c_int, c_int, c_int, c_int, c_int)
        def dailyCallback(assetId, date, sOpen, sHigh, sLow, sClose, sVol, sAjuste, 
                         sMaxLimit, sMinLimit, sVolBuyer, sVolSeller, nQtd, nNegocios, 
                         nContratosOpen, nQtdBuyer, nQtdSeller, nNegBuyer, nNegSeller):
            
            self.callbacks['daily'] += 1
            
            # Adicionar candle
            candle = {
                'timestamp': datetime.now(),
                'open': float(sOpen),
                'high': float(sHigh),
                'low': float(sLow),
                'close': float(sClose),
                'volume': float(sVol),
                'trades': int(nNegocios)
            }
            
            self.candles.append(candle)
            
            # Atualizar preço atual com o close do candle
            if sClose > 0:
                self.current_price = float(sClose)
                self.last_price_update = time.time()
            
            # Log
            self.logger.info(f"[DAILY #{self.callbacks['daily']}] OHLC: {sOpen:.2f}/{sHigh:.2f}/{sLow:.2f}/{sClose:.2f} Vol: {sVol}")
            
            # Manter apenas últimos 100
            if len(self.candles) > 100:
                self.candles.pop(0)
                
            return None
                
        self.callback_refs['daily'] = dailyCallback
        
        # History callback
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_wchar_p, c_double, c_double, 
                    c_double, c_double, c_double, c_double, c_double, c_double, 
                    c_double, c_double, c_int, c_int, c_int, c_int, c_int, c_int, c_int)
        def historyCallback(assetId, date, sOpen, sHigh, sLow, sClose, sVol, sAjuste, 
                           sMaxLimit, sMinLimit, sVolBuyer, sVolSeller, nQtd, nNegocios, 
                           nContratosOpen, nQtdBuyer, nQtdSeller, nNegBuyer, nNegSeller):
            self.callbacks['history'] += 1
            
            if self.callbacks['history'] % 10 == 0:
                self.logger.debug(f"[HISTORY] Recebidos {self.callbacks['history']} candles históricos")
                
            return None
            
        self.callback_refs['history'] = historyCallback
        
        # Progress callback
        @WINFUNCTYPE(None, POINTER(TAssetIDRec), c_int32)
        def progressCallBack(assetId, nProgress):
            self.callbacks['progress'] += 1
            
            if nProgress == 100:
                self.logger.info(f"[PROGRESS] Download histórico completo")
            elif nProgress % 25 == 0:
                self.logger.debug(f"[PROGRESS] {nProgress}%")
                
            return None
            
        self.callback_refs['progress'] = progressCallBack
        
        self.logger.info(f"[OK] {len(self.callback_refs)} callbacks criados")
        
    def subscribe_ticker(self, ticker=None):
        """Subscreve ticker"""
        if ticker is None:
            ticker = self.target_ticker
            
        try:
            result = self.dll.SubscribeTicker(
                c_wchar_p(ticker), 
                c_wchar_p("F")
            )
            
            if result == 0:
                self.logger.info(f"[OK] Subscrito a {ticker}")
                self.target_ticker = ticker
                return True
            else:
                self.logger.error(f"Erro ao subscrever {ticker}: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro: {e}")
            return False
            
    def _load_ml_models(self):
        """Carrega modelos ML disponíveis"""
        try:
            models_dir = Path('models')
            if not models_dir.exists():
                self.logger.warning("Diretório de modelos não encontrado")
                return
                
            # Lista de modelos compatíveis
            # Modelos de 65 features (prioridade)
            compatible_models_65 = ['xgboost_fast', 'xgboost_balanced_20250807_061838', 
                                   'lightgbm_balanced', 'random_forest_stable', 
                                   'random_forest_balanced_20250807_061838']
            # Modelo de fallback (11 features)
            compatible_models_11 = ['simple_model']
            
            # Combinar listas (65 features primeiro, depois fallback)
            compatible_models = compatible_models_65 + compatible_models_11
            
            for model_file in models_dir.glob('*.pkl'):
                try:
                    model_name = model_file.stem
                    
                    if 'scaler' in model_name.lower():
                        continue
                    
                    # Carregar apenas modelos compatíveis
                    if model_name not in compatible_models:
                        self.logger.debug(f"Pulando modelo incompatível: {model_name}")
                        continue
                        
                    self.logger.info(f"Carregando modelo: {model_name}")
                    
                    model = joblib.load(model_file)
                    self.models[model_name] = model
                    
                    features_file = model_file.with_suffix('.json')
                    if features_file.exists():
                        with open(features_file) as f:
                            data = json.load(f)
                            self.features_lists[model_name] = data.get('features', [])
                            
                    self.logger.info(f"[OK] {model_name}: {len(self.features_lists.get(model_name, []))} features")
                    
                except Exception as e:
                    self.logger.error(f"Erro ao carregar {model_file}: {e}")
                    
            self.logger.info(f"Total de modelos carregados: {len(self.models)}")
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar modelos: {e}")
            
    def _start_monitor(self):
        """[DESABILITADO] Monitor GUI antigo - Use Enhanced Monitor"""
        # Monitor antigo desabilitado - sistema HMARL usa Enhanced Monitor
        return
        # try:
        #     self.logger.info("Iniciando monitor GUI...")
        #     
        #     self.monitor_process = subprocess.Popen(
        #         [sys.executable, "monitor_gui.py"],
        #         creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        #     )
        #     
        #     self.logger.info("[OK] Monitor iniciado")
        #     
        # except Exception as e:
        #     self.logger.warning(f"Monitor não iniciado: {e}")
            
    def _calculate_features(self):
        """Calcula features com dados reais"""
        if len(self.candles) < 20:
            return None
            
        try:
            df = pd.DataFrame(self.candles)
            features = {}
            
            # Preços
            closes = df['close'].values
            features['price_current'] = self.current_price if self.current_price > 0 else closes[-1]
            features['price_mean_5'] = np.mean(closes[-5:])
            features['price_mean_20'] = np.mean(closes[-20:])
            features['price_std_20'] = np.std(closes[-20:])
            
            # Retornos
            returns = np.diff(closes) / closes[:-1]
            features['return_1'] = returns[-1] if len(returns) > 0 else 0
            features['return_mean_5'] = np.mean(returns[-5:]) if len(returns) >= 5 else 0
            features['return_std_5'] = np.std(returns[-5:]) if len(returns) >= 5 else 0
            
            # Volume
            volumes = df['volume'].values
            features['volume_mean_5'] = np.mean(volumes[-5:])
            features['volume_ratio'] = volumes[-1] / features['volume_mean_5'] if features['volume_mean_5'] > 0 else 1
            
            # RSI
            gains = [r if r > 0 else 0 for r in returns[-14:]]
            losses = [-r if r < 0 else 0 for r in returns[-14:]]
            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            features['rsi_14'] = 100 - (100 / (1 + rs))
            
            # Momentum
            if len(closes) >= 10:
                features['momentum_10'] = (features['price_current'] / closes[-10]) - 1
            else:
                features['momentum_10'] = 0
                
            return features
            
        except Exception as e:
            self.logger.error(f"Erro ao calcular features: {e}")
            return None
            
    def _make_prediction(self):
        """Faz predição ML com dados reais"""
        if not self.models:
            self.logger.debug("Sem modelos carregados")
            return None
            
        try:
            features = self._calculate_features()
            if not features:
                self.logger.debug("Features não calculadas")
                return None
                
            predictions = []
            confidences = []
            
            for model_name, model in self.models.items():
                try:
                    feature_list = self.features_lists.get(model_name, [])
                    if not feature_list:
                        self.logger.debug(f"Sem lista de features para {model_name}")
                        continue
                        
                    feature_vector = []
                    for feat_name in feature_list:
                        value = features.get(feat_name, 0)
                        feature_vector.append(value)
                        
                    X = np.array([feature_vector])
                    
                    if hasattr(model, 'predict_proba'):
                        proba = model.predict_proba(X)[0]
                        pred = proba[1]
                        conf = max(proba)
                    else:
                        pred = model.predict(X)[0]
                        conf = abs(pred)
                        
                    predictions.append(pred)
                    confidences.append(conf)
                    self.logger.debug(f"{model_name}: pred={pred:.4f}, conf={conf:.4f}")
                    
                except Exception as e:
                    self.logger.error(f"Erro na predição {model_name}: {e}")
                    
            if not predictions:
                self.logger.debug("Nenhuma predição gerada")
                return None
                
            # Ensemble
            total_conf = sum(confidences)
            if total_conf > 0:
                weighted_pred = sum(p * c for p, c in zip(predictions, confidences)) / total_conf
                avg_conf = np.mean(confidences)
            else:
                weighted_pred = np.mean(predictions)
                avg_conf = 0.5
                
            self.stats['predictions'] += 1
            
            prediction_result = {
                'direction': weighted_pred,
                'confidence': avg_conf,
                'models_used': len(predictions)
            }
            
            # Salvar última predição para o monitor
            self._last_prediction = prediction_result.copy()
            
            return prediction_result
            
        except Exception as e:
            self.logger.error(f"Erro na predição: {e}")
            return None
            
    def run_strategy(self):
        """Loop principal da estratégia"""
        self.logger.info("[STRATEGY] Iniciando estratégia ML")
        
        last_prediction_time = 0
        last_status_time = 0
        last_trade_check = 0
        
        while self.is_running:
            try:
                current_time = time.time()
                
                # Verificar dados
                if self.last_price_update > 0:
                    data_age = current_time - self.last_price_update
                    if data_age > 10:
                        self.logger.warning(f"[DATA] Sem atualizações há {data_age:.1f}s")
                        
                # Predição a cada 30 segundos
                if (current_time - last_prediction_time) > 30 and len(self.candles) >= 20:
                    prediction = self._make_prediction()
                    
                    if prediction:
                        self.logger.info(f"\n[ML] Dir: {prediction['direction']:.3f} | "
                                       f"Conf: {prediction['confidence']:.3f} | "
                                       f"Models: {prediction['models_used']}")
                        
                        # Verificar sinal de trading
                        signal = self._check_trading_signal(prediction)
                        if signal:
                            self._execute_trade(signal)
                        
                    last_prediction_time = current_time
                    
                # Verificar posições a cada 5 segundos
                if (current_time - last_trade_check) > 5 and self.position != 0:
                    self._check_position()
                    last_trade_check = current_time
                    
                # Status a cada 60 segundos
                if (current_time - last_status_time) > 60:
                    self._log_status()
                    last_status_time = current_time
                    
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Erro na estratégia: {e}")
                time.sleep(5)
                
    def _check_trading_signal(self, prediction):
        """Verifica se deve gerar sinal de trading"""
        # Verificar limites diários
        if self.daily_pnl <= self.max_daily_loss:
            self.logger.warning(f"[RISK] Limite diário atingido: {self.daily_pnl:.2f}")
            return None
            
        # Verificar posição máxima
        if abs(self.position) >= self.max_position:
            return None
            
        # Thresholds
        direction_threshold = 0.6
        confidence_threshold = 0.65
        
        # Verificar sinal
        if prediction['confidence'] >= confidence_threshold:
            if prediction['direction'] >= direction_threshold:
                return {'side': 'BUY', 'confidence': prediction['confidence']}
            elif prediction['direction'] <= (1 - direction_threshold):
                return {'side': 'SELL', 'confidence': prediction['confidence']}
                
        return None
        
    def _execute_trade(self, signal):
        """Executa trade (simulado por enquanto)"""
        try:
            # Por enquanto apenas simular
            self.position = 1 if signal['side'] == 'BUY' else -1
            self.entry_price = self.current_price
            
            self.logger.info(f"\n[ORDER] {signal['side']} @ {self.current_price:.2f} | "
                           f"Conf: {signal['confidence']:.3f}")
            
            self.stats['trades'] += 1
            
        except Exception as e:
            self.logger.error(f"Erro ao executar trade: {e}")
            
    def _check_position(self):
        """Verifica posição aberta"""
        if self.position == 0 or self.entry_price == 0:
            return
            
        # Calcular P&L
        if self.position > 0:
            pnl_pct = (self.current_price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - self.current_price) / self.entry_price
            
        pnl_money = pnl_pct * self.entry_price * abs(self.position)
        
        # Verificar stops
        if pnl_pct <= -self.stop_loss_pct:
            self.logger.info(f"[STOP LOSS] P&L: {pnl_money:.2f} ({pnl_pct*100:.2f}%)")
            self._close_position('STOP_LOSS', pnl_money)
        elif pnl_pct >= self.take_profit_pct:
            self.logger.info(f"[TAKE PROFIT] P&L: {pnl_money:.2f} ({pnl_pct*100:.2f}%)")
            self._close_position('TAKE_PROFIT', pnl_money)
            
    def _close_position(self, reason, pnl):
        """Fecha posição"""
        self.daily_pnl += pnl
        self.stats['total_pnl'] += pnl
        
        if pnl > 0:
            self.stats['wins'] += 1
        else:
            self.stats['losses'] += 1
            
        self.logger.info(f"[CLOSE] {reason} | P&L: {pnl:.2f} | Daily: {self.daily_pnl:.2f}")
        
        self.position = 0
        self.entry_price = 0
        
    def _log_status(self):
        """Log de status com callbacks"""
        elapsed = (time.time() - self.stats['start_time']) / 60
        
        self.logger.info(f"\n[STATUS] {elapsed:.1f}min | Price: {self.current_price:.2f} | "
                        f"Pos: {self.position} | P&L: {self.daily_pnl:.2f}")
        
        # Log callbacks
        callback_summary = ", ".join([f"{k}: {v}" for k, v in self.callbacks.items() if v > 0])
        self.logger.info(f"Callbacks: {callback_summary}")
        
        # Log ML
        if self.stats['predictions'] > 0:
            self.logger.info(f"ML Stats: {self.stats['predictions']} predictions | "
                           f"{self.stats['trades']} trades | "
                           f"W/L: {self.stats['wins']}/{self.stats['losses']}")
        
        # Salvar dados compartilhados
        self._save_shared_data()
        
    def _save_shared_data(self):
        """Salva dados compartilhados para o monitor"""
        try:
            # Coletar modelos ativos
            active_models = []
            for model_name in self.models.keys():
                if 'scaler' not in model_name.lower() and 'balanced' not in model_name:
                    active_models.append(model_name)
            
            shared_data = {
                'timestamp': datetime.now().isoformat(),
                'price': self.current_price,
                'position': self.position,
                'entry_price': self.entry_price,
                'pnl': (self.current_price - self.entry_price) * self.position if self.position != 0 else 0,
                'daily_pnl': self.daily_pnl,
                'total_pnl': self.stats['total_pnl'],
                'trades': self.stats['trades'],
                'wins': self.stats['wins'],
                'losses': self.stats['losses'],
                'predictions': self.stats['predictions'],
                'ticker': self.target_ticker,
                'callbacks': dict(self.callbacks),
                'status': 'Operacional' if self.is_running else 'Parado',
                'active_models': active_models
            }
            
            # Adicionar última predição se existir
            if hasattr(self, '_last_prediction') and self._last_prediction:
                shared_data['last_prediction'] = self._last_prediction
            
            with open(self.shared_data_file, 'w') as f:
                json.dump(shared_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Erro ao salvar dados compartilhados: {e}")
        
    def start(self):
        """Inicia sistema"""
        self.is_running = True
        
        strategy_thread = threading.Thread(target=self.run_strategy)
        strategy_thread.daemon = True
        strategy_thread.start()
        
        return True
        
    def stop(self):
        """Para sistema"""
        self.is_running = False
        
        # Monitor antigo desabilitado
        # if self.monitor_process:
        #     try:
        #         self.monitor_process.terminate()
        #     except:
        #         pass
                
    def cleanup(self):
        """Finaliza DLL"""
        if self.dll and hasattr(self.dll, 'DLLFinalize'):
            self.dll.DLLFinalize()

# Variável global
system = None

def signal_handler(signum, frame):
    """Handler para Ctrl+C"""
    global system
    print("\n\nFinalizando sistema...")
    if system:
        system.stop()
    sys.exit(0)

def main():
    global system
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("\n" + "="*60)
    print("QUANTUM TRADER ML - PRODUÇÃO CORRIGIDA")
    print("="*60)
    print(f"Data: {datetime.now()}")
    print("="*60)
    
    # Argumentos de teste
    test_mode = None
    if len(sys.argv) > 1:
        test_mode = sys.argv[1]
        print(f"Modo de teste: {test_mode}")
    
    try:
        # Criar sistema
        system = ProductionFixedSystem()
        
        # Inicializar
        if not system.initialize():
            print("\nERRO: Falha na inicialização")
            return 1
            
        # Aguardar estabilização
        print("\nSistema conectado. Aguardando dados...")
        time.sleep(3)
        
        # Subscrever
        ticker = os.getenv('TICKER', 'WDOU25')
        if not system.subscribe_ticker(ticker):
            print(f"\nERRO: Falha ao subscrever {ticker}")
            return 1
            
        # Aguardar dados
        print(f"\nAguardando dados de {ticker}...")
        time.sleep(5)
        
        # Verificar recepção
        print(f"\nCallbacks recebidos:")
        for cb_type, count in system.callbacks.items():
            if count > 0:
                print(f"  {cb_type}: {count:,}")
                
        # Modo de teste
        if test_mode == '--test-data':
            print("\nModo teste de dados. Monitorando por 30 segundos...")
            time.sleep(30)
            return 0
            
        # Iniciar estratégia
        if not system.start():
            return 1
            
        print("\n" + "="*60)
        print(f"SISTEMA OPERACIONAL")
        print(f"Modelos ML: {len(system.models)}")
        print(f"Ticker: {ticker}")
        print("Para parar: CTRL+C")
        print("="*60)
        
        # Loop principal
        while system.is_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário")
        
    except Exception as e:
        print(f"\nERRO FATAL: {e}")
        logger.error(f"Erro fatal: {e}", exc_info=True)
        
    finally:
        if system:
            system.stop()
            system.cleanup()
            
        # Stats finais
        if system:
            print("\n" + "="*60)
            print("ESTATÍSTICAS FINAIS")
            print("="*60)
            print(f"Callbacks totais:")
            for cb_type, count in system.callbacks.items():
                if count > 0:
                    print(f"  {cb_type}: {count:,}")
            print(f"Predições ML: {system.stats['predictions']}")
            print("="*60)
            
        print(f"\nLogs: {log_file}")

if __name__ == "__main__":
    sys.exit(main())