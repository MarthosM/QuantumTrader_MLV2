"""
Monitor Unificado - Sistema Completo com Regime + HMARL
Combina informações do regime, features, ML e HMARL em uma única interface
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


class UnifiedSystemMonitor:
    """Monitor Unificado para Sistema Completo"""
    
    def __init__(self):
        self.running = True
        self.start_time = datetime.now()
        
        # Histórico de dados
        self.feature_history = deque(maxlen=100)
        self.regime_history = deque(maxlen=100)
        self.signal_history = deque(maxlen=50)
        self.trade_history = deque(maxlen=50)
        
        # Contadores
        self.counters = {
            'features': 0,
            'predictions': 0,
            'trades': 0,
            'regime_changes': 0,
            'signals_generated': 0
        }
        
        # Cache de dados
        self.last_regime = "UNDEFINED"
        self.last_signal = None
        self.last_features = {}
        self.last_update = datetime.now()
        
        # Configuração de display
        self.screen_width = 120
        self.refresh_rate = 2  # segundos
        
        # Estatísticas
        self.stats = {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'trend_trades': 0,
            'lateral_trades': 0
        }
    
    def clear_screen(self):
        """Limpa a tela"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def draw_header(self):
        """Desenha cabeçalho do monitor"""
        print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}")
        print("=" * self.screen_width)
        print(f"{'QUANTUM TRADER - UNIFIED SYSTEM MONITOR':^{self.screen_width}}")
        print(f"{'Regime Detection | ML Layers | HMARL Agents | Real-time Trading':^{self.screen_width}}")
        print("=" * self.screen_width)
        print(Style.RESET_ALL)
        
        # Info bar
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        info = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] | Uptime: {uptime_str} | Refresh: {self.refresh_rate}s"
        print(f"{Fore.CYAN}{info:^{self.screen_width}}{Fore.RESET}\n")
    
    def draw_regime_panel(self):
        """Painel de Regime e Estratégia"""
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}+{'=' * 58}+{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}|{'MARKET REGIME & STRATEGY':^58}|{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}+{'-' * 58}+{Style.RESET_ALL}")
        
        # Ler dados do regime
        regime_data = self.read_regime_status()
        current_regime = regime_data.get('regime', 'UNDEFINED')
        regime_confidence = regime_data.get('confidence', 0.0)
        strategy = regime_data.get('strategy', 'none')
        
        # Definir cor baseado no regime
        regime_colors = {
            'strong_uptrend': Fore.GREEN + Style.BRIGHT,
            'uptrend': Fore.GREEN,
            'lateral': Fore.YELLOW,
            'downtrend': Fore.RED,
            'strong_downtrend': Fore.RED + Style.BRIGHT,
            'undefined': Fore.WHITE
        }
        
        color = regime_colors.get(current_regime.lower(), Fore.WHITE)
        
        # Estratégia e RR
        if 'trend' in current_regime.lower():
            strategy_display = "TREND FOLLOWING (RR 1.5:1)"
            strategy_color = Fore.CYAN
        elif 'lateral' in current_regime.lower():
            strategy_display = "SUPPORT/RESISTANCE (RR 1.0:1)"
            strategy_color = Fore.MAGENTA
        else:
            strategy_display = "WAITING FOR SETUP"
            strategy_color = Fore.WHITE
        
        print(f"{Fore.CYAN}| Regime: {color}{current_regime.upper():<15}{Fore.RESET} "
              f"Conf: {self.draw_progress_bar(regime_confidence, 10)} {regime_confidence:.0%}  |")
        print(f"{Fore.CYAN}| Strategy: {strategy_color}{strategy_display:<44}{Fore.RESET} |")
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}+{'=' * 58}+{Style.RESET_ALL}")
    
    def draw_ml_panel(self):
        """Painel ML (compatibilidade)"""
        print(f"\n{Back.BLACK}{Fore.BLUE}{Style.BRIGHT}+{'=' * 58}+{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.BLUE}{Style.BRIGHT}|{'ML SYSTEM STATUS (3 Layers)':^58}|{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.BLUE}{Style.BRIGHT}+{'-' * 58}+{Style.RESET_ALL}")
        
        # Ler status ML/Regime
        ml_data = self.read_ml_status()
        
        # Mostrar camadas (agora baseado em regime)
        if ml_data.get('regime'):
            regime = ml_data.get('regime', 'undefined')
            confidence = ml_data.get('confidence', 0.0)
            
            # Simular camadas baseado no regime
            if 'trend' in regime.lower():
                context = 'TREND'
                micro = 'MOMENTUM'
            elif 'lateral' in regime.lower():
                context = 'RANGE'
                micro = 'REVERSAL'
            else:
                context = 'NEUTRAL'
                micro = 'NEUTRAL'
            
            print(f"{Fore.CYAN}| Context Layer: {Fore.YELLOW}{context:<12}{Fore.RESET} "
                  f"Micro: {Fore.YELLOW}{micro:<12}{Fore.RESET}      |")
            print(f"{Fore.CYAN}| Meta Decision: {self.get_signal_color(ml_data.get('signal', 0))}"
                  f"{self.get_signal_text(ml_data.get('signal', 0)):<10}{Fore.RESET} "
                  f"Confidence: {confidence:.0%}          |")
        else:
            print(f"{Fore.CYAN}| {Fore.YELLOW}System initializing...{Fore.RESET}                               |")
        
        print(f"{Back.BLACK}{Fore.BLUE}{Style.BRIGHT}+{'=' * 58}+{Style.RESET_ALL}")
    
    def draw_signals_panel(self):
        """Painel de Sinais de Trading"""
        print(f"\n{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}+{'=' * 58}+{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}|{'TRADING SIGNALS & LEVELS':^58}|{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}+{'-' * 58}+{Style.RESET_ALL}")
        
        # Ler último sinal
        signal_data = self.read_latest_signal()
        
        if signal_data:
            signal = signal_data.get('signal', 0)
            confidence = signal_data.get('confidence', 0.0)
            entry = signal_data.get('entry_price', 0)
            stop = signal_data.get('stop_loss', 0)
            target = signal_data.get('take_profit', 0)
            rr = signal_data.get('risk_reward', 0)
            
            signal_color = self.get_signal_color(signal)
            signal_text = self.get_signal_text(signal)
            
            print(f"{Fore.CYAN}| Signal: {signal_color}{signal_text:<8}{Fore.RESET} "
                  f"Conf: {confidence:.0%} "
                  f"RR: {Fore.YELLOW}{rr:.1f}:1{Fore.RESET}                    |")
            
            if signal != 0 and entry > 0:
                print(f"{Fore.CYAN}| Entry: {Fore.WHITE}{entry:>8.2f}{Fore.RESET}  "
                      f"Stop: {Fore.RED}{stop:>8.2f}{Fore.RESET}  "
                      f"Target: {Fore.GREEN}{target:>8.2f}{Fore.RESET}   |")
            else:
                print(f"{Fore.CYAN}| {Fore.YELLOW}Waiting for valid setup...{Fore.RESET}                          |")
        else:
            print(f"{Fore.CYAN}| {Fore.YELLOW}No signals generated yet...{Fore.RESET}                         |")
            print(f"{Fore.CYAN}| {Fore.WHITE}System analyzing market conditions{Fore.RESET}                  |")
        
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}+{'=' * 58}+{Style.RESET_ALL}")
    
    def draw_hmarl_panel(self):
        """Painel HMARL compacto"""
        print(f"\n{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}+{'=' * 58}+{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}|{'HMARL AGENTS CONSENSUS (Timing)':^58}|{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}+{'-' * 58}+{Style.RESET_ALL}")
        
        # Obter dados dos agentes
        agents = self.get_hmarl_agents()
        
        # Mostrar em linha única
        agent_summary = []
        consensus_buy = 0
        consensus_sell = 0
        
        for agent in agents:
            if agent['signal'] == 'BUY':
                consensus_buy += 1
                agent_summary.append(f"{Fore.GREEN}{agent['name'][:3]}^{Fore.RESET}")
            elif agent['signal'] == 'SELL':
                consensus_sell += 1
                agent_summary.append(f"{Fore.RED}{agent['name'][:3]}v{Fore.RESET}")
            else:
                agent_summary.append(f"{Fore.YELLOW}{agent['name'][:3]}={Fore.RESET}")
        
        # Consenso final
        if consensus_buy > consensus_sell and consensus_buy >= 2:
            consensus = "BUY"
            consensus_color = Fore.GREEN
        elif consensus_sell > consensus_buy and consensus_sell >= 2:
            consensus = "SELL"
            consensus_color = Fore.RED
        else:
            consensus = "HOLD"
            consensus_color = Fore.YELLOW
        
        agents_str = " ".join(agent_summary)
        print(f"{Fore.CYAN}| Agents: {agents_str}  Consensus: {consensus_color}{consensus:<6}{Fore.RESET}     |")
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}+{'=' * 58}+{Style.RESET_ALL}")
    
    def draw_performance_panel(self):
        """Painel de Performance"""
        print(f"\n{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}+{'=' * 58}+{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}|{'PERFORMANCE & STATISTICS':^58}|{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}+{'-' * 58}+{Style.RESET_ALL}")
        
        # Ler estatísticas
        stats = self.read_statistics()
        
        total = stats.get('total_trades', 0)
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        wr = (wins / total * 100) if total > 0 else 0
        
        trend_trades = stats.get('trend_trades', 0)
        lateral_trades = stats.get('lateral_trades', 0)
        
        # Distribuição de regime
        regime_dist = stats.get('regime_distribution', {})
        total_periods = sum(regime_dist.values()) if regime_dist else 0
        
        trend_pct = 0
        lateral_pct = 0
        if total_periods > 0:
            for regime, count in regime_dist.items():
                if 'trend' in regime.lower():
                    trend_pct += count / total_periods * 100
                elif 'lateral' in regime.lower():
                    lateral_pct += count / total_periods * 100
        
        # Primeira linha - trades
        print(f"{Fore.CYAN}| Trades: {Fore.WHITE}{total:>3}{Fore.RESET}  "
              f"W: {Fore.GREEN}{wins:>3}{Fore.RESET}  "
              f"L: {Fore.RED}{losses:>3}{Fore.RESET}  "
              f"WR: {self.get_colored_percentage(wr)}%  "
              f"Trend: {trend_trades:>3}  Lateral: {lateral_trades:>3} |")
        
        # Segunda linha - distribuição de mercado
        print(f"{Fore.CYAN}| Market: "
              f"Trending {Fore.GREEN}{trend_pct:.0f}%{Fore.RESET} | "
              f"Ranging {Fore.YELLOW}{lateral_pct:.0f}%{Fore.RESET} | "
              f"Other {Fore.WHITE}{100-trend_pct-lateral_pct:.0f}%{Fore.RESET}        |")
        
        print(f"{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}+{'=' * 58}+{Style.RESET_ALL}")
    
    def draw_status_bar(self):
        """Barra de status inferior"""
        # Verificar se sistema está rodando
        system_status = self.check_system_status()
        
        if system_status:
            status_color = Fore.GREEN
            status_text = "SYSTEM RUNNING"
        else:
            status_color = Fore.RED
            status_text = "SYSTEM STOPPED"
        
        # Contar sinais e trades hoje
        signals_today = self.counters.get('signals_generated', 0)
        trades_today = self.stats.get('total_trades', 0)
        
        print(f"\n{Fore.CYAN}{'-' * self.screen_width}{Fore.RESET}")
        print(f"{status_color}* {status_text}{Fore.RESET} | "
              f"Signals Today: {signals_today} | "
              f"Trades Today: {trades_today} | "
              f"Press Ctrl+C to exit")
        print(f"{Fore.CYAN}{'-' * self.screen_width}{Fore.RESET}")
    
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
    
    def get_signal_color(self, signal):
        """Retorna cor baseada no sinal"""
        if signal > 0:
            return Fore.GREEN
        elif signal < 0:
            return Fore.RED
        else:
            return Fore.YELLOW
    
    def get_signal_text(self, signal):
        """Retorna texto do sinal"""
        if signal > 0:
            return "BUY"
        elif signal < 0:
            return "SELL"
        else:
            return "HOLD"
    
    def get_colored_percentage(self, value):
        """Retorna percentual colorido"""
        if value >= 60:
            return f"{Fore.GREEN}{value:.0f}{Fore.RESET}"
        elif value >= 40:
            return f"{Fore.YELLOW}{value:.0f}{Fore.RESET}"
        else:
            return f"{Fore.RED}{value:.0f}{Fore.RESET}"
    
    def read_regime_status(self):
        """Lê status do regime"""
        try:
            status_file = Path('data/monitor/regime_status.json')
            if status_file.exists():
                with open(status_file, 'r') as f:
                    data = json.load(f)
                    # Atualizar contador se mudou
                    if data.get('regime') != self.last_regime:
                        self.counters['regime_changes'] += 1
                        self.last_regime = data.get('regime')
                    return data
        except Exception:
            pass
        return {'regime': 'undefined', 'confidence': 0.0}
    
    def read_ml_status(self):
        """Lê status ML (compatibilidade)"""
        try:
            # Primeiro tentar ler regime (novo sistema)
            regime_data = self.read_regime_status()
            if regime_data.get('regime') != 'undefined':
                return regime_data
            
            # Fallback para ML status antigo
            ml_file = Path('data/monitor/ml_status.json')
            if ml_file.exists():
                with open(ml_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def read_latest_signal(self):
        """Lê último sinal"""
        try:
            signal_file = Path('data/monitor/latest_signal.json')
            if signal_file.exists():
                with open(signal_file, 'r') as f:
                    data = json.load(f)
                    # Atualizar contador se é novo sinal
                    if data != self.last_signal:
                        self.counters['signals_generated'] += 1
                        self.last_signal = data
                    return data
        except Exception:
            pass
        return None
    
    def read_statistics(self):
        """Lê estatísticas"""
        try:
            stats_file = Path('data/monitor/regime_stats.json')
            if stats_file.exists():
                with open(stats_file, 'r') as f:
                    data = json.load(f)
                    # Atualizar stats locais
                    self.stats.update(data)
                    return data
        except Exception:
            pass
        return self.stats
    
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
    
    def check_system_status(self):
        """Verifica se sistema está rodando"""
        try:
            # Verificar se arquivo de status existe e é recente
            status_file = Path('data/monitor/regime_status.json')
            if status_file.exists():
                # Se foi atualizado nos últimos 10 segundos
                age = time.time() - status_file.stat().st_mtime
                return age < 10
        except Exception:
            pass
        return False
    
    def run(self):
        """Loop principal do monitor"""
        print(f"{Fore.GREEN}Iniciando Monitor Unificado...{Fore.RESET}")
        print(f"{Fore.YELLOW}Pressione Ctrl+C para sair{Fore.RESET}\n")
        
        try:
            while self.running:
                self.clear_screen()
                self.draw_header()
                self.draw_regime_panel()
                self.draw_ml_panel()
                self.draw_signals_panel()
                self.draw_hmarl_panel()
                self.draw_performance_panel()
                self.draw_status_bar()
                
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
    monitor = UnifiedSystemMonitor()
    monitor.run()


if __name__ == "__main__":
    main()