"""
Monitor Enhanced - Sistema de Monitoramento Completo
Mostra: Predições ML, Agentes HMARL, Book Models, Métricas
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import json
import time
from datetime import datetime
from pathlib import Path
import threading
import queue

try:
    import valkey
    VALKEY_AVAILABLE = True
except:
    VALKEY_AVAILABLE = False

class EnhancedMonitor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("QuantumTrader ML - Monitor Enhanced")
        self.root.geometry("1400x900")
        
        # Dark theme colors
        self.bg_color = "#1e1e1e"
        self.fg_color = "#ffffff"
        self.accent_color = "#00ff41"
        self.warning_color = "#ffaa00"
        self.error_color = "#ff3333"
        
        self.root.configure(bg=self.bg_color)
        
        # Data sources
        self.monitor_file = Path('data/monitor_data.json')
        self.predictions_queue = queue.Queue()
        self.hmarl_queue = queue.Queue()
        
        # Valkey connection
        self.valkey_client = None
        if VALKEY_AVAILABLE:
            try:
                self.valkey_client = valkey.Valkey(host='localhost', port=6379, decode_responses=True)
                self.valkey_client.ping()
            except:
                self.valkey_client = None
        
        # Data storage
        self.current_data = {}
        self.predictions_history = []
        self.hmarl_agents = {}
        self.models_info = self._load_models_info()
        
        self.create_widgets()
        self.start_update_thread()
        
    def _load_models_info(self):
        """Carrega informações dos modelos disponíveis"""
        models = {
            'book_models': [],
            'csv_models': [],
            'active_models': []
        }
        
        models_dir = Path('models')
        
        # Book models
        for book_dir in models_dir.glob('book_*'):
            metadata_files = list(book_dir.glob('metadata*.json'))
            if metadata_files:
                try:
                    with open(metadata_files[0]) as f:
                        data = json.load(f)
                        models['book_models'].append({
                            'name': book_dir.name,
                            'accuracy': data.get('cv_results', {}).get('lightgbm', {}).get('avg_accuracy', 0),
                            'trading_acc': data.get('cv_results', {}).get('lightgbm', {}).get('avg_trading_accuracy', 0),
                            'date': data.get('training_date', '')
                        })
                except:
                    pass
        
        # CSV models
        for csv_dir in models_dir.glob('csv_*'):
            metadata_files = list(csv_dir.glob('*metadata*.json')) + list(csv_dir.glob('*report*.json'))
            if metadata_files:
                try:
                    with open(metadata_files[0]) as f:
                        data = json.load(f)
                        if 'best_for_trading' in data:
                            models['csv_models'].append({
                                'name': csv_dir.name,
                                'accuracy': data.get('models_performance', {}).get('ensemble', {}).get('accuracy_overall', 0),
                                'trading_acc': data.get('best_for_trading', {}).get('trading_accuracy', 0),
                                'date': data.get('training_date', '')
                            })
                except:
                    pass
        
        # Sort by trading accuracy
        models['book_models'].sort(key=lambda x: x['trading_acc'], reverse=True)
        models['csv_models'].sort(key=lambda x: x['trading_acc'], reverse=True)
        
        return models
        
    def create_widgets(self):
        """Cria interface gráfica"""
        
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top section - System Status
        status_frame = ttk.LabelFrame(main_frame, text="System Status", padding=10)
        status_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        # Status indicators
        self.status_labels = {}
        status_items = [
            ('Connection', 'connection'),
            ('Price', 'price'),
            ('ML Models', 'models'),
            ('HMARL', 'hmarl'),
            ('Valkey', 'valkey')
        ]
        
        for i, (label, key) in enumerate(status_items):
            tk.Label(status_frame, text=f"{label}:", bg=self.bg_color, fg=self.fg_color).grid(row=0, column=i*2, sticky='w')
            self.status_labels[key] = tk.Label(status_frame, text="--", bg=self.bg_color, fg=self.accent_color, font=('Arial', 10, 'bold'))
            self.status_labels[key].grid(row=0, column=i*2+1, padx=(5, 20))
        
        # Left column - Trading & ML
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        
        # Trading info
        trading_frame = ttk.LabelFrame(left_frame, text="Trading", padding=10)
        trading_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))
        
        self.trading_labels = {}
        trading_items = ['position', 'entry_price', 'pnl', 'daily_pnl', 'trades', 'wins', 'losses']
        
        for i, item in enumerate(trading_items):
            row = i // 2
            col = (i % 2) * 2
            tk.Label(trading_frame, text=f"{item.replace('_', ' ').title()}:", bg=self.bg_color, fg=self.fg_color).grid(row=row, column=col, sticky='w')
            self.trading_labels[item] = tk.Label(trading_frame, text="0", bg=self.bg_color, fg=self.fg_color)
            self.trading_labels[item].grid(row=row, column=col+1, sticky='w', padx=(5, 20))
        
        # ML Predictions
        ml_frame = ttk.LabelFrame(left_frame, text="ML Predictions", padding=10)
        ml_frame.pack(fill=tk.BOTH, expand=True)
        
        # Predictions display
        self.predictions_text = scrolledtext.ScrolledText(
            ml_frame, 
            height=8, 
            width=50,
            bg="#2d2d2d",
            fg=self.accent_color,
            font=('Consolas', 9)
        )
        self.predictions_text.pack(fill=tk.BOTH, expand=True)
        
        # Middle column - Models Info
        middle_frame = ttk.Frame(main_frame)
        middle_frame.grid(row=1, column=1, sticky="nsew", padx=5)
        
        # Active Models
        active_frame = ttk.LabelFrame(middle_frame, text="Active Models", padding=10)
        active_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))
        
        self.active_models_text = scrolledtext.ScrolledText(
            active_frame,
            height=6,
            width=45,
            bg="#2d2d2d",
            fg=self.fg_color,
            font=('Consolas', 9)
        )
        self.active_models_text.pack(fill=tk.BOTH, expand=True)
        
        # Best Models
        best_frame = ttk.LabelFrame(middle_frame, text="Best Available Models", padding=10)
        best_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for model categories
        notebook = ttk.Notebook(best_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Book models tab
        book_tab = ttk.Frame(notebook)
        notebook.add(book_tab, text="Book Models")
        
        self.book_models_text = scrolledtext.ScrolledText(
            book_tab,
            height=10,
            width=45,
            bg="#2d2d2d",
            fg=self.fg_color,
            font=('Consolas', 9)
        )
        self.book_models_text.pack(fill=tk.BOTH, expand=True)
        
        # CSV models tab
        csv_tab = ttk.Frame(notebook)
        notebook.add(csv_tab, text="CSV Models")
        
        self.csv_models_text = scrolledtext.ScrolledText(
            csv_tab,
            height=10,
            width=45,
            bg="#2d2d2d",
            fg=self.fg_color,
            font=('Consolas', 9)
        )
        self.csv_models_text.pack(fill=tk.BOTH, expand=True)
        
        # Right column - HMARL & Callbacks
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=2, sticky="nsew", padx=(5, 0))
        
        # HMARL Agents
        hmarl_frame = ttk.LabelFrame(right_frame, text="HMARL Agents", padding=10)
        hmarl_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))
        
        self.hmarl_text = scrolledtext.ScrolledText(
            hmarl_frame,
            height=8,
            width=45,
            bg="#2d2d2d",
            fg=self.warning_color,
            font=('Consolas', 9)
        )
        self.hmarl_text.pack(fill=tk.BOTH, expand=True)
        
        # Callbacks counter
        callbacks_frame = ttk.LabelFrame(right_frame, text="Callbacks", padding=10)
        callbacks_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 10))
        
        self.callbacks_text = scrolledtext.ScrolledText(
            callbacks_frame,
            height=6,
            width=45,
            bg="#2d2d2d",
            fg=self.fg_color,
            font=('Consolas', 9)
        )
        self.callbacks_text.pack(fill=tk.BOTH, expand=True)
        
        # Logs
        logs_frame = ttk.LabelFrame(right_frame, text="System Logs", padding=10)
        logs_frame.pack(fill=tk.BOTH, expand=True)
        
        self.logs_text = scrolledtext.ScrolledText(
            logs_frame,
            height=8,
            width=45,
            bg="#2d2d2d",
            fg=self.fg_color,
            font=('Consolas', 8)
        )
        self.logs_text.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_columnconfigure(2, weight=1)
        
        # Initial model display
        self.update_models_display()
        
    def update_models_display(self):
        """Atualiza display dos modelos"""
        # Book models
        self.book_models_text.delete(1.0, tk.END)
        self.book_models_text.insert(tk.END, "Top Book Models (by Trading Accuracy):\n\n")
        
        for model in self.models_info['book_models'][:5]:
            self.book_models_text.insert(tk.END, f"📊 {model['name']}\n")
            self.book_models_text.insert(tk.END, f"   Trading Acc: {model['trading_acc']:.2%}\n")
            self.book_models_text.insert(tk.END, f"   Overall Acc: {model['accuracy']:.2%}\n")
            self.book_models_text.insert(tk.END, f"   Date: {model['date'][:10]}\n\n")
        
        # CSV models
        self.csv_models_text.delete(1.0, tk.END)
        self.csv_models_text.insert(tk.END, "Top CSV Models (by Trading Accuracy):\n\n")
        
        for model in self.models_info['csv_models'][:5]:
            self.csv_models_text.insert(tk.END, f"📈 {model['name']}\n")
            self.csv_models_text.insert(tk.END, f"   Trading Acc: {model['trading_acc']:.2%}\n")
            self.csv_models_text.insert(tk.END, f"   Overall Acc: {model['accuracy']:.2%}\n")
            self.csv_models_text.insert(tk.END, f"   Date: {model['date'][:10]}\n\n")
    
    def update_display(self):
        """Atualiza toda a interface"""
        try:
            # Load monitor data
            if self.monitor_file.exists():
                with open(self.monitor_file) as f:
                    self.current_data = json.load(f)
            
            # Update status
            self.status_labels['connection'].config(text="Connected" if self.current_data.get('status') == 'Operacional' else "Disconnected")
            self.status_labels['price'].config(text=f"R$ {self.current_data.get('price', 0):.2f}")
            self.status_labels['models'].config(text=f"{len(self.current_data.get('active_models', []))} Active")
            self.status_labels['hmarl'].config(text="Active" if self.valkey_client else "Inactive")
            self.status_labels['valkey'].config(text="Connected" if self.valkey_client else "Disconnected")
            
            # Update trading info
            for key in self.trading_labels:
                value = self.current_data.get(key, 0)
                if key in ['pnl', 'daily_pnl']:
                    color = self.accent_color if value >= 0 else self.error_color
                    self.trading_labels[key].config(text=f"R$ {value:.2f}", fg=color)
                else:
                    self.trading_labels[key].config(text=str(value))
            
            # Update predictions
            if 'last_prediction' in self.current_data:
                pred = self.current_data['last_prediction']
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                self.predictions_text.insert(tk.END, f"[{timestamp}] Prediction:\n")
                self.predictions_text.insert(tk.END, f"  Direction: {pred.get('direction', 0):.3f}\n")
                self.predictions_text.insert(tk.END, f"  Confidence: {pred.get('confidence', 0):.3f}\n")
                self.predictions_text.insert(tk.END, f"  Models: {pred.get('models_used', 0)}\n")
                
                if pred.get('hmarl_enhanced'):
                    self.predictions_text.insert(tk.END, f"  [HMARL Enhanced]\n")
                
                self.predictions_text.insert(tk.END, "-" * 40 + "\n")
                self.predictions_text.see(tk.END)
                
                # Keep only last 10 predictions
                lines = self.predictions_text.get(1.0, tk.END).split('\n')
                if len(lines) > 50:
                    self.predictions_text.delete(1.0, '6.0')
            
            # Update active models
            self.active_models_text.delete(1.0, tk.END)
            active_models = self.current_data.get('active_models', [])
            if active_models:
                for model in active_models:
                    self.active_models_text.insert(tk.END, f"✓ {model}\n")
            else:
                self.active_models_text.insert(tk.END, "No active models\n")
            
            # Update HMARL from Valkey
            if self.valkey_client:
                try:
                    # Get agent status
                    agents = ['order_flow', 'liquidity', 'tape_reading', 'footprint']
                    self.hmarl_text.delete(1.0, tk.END)
                    
                    for agent in agents:
                        key = f"agent:{agent}:status"
                        status = self.valkey_client.get(key)
                        
                        if status:
                            data = json.loads(status)
                            self.hmarl_text.insert(tk.END, f"🤖 {agent.upper()}\n")
                            self.hmarl_text.insert(tk.END, f"   Signals: {data.get('signals', 0)}\n")
                            self.hmarl_text.insert(tk.END, f"   Confidence: {data.get('avg_confidence', 0):.2f}\n\n")
                    
                    # Get consensus
                    consensus = self.valkey_client.get(f"consensus:{self.current_data.get('ticker', 'WDOU25')}")
                    if consensus:
                        data = json.loads(consensus)
                        self.hmarl_text.insert(tk.END, "=" * 30 + "\n")
                        self.hmarl_text.insert(tk.END, f"CONSENSUS: {data.get('action', 'HOLD')}\n")
                        self.hmarl_text.insert(tk.END, f"Agreement: {data.get('agreement', 0):.1%}\n")
                        
                except Exception as e:
                    self.hmarl_text.insert(tk.END, f"HMARL data unavailable\n")
            
            # Update callbacks
            callbacks = self.current_data.get('callbacks', {})
            self.callbacks_text.delete(1.0, tk.END)
            
            for cb_type, count in callbacks.items():
                if count > 0:
                    self.callbacks_text.insert(tk.END, f"{cb_type}: {count:,}\n")
            
            # Update logs with recent activity
            if 'recent_logs' in self.current_data:
                self.logs_text.delete(1.0, tk.END)
                for log in self.current_data['recent_logs'][-10:]:
                    self.logs_text.insert(tk.END, f"{log}\n")
                self.logs_text.see(tk.END)
                
        except Exception as e:
            print(f"Error updating display: {e}")
    
    def update_loop(self):
        """Loop de atualização em thread separada"""
        while True:
            try:
                self.root.after(0, self.update_display)
                time.sleep(1)
            except:
                break
    
    def start_update_thread(self):
        """Inicia thread de atualização"""
        thread = threading.Thread(target=self.update_loop, daemon=True)
        thread.start()
    
    def run(self):
        """Executa o monitor"""
        self.root.mainloop()

if __name__ == "__main__":
    monitor = EnhancedMonitor()
    monitor.run()