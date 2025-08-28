"""
Monitor Visual Integrado - Display completo com HMARL, ML e Position Monitor
Performance otimizada com cache e atualizações assíncronas
"""

import os
import sys
import time
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
import numpy as np

# Adicionar path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Importar componentes
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
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = BLACK = RESET = ''
    class Back:
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ''


class IntegratedVisualMonitor:
    """Monitor Visual Integrado com otimizações de performance"""
    
    def __init__(self):
        self.running = True
        self.start_time = datetime.now()
        
        # Cache com TTL para evitar leituras desnecessárias
        self.cache = {
            'position': {'data': None, 'timestamp': None, 'ttl': 1.0},  # 1 segundo
            'metrics': {'data': None, 'timestamp': None, 'ttl': 2.0},   # 2 segundos
            'agents': {'data': None, 'timestamp': None, 'ttl': 0.5},    # 500ms
            'ml_status': {'data': None, 'timestamp': None, 'ttl': 1.0}, # 1 segundo
            'decisions': {'data': [], 'timestamp': None, 'ttl': 0.5}    # 500ms
        }
        
        # Histórico de decisões (circular buffer)
        self.decision_history = deque(maxlen=10)
        self.trade_history = deque(maxlen=20)
        
        # Contadores e métricas
        self.counters = {
            'updates': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0
        }
        
        # Configuração de display
        self.screen_width = 120
        self.refresh_rate = 0.5  # Mais rápido mas com cache
        
        # Thread de atualização de cache
        self.cache_thread = threading.Thread(target=self._cache_updater, daemon=True)
        self.cache_thread.start()
    
    def _get_cached_data(self, key, fetcher_func):
        """Obtém dados com cache para otimizar performance"""
        now = datetime.now()
        cache_entry = self.cache.get(key)
        
        if cache_entry and cache_entry['timestamp']:
            age = (now - cache_entry['timestamp']).total_seconds()
            if age < cache_entry['ttl']:
                self.counters['cache_hits'] += 1
                return cache_entry['data']
        
        # Cache miss - buscar novos dados
        self.counters['cache_misses'] += 1
        try:
            data = fetcher_func()
            self.cache[key] = {
                'data': data,
                'timestamp': now,
                'ttl': cache_entry['ttl'] if cache_entry else 1.0
            }
            return data
        except Exception as e:
            self.counters['errors'] += 1
            return cache_entry['data'] if cache_entry else None
    
    def _cache_updater(self):
        """Thread para atualizar cache em background (não bloqueia display)"""
        while self.running:
            try:
                # Atualizar dados críticos em background
                self._update_position_cache()
                self._update_metrics_cache()
                time.sleep(0.5)
            except:
                pass
    
    def _update_position_cache(self):
        """Atualiza cache de posição"""
        position_file = Path('data/monitor/position_status.json')
        if position_file.exists():
            try:
                with open(position_file, 'r') as f:
                    data = json.load(f)
                    self.cache['position']['data'] = data
                    self.cache['position']['timestamp'] = datetime.now()
            except:
                pass
    
    def _update_metrics_cache(self):
        """Atualiza cache de métricas"""
        metrics_file = Path('metrics/current_metrics.json')
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r') as f:
                    data = json.load(f)
                    self.cache['metrics']['data'] = data
                    self.cache['metrics']['timestamp'] = datetime.now()
            except:
                pass
    
    def clear_screen(self):
        """Limpa a tela"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def draw_header(self):
        """Cabeçalho otimizado"""
        print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}")
        print("═" * self.screen_width)
        print(f"{'QUANTUM TRADER - MONITOR VISUAL INTEGRADO':^{self.screen_width}}")
        print(f"{'Position Monitor | HMARL Agents | ML Models | Real-time Decisions':^{self.screen_width}}")
        print("═" * self.screen_width)
        print(Style.RESET_ALL)
        
        # Info bar com cache stats
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        cache_ratio = self.counters['cache_hits'] / max(1, self.counters['cache_hits'] + self.counters['cache_misses'])
        
        info = (f"⏰ {datetime.now().strftime('%H:%M:%S')} | "
                f"⏱️ {uptime_str} | "
                f"🔄 {self.refresh_rate}s | "
                f"💾 Cache: {cache_ratio:.0%}")
        print(f"{Fore.CYAN}{info:^{self.screen_width}}{Fore.RESET}\n")
    
    def draw_position_panel(self):
        """Painel de Posição Integrado com Position Monitor"""
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}╔{'═' * 56}╗{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}║{'💼 POSITION MONITOR':^56}║{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        
        # Obter dados do Position Monitor
        position_data = self._get_cached_data('position', self._fetch_position_data)
        
        if position_data and position_data.get('has_position'):
            positions = position_data.get('positions', [])
            if positions:
                pos = positions[0]  # Primeira posição
                
                # Cores baseadas em P&L
                pnl = pos.get('pnl', 0)
                pnl_color = Fore.GREEN if pnl > 0 else Fore.RED if pnl < 0 else Fore.YELLOW
                
                # Status da posição
                side_color = Fore.GREEN if pos['side'] == 'BUY' else Fore.RED
                
                print(f"{Fore.GREEN}║ Symbol: {Fore.WHITE}{pos['symbol']:<10} "
                      f"│ Side: {side_color}{pos['side']:<4}{Fore.GREEN} "
                      f"│ Qty: {Fore.WHITE}{pos['quantity']:>2}{Fore.GREEN}  ║{Style.RESET_ALL}")
                
                print(f"{Fore.GREEN}║ Entry: {Fore.WHITE}{pos['entry_price']:>8.2f} "
                      f"│ Current: {Fore.YELLOW}{pos['current_price']:>8.2f} "
                      f"│ P&L: {pnl_color}{pnl:>+7.2f}{Fore.GREEN} ║{Style.RESET_ALL}")
                
                print(f"{Fore.GREEN}║ Stop: {Fore.RED}{pos.get('stop_price', 0):>8.2f} "
                      f"│ Take: {Fore.GREEN}{pos.get('take_price', 0):>8.2f} "
                      f"│ P&L%: {pnl_color}{pos.get('pnl_percentage', 0):>+6.2f}%{Fore.GREEN} ║{Style.RESET_ALL}")
                
                # Tempo na posição
                if 'open_time' in pos:
                    open_time = datetime.fromisoformat(pos['open_time'])
                    duration = datetime.now() - open_time
                    duration_str = str(duration).split('.')[0]
                else:
                    duration_str = "00:00:00"
                
                print(f"{Fore.GREEN}║ Status: {Fore.YELLOW}{pos.get('status', 'open'):<10} "
                      f"│ Duration: {Fore.CYAN}{duration_str:>12}       ║{Style.RESET_ALL}")
            else:
                self._draw_no_position()
        else:
            self._draw_no_position()
        
        print(f"{Back.BLACK}{Fore.GREEN}{Style.BRIGHT}╚{'═' * 56}╝{Style.RESET_ALL}")
    
    def _draw_no_position(self):
        """Desenha quando não há posição"""
        print(f"{Fore.YELLOW}║{'NO POSITION':^56}║{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}║{'Waiting for signal...':^56}║{Style.RESET_ALL}")
    
    def draw_ml_panel(self):
        """Painel ML otimizado"""
        print(f"\n{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}╔{'═' * 56}╗{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}║{'🧠 ML MODELS (3 Layers)':^56}║{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        
        ml_data = self._get_cached_data('ml_status', self._fetch_ml_status)
        
        if ml_data:
            # Mostrar predições das 3 camadas
            layers = [
                ('Context Layer', ml_data.get('context_pred', 'HOLD'), ml_data.get('context_conf', 0.5)),
                ('Microstructure', ml_data.get('micro_pred', 'HOLD'), ml_data.get('micro_conf', 0.5)),
                ('Meta-Learner', ml_data.get('meta_pred', 'HOLD'), ml_data.get('meta_conf', 0.5))
            ]
            
            for name, pred, conf in layers:
                pred_color = Fore.GREEN if pred == 'BUY' else Fore.RED if pred == 'SELL' else Fore.YELLOW
                icon = "↑" if pred == 'BUY' else "↓" if pred == 'SELL' else "→"
                conf_bar = self._draw_mini_bar(conf, 10)
                
                print(f"{Fore.CYAN}║ {name:<20} {pred_color}{icon} {pred:<5}{Fore.CYAN} "
                      f"{conf_bar} {conf:.1%}      ║{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}║{'ML Models Loading...':^56}║{Style.RESET_ALL}")
        
        print(f"{Back.BLACK}{Fore.CYAN}{Style.BRIGHT}╚{'═' * 56}╝{Style.RESET_ALL}")
    
    def draw_agents_panel(self):
        """Painel HMARL otimizado"""
        print(f"\n{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}╔{'═' * 56}╗{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}║{'🤖 HMARL AGENTS':^56}║{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        
        agents = self._get_cached_data('agents', self._fetch_agents_data)
        
        if agents:
            for agent in agents:
                signal_color = Fore.GREEN if agent['signal'] == 'BUY' else Fore.RED if agent['signal'] == 'SELL' else Fore.YELLOW
                icon = "↑" if agent['signal'] == 'BUY' else "↓" if agent['signal'] == 'SELL' else "→"
                conf_bar = self._draw_mini_bar(agent['confidence'], 10)
                
                print(f"{Fore.MAGENTA}║ {agent['name']:<20} {signal_color}{icon} {agent['signal']:<5}{Fore.MAGENTA} "
                      f"{conf_bar} {agent['confidence']:.1%}      ║{Style.RESET_ALL}")
        else:
            # Agentes padrão
            default_agents = ['OrderFlow', 'Liquidity', 'TapeReading', 'Footprint']
            for name in default_agents:
                print(f"{Fore.MAGENTA}║ {name:<20} {Fore.YELLOW}→ HOLD  "
                      f"{'█' * 5 + '░' * 5} 50.0%      ║{Style.RESET_ALL}")
        
        print(f"{Back.BLACK}{Fore.MAGENTA}{Style.BRIGHT}╚{'═' * 56}╝{Style.RESET_ALL}")
    
    def draw_decisions_panel(self):
        """Painel de Decisões em Tempo Real"""
        print(f"\n{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}╔{'═' * 56}╗{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}║{'⚡ REAL-TIME DECISIONS':^56}║{Style.RESET_ALL}")
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}╠{'═' * 56}╣{Style.RESET_ALL}")
        
        # Mostrar últimas decisões
        if self.decision_history:
            for decision in list(self.decision_history)[-5:]:  # Últimas 5
                time_str = decision.get('time', '').split(' ')[1] if 'time' in decision else ''
                signal = decision.get('signal', 'HOLD')
                conf = decision.get('confidence', 0)
                source = decision.get('source', 'System')
                
                signal_color = Fore.GREEN if signal == 'BUY' else Fore.RED if signal == 'SELL' else Fore.YELLOW
                
                print(f"{Fore.YELLOW}║ {time_str:<8} {source:<12} "
                      f"{signal_color}{signal:<5}{Fore.YELLOW} Conf: {conf:.1%}         ║{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}║{'Waiting for decisions...':^56}║{Style.RESET_ALL}")
        
        print(f"{Back.BLACK}{Fore.YELLOW}{Style.BRIGHT}╚{'═' * 56}╝{Style.RESET_ALL}")
    
    def draw_performance_panel(self):
        """Painel de Performance compacto"""
        metrics = self._get_cached_data('metrics', self._fetch_metrics)
        
        if metrics:
            gauges = metrics.get('metrics', {}).get('gauges', {})
            trades = gauges.get('trades.executed', 0)
            wins = gauges.get('trades.wins', 0)
            losses = gauges.get('trades.losses', 0)
            win_rate = wins / max(1, wins + losses)
            
            print(f"\n{Fore.BLUE}═══ PERFORMANCE ═══{Style.RESET_ALL}")
            print(f"Trades: {trades} | Wins: {Fore.GREEN}{wins}{Fore.RESET} | "
                  f"Losses: {Fore.RED}{losses}{Fore.RESET} | "
                  f"Win Rate: {self._color_value(win_rate, 0.5, 0.3)}{win_rate:.1%}{Fore.RESET}")
    
    def _draw_mini_bar(self, value, width=10):
        """Desenha barra de progresso pequena"""
        filled = int(value * width)
        empty = width - filled
        return f"{'█' * filled}{'░' * empty}"
    
    def _color_value(self, value, good_threshold, bad_threshold):
        """Retorna cor baseada no valor"""
        if value >= good_threshold:
            return Fore.GREEN
        elif value <= bad_threshold:
            return Fore.RED
        return Fore.YELLOW
    
    def _fetch_position_data(self):
        """Busca dados de posição"""
        position_file = Path('data/monitor/position_status.json')
        if position_file.exists():
            with open(position_file, 'r') as f:
                return json.load(f)
        return None
    
    def _fetch_ml_status(self):
        """Busca status ML"""
        ml_file = Path('data/monitor/ml_status.json')
        if ml_file.exists():
            with open(ml_file, 'r') as f:
                return json.load(f)
        return None
    
    def _fetch_agents_data(self):
        """Busca dados dos agentes do arquivo hmarl_status.json"""
        # Primeiro tentar ler do arquivo JSON
        hmarl_file = Path('data/monitor/hmarl_status.json')
        if hmarl_file.exists():
            try:
                with open(hmarl_file, 'r') as f:
                    data = json.load(f)
                
                # Verificar idade dos dados
                from datetime import datetime
                timestamp = datetime.fromisoformat(data['timestamp'])
                age = (datetime.now() - timestamp).total_seconds()
                
                # Se dados muito antigos, ignorar
                if age > 60:  # Mais de 1 minuto
                    print(f"Dados HMARL muito antigos ({age:.1f}s)")
                
                # Extrair dados dos agentes
                agents_data = []
                if 'consensus' in data and 'agents' in data['consensus']:
                    for name, agent_info in data['consensus']['agents'].items():
                        # Converter nome para formato display
                        display_name = name.replace('Specialist', '').replace('Agent', '')
                        
                        # Determinar ação baseada no sinal
                        signal = agent_info.get('signal', 0)
                        if signal > 0.3:
                            action = 'BUY'
                        elif signal < -0.3:
                            action = 'SELL'
                        else:
                            action = 'HOLD'
                        
                        agents_data.append({
                            'name': display_name,
                            'signal': action,
                            'confidence': agent_info.get('confidence', 0.5)
                        })
                
                return agents_data if agents_data else None
                
            except Exception as e:
                print(f"Erro ao ler hmarl_status.json: {e}")
        
        # Fallback para bridge se disponível
        if BRIDGE_AVAILABLE:
            try:
                bridge = get_bridge()
                return bridge.get_formatted_agents_data()
            except:
                pass
        
        return None
    
    def _fetch_metrics(self):
        """Busca métricas"""
        metrics_file = Path('metrics/current_metrics.json')
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                return json.load(f)
        return None
    
    def capture_decision(self, signal, confidence, source='System'):
        """Captura uma decisão para histórico"""
        decision = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'signal': signal,
            'confidence': confidence,
            'source': source
        }
        self.decision_history.append(decision)
    
    def run(self):
        """Loop principal otimizado"""
        while self.running:
            try:
                self.clear_screen()
                self.draw_header()
                
                # Layout em duas colunas
                # Coluna esquerda
                self.draw_position_panel()
                self.draw_ml_panel()
                
                # Coluna direita (simulada com espaçamento)
                self.draw_agents_panel()
                self.draw_decisions_panel()
                
                # Rodapé com performance
                self.draw_performance_panel()
                
                # Status do cache
                print(f"\n{Fore.CYAN}Cache: Hits={self.counters['cache_hits']} "
                      f"Misses={self.counters['cache_misses']} "
                      f"Errors={self.counters['errors']}{Style.RESET_ALL}")
                
                print(f"\n{Fore.YELLOW}Press Ctrl+C to exit{Style.RESET_ALL}")
                
                self.counters['updates'] += 1
                time.sleep(self.refresh_rate)
                
            except KeyboardInterrupt:
                print(f"\n{Fore.RED}Shutting down...{Style.RESET_ALL}")
                self.running = False
                break
            except Exception as e:
                print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
                time.sleep(1)


def main():
    """Função principal"""
    monitor = IntegratedVisualMonitor()
    
    print(f"{Fore.GREEN}Starting Integrated Visual Monitor...{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Optimized for performance with intelligent caching{Style.RESET_ALL}")
    time.sleep(2)
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Monitor stopped.{Style.RESET_ALL}")
    finally:
        monitor.running = False


if __name__ == "__main__":
    main()