#!/usr/bin/env python3
"""
Script de Verificação de Dados Reais do Mercado
Confirma que o sistema está recebendo e processando dados reais da B3
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from colorama import init, Fore, Back, Style

# Inicializar colorama
init(autoreset=True)

class RealDataVerifier:
    """Verificador de dados reais do mercado"""
    
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []
        
    def print_header(self):
        """Imprime cabeçalho"""
        print(f"\n{Back.BLUE}{Fore.WHITE}{'=' * 60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}[CHECK] VERIFICACAO DE DADOS REAIS DO MERCADO{Style.RESET_ALL}")
        print(f"{Back.BLUE}{Fore.WHITE}{'=' * 60}{Style.RESET_ALL}\n")
        
    def check_connection_logs(self):
        """Verifica logs de conexão com a B3"""
        print(f"{Fore.YELLOW} Verificando Conexão com B3...{Style.RESET_ALL}")
        
        # Buscar log mais recente
        log_dir = self.base_path / "logs"
        log_files = list(log_dir.glob("system_complete_oco_events_*.log"))
        
        if not log_files:
            self.checks_failed += 1
            print(f"  {Fore.RED} Nenhum log de sistema encontrado{Style.RESET_ALL}")
            return False
            
        latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
        log_age = datetime.now() - datetime.fromtimestamp(latest_log.stat().st_mtime)
        
        print(f"  Log mais recente: {latest_log.name}")
        print(f"  Idade: {log_age.total_seconds():.0f} segundos")
        
        # Verificar conteúdo
        with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        checks = {
            "LOGIN conectado": "Autenticação B3",
            "ROTEAMENTO conectado": "Roteamento B3",
            "MARKET DATA conectado": "Dados de Mercado",
            "Conexão v4.0.0.30 estabelecida": "ProfitDLL v4",
            "WDOQ25": "Símbolo WDO"
        }
        
        for pattern, description in checks.items():
            if pattern in content:
                self.checks_passed += 1
                print(f"  {Fore.GREEN} {description}: OK{Style.RESET_ALL}")
            else:
                self.checks_failed += 1
                print(f"  {Fore.RED} {description}: NÃO ENCONTRADO{Style.RESET_ALL}")
                
        return True
        
    def check_position_monitor(self):
        """Verifica Position Monitor"""
        print(f"\n{Fore.YELLOW} Verificando Position Monitor...{Style.RESET_ALL}")
        
        position_file = self.base_path / "data" / "monitor" / "position_status.json"
        
        if not position_file.exists():
            self.checks_failed += 1
            print(f"  {Fore.RED} Arquivo position_status.json não encontrado{Style.RESET_ALL}")
            return False
            
        try:
            with open(position_file, 'r') as f:
                data = json.load(f)
                
            # Verificar timestamp
            timestamp = datetime.fromisoformat(data['timestamp'])
            age = datetime.now() - timestamp
            
            print(f"  Última atualização: {timestamp.strftime('%H:%M:%S')}")
            print(f"  Idade: {age.total_seconds():.0f} segundos")
            
            if age.total_seconds() < 300:  # 5 minutos
                self.checks_passed += 1
                print(f"  {Fore.GREEN} Position Monitor ATIVO{Style.RESET_ALL}")
            else:
                self.warnings.append("Position Monitor não atualizado há mais de 5 minutos")
                print(f"  {Fore.YELLOW} Position Monitor INATIVO (dados antigos){Style.RESET_ALL}")
                
            # Status da posição
            if data.get('has_position'):
                print(f"  {Fore.CYAN} POSIÇÃO ABERTA{Style.RESET_ALL}")
                for pos in data.get('positions', []):
                    print(f"    Símbolo: {pos.get('symbol')}")
                    print(f"    Lado: {pos.get('side')}")
                    print(f"    Qtd: {pos.get('quantity')}")
            else:
                print(f"  [ ] Sem posicoes abertas")
                
        except Exception as e:
            self.checks_failed += 1
            print(f"  {Fore.RED} Erro ao ler position_status.json: {e}{Style.RESET_ALL}")
            return False
            
        return True
        
    def check_ml_predictions(self):
        """Verifica predições ML"""
        print(f"\n{Fore.YELLOW} Verificando Predições ML...{Style.RESET_ALL}")
        
        ml_file = self.base_path / "data" / "monitor" / "ml_status.json"
        
        if not ml_file.exists():
            self.checks_failed += 1
            print(f"  {Fore.RED} Arquivo ml_status.json não encontrado{Style.RESET_ALL}")
            return False
            
        try:
            with open(ml_file, 'r') as f:
                data = json.load(f)
                
            # Verificar timestamp
            timestamp = datetime.fromisoformat(data['timestamp'])
            age = datetime.now() - timestamp
            
            print(f"  Última predição: {timestamp.strftime('%H:%M:%S')}")
            print(f"  Idade: {age.total_seconds():.0f} segundos")
            
            # Verificar se está ativo
            if data.get('ml_status') == 'ACTIVE':
                self.checks_passed += 1
                print(f"  {Fore.GREEN} ML Models ATIVOS{Style.RESET_ALL}")
                
                # Mostrar predições
                print(f"\n  Predições:")
                print(f"    Context: {data.get('context_pred')} ({data.get('context_conf', 0):.1%})")
                print(f"    Microstructure: {data.get('micro_pred')} ({data.get('micro_conf', 0):.1%})")
                print(f"    Meta-Learner: {data.get('meta_pred')} ({data.get('meta_conf', 0):.1%})")
                
                # Verificar se valores não são sintéticos
                conf_values = [
                    data.get('context_conf', 0),
                    data.get('micro_conf', 0),
                    data.get('meta_conf', 0)
                ]
                
                # Valores muito redondos ou repetidos indicam dados sintéticos
                if all(c == conf_values[0] for c in conf_values):
                    self.warnings.append("Confiança ML idêntica - possível dados sintéticos")
                    print(f"  {Fore.YELLOW} Valores de confiança idênticos{Style.RESET_ALL}")
                elif all(c in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0] for c in conf_values):
                    self.warnings.append("Confiança ML muito redonda - possível dados sintéticos")
                    print(f"  {Fore.YELLOW} Valores muito redondos{Style.RESET_ALL}")
                else:
                    print(f"  {Fore.GREEN} Valores parecem ser de dados reais{Style.RESET_ALL}")
                    
            else:
                self.checks_failed += 1
                print(f"  {Fore.RED} ML Models INATIVOS{Style.RESET_ALL}")
                
        except Exception as e:
            self.checks_failed += 1
            print(f"  {Fore.RED} Erro ao ler ml_status.json: {e}{Style.RESET_ALL}")
            return False
            
        return True
        
    def check_market_data_files(self):
        """Verifica arquivos de dados de mercado"""
        print(f"\n{Fore.YELLOW} Verificando Coleta de Dados de Mercado...{Style.RESET_ALL}")
        
        data_dir = self.base_path / "data" / "book_tick_data"
        
        if not data_dir.exists():
            self.checks_failed += 1
            print(f"  {Fore.RED} Diretório book_tick_data não encontrado{Style.RESET_ALL}")
            return False
            
        # Buscar arquivos recentes
        book_files = list(data_dir.glob("book_data_*.csv"))
        tick_files = list(data_dir.glob("tick_data_*.csv"))
        
        print(f"  Total de arquivos book: {len(book_files)}")
        print(f"  Total de arquivos tick: {len(tick_files)}")
        
        if book_files:
            latest_book = max(book_files, key=lambda p: p.stat().st_mtime)
            book_age = datetime.now() - datetime.fromtimestamp(latest_book.stat().st_mtime)
            book_size = latest_book.stat().st_size
            
            print(f"\n  Book mais recente: {latest_book.name}")
            print(f"  Tamanho: {book_size} bytes")
            print(f"  Idade: {book_age.total_seconds():.0f} segundos")
            
            # Verificar conteúdo
            with open(latest_book, 'r') as f:
                lines = f.readlines()
                
            if len(lines) > 1 and book_size > 100:
                self.checks_passed += 1
                print(f"  {Fore.GREEN} Book data com dados ({len(lines)-1} linhas){Style.RESET_ALL}")
            elif book_size < 100:
                self.warnings.append("Arquivo book_data muito pequeno - possível falta de dados")
                print(f"  {Fore.YELLOW} Book data vazio ou muito pequeno{Style.RESET_ALL}")
            else:
                print(f"  [ ] Book data apenas com header")
                
        if tick_files:
            latest_tick = max(tick_files, key=lambda p: p.stat().st_mtime)
            tick_age = datetime.now() - datetime.fromtimestamp(latest_tick.stat().st_mtime)
            tick_size = latest_tick.stat().st_size
            
            print(f"\n  Tick mais recente: {latest_tick.name}")
            print(f"  Tamanho: {tick_size} bytes")
            print(f"  Idade: {tick_age.total_seconds():.0f} segundos")
            
            if tick_size > 50:
                self.checks_passed += 1
                print(f"  {Fore.GREEN} Tick data com dados{Style.RESET_ALL}")
            else:
                self.warnings.append("Arquivo tick_data muito pequeno - possível falta de dados")
                print(f"  {Fore.YELLOW} Tick data vazio ou muito pequeno{Style.RESET_ALL}")
                
        return True
        
    def check_market_hours(self):
        """Verifica horário de mercado"""
        print(f"\n{Fore.YELLOW}[TIME] Verificando Horario de Mercado...{Style.RESET_ALL}")
        
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()
        
        print(f"  Hora atual: {now.strftime('%H:%M:%S')}")
        print(f"  Dia da semana: {['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'][weekday]}")
        
        # Mercado funciona de segunda a sexta, 9h às 18h
        if weekday < 5:  # Segunda a Sexta
            if 9 <= hour < 18:
                self.checks_passed += 1
                print(f"  {Fore.GREEN} MERCADO ABERTO{Style.RESET_ALL}")
                return True
            else:
                self.warnings.append("Fora do horário de trading (9h-18h)")
                print(f"  {Fore.YELLOW} MERCADO FECHADO (horário){Style.RESET_ALL}")
                return False
        else:
            self.warnings.append("Final de semana - mercado fechado")
            print(f"  {Fore.YELLOW} MERCADO FECHADO (fim de semana){Style.RESET_ALL}")
            return False
            
    def print_summary(self):
        """Imprime resumo da verificação"""
        print(f"\n{Back.BLUE}{Fore.WHITE}{'=' * 60}{Style.RESET_ALL}")
        print(f"{Fore.CYAN} RESUMO DA VERIFICAÇÃO{Style.RESET_ALL}")
        print(f"{Back.BLUE}{Fore.WHITE}{'=' * 60}{Style.RESET_ALL}\n")
        
        total_checks = self.checks_passed + self.checks_failed
        
        if total_checks > 0:
            success_rate = (self.checks_passed / total_checks) * 100
            
            print(f"   Verificações aprovadas: {self.checks_passed}")
            print(f"   Verificações falhadas: {self.checks_failed}")
            print(f"  Taxa de sucesso: {success_rate:.1f}%")
            
            if self.warnings:
                print(f"\n  {Fore.YELLOW} Avisos:{Style.RESET_ALL}")
                for warning in self.warnings:
                    print(f"    - {warning}")
                    
            print()
            
            if success_rate >= 80:
                print(f"{Back.GREEN}{Fore.WHITE}  SISTEMA OPERANDO COM DADOS REAIS {Style.RESET_ALL}")
                print(f"{Fore.GREEN}O sistema está conectado e recebendo dados reais da B3!{Style.RESET_ALL}")
            elif success_rate >= 50:
                print(f"{Back.YELLOW}{Fore.BLACK} ️ SISTEMA PARCIALMENTE OPERACIONAL {Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Alguns componentes não estão recebendo dados reais.{Style.RESET_ALL}")
            else:
                print(f"{Back.RED}{Fore.WHITE}  SISTEMA SEM DADOS REAIS {Style.RESET_ALL}")
                print(f"{Fore.RED}O sistema não está recebendo dados reais do mercado!{Style.RESET_ALL}")
                
        print(f"\n{Fore.CYAN}Dica: Execute durante horário de mercado (9h-18h) para melhores resultados.{Style.RESET_ALL}")
        
    def run(self):
        """Executa todas as verificações"""
        self.print_header()
        
        # Executar verificações
        self.check_connection_logs()
        self.check_position_monitor()
        self.check_ml_predictions()
        self.check_market_data_files()
        market_open = self.check_market_hours()
        
        # Resumo
        self.print_summary()
        
        # Retornar status
        return self.checks_passed > self.checks_failed

def main():
    """Função principal"""
    verifier = RealDataVerifier()
    success = verifier.run()
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())