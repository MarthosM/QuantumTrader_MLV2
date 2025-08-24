"""
Monitor Enhanced para Sistema Baseado em Regime
Exibe informações do detector de regime, estratégias e HMARL
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from collections import deque
import numpy as np

# Adicionar path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Importar bridge dos agentes HMARL
try:
    from src.monitoring.hmarl_monitor_bridge import get_bridge
    BRIDGE_AVAILABLE = True
except ImportError:
    BRIDGE_AVAILABLE = False

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


class RegimeMonitor:
    """Monitor para Sistema de Trading Baseado em Regime"""
    
    def __init__(self):
        self.running = True
        self.start_time = datetime.now()
        
        # Histórico de dados
        self.regime_history = deque(maxlen=100)
        self.signal_history = deque(maxlen=50)
        self.trade_history = deque(maxlen=50)
        
        # Contadores
        self.counters = {
            'uptrend_signals': 0,
            'downtrend_signals': 0,
            'lateral_signals': 0,
            'total_trades': 0,
            'wins': 0,
            'losses': 0
        }
        
        # Cache de dados
        self.last_regime = "UNDEFINED"
        self.last_signal = None
        self.last_update = datetime.now()
        
        # Configuração de display
        self.screen_width = 120
        self.refresh_rate = 2  # segundos
    
    def clear_screen(self):
        """Limpa a tela"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def draw_header(self):
        """Desenha cabeçalho do monitor"""
        print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}")
        print("=" * self.screen_width)
        print(f"{'QUANTUM TRADER - REGIME-BASED SYSTEM MONITOR':^{self.screen_width}}")
        print(f"{'Regime Detection | Strategy Selection | HMARL Timing':^{self.screen_width}}")
        print("=" * self.screen_width)
        print(Style.RESET_ALL)
        
        # Info bar
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        info = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] | Uptime: {uptime_str} | Refresh: {self.refresh_rate}s"
        print(f"{Fore.CYAN}{info:^{self.screen_width}}{Fore.RESET}\n")
    
    def draw_regime_panel(self):
        """Painel de Detecção de Regime"""
        print(f"\n{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}|{'MARKET REGIME DETECTOR':^56}|{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
        
        # Ler dados do regime
        regime_data = self.read_regime_status()
        
        current_regime = regime_data.get('regime', 'UNDEFINED')
        regime_confidence = regime_data.get('confidence', 0.0)
        
        # Definir cor e ícone baseado no regime
        regime_colors = {
            'strong_uptrend': (Fore.GREEN + Style.BRIGHT, '^^'),
            'uptrend': (Fore.GREEN, '^'),
            'lateral': (Fore.YELLOW, '='),
            'downtrend': (Fore.RED, 'v'),
            'strong_downtrend': (Fore.RED + Style.BRIGHT, 'vv'),
            'undefined': (Fore.WHITE, '?')
        }
        
        color, icon = regime_colors.get(current_regime.lower(), (Fore.WHITE, '❓'))
        
        print(f"{Fore.CYAN}| Current Regime: {color}{current_regime.upper():<20}{Fore.RESET} {icon}      |")
        print(f"{Fore.CYAN}| Confidence: {self.draw_progress_bar(regime_confidence, 15)} {regime_confidence:.1%}  |")
        
        # Estratégia ativa baseada no regime
        if 'trend' in current_regime.lower():
            strategy = "TREND FOLLOWING"
            rr_ratio = "1.5:1"
            strategy_color = Fore.CYAN
        elif 'lateral' in current_regime.lower():
            strategy = "SUPPORT/RESISTANCE"
            rr_ratio = "1.0:1"
            strategy_color = Fore.MAGENTA
        else:
            strategy = "WAITING"
            rr_ratio = "N/A"
            strategy_color = Fore.WHITE
        
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
        print(f"{Fore.CYAN}| Active Strategy: {strategy_color}{strategy:<20}{Fore.RESET}       |")
        print(f"{Fore.CYAN}| Risk/Reward: {Fore.YELLOW}{rr_ratio:<10}{Fore.RESET}                         |")
        
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
    
    def draw_signals_panel(self):
        """Painel de Sinais de Trading"""
        print(f"\n{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}|{'TRADING SIGNALS':^56}|{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
        
        # Ler último sinal
        signal_data = self.read_latest_signal()
        
        if signal_data:
            signal = signal_data.get('signal', 0)
            confidence = signal_data.get('confidence', 0.0)
            entry_price = signal_data.get('entry_price', 0)
            stop_loss = signal_data.get('stop_loss', 0)
            take_profit = signal_data.get('take_profit', 0)
            
            # Cor e direção do sinal
            if signal > 0:
                signal_color = Fore.GREEN
                direction = "BUY ^"
            elif signal < 0:
                signal_color = Fore.RED
                direction = "SELL v"
            else:
                signal_color = Fore.YELLOW
                direction = "HOLD ="
            
            print(f"{Fore.CYAN}| Last Signal: {signal_color}{direction:<10}{Fore.RESET}                        |")
            print(f"{Fore.CYAN}| Confidence: {self.draw_progress_bar(confidence, 15)} {confidence:.1%}  |")
            
            if signal != 0 and entry_price > 0:
                print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
                print(f"{Fore.CYAN}| Entry: {Fore.WHITE}{entry_price:>8.2f}{Fore.RESET}  "
                      f"Stop: {Fore.RED}{stop_loss:>8.2f}{Fore.RESET}  "
                      f"Target: {Fore.GREEN}{take_profit:>8.2f}{Fore.RESET} |")
        else:
            print(f"{Fore.CYAN}| {Fore.YELLOW}Waiting for signals...{Fore.RESET}                        |")
        
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
    
    def draw_hmarl_panel(self):
        """Painel de Agentes HMARL para Timing"""
        print(f"\n{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}|{'HMARL TIMING AGENTS':^56}|{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
        
        # Obter dados dos agentes
        agents = self.get_hmarl_agents()
        
        for agent in agents:
            name = agent['name']
            signal = agent['signal']
            confidence = agent['confidence']
            
            # Cor baseada no sinal
            if signal == 'BUY':
                signal_color = Fore.GREEN
                icon = "^"
            elif signal == 'SELL':
                signal_color = Fore.RED
                icon = "v"
            else:
                signal_color = Fore.YELLOW
                icon = "="
            
            conf_bar = self.draw_progress_bar(confidence, 10)
            print(f"{Fore.CYAN}| {name:<15} {signal_color}{icon} {signal:<5}{Fore.RESET} "
                  f"{conf_bar} {confidence:.1%}  |")
        
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
    
    def draw_statistics_panel(self):
        """Painel de Estatísticas"""
        print(f"\n{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}|{'TRADING STATISTICS':^56}|{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
        
        # Estatísticas de regime
        stats = self.read_statistics()
        
        total_trades = stats.get('total_trades', 0)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Estatísticas por regime
        trend_trades = stats.get('trend_trades', 0)
        lateral_trades = stats.get('lateral_trades', 0)
        
        print(f"{Fore.CYAN}| Total Trades: {Fore.WHITE}{total_trades:>5}{Fore.RESET}  "
              f"Wins: {Fore.GREEN}{wins:>3}{Fore.RESET}  "
              f"Losses: {Fore.RED}{losses:>3}{Fore.RESET}  "
              f"WR: {self.get_colored_percentage(win_rate)}%  |")
        
        print(f"{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}| Trend Trades: {Fore.WHITE}{trend_trades:>5}{Fore.RESET}  "
              f"Lateral Trades: {Fore.WHITE}{lateral_trades:>5}{Fore.RESET}         |")
        
        # Distribuição de regimes
        regime_dist = stats.get('regime_distribution', {})
        if regime_dist:
            total_periods = sum(regime_dist.values())
            trend_pct = (regime_dist.get('uptrend', 0) + regime_dist.get('downtrend', 0)) / total_periods * 100 if total_periods > 0 else 0
            lateral_pct = regime_dist.get('lateral', 0) / total_periods * 100 if total_periods > 0 else 0
            
            print(f"{Fore.CYAN}| Market: Trend {Fore.GREEN}{trend_pct:.0f}%{Fore.RESET} | "
                  f"Lateral {Fore.YELLOW}{lateral_pct:.0f}%{Fore.RESET}                  |")
        
        print(f"{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}+{'-' * 56}+{Style.RESET_ALL}")
    
    def draw_progress_bar(self, value, width=10):
        """Desenha barra de progresso"""
        filled = int(value * width)
        empty = width - filled
        
        if value >= 0.7:
            color = Fore.GREEN
        elif value >= 0.4:
            color = Fore.YELLOW
        else:
            color = Fore.RED
        
        return f"{color}{'#' * filled}{Fore.WHITE}{'.' * empty}{Fore.RESET}"
    
    def get_colored_percentage(self, value):
        """Retorna percentual colorido"""
        if value >= 60:
            return f"{Fore.GREEN}{value:.0f}{Fore.RESET}"
        elif value >= 40:
            return f"{Fore.YELLOW}{value:.0f}{Fore.RESET}"
        else:
            return f"{Fore.RED}{value:.0f}{Fore.RESET}"
    
    def read_regime_status(self):
        """Lê status do regime do arquivo"""
        try:
            status_file = Path('data/monitor/regime_status.json')
            if status_file.exists():
                with open(status_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        
        return {
            'regime': 'undefined',
            'confidence': 0.0
        }
    
    def read_latest_signal(self):
        """Lê último sinal de trading"""
        try:
            signal_file = Path('data/monitor/latest_signal.json')
            if signal_file.exists():
                with open(signal_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return None
    
    def read_statistics(self):
        """Lê estatísticas do sistema"""
        try:
            stats_file = Path('data/monitor/regime_stats.json')
            if stats_file.exists():
                with open(stats_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'trend_trades': 0,
            'lateral_trades': 0,
            'regime_distribution': {}
        }
    
    def get_hmarl_agents(self):
        """Obtém dados dos agentes HMARL"""
        if BRIDGE_AVAILABLE:
            try:
                bridge = get_bridge()
                agents = bridge.get_formatted_agents_data()
                if agents:
                    return agents
            except Exception:
                pass
        
        # Dados padrão
        return [
            {"name": "OrderFlow", "signal": "HOLD", "confidence": 0.50},
            {"name": "Liquidity", "signal": "HOLD", "confidence": 0.50},
            {"name": "TapeReading", "signal": "HOLD", "confidence": 0.50},
            {"name": "Footprint", "signal": "HOLD", "confidence": 0.50}
        ]
    
    def run(self):
        """Loop principal do monitor"""
        print(f"{Fore.GREEN}Iniciando Monitor do Sistema Baseado em Regime...{Fore.RESET}")
        print(f"{Fore.YELLOW}Pressione Ctrl+C para sair{Fore.RESET}\n")
        
        try:
            while self.running:
                self.clear_screen()
                self.draw_header()
                self.draw_regime_panel()
                self.draw_signals_panel()
                self.draw_hmarl_panel()
                self.draw_statistics_panel()
                
                # Footer
                print(f"\n{Fore.CYAN}{'-' * self.screen_width}{Fore.RESET}")
                print(f"{Fore.WHITE}Sistema: Regime Detection -> Strategy Selection -> HMARL Timing -> Trade Execution{Fore.RESET}")
                print(f"{Fore.WHITE}Risk/Reward: Tendencia 1.5:1 | Lateralizacao 1.0:1{Fore.RESET}")
                
                time.sleep(self.refresh_rate)
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Monitor encerrado pelo usuário{Fore.RESET}")
        except Exception as e:
            print(f"\n{Fore.RED}Erro no monitor: {e}{Fore.RESET}")
        finally:
            self.running = False
            print(f"{Fore.GREEN}Monitor finalizado{Fore.RESET}")


def main():
    """Função principal"""
    monitor = RegimeMonitor()
    monitor.run()


if __name__ == "__main__":
    main()