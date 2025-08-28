#!/usr/bin/env python3
"""
Dashboard de Monitoramento de Volume e Fluxo de Ordens
Atualiza em tempo real mostrando volume capturado, delta e análise de fluxo
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from colorama import init, Fore, Back, Style

# Inicializar colorama para Windows
init()

class VolumeFlowMonitor:
    """Monitor de volume e fluxo de ordens"""
    
    def __init__(self):
        self.monitor_dir = Path("data/monitor")
        self.last_volume_data = {}
        self.trade_history = []
        self.max_history = 50
        
    def clear_screen(self):
        """Limpa a tela"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def get_volume_data(self):
        """Obtém dados de volume do arquivo de monitoramento"""
        try:
            volume_file = self.monitor_dir / "volume_stats.json"
            if volume_file.exists():
                with open(volume_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        
        # Tentar obter do arquivo de ML status
        try:
            ml_file = self.monitor_dir / "ml_status.json"
            if ml_file.exists():
                with open(ml_file, 'r') as f:
                    ml_data = json.load(f)
                    # Extrair volume se disponível
                    return {
                        'cumulative_volume': 0,
                        'current_volume': 0,
                        'buy_volume': 0,
                        'sell_volume': 0,
                        'delta_volume': 0,
                        'last_trade': None
                    }
        except:
            pass
        
        return {
            'cumulative_volume': 0,
            'current_volume': 0,
            'buy_volume': 0,
            'sell_volume': 0,
            'delta_volume': 0,
            'last_trade': None
        }
    
    def get_market_data(self):
        """Obtém dados do mercado"""
        try:
            hmarl_file = self.monitor_dir / "hmarl_status.json"
            if hmarl_file.exists():
                with open(hmarl_file, 'r') as f:
                    data = json.load(f)
                    return data.get('market_data', {})
        except:
            pass
        return {'price': 0, 'volume': 0}
    
    def format_volume(self, volume):
        """Formata volume com cores"""
        if volume == 0:
            return f"{Fore.YELLOW}{volume:,}{Style.RESET_ALL}"
        elif volume > 100:
            return f"{Fore.GREEN}{Style.BRIGHT}{volume:,}{Style.RESET_ALL}"
        else:
            return f"{Fore.CYAN}{volume:,}{Style.RESET_ALL}"
    
    def format_delta(self, delta):
        """Formata delta com cores"""
        if delta > 0:
            return f"{Fore.GREEN}+{delta:,} ↑{Style.RESET_ALL}"
        elif delta < 0:
            return f"{Fore.RED}{delta:,} ↓{Style.RESET_ALL}"
        else:
            return f"{Fore.YELLOW}{delta:,} ={Style.RESET_ALL}"
    
    def calculate_flow_strength(self, buy_vol, sell_vol):
        """Calcula força do fluxo"""
        total = buy_vol + sell_vol
        if total == 0:
            return "NEUTRO", Fore.YELLOW
        
        buy_ratio = buy_vol / total
        
        if buy_ratio > 0.7:
            return "COMPRA FORTE", Fore.GREEN + Style.BRIGHT
        elif buy_ratio > 0.55:
            return "COMPRA", Fore.GREEN
        elif buy_ratio < 0.3:
            return "VENDA FORTE", Fore.RED + Style.BRIGHT
        elif buy_ratio < 0.45:
            return "VENDA", Fore.RED
        else:
            return "NEUTRO", Fore.YELLOW
    
    def draw_volume_bar(self, buy_vol, sell_vol, width=40):
        """Desenha barra visual de volume"""
        total = buy_vol + sell_vol
        if total == 0:
            return "=" * width
        
        buy_width = int((buy_vol / total) * width)
        sell_width = width - buy_width
        
        bar = (
            f"{Back.GREEN}{' ' * buy_width}{Style.RESET_ALL}"
            f"{Back.RED}{' ' * sell_width}{Style.RESET_ALL}"
        )
        
        return bar
    
    def display(self):
        """Exibe o dashboard"""
        self.clear_screen()
        
        # Header
        print(f"{Fore.CYAN}{Style.BRIGHT}")
        print("=" * 60)
        print("         MONITOR DE VOLUME E FLUXO DE ORDENS")
        print("=" * 60)
        print(Style.RESET_ALL)
        
        # Timestamp
        now = datetime.now()
        print(f"[{now.strftime('%H:%M:%S')}] Atualizando...")
        print()
        
        # Obter dados
        volume_data = self.get_volume_data()
        market_data = self.get_market_data()
        
        # Seção de Volume
        print(f"{Fore.CYAN}📊 VOLUME CAPTURADO{Style.RESET_ALL}")
        print("-" * 40)
        
        # Volume Total
        total_vol = volume_data['cumulative_volume']
        if total_vol > 0:
            print(f"Total: {self.format_volume(total_vol)} contratos")
        else:
            print(f"Total: {Fore.RED}Aguardando trades...{Style.RESET_ALL}")
        
        # Volume Atual
        current_vol = volume_data['current_volume']
        print(f"Último: {self.format_volume(current_vol)} contratos")
        print()
        
        # Análise Buy/Sell
        buy_vol = volume_data['buy_volume']
        sell_vol = volume_data['sell_volume']
        delta = volume_data['delta_volume']
        
        print(f"{Fore.CYAN}📈 ANÁLISE DE FLUXO{Style.RESET_ALL}")
        print("-" * 40)
        
        # Volumes
        print(f"Compra: {Fore.GREEN}{buy_vol:,}{Style.RESET_ALL} contratos")
        print(f"Venda:  {Fore.RED}{sell_vol:,}{Style.RESET_ALL} contratos")
        print(f"Delta:  {self.format_delta(delta)}")
        print()
        
        # Barra visual
        if buy_vol > 0 or sell_vol > 0:
            print("Distribuição:")
            print(self.draw_volume_bar(buy_vol, sell_vol))
            
            # Percentuais
            total = buy_vol + sell_vol
            buy_pct = (buy_vol / total) * 100 if total > 0 else 0
            sell_pct = (sell_vol / total) * 100 if total > 0 else 0
            
            print(f"{Fore.GREEN}Buy: {buy_pct:.1f}%{Style.RESET_ALL} | "
                  f"{Fore.RED}Sell: {sell_pct:.1f}%{Style.RESET_ALL}")
            print()
        
        # Força do Fluxo
        flow_strength, flow_color = self.calculate_flow_strength(buy_vol, sell_vol)
        print(f"Força do Fluxo: {flow_color}{flow_strength}{Style.RESET_ALL}")
        print()
        
        # Último Trade
        if volume_data.get('last_trade'):
            trade = volume_data['last_trade']
            trade_type = 'COMPRA' if trade.get('trade_type') == 2 else 'VENDA'
            trade_color = Fore.GREEN if trade.get('trade_type') == 2 else Fore.RED
            
            print(f"{Fore.CYAN}🔄 ÚLTIMO TRADE{Style.RESET_ALL}")
            print("-" * 40)
            print(f"Tipo: {trade_color}{trade_type}{Style.RESET_ALL}")
            print(f"Volume: {trade['volume']} contratos")
            print(f"Preço: R$ {trade['price']:.2f}")
            print()
        
        # Preço atual
        price = market_data.get('price', 0)
        if price > 0:
            print(f"{Fore.CYAN}💰 MERCADO{Style.RESET_ALL}")
            print("-" * 40)
            print(f"Preço: R$ {price:.2f}")
            
            # Calcular pressão baseada no delta
            if delta > 100:
                pressure = "Pressão COMPRADORA"
                pressure_color = Fore.GREEN + Style.BRIGHT
            elif delta > 50:
                pressure = "Pressão compradora"
                pressure_color = Fore.GREEN
            elif delta < -100:
                pressure = "Pressão VENDEDORA"
                pressure_color = Fore.RED + Style.BRIGHT
            elif delta < -50:
                pressure = "Pressão vendedora"
                pressure_color = Fore.RED
            else:
                pressure = "Mercado equilibrado"
                pressure_color = Fore.YELLOW
            
            print(f"Status: {pressure_color}{pressure}{Style.RESET_ALL}")
            print()
        
        # Status do Sistema
        print(f"{Fore.CYAN}⚙️ STATUS DO SISTEMA{Style.RESET_ALL}")
        print("-" * 40)
        
        if total_vol > 0:
            print(f"{Fore.GREEN}✓ Volume sendo capturado{Style.RESET_ALL}")
            print(f"  Taxa de captura: {total_vol / max(1, (now.hour * 60 + now.minute - 9*60)):.1f} contratos/min")
        else:
            print(f"{Fore.YELLOW}⚠ Aguardando trades do mercado{Style.RESET_ALL}")
            print(f"  Certifique-se que o mercado está aberto")
        
        # Detectar mudanças
        if self.last_volume_data:
            vol_change = total_vol - self.last_volume_data.get('cumulative_volume', 0)
            if vol_change > 0:
                print(f"\n{Fore.GREEN}📈 +{vol_change} novos contratos capturados!{Style.RESET_ALL}")
        
        self.last_volume_data = volume_data.copy()
        
        # Rodapé
        print()
        print("=" * 60)
        print(f"{Fore.CYAN}Pressione CTRL+C para sair{Style.RESET_ALL}")
        print("=" * 60)
    
    def run(self, interval=1):
        """Executa o monitor continuamente"""
        print(f"{Fore.CYAN}Iniciando Monitor de Volume...{Style.RESET_ALL}")
        time.sleep(2)
        
        try:
            while True:
                self.display()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.clear_screen()
            print(f"\n{Fore.YELLOW}Monitor encerrado.{Style.RESET_ALL}")
            return

def main():
    """Função principal"""
    monitor = VolumeFlowMonitor()
    monitor.run()

if __name__ == "__main__":
    main()