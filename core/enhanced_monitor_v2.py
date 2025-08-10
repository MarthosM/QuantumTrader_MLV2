"""
Enhanced Monitor V2 - Sistema de Monitoramento Completo
Visualização das 65 features, sinais dos agentes e métricas em tempo real
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import json
import numpy as np
from datetime import datetime
from collections import deque
import logging
from typing import Dict, List, Optional
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeatureMonitorPanel(ttk.Frame):
    """Painel para monitorar as 65 features"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.features_data = {}
        self.create_widgets()
    
    def create_widgets(self):
        # Título
        title = ttk.Label(self, text="📊 65 Features Monitor", font=('Arial', 12, 'bold'))
        title.pack(pady=5)
        
        # Frame com scroll
        canvas = tk.Canvas(self, height=400)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Categorias de features
        categories = {
            "Volatility (10)": ["volatility_5", "volatility_10", "volatility_20", "volatility_50", 
                               "volatility_100", "volatility_gk", "volatility_rs", "volatility_yz", 
                               "atr_14", "atr_20"],
            "Returns (10)": ["returns_1", "returns_2", "returns_5", "returns_10", "returns_20",
                            "returns_50", "returns_100", "log_returns_1", "log_returns_5", "log_returns_20"],
            "Order Flow (8)": ["order_flow_imbalance_5", "order_flow_imbalance_10", "order_flow_imbalance_20",
                              "signed_volume_5", "signed_volume_10", "signed_volume_20",
                              "trade_flow_5", "trade_flow_10"],
            "Volume (8)": ["volume_20", "volume_50", "volume_100", "volume_mean",
                          "volume_std", "volume_skew", "volume_kurt", "relative_volume"],
            "Technical (8)": ["rsi_14", "ma_5_20_ratio", "ma_20_50_ratio", "ema_distance",
                             "bb_position", "sharpe_20", "sortino_20", "max_drawdown_20"],
            "Microstructure (15)": ["spread", "spread_ma", "spread_std", "bid_volume_total",
                                   "ask_volume_total", "bid_levels_active", "ask_levels_active",
                                   "book_imbalance", "book_pressure", "micro_price",
                                   "weighted_mid_price", "vwap", "vwap_distance",
                                   "top_trader_ratio", "top_trader_side_bias"],
            "Temporal (6)": ["hour", "minute", "hour_sin", "hour_cos", "is_opening", "is_closing"]
        }
        
        self.feature_labels = {}
        
        for category, features in categories.items():
            # Frame da categoria
            cat_frame = ttk.LabelFrame(scrollable_frame, text=category, padding=5)
            cat_frame.pack(fill='x', padx=5, pady=2)
            
            # Grid de features
            for i, feature in enumerate(features):
                row = i // 3
                col = i % 3
                
                # Label da feature
                label = ttk.Label(cat_frame, text=f"{feature}: --", 
                                 font=('Courier', 9))
                label.grid(row=row, column=col, padx=5, pady=1, sticky='w')
                self.feature_labels[feature] = label
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def update_features(self, features: Dict):
        """Atualiza display das features"""
        for feature_name, label in self.feature_labels.items():
            if feature_name in features:
                value = features[feature_name]
                if isinstance(value, (int, float)):
                    if abs(value) < 0.01:
                        text = f"{feature_name}: {value:.4f}"
                    else:
                        text = f"{feature_name}: {value:.2f}"
                else:
                    text = f"{feature_name}: {value}"
                
                # Colorir baseado no valor
                if isinstance(value, (int, float)):
                    if value > 0:
                        label.config(foreground='green')
                    elif value < 0:
                        label.config(foreground='red')
                    else:
                        label.config(foreground='black')
                
                label.config(text=text)


class AgentSignalsPanel(ttk.Frame):
    """Painel para monitorar sinais dos agentes HMARL"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.create_widgets()
    
    def create_widgets(self):
        # Título
        title = ttk.Label(self, text="🤖 Agent Signals", font=('Arial', 12, 'bold'))
        title.pack(pady=5)
        
        # Frame para agentes
        self.agents_frame = ttk.Frame(self)
        self.agents_frame.pack(fill='both', expand=True, padx=5)
        
        # Agentes
        agents = ["OrderFlowSpecialist", "LiquidityAgent", "TapeReadingAgent", "FootprintPatternAgent"]
        self.agent_widgets = {}
        
        for i, agent in enumerate(agents):
            # Frame do agente
            agent_frame = ttk.LabelFrame(self.agents_frame, text=agent, padding=5)
            agent_frame.grid(row=i//2, column=i%2, padx=5, pady=5, sticky='ew')
            
            # Signal
            signal_label = ttk.Label(agent_frame, text="Signal: --", font=('Arial', 10))
            signal_label.pack(anchor='w')
            
            # Confidence
            conf_label = ttk.Label(agent_frame, text="Confidence: --", font=('Arial', 10))
            conf_label.pack(anchor='w')
            
            # Reasoning
            reason_text = tk.Text(agent_frame, height=3, width=30, font=('Courier', 8))
            reason_text.pack(fill='x', pady=2)
            
            self.agent_widgets[agent] = {
                'signal': signal_label,
                'confidence': conf_label,
                'reasoning': reason_text
            }
        
        # Consenso
        consensus_frame = ttk.LabelFrame(self, text="📊 Consensus", padding=5)
        consensus_frame.pack(fill='x', padx=5, pady=5)
        
        self.consensus_label = ttk.Label(consensus_frame, text="Action: HOLD", 
                                        font=('Arial', 12, 'bold'))
        self.consensus_label.pack()
        
        self.consensus_conf = ttk.Label(consensus_frame, text="Confidence: 0%", 
                                       font=('Arial', 10))
        self.consensus_conf.pack()
        
        self.consensus_signal = ttk.Label(consensus_frame, text="Signal: 0.000", 
                                         font=('Arial', 10))
        self.consensus_signal.pack()
    
    def update_agents(self, agent_data: Dict):
        """Atualiza sinais dos agentes"""
        for agent_name, widgets in self.agent_widgets.items():
            if agent_name in agent_data:
                data = agent_data[agent_name]
                
                # Signal
                signal = data.get('signal', '--')
                widgets['signal'].config(text=f"Signal: {signal}")
                
                # Confidence
                conf = data.get('confidence', 0)
                widgets['confidence'].config(text=f"Confidence: {conf:.1%}")
                
                # Reasoning
                reasoning = data.get('reasoning', {})
                widgets['reasoning'].delete(1.0, tk.END)
                widgets['reasoning'].insert(1.0, json.dumps(reasoning, indent=2)[:100])
    
    def update_consensus(self, consensus: Dict):
        """Atualiza consenso"""
        action = consensus.get('action', 'HOLD')
        confidence = consensus.get('confidence', 0)
        signal = consensus.get('signal', 0)
        
        self.consensus_label.config(text=f"Action: {action}")
        self.consensus_conf.config(text=f"Confidence: {confidence:.1%}")
        self.consensus_signal.config(text=f"Signal: {signal:.3f}")
        
        # Colorir baseado na ação
        if 'BUY' in action:
            self.consensus_label.config(foreground='green')
        elif 'SELL' in action:
            self.consensus_label.config(foreground='red')
        else:
            self.consensus_label.config(foreground='gray')


class MicrostructureChart(ttk.Frame):
    """Gráfico de microestrutura do mercado"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.create_widgets()
        self.data_history = {
            'timestamps': deque(maxlen=100),
            'bid_volumes': deque(maxlen=100),
            'ask_volumes': deque(maxlen=100),
            'spreads': deque(maxlen=100),
            'imbalances': deque(maxlen=100)
        }
    
    def create_widgets(self):
        # Figura matplotlib
        self.fig = Figure(figsize=(8, 4), dpi=80)
        
        # Subplots
        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212)
        
        # Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, self)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        
        # Configurar plots
        self.ax1.set_title('Book Volume & Imbalance')
        self.ax1.set_ylabel('Volume')
        self.ax1.grid(True, alpha=0.3)
        
        self.ax2.set_title('Spread Evolution')
        self.ax2.set_ylabel('Spread')
        self.ax2.set_xlabel('Time')
        self.ax2.grid(True, alpha=0.3)
        
        self.fig.tight_layout()
    
    def update_chart(self, data: Dict):
        """Atualiza gráfico com novos dados"""
        # Adicionar aos históricos
        self.data_history['timestamps'].append(datetime.now())
        self.data_history['bid_volumes'].append(data.get('bid_volume_total', 0))
        self.data_history['ask_volumes'].append(data.get('ask_volume_total', 0))
        self.data_history['spreads'].append(data.get('spread', 0))
        self.data_history['imbalances'].append(data.get('book_imbalance', 0))
        
        # Limpar plots
        self.ax1.clear()
        self.ax2.clear()
        
        if len(self.data_history['timestamps']) > 1:
            # Plot volumes e imbalance
            x_range = range(len(self.data_history['timestamps']))
            
            self.ax1.plot(x_range, self.data_history['bid_volumes'], 
                         'g-', label='Bid Vol', alpha=0.7)
            self.ax1.plot(x_range, self.data_history['ask_volumes'], 
                         'r-', label='Ask Vol', alpha=0.7)
            
            # Imbalance no eixo secundário
            ax1_twin = self.ax1.twinx()
            ax1_twin.plot(x_range, self.data_history['imbalances'], 
                         'b--', label='Imbalance', alpha=0.5)
            ax1_twin.set_ylabel('Imbalance', color='b')
            
            self.ax1.legend(loc='upper left')
            self.ax1.set_title('Book Volume & Imbalance')
            self.ax1.grid(True, alpha=0.3)
            
            # Plot spread
            self.ax2.plot(x_range, self.data_history['spreads'], 
                         'purple', label='Spread')
            self.ax2.fill_between(x_range, self.data_history['spreads'], 
                                 alpha=0.3, color='purple')
            self.ax2.set_title('Spread Evolution')
            self.ax2.grid(True, alpha=0.3)
        
        self.canvas.draw()


class MetricsPanel(ttk.Frame):
    """Painel de métricas do sistema"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.create_widgets()
    
    def create_widgets(self):
        # Título
        title = ttk.Label(self, text="📈 System Metrics", font=('Arial', 12, 'bold'))
        title.grid(row=0, column=0, columnspan=3, pady=5)
        
        # Métricas
        metrics = [
            ("Features/sec", "0"),
            ("Predictions/sec", "0"),
            ("Avg Latency", "0ms"),
            ("Total Features", "0"),
            ("Total Predictions", "0"),
            ("Total Signals", "0"),
            ("Win Rate", "0%"),
            ("Sharpe Ratio", "0.00"),
            ("Max Drawdown", "0%"),
            ("Active Position", "0"),
            ("PnL Today", "$0"),
            ("Uptime", "00:00:00")
        ]
        
        self.metric_labels = {}
        
        for i, (name, default) in enumerate(metrics):
            row = (i // 3) + 1
            col = i % 3
            
            frame = ttk.Frame(self)
            frame.grid(row=row, column=col, padx=5, pady=5)
            
            ttk.Label(frame, text=name, font=('Arial', 9)).pack()
            label = ttk.Label(frame, text=default, font=('Arial', 10, 'bold'))
            label.pack()
            
            self.metric_labels[name] = label
    
    def update_metrics(self, metrics: Dict):
        """Atualiza métricas"""
        for name, label in self.metric_labels.items():
            if name in metrics:
                label.config(text=str(metrics[name]))


class LogPanel(ttk.Frame):
    """Painel de logs do sistema"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.create_widgets()
    
    def create_widgets(self):
        # Título
        title = ttk.Label(self, text="📝 System Logs", font=('Arial', 10, 'bold'))
        title.pack(pady=2)
        
        # Text widget com scroll
        self.log_text = scrolledtext.ScrolledText(self, height=8, width=80, 
                                                  font=('Courier', 8))
        self.log_text.pack(fill='both', expand=True, padx=5, pady=2)
        
        # Tags para cores
        self.log_text.tag_config('INFO', foreground='black')
        self.log_text.tag_config('WARNING', foreground='orange')
        self.log_text.tag_config('ERROR', foreground='red')
        self.log_text.tag_config('SUCCESS', foreground='green')
    
    def add_log(self, message: str, level: str = 'INFO'):
        """Adiciona mensagem ao log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_msg = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, formatted_msg, level)
        self.log_text.see(tk.END)
        
        # Limitar tamanho do log
        lines = int(self.log_text.index('end-1c').split('.')[0])
        if lines > 1000:
            self.log_text.delete('1.0', '2.0')


class EnhancedMonitorV2:
    """Monitor principal do sistema"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Enhanced Monitor V2 - 65 Features HMARL System")
        self.root.geometry("1400x900")
        
        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        
        # Data source
        self.data_source = None
        self.running = True
        
        # Criar interface
        self.create_interface()
        
        # Thread de atualização
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()
        
        # Métricas
        self.start_time = datetime.now()
        self.feature_count = 0
        self.prediction_count = 0
    
    def create_interface(self):
        """Cria interface do monitor"""
        # Notebook principal
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab 1: Features & Agents
        tab1 = ttk.Frame(notebook)
        notebook.add(tab1, text="Features & Agents")
        
        # Layout tab1
        left_frame = ttk.Frame(tab1)
        left_frame.pack(side='left', fill='both', expand=True)
        
        right_frame = ttk.Frame(tab1)
        right_frame.pack(side='right', fill='both', expand=True)
        
        # Features panel
        self.features_panel = FeatureMonitorPanel(left_frame)
        self.features_panel.pack(fill='both', expand=True)
        
        # Agents panel
        self.agents_panel = AgentSignalsPanel(right_frame)
        self.agents_panel.pack(fill='both', expand=True)
        
        # Tab 2: Microstructure
        tab2 = ttk.Frame(notebook)
        notebook.add(tab2, text="Microstructure")
        
        self.microstructure_chart = MicrostructureChart(tab2)
        self.microstructure_chart.pack(fill='both', expand=True)
        
        # Tab 3: Metrics & Logs
        tab3 = ttk.Frame(notebook)
        notebook.add(tab3, text="Metrics & Logs")
        
        # Metrics no topo
        self.metrics_panel = MetricsPanel(tab3)
        self.metrics_panel.pack(fill='x', padx=5, pady=5)
        
        # Logs embaixo
        self.log_panel = LogPanel(tab3)
        self.log_panel.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Status bar
        self.status_bar = ttk.Label(self.root, text="Status: Initializing...", 
                                   relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side='bottom', fill='x')
    
    def connect_to_system(self, data_source):
        """Conecta a uma fonte de dados"""
        self.data_source = data_source
        self.log_panel.add_log("Connected to data source", 'SUCCESS')
    
    def update_loop(self):
        """Loop de atualização do monitor"""
        while self.running:
            try:
                # Simular dados para teste
                features = self.generate_test_features()
                agents = self.generate_test_agents()
                consensus = self.generate_test_consensus()
                metrics = self.calculate_metrics()
                
                # Atualizar interface
                self.root.after(0, self.features_panel.update_features, features)
                self.root.after(0, self.agents_panel.update_agents, agents)
                self.root.after(0, self.agents_panel.update_consensus, consensus)
                self.root.after(0, self.microstructure_chart.update_chart, features)
                self.root.after(0, self.metrics_panel.update_metrics, metrics)
                
                # Status
                self.root.after(0, self.update_status, "Connected - Running")
                
                # Log periódico
                if self.feature_count % 10 == 0:
                    self.root.after(0, self.log_panel.add_log, 
                                  f"Processed {self.feature_count} features", 'INFO')
                
                time.sleep(1)  # Atualizar a cada 1 segundo
                
            except Exception as e:
                self.root.after(0, self.log_panel.add_log, 
                              f"Error: {str(e)}", 'ERROR')
                time.sleep(5)
    
    def generate_test_features(self) -> Dict:
        """Gera features de teste"""
        self.feature_count += 1
        
        features = {}
        for i in range(65):
            features[f'feature_{i}'] = np.random.randn() * 0.1
        
        # Adicionar features específicas
        features.update({
            'volatility_20': 0.015 + np.random.randn() * 0.005,
            'returns_5': np.random.randn() * 0.01,
            'order_flow_imbalance_5': np.random.randn() * 0.2,
            'bid_volume_total': 5000 + np.random.randint(-1000, 1000),
            'ask_volume_total': 4800 + np.random.randint(-1000, 1000),
            'spread': 1.0 + np.random.randn() * 0.2,
            'book_imbalance': np.random.randn() * 0.1,
            'rsi_14': 50 + np.random.randn() * 20,
            'vwap': 5450 + np.random.randn() * 10
        })
        
        return features
    
    def generate_test_agents(self) -> Dict:
        """Gera sinais de agentes de teste"""
        agents = {}
        
        for agent in ["OrderFlowSpecialist", "LiquidityAgent", 
                     "TapeReadingAgent", "FootprintPatternAgent"]:
            signal = np.random.choice(['BUY', 'SELL', 'HOLD'])
            confidence = np.random.random()
            
            agents[agent] = {
                'signal': signal,
                'confidence': confidence,
                'reasoning': {
                    'score': round(np.random.randn(), 3),
                    'factors': np.random.randint(1, 5)
                }
            }
        
        return agents
    
    def generate_test_consensus(self) -> Dict:
        """Gera consenso de teste"""
        self.prediction_count += 1
        
        return {
            'action': np.random.choice(['BUY', 'HOLD', 'SELL']),
            'confidence': np.random.random(),
            'signal': np.random.randn() * 0.5
        }
    
    def calculate_metrics(self) -> Dict:
        """Calcula métricas do sistema"""
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]
        
        return {
            'Features/sec': f"{self.feature_count / max(1, uptime.total_seconds()):.1f}",
            'Predictions/sec': f"{self.prediction_count / max(1, uptime.total_seconds()):.1f}",
            'Avg Latency': f"{np.random.randint(1, 5)}ms",
            'Total Features': str(self.feature_count),
            'Total Predictions': str(self.prediction_count),
            'Total Signals': str(self.prediction_count // 2),
            'Win Rate': f"{50 + np.random.randint(-10, 10)}%",
            'Sharpe Ratio': f"{1.5 + np.random.randn() * 0.3:.2f}",
            'Max Drawdown': f"{np.random.randint(0, 5)}%",
            'Active Position': str(np.random.choice([0, 1, -1])),
            'PnL Today': f"${np.random.randint(-1000, 2000):+,}",
            'Uptime': uptime_str
        }
    
    def update_status(self, message: str):
        """Atualiza barra de status"""
        self.status_bar.config(text=f"Status: {message}")
    
    def run(self):
        """Executa o monitor"""
        self.log_panel.add_log("Enhanced Monitor V2 started", 'SUCCESS')
        self.log_panel.add_log("Monitoring 65 features with HMARL agents", 'INFO')
        self.root.mainloop()
    
    def stop(self):
        """Para o monitor"""
        self.running = False
        self.root.quit()


def main():
    """Função principal"""
    monitor = EnhancedMonitorV2()
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        monitor.stop()
        print("\nMonitor stopped")


if __name__ == "__main__":
    main()