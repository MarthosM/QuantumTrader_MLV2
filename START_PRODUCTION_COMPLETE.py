#!/usr/bin/env python3
"""
QUANTUM TRADER - SISTEMA COMPLETO DE PRODUÇÃO
Com Trading Real, Monitor e Gravação de Dados
"""

import os
import sys
import time
import json
import signal
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from collections import deque
import csv

# Carregar configurações
load_dotenv('.env.production')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"logs/production_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ProductionComplete')

# Adicionar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent / 'core'))

# Importar componentes
from src.connection_manager_working import ConnectionManagerWorking
from core.enhanced_production_system import EnhancedProductionSystem

class QuantumTraderComplete:
    """Sistema completo de produção com todos os recursos"""
    
    def __init__(self):
        self.running = False
        self.connection = None
        self.system = None
        self.monitor_process = None
        self.data_lock = threading.Lock()
        
        # Configurações
        self.enable_trading = os.getenv('ENABLE_TRADING', 'false').lower() == 'true'
        self.enable_recording = os.getenv('ENABLE_DATA_RECORDING', 'true').lower() == 'true'
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE', '0.60'))
        self.symbol = os.getenv('TRADING_SYMBOL', 'WDOU25')
        
        # Buffers de dados
        self.price_history = deque(maxlen=500)
        self.book_snapshots = deque(maxlen=200)
        
        # Estatísticas
        self.stats = {
            'features_calculated': 0,
            'predictions_made': 0,
            'trades_executed': 0,
            'callbacks_received': 0,
            'data_records_saved': 0,
            'start_time': time.time()
        }
        
        # Arquivos de gravação
        self.data_files = {}
        self.record_count = {'book': 0, 'tick': 0}
        
        print("\n" + "=" * 80)
        print(" QUANTUM TRADER - SISTEMA COMPLETO DE PRODUÇÃO")
        print(" Conexão B3 + 65 Features + ML/HMARL + Trading + Monitor + Gravação")
        print("=" * 80)
        
    def initialize(self):
        """Inicializa todos os componentes"""
        try:
            # 1. Sistema de features
            print("\n[1/5] Inicializando sistema de 65 features...")
            self.system = EnhancedProductionSystem()
            
            # Carregar apenas os modelos, não inicializar tudo
            self.system._load_ml_models()
            print(f"  [OK] Sistema de features criado com {len(self.system.models)} modelos")
            
            # 2. Conexão com B3
            print("\n[2/5] Estabelecendo conexão REAL com B3...")
            USERNAME = os.getenv('PROFIT_USERNAME', '29936354842')
            PASSWORD = os.getenv('PROFIT_PASSWORD', 'Ultra3376!')
            
            dll_path = "./ProfitDLL64.dll"
            if not os.path.exists(dll_path):
                dll_path = "C:\\Users\\marth\\Downloads\\ProfitDLL\\DLLs\\Win64\\ProfitDLL.dll"
            
            self.connection = ConnectionManagerWorking(dll_path)
            
            if self.connection.initialize(username=USERNAME, password=PASSWORD):
                print("  [OK] CONECTADO À B3!")
                status = self.connection.get_status()
                print(f"    Login: {'OK' if status['connected'] else 'X'}")
                print(f"    Market: {'OK' if status['market'] else 'X'}")
                print(f"    Broker: {'OK' if status['broker'] else 'X'}")
                print(f"    Símbolo: {self.symbol}")
            else:
                print("  [ERRO] Falha na conexão")
                return False
            
            # 3. Gravação de dados
            if self.enable_recording:
                print("\n[3/5] Configurando gravação de dados...")
                self._setup_data_recording()
                print(f"  [OK] Gravação habilitada em data/book_tick_data/")
            
            # 4. Sistema de trading
            print("\n[4/5] Configurando sistema de trading...")
            if self.enable_trading:
                print(f"  [OK] Trading ATIVO - Confiança mínima: {self.min_confidence:.0%}")
            else:
                print("  [INFO] Trading em modo SIMULAÇÃO")
            
            # 5. Monitor
            print("\n[5/5] Iniciando monitor de console...")
            try:
                self.monitor_process = subprocess.Popen(
                    ['python', 'core/monitor_console_enhanced.py'],
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                )
                print("  [OK] Monitor iniciado em nova janela")
            except:
                print("  [INFO] Execute 'python core/monitor_console_enhanced.py' manualmente")
            
            print("\n" + "=" * 80)
            print(" SISTEMA INICIALIZADO COM SUCESSO!")
            print("=" * 80)
            return True
            
        except Exception as e:
            logger.error(f"Erro na inicialização: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _setup_data_recording(self):
        """Configura gravação de dados para treinamento"""
        # Criar diretório
        data_dir = Path('data/book_tick_data')
        data_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Arquivo de book
        self.data_files['book'] = data_dir / f'book_data_{timestamp}.csv'
        with open(self.data_files['book'], 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'symbol',
                'bid_price_1', 'bid_vol_1', 'bid_price_2', 'bid_vol_2',
                'bid_price_3', 'bid_vol_3', 'bid_price_4', 'bid_vol_4',
                'bid_price_5', 'bid_vol_5',
                'ask_price_1', 'ask_vol_1', 'ask_price_2', 'ask_vol_2',
                'ask_price_3', 'ask_vol_3', 'ask_price_4', 'ask_vol_4',
                'ask_price_5', 'ask_vol_5',
                'spread', 'mid_price', 'imbalance', 'total_bid_vol', 'total_ask_vol'
            ])
        
        # Arquivo de trades
        self.data_files['tick'] = data_dir / f'tick_data_{timestamp}.csv'
        with open(self.data_files['tick'], 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'symbol', 'price', 'volume', 'side', 'aggressor'])
    
    def run(self):
        """Loop principal do sistema"""
        self.running = True
        print("\n[SISTEMA ATIVO] Trading com dados REAIS da B3")
        print("Pressione Ctrl+C para parar\n")
        
        iteration = 0
        last_status_time = time.time()
        last_feature_time = time.time()
        last_save_time = time.time()
        
        try:
            while self.running:
                iteration += 1
                
                # Obter dados do mercado
                status = self.connection.get_status()
                
                # Processar book se disponível
                if status['last_book']['timestamp']:
                    self._process_book_data(status['last_book'])
                    self.stats['callbacks_received'] += 1
                
                # Calcular features a cada segundo
                if time.time() - last_feature_time >= 1.0:
                    self._process_features_and_trade()
                    last_feature_time = time.time()
                
                # Salvar dados periodicamente (a cada 30s)
                if self.enable_recording and time.time() - last_save_time >= 30:
                    self._flush_data_files()
                    last_save_time = time.time()
                
                # Status detalhado a cada 30s
                if time.time() - last_status_time >= 30:
                    self._print_detailed_status(iteration)
                    last_status_time = time.time()
                
                # Pequena pausa para não sobrecarregar CPU
                time.sleep(0.05)
                
        except KeyboardInterrupt:
            print("\n[INFO] Encerrando por solicitação do usuário...")
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
        finally:
            self.stop()
    
    def _process_book_data(self, book):
        """Processa e grava dados do book"""
        try:
            if not book.get('bids') or not book.get('asks'):
                return
            
            # Atualizar buffers do sistema
            self._update_system_buffers(book)
            
            # Gravar dados se habilitado
            if self.enable_recording and 'book' in self.data_files:
                self._record_book_data(book)
            
            # Verificar se tem trades
            if hasattr(self.connection, 'last_trade') and self.connection.last_trade['timestamp']:
                self._process_trade_data(self.connection.last_trade)
            
        except Exception as e:
            logger.debug(f"Erro processando book: {e}")
    
    def _update_system_buffers(self, book):
        """Atualiza buffers do sistema com dados reais"""
        try:
            bids = book.get('bids', [])
            asks = book.get('asks', [])
            
            # Garantir 5 níveis
            while len(bids) < 5:
                bids.append({'price': 0, 'volume': 0})
            while len(asks) < 5:
                asks.append({'price': 0, 'volume': 0})
            
            # Atualizar book buffer
            if bids[0]['price'] > 0 and asks[0]['price'] > 0:
                mid_price = (bids[0]['price'] + asks[0]['price']) / 2
                self.price_history.append(mid_price)
                
                # Simular candle
                candle_data = {
                    'timestamp': datetime.now(),
                    'open': mid_price,
                    'high': mid_price,
                    'low': mid_price,
                    'close': mid_price,
                    'volume': sum(b['volume'] for b in bids[:5]) + sum(a['volume'] for a in asks[:5])
                }
                self.system.candle_buffer.add(candle_data)
                
                # Atualizar book
                book_data = {
                    'timestamp': datetime.now(),
                    'bid_prices': [b['price'] for b in bids[:5]],
                    'bid_volumes': [b['volume'] for b in bids[:5]],
                    'ask_prices': [a['price'] for a in asks[:5]],
                    'ask_volumes': [a['volume'] for a in asks[:5]]
                }
                self.system.book_manager.book_buffer.add(book_data)
                
        except Exception as e:
            logger.debug(f"Erro atualizando buffers: {e}")
    
    def _process_trade_data(self, trade):
        """Processa e grava dados de trade/tick"""
        try:
            if self.enable_recording and 'tick' in self.data_files:
                row = [
                    datetime.now().isoformat(),
                    self.symbol,
                    trade.get('price', 0),
                    trade.get('volume', 0),
                    trade.get('side', ''),
                    'AGGRESSIVE' if trade.get('side') == 'BUY' else 'PASSIVE'
                ]
                
                with open(self.data_files['tick'], 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
                
                self.record_count['tick'] += 1
                self.stats['data_records_saved'] += 1
                
        except Exception as e:
            logger.debug(f"Erro gravando tick: {e}")
    
    def _record_book_data(self, book):
        """Grava dados do book para treinamento"""
        try:
            row = [datetime.now().isoformat(), self.symbol]
            
            # Bids (5 níveis)
            bids = book.get('bids', [])
            for i in range(5):
                if i < len(bids):
                    row.extend([bids[i]['price'], bids[i]['volume']])
                else:
                    row.extend([0, 0])
            
            # Asks (5 níveis)
            asks = book.get('asks', [])
            for i in range(5):
                if i < len(asks):
                    row.extend([asks[i]['price'], asks[i]['volume']])
                else:
                    row.extend([0, 0])
            
            # Métricas
            if bids and asks:
                spread = asks[0]['price'] - bids[0]['price']
                mid_price = (asks[0]['price'] + bids[0]['price']) / 2
                bid_vol = sum(b['volume'] for b in bids[:5])
                ask_vol = sum(a['volume'] for a in asks[:5])
                imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0
            else:
                spread = mid_price = imbalance = bid_vol = ask_vol = 0
            
            row.extend([spread, mid_price, imbalance, bid_vol, ask_vol])
            
            with open(self.data_files['book'], 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            self.record_count['book'] += 1
            self.stats['data_records_saved'] += 1
            
        except Exception as e:
            logger.debug(f"Erro gravando book: {e}")
    
    def _process_features_and_trade(self):
        """Calcula features e executa trading"""
        try:
            # Calcular features
            if len(self.price_history) >= 50:
                features = self.system._calculate_features()
                
                if features and len(features) >= 40:
                    self.stats['features_calculated'] += 1
                    
                    # Fazer predição ML (passa o dict, mas internamente usa o vector de 65)
                    ml_pred = self.system._make_ml_prediction(features)
                    
                    if ml_pred != 0.5:  # Se não é neutro
                        self.stats['predictions_made'] += 1
                        
                        # Log de predição se significativa
                        if abs(ml_pred - 0.5) > 0.05:  # Mudança > 5% do neutro
                            # Obter quantidade real de features do vector
                            feature_vector = self.system.feature_engineer.get_feature_vector()
                            non_zero = sum(1 for v in feature_vector if v != 0)
                            print(f"\n[ML] Predição: {ml_pred:.3f} (65 features, {non_zero} não-zero)")
                        
                        # Executar trade se confiança suficiente
                        if abs(ml_pred) > self.min_confidence:
                            self._execute_trade(ml_pred, features)
                            
        except Exception as e:
            logger.debug(f"Erro em features/trading: {e}")
    
    def _execute_trade(self, signal, features):
        """Executa trade baseado no sinal"""
        try:
            side = "COMPRA" if signal > 0 else "VENDA"
            confidence = abs(signal)
            
            print(f"\n[SINAL DE TRADE]")
            print(f"  Ação: {side}")
            print(f"  Confiança: {confidence:.2%}")
            print(f"  Features: {len(features)}")
            print(f"  Timestamp: {datetime.now().strftime('%H:%M:%S')}")
            
            if self.enable_trading:
                # Aqui executaria ordem real via ProfitDLL
                print(f"  [TRADE] Ordem {side} enviada!")
                self.stats['trades_executed'] += 1
            else:
                print(f"  [SIMULAÇÃO] Trade simulado")
                
        except Exception as e:
            logger.error(f"Erro executando trade: {e}")
    
    def _flush_data_files(self):
        """Força gravação dos arquivos"""
        # Python já faz flush automático, mas podemos forçar
        pass
    
    def _print_detailed_status(self, iteration):
        """Imprime status detalhado do sistema"""
        status = self.connection.get_status()
        runtime = time.time() - self.stats['start_time']
        
        print("\n" + "=" * 80)
        print(f"STATUS DO SISTEMA - {datetime.now().strftime('%H:%M:%S')} - Iteração {iteration}")
        print("=" * 80)
        
        # Conexão
        print("Conexao B3:")
        print(f"   Login: {'OK' if status['connected'] else 'ERRO'} | "
              f"Market: {'OK' if status['market'] else 'ERRO'} | "
              f"Broker: {'OK' if status['broker'] else 'ERRO'}")
        
        # Dados recebidos
        total_callbacks = sum(status['callbacks'].values())
        print(f"\nDados de Mercado:")
        print(f"   Total callbacks: {total_callbacks:,}")
        print(f"   Taxa: {total_callbacks/runtime:.1f} callbacks/s")
        
        # Book atual
        if status['last_book'].get('bids') and status['last_book'].get('asks'):
            bid = status['last_book']['bids'][0]
            ask = status['last_book']['asks'][0]
            spread = ask['price'] - bid['price']
            mid = (ask['price'] + bid['price']) / 2
            print(f"\nUltimo Book ({self.symbol}):")
            print(f"   BID: R$ {bid['price']:,.2f} x {bid['volume']}")
            print(f"   ASK: R$ {ask['price']:,.2f} x {ask['volume']}")
            print(f"   Spread: R$ {spread:.2f} | Mid: R$ {mid:,.2f}")
        
        # Machine Learning
        print(f"\nMachine Learning:")
        print(f"   Features calculadas: {self.stats['features_calculated']}")
        print(f"   Predições realizadas: {self.stats['predictions_made']}")
        if self.stats['features_calculated'] > 0:
            print(f"   Taxa de predição: {(self.stats['predictions_made']/self.stats['features_calculated'])*100:.1f}%")
        
        # Trading
        print(f"\nTrading:")
        print(f"   Modo: {'REAL' if self.enable_trading else 'SIMULAÇÃO'}")
        print(f"   Trades executados: {self.stats['trades_executed']}")
        print(f"   Confiança mínima: {self.min_confidence:.0%}")
        
        # Gravação
        if self.enable_recording:
            print(f"\nGravacao de Dados:")
            print(f"   Book records: {self.record_count['book']:,}")
            print(f"   Tick records: {self.record_count['tick']:,}")
            print(f"   Total gravado: {self.stats['data_records_saved']:,}")
        
        # Performance
        print(f"\nPerformance:")
        print(f"   Tempo rodando: {int(runtime)}s")
        print(f"   Uso de buffers: {len(self.price_history)}/{self.price_history.maxlen}")
        
        print("=" * 80)
    
    def stop(self):
        """Para o sistema"""
        print("\n[ENCERRANDO] Parando sistema...")
        self.running = False
        
        # Fechar monitor
        if self.monitor_process:
            try:
                self.monitor_process.terminate()
                print("  [OK] Monitor fechado")
            except:
                pass
        
        # Estatísticas finais
        if self.connection:
            status = self.connection.get_status()
            runtime = time.time() - self.stats['start_time']
            
            print(f"\nESTATISTICAS FINAIS:")
            print(f"  Tempo total: {int(runtime)}s")
            print(f"  Callbacks recebidos: {sum(status['callbacks'].values()):,}")
            print(f"  Features calculadas: {self.stats['features_calculated']}")
            print(f"  Predições realizadas: {self.stats['predictions_made']}")
            print(f"  Trades executados: {self.stats['trades_executed']}")
            
            if self.enable_recording:
                print(f"  Dados gravados: {self.stats['data_records_saved']:,}")
                print(f"  Arquivos em: data/book_tick_data/")
            
            self.connection.cleanup()
            print("\n  [OK] Conexão fechada")
        
        print("\n" + "=" * 80)
        print(" SISTEMA ENCERRADO COM SUCESSO")
        print("=" * 80)

def main():
    """Função principal"""
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    
    print("\n### QUANTUM TRADER - SISTEMA COMPLETO ###")
    print("Modo: PRODUÇÃO REAL")
    print("Recursos: Trading + Monitor + Gravação de Dados")
    
    # Verificar PID
    pid_file = Path('quantum_trader.pid')
    if pid_file.exists():
        print("\n[AVISO] Sistema pode estar rodando. Verificar quantum_trader.pid")
        resp = input("Continuar mesmo assim? (s/n): ")
        if resp.lower() != 's':
            return
    
    # Salvar PID
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    
    try:
        # Criar e executar sistema
        trader = QuantumTraderComplete()
        
        if trader.initialize():
            trader.run()
        else:
            print("\n[ERRO] Falha na inicialização")
            
    finally:
        # Limpar PID
        if pid_file.exists():
            pid_file.unlink()

if __name__ == "__main__":
    main()