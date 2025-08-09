"""
Monitor de Console Enhanced - Visual aprimorado similar ao Enhanced Monitor V2
Sem interface gráfica, mas com formatação rica no console
"""

import os
import sys
import time
import json
import random
from datetime import datetime
from pathlib import Path
from collections import deque
import numpy as np

try:
    from colorama import init, Fore, Back, Style
    init()
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    # Fallback - sem cores
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''
    class Back:
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ''


class EnhancedConsoleMonitor:
    """Monitor Enhanced para Console com visual rico"""
    
    def __init__(self):
        self.running = True
        self.start_time = datetime.now()
        
        # Histórico de dados
        self.feature_history = deque(maxlen=100)
        self.prediction_history = deque(maxlen=100)
        self.trade_history = deque(maxlen=50)
        
        # Contadores
        self.counters = {
            'features': 0,
            'predictions': 0,
            'trades': 0,
            'errors': 0
        }
        
        # Cache de métricas
        self.last_metrics = {}
        self.last_features = {}
        
        # Configuração de display
        self.screen_width = 120
        self.refresh_rate = 2  # segundos
    
    def clear_screen(self):
        """Limpa a tela"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def draw_header(self):
        """Desenha cabeçalho do monitor"""
        print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}")
        print("═" * self.screen_width)
        print(f"{'QUANTUM TRADER ML - ENHANCED MONITOR':^{self.screen_width}}")
        print(f"{'65 Features | 4 HMARL Agents | Real-time Trading':^{self.screen_width}}")
        print("═" * self.screen_width)
        print(Style.RESET_ALL)
        
        # Info bar
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        info = f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ⏱️ Uptime: {uptime_str} | 🔄 Refresh: {self.refresh_rate}s"
        print(f"{Fore.CYAN}{info:^{self.screen_width}}{Fore.RESET}\n")
    
    def draw_features_panel(self):
        """Painel de Features (65 features organizadas por categoria)"""
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}╔{'═' * 56}╗{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}║{'📊 65 FEATURES MONITOR':^56}║{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        
        # Categorias de features
        categories = {
            "Volatility (10)": {
                'color': Fore.YELLOW,
                'features': ['vol_5', 'vol_10', 'vol_20', 'vol_50', 'vol_100', 
                           'vol_gk', 'vol_rs', 'vol_yz', 'atr_14', 'atr_20'],
                'values': [self.get_feature_value(f"volatility_{i}") for i in [5,10,20,50,100]] +
                         [self.get_feature_value(f) for f in ['volatility_gk', 'volatility_rs', 'volatility_yz', 'atr_14', 'atr_20']]
            },
            "Returns (10)": {
                'color': Fore.CYAN,
                'features': ['ret_1', 'ret_2', 'ret_5', 'ret_10', 'ret_20',
                           'ret_50', 'ret_100', 'log_1', 'log_5', 'log_20'],
                'values': [self.get_feature_value(f"returns_{i}") for i in [1,2,5,10,20,50,100]] +
                         [self.get_feature_value(f"log_returns_{i}") for i in [1,5,20]]
            },
            "Order Flow (8)": {
                'color': Fore.MAGENTA,
                'features': ['ofi_5', 'ofi_10', 'ofi_20', 'sv_5', 'sv_10', 'sv_20', 'tf_5', 'tf_10'],
                'values': [self.get_feature_value(f"order_flow_imbalance_{i}") for i in [5,10,20]] +
                         [self.get_feature_value(f"signed_volume_{i}") for i in [5,10,20]] +
                         [self.get_feature_value(f"trade_flow_{i}") for i in [5,10]]
            },
            "Volume (8)": {
                'color': Fore.BLUE,
                'features': ['vol_20', 'vol_50', 'vol_100', 'vol_mean', 'vol_std', 'vol_skew', 'vol_kurt', 'rel_vol'],
                'values': [self.get_feature_value(f"volume_{i}") for i in [20,50,100]] +
                         [self.get_feature_value(f"volume_{stat}") for stat in ['mean', 'std', 'skew', 'kurt']] +
                         [self.get_feature_value("relative_volume")]
            },
            "Technical (8)": {
                'color': Fore.GREEN,
                'features': ['rsi_14', 'ma_5_20', 'ma_20_50', 'ema_dist', 'bb_pos', 'sharpe', 'sortino', 'max_dd'],
                'values': [self.get_feature_value(f) for f in ['rsi_14', 'ma_5_20_ratio', 'ma_20_50_ratio', 
                          'ema_distance', 'bb_position', 'sharpe_20', 'sortino_20', 'max_drawdown_20']]
            },
            "Microstructure (15)": {
                'color': Fore.RED,
                'features': ['spread', 'spr_ma', 'spr_std', 'bid_vol', 'ask_vol', 'bid_lvl', 'ask_lvl',
                           'book_imb', 'book_prs', 'micro_px', 'wmid', 'vwap', 'vwap_d', 'top_tr', 'top_bias'],
                'values': [self.get_feature_value(f) for f in ['spread', 'spread_ma', 'spread_std', 'bid_volume_total',
                          'ask_volume_total', 'bid_levels_active', 'ask_levels_active', 'book_imbalance',
                          'book_pressure', 'micro_price', 'weighted_mid_price', 'vwap', 'vwap_distance',
                          'top_trader_ratio', 'top_trader_side_bias']]
            },
            "Temporal (6)": {
                'color': Fore.WHITE,
                'features': ['hour', 'min', 'h_sin', 'h_cos', 'is_open', 'is_close'],
                'values': [self.get_feature_value(f) for f in ['hour', 'minute', 'hour_sin', 'hour_cos', 
                          'is_opening', 'is_closing']]
            }
        }
        
        # Exibir features por categoria
        for cat_name, cat_info in categories.items():
            print(f"{cat_info['color']}║ {cat_name:<20}", end='')
            
            # Mostrar primeiras 3 features como preview
            preview_features = cat_info['features'][:3]
            preview_values = cat_info['values'][:3]
            
            for feat, val in zip(preview_features, preview_values):
                if isinstance(val, (int, float)):
                    color = Fore.GREEN if val > 0 else Fore.RED if val < 0 else Fore.YELLOW
                    print(f"{color}{feat}:{val:>6.3f} ", end='')
                else:
                    print(f"{Fore.YELLOW}{feat}:-- ", end='')
            
            # Indicador de mais features
            remaining = len(cat_info['features']) - 3
            if remaining > 0:
                print(f"{Fore.WHITE}(+{remaining} more)", end='')
            
            # Preencher espaço restante
            print(f"{' ' * (56 - len(cat_name) - 35)}║{Fore.RESET}")
        
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}╚{'═' * 56}╝{Style.RESET_ALL}")
    
    def draw_agents_panel(self):
        """Painel de Agentes HMARL"""
        print(f"\n{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}╔{'═' * 56}╗{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}║{'🤖 HMARL AGENTS (4 Specialists)':^56}║{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        
        # Agentes simulados
        agents = [
            {"name": "OrderFlowSpecialist", "signal": "BUY", "confidence": 0.75, "weight": 0.30},
            {"name": "LiquidityAgent", "signal": "HOLD", "confidence": 0.60, "weight": 0.20},
            {"name": "TapeReadingAgent", "signal": "BUY", "confidence": 0.65, "weight": 0.25},
            {"name": "FootprintPatternAgent", "signal": "HOLD", "confidence": 0.55, "weight": 0.25}
        ]
        
        for agent in agents:
            # Cor baseada no sinal
            if agent['signal'] == 'BUY':
                signal_color = Fore.GREEN
                signal_icon = "↑"
            elif agent['signal'] == 'SELL':
                signal_color = Fore.RED
                signal_icon = "↓"
            else:
                signal_color = Fore.YELLOW
                signal_icon = "→"
            
            # Barra de confiança
            conf_bar = self.draw_progress_bar(agent['confidence'], 10)
            
            print(f"{Fore.MAGENTA}║ {agent['name']:<22} {signal_color}{signal_icon} {agent['signal']:<5}{Fore.RESET} "
                  f"{conf_bar} {agent['confidence']:.1%} (w:{agent['weight']:.0%}) ║")
        
        # Consenso
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        consensus_signal = "BUY"  # Simulado
        consensus_confidence = 0.68
        consensus_color = Fore.GREEN if consensus_signal == "BUY" else Fore.RED if consensus_signal == "SELL" else Fore.YELLOW
        
        print(f"{Fore.MAGENTA}║ {Style.BRIGHT}CONSENSUS:{Style.NORMAL} "
              f"{consensus_color}{consensus_signal:^8}{Fore.RESET} | "
              f"Confidence: {self.draw_progress_bar(consensus_confidence, 15)} {consensus_confidence:.1%}  ║")
        
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}╚{'═' * 56}╝{Style.RESET_ALL}")
    
    def draw_metrics_panel(self):
        """Painel de Métricas de Performance"""
        print(f"\n{Back.BLACK}{Fore.BLUE}{Style.BRIGHT}╔{'═' * 56}╗{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.BLUE}{Style.BRIGHT}║{'📈 PERFORMANCE METRICS':^56}║{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.BLUE}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        
        # Ler métricas reais
        metrics = self.read_latest_metrics()
        
        # Métricas principais
        metrics_data = [
            ("Features/sec", f"{self.counters['features'] / max(1, (datetime.now() - self.start_time).total_seconds()):.1f}"),
            ("Predictions/sec", f"{self.counters['predictions'] / max(1, (datetime.now() - self.start_time).total_seconds()):.1f}"),
            ("Avg Latency", f"{metrics.get('avg_latency_ms', 0):.1f}ms"),
            ("Total Trades", str(self.counters['trades'])),
            ("Win Rate", f"{metrics.get('win_rate', 0):.1%}"),
            ("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}"),
            ("Max Drawdown", f"{metrics.get('max_drawdown', 0):.1%}"),
            ("PnL Today", f"${metrics.get('pnl_today', 0):.2f}")
        ]
        
        # Exibir em duas colunas
        for i in range(0, len(metrics_data), 2):
            left = metrics_data[i] if i < len(metrics_data) else ("", "")
            right = metrics_data[i+1] if i+1 < len(metrics_data) else ("", "")
            
            # Colorir valores
            left_val = self.colorize_metric(left[0], left[1])
            right_val = self.colorize_metric(right[0], right[1]) if right[0] else ""
            
            print(f"{Fore.BLUE}║ {left[0]:<15} {left_val:<12} │ ", end='')
            if right[0]:
                print(f"{right[0]:<15} {right_val:<12} ║")
            else:
                print(f"{' ' * 28}║")
        
        print(f"{Back.BLACK}{Fore.BLUE}{Style.BRIGHT}╚{'═' * 56}╝{Style.RESET_ALL}")
    
    def draw_trading_panel(self):
        """Painel de Trading em Tempo Real"""
        print(f"\n{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}╔{'═' * 56}╗{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}║{'💰 TRADING ACTIVITY':^56}║{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        
        # Status de posição
        position = self.get_position_status()
        if position > 0:
            pos_str = f"{Fore.GREEN}LONG {position}{Fore.RESET}"
        elif position < 0:
            pos_str = f"{Fore.RED}SHORT {abs(position)}{Fore.RESET}"
        else:
            pos_str = f"{Fore.YELLOW}FLAT{Fore.RESET}"
        
        print(f"{Fore.YELLOW}║ Position: {pos_str:<20} │ Open Orders: 0           ║{Fore.RESET}")
        
        # Últimos trades (simulados por enquanto)
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}║ Recent Trades:{' ' * 41}║{Fore.RESET}")
        
        recent_trades = self.get_recent_trades()
        if recent_trades:
            for trade in recent_trades[-3:]:  # Últimos 3 trades
                trade_color = Fore.GREEN if trade['side'] == 'BUY' else Fore.RED
                pnl_color = Fore.GREEN if trade['pnl'] > 0 else Fore.RED
                print(f"{Fore.YELLOW}║ {trade['time']} {trade_color}{trade['side']:>4}{Fore.RESET} "
                      f"@ {trade['price']} {pnl_color}PnL: ${trade['pnl']:>6.2f}{Fore.RESET}    ║")
        else:
            print(f"{Fore.YELLOW}║   No trades yet{' ' * 40}║{Fore.RESET}")
        
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}╚{'═' * 56}╝{Style.RESET_ALL}")
    
    def draw_logs_panel(self):
        """Painel de Logs Recentes"""
        print(f"\n{Back.BLACK}{Fore.WHITE}{Style.BRIGHT}╔{'═' * 56}╗{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.WHITE}{Style.BRIGHT}║{'📜 SYSTEM LOGS':^56}║{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.WHITE}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        
        logs = self.read_recent_logs(5)
        for log in logs:
            log = log.strip()[:54]  # Limitar tamanho
            
            # Colorir por nível
            if 'ERROR' in log or 'ERRO' in log:
                log_color = Fore.RED
            elif 'WARNING' in log or 'AVISO' in log:
                log_color = Fore.YELLOW
            elif 'TRADE' in log:
                log_color = Fore.GREEN
            elif 'DEBUG' in log:
                log_color = Fore.CYAN
            else:
                log_color = Fore.WHITE
            
            print(f"{log_color}║ {log:<54} ║{Fore.RESET}")
        
        # Preencher linhas vazias se necessário
        for _ in range(5 - len(logs)):
            print(f"{Fore.WHITE}║{' ' * 56}║{Fore.RESET}")
        
        print(f"{Back.BLACK}{Fore.WHITE}{Style.BRIGHT}╚{'═' * 56}╝{Style.RESET_ALL}")
    
    def draw_footer(self):
        """Rodapé com instruções"""
        print(f"\n{Fore.CYAN}{'─' * self.screen_width}{Fore.RESET}")
        
        # Status do sistema
        pid_file = Path('quantum_trader.pid')
        if pid_file.exists():
            status = f"{Fore.GREEN}● SYSTEM RUNNING{Fore.RESET}"
        else:
            status = f"{Fore.RED}● SYSTEM STOPPED{Fore.RESET}"
        
        # Data recording status
        book_count, tick_count = self.count_data_records()
        data_status = f"Book: {book_count:,} | Tick: {tick_count:,}"
        
        print(f"{status} | {data_status} | Press Ctrl+C to exit monitor")
        print(f"{Fore.CYAN}{'─' * self.screen_width}{Fore.RESET}")
    
    # === Métodos auxiliares ===
    
    def draw_progress_bar(self, value, width):
        """Desenha uma barra de progresso"""
        filled = int(value * width)
        empty = width - filled
        
        bar = f"{Fore.GREEN}{'█' * filled}{Fore.WHITE}{'░' * empty}{Fore.RESET}"
        return bar
    
    def colorize_metric(self, name, value):
        """Coloriza valor de métrica baseado no contexto"""
        try:
            if 'Rate' in name or '%' in value:
                val = float(value.replace('%', ''))
                if val >= 60:
                    return f"{Fore.GREEN}{value}{Fore.RESET}"
                elif val >= 40:
                    return f"{Fore.YELLOW}{value}{Fore.RESET}"
                else:
                    return f"{Fore.RED}{value}{Fore.RESET}"
            elif 'PnL' in name or '$' in value:
                val = float(value.replace('$', ''))
                if val > 0:
                    return f"{Fore.GREEN}{value}{Fore.RESET}"
                elif val < 0:
                    return f"{Fore.RED}{value}{Fore.RESET}"
                else:
                    return f"{Fore.YELLOW}{value}{Fore.RESET}"
            elif 'Latency' in name:
                val = float(value.replace('ms', ''))
                if val < 10:
                    return f"{Fore.GREEN}{value}{Fore.RESET}"
                elif val < 50:
                    return f"{Fore.YELLOW}{value}{Fore.RESET}"
                else:
                    return f"{Fore.RED}{value}{Fore.RESET}"
        except:
            pass
        
        return f"{Fore.WHITE}{value}{Fore.RESET}"
    
    def get_feature_value(self, feature_name):
        """Obtém valor de uma feature (simulado por enquanto)"""
        if feature_name in self.last_features:
            return self.last_features[feature_name]
        # Simulado
        return random.uniform(-0.1, 0.1)
    
    def get_position_status(self):
        """Obtém status da posição atual"""
        # TODO: Ler de arquivo ou métricas
        return 0
    
    def get_recent_trades(self):
        """Obtém trades recentes"""
        # TODO: Ler de log ou métricas
        return []
    
    def read_latest_metrics(self):
        """Lê métricas mais recentes"""
        metrics_file = Path('metrics/current_metrics.json')
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r') as f:
                    data = json.load(f)
                    if 'metrics' in data:
                        return data['metrics'].get('gauges', {})
            except:
                pass
        return {}
    
    def read_recent_logs(self, num_lines=5):
        """Lê últimas linhas do log"""
        log_file = Path(f"logs/production_{datetime.now().strftime('%Y%m%d')}.log")
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    return [line.strip() for line in lines[-num_lines:]]
            except:
                pass
        return []
    
    def count_data_records(self):
        """Conta registros gravados"""
        data_dir = Path('data/book_tick_data')
        book_count = 0
        tick_count = 0
        
        if data_dir.exists():
            today = datetime.now().strftime('%Y%m%d')
            for file in data_dir.glob(f'*{today}*.csv'):
                try:
                    with open(file, 'r') as f:
                        line_count = sum(1 for _ in f) - 1
                        if 'book' in file.name:
                            book_count += line_count
                        elif 'tick' in file.name:
                            tick_count += line_count
                except:
                    pass
        
        return book_count, tick_count
    
    def display(self):
        """Exibe o monitor completo"""
        self.clear_screen()
        
        # Layout principal
        self.draw_header()
        
        # Painéis lado a lado (features e agents)
        print(f"{Fore.WHITE}{'=' * self.screen_width}{Fore.RESET}")
        
        # Features Panel (esquerda)
        self.draw_features_panel()
        
        # Agents Panel (direita - na mesma área)
        self.draw_agents_panel()
        
        # Metrics Panel
        self.draw_metrics_panel()
        
        # Trading Panel
        self.draw_trading_panel()
        
        # Logs Panel
        self.draw_logs_panel()
        
        # Footer
        self.draw_footer()
    
    def run(self):
        """Loop principal do monitor"""
        print("Iniciando Enhanced Console Monitor...")
        print(f"Atualizando a cada {self.refresh_rate} segundos...")
        
        if not COLORS_AVAILABLE:
            print("\n[AVISO] Instale 'colorama' para melhor visualização:")
            print("  pip install colorama\n")
            time.sleep(2)
        
        while self.running:
            try:
                self.display()
                time.sleep(self.refresh_rate)
                
                # Atualizar contadores (simulado por enquanto)
                self.counters['features'] += random.randint(0, 2)
                self.counters['predictions'] += random.randint(0, 1)
                if random.random() > 0.9:
                    self.counters['trades'] += 1
                    
            except KeyboardInterrupt:
                print(f"\n\n{Fore.YELLOW}Monitor encerrado.{Fore.RESET}")
                break
            except Exception as e:
                print(f"{Fore.RED}Erro no monitor: {e}{Fore.RESET}")
                time.sleep(5)


def main():
    """Função principal"""
    monitor = EnhancedConsoleMonitor()
    monitor.run()


if __name__ == "__main__":
    main()