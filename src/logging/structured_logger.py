"""
Sistema de Logging Estruturado
Logging em formato JSON com suporte para análise e monitoramento
"""

import logging
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import traceback
from enum import Enum
from dataclasses import dataclass, asdict
import threading
from collections import deque
import time


class LogLevel(Enum):
    """Níveis de log customizados"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    TRADE = "TRADE"  # Específico para operações de trading
    FEATURE = "FEATURE"  # Específico para cálculo de features
    AGENT = "AGENT"  # Específico para decisões de agentes
    METRIC = "METRIC"  # Específico para métricas


@dataclass
class LogEntry:
    """Estrutura de uma entrada de log"""
    timestamp: str
    level: str
    component: str
    message: str
    data: Dict[str, Any]
    context: Dict[str, Any]
    
    def to_json(self) -> str:
        """Converte para JSON"""
        return json.dumps(asdict(self))


class StructuredLogger:
    """Logger estruturado com formato JSON"""
    
    def __init__(self, component: str, log_dir: str = "logs"):
        self.component = component
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Arquivo de log
        timestamp = datetime.now().strftime("%Y%m%d")
        self.log_file = self.log_dir / f"{component}_{timestamp}.jsonl"
        
        # Buffer para logs recentes
        self.recent_logs = deque(maxlen=1000)
        
        # Lock para thread-safety
        self.lock = threading.Lock()
        
        # Contexto global
        self.global_context = {
            'session_id': datetime.now().strftime("%Y%m%d_%H%M%S"),
            'component': component,
            'pid': os.getpid()
        }
        
        # Estatísticas
        self.stats = {
            'total_logs': 0,
            'by_level': {},
            'errors': 0,
            'warnings': 0
        }
        
        # Configurar logger Python padrão
        self._setup_python_logger()
    
    def _setup_python_logger(self):
        """Configura logger Python para capturar logs existentes"""
        self.python_logger = logging.getLogger(self.component)
        self.python_logger.setLevel(logging.DEBUG)
        
        # Handler customizado
        handler = logging.StreamHandler()
        handler.setFormatter(self)
        self.python_logger.addHandler(handler)
    
    def format(self, record: logging.LogRecord) -> str:
        """Formata log record para JSON (para compatibilidade com logging padrão)"""
        entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'component': record.name,
            'message': record.getMessage(),
            'data': getattr(record, 'data', {}),
            'context': self.global_context
        }
        return json.dumps(entry)
    
    def log(self, level: LogLevel, message: str, data: Optional[Dict] = None, **kwargs):
        """Log genérico estruturado"""
        with self.lock:
            # Criar entrada
            entry = LogEntry(
                timestamp=datetime.now().isoformat(),
                level=level.value,
                component=self.component,
                message=message,
                data=data or {},
                context={**self.global_context, **kwargs}
            )
            
            # Adicionar ao buffer
            self.recent_logs.append(entry)
            
            # Escrever no arquivo
            self._write_to_file(entry)
            
            # Atualizar estatísticas
            self._update_stats(level)
            
            # Console output (desenvolvimento)
            if os.getenv('LOG_TO_CONSOLE', 'false').lower() == 'true':
                self._console_output(entry)
    
    def _write_to_file(self, entry: LogEntry):
        """Escreve entrada no arquivo"""
        try:
            with open(self.log_file, 'a') as f:
                f.write(entry.to_json() + '\n')
        except Exception as e:
            print(f"Erro ao escrever log: {e}", file=sys.stderr)
    
    def _update_stats(self, level: LogLevel):
        """Atualiza estatísticas de logging"""
        self.stats['total_logs'] += 1
        self.stats['by_level'][level.value] = self.stats['by_level'].get(level.value, 0) + 1
        
        if level == LogLevel.ERROR or level == LogLevel.CRITICAL:
            self.stats['errors'] += 1
        elif level == LogLevel.WARNING:
            self.stats['warnings'] += 1
    
    def _console_output(self, entry: LogEntry):
        """Output formatado para console"""
        colors = {
            'DEBUG': '\033[90m',  # Cinza
            'INFO': '\033[0m',    # Normal
            'WARNING': '\033[93m', # Amarelo
            'ERROR': '\033[91m',   # Vermelho
            'CRITICAL': '\033[91m\033[1m',  # Vermelho negrito
            'TRADE': '\033[92m',   # Verde
            'FEATURE': '\033[94m', # Azul
            'AGENT': '\033[95m',   # Magenta
            'METRIC': '\033[96m'   # Ciano
        }
        
        color = colors.get(entry.level, '\033[0m')
        reset = '\033[0m'
        
        print(f"{color}[{entry.timestamp}] {entry.level} - {entry.component}: {entry.message}{reset}")
        if entry.data:
            print(f"  Data: {json.dumps(entry.data, indent=2)}")
    
    # Métodos de conveniência
    def debug(self, message: str, **data):
        """Log nível DEBUG"""
        self.log(LogLevel.DEBUG, message, data)
    
    def info(self, message: str, **data):
        """Log nível INFO"""
        self.log(LogLevel.INFO, message, data)
    
    def warning(self, message: str, **data):
        """Log nível WARNING"""
        self.log(LogLevel.WARNING, message, data)
    
    def error(self, message: str, exception: Optional[Exception] = None, **data):
        """Log nível ERROR"""
        error_data = data.copy()
        if exception:
            error_data['exception'] = str(exception)
            error_data['traceback'] = traceback.format_exc()
        self.log(LogLevel.ERROR, message, error_data)
    
    def critical(self, message: str, **data):
        """Log nível CRITICAL"""
        self.log(LogLevel.CRITICAL, message, data)
    
    def trade(self, action: str, **data):
        """Log específico para trades"""
        self.log(LogLevel.TRADE, f"Trade action: {action}", data)
    
    def feature(self, feature_name: str, value: Any, **data):
        """Log específico para features"""
        feature_data = {'feature': feature_name, 'value': value, **data}
        self.log(LogLevel.FEATURE, f"Feature calculated: {feature_name}", feature_data)
    
    def agent(self, agent_name: str, decision: str, **data):
        """Log específico para agentes"""
        agent_data = {'agent': agent_name, 'decision': decision, **data}
        self.log(LogLevel.AGENT, f"Agent decision: {agent_name} -> {decision}", agent_data)
    
    def metric(self, metric_name: str, value: Any, **data):
        """Log específico para métricas"""
        metric_data = {'metric': metric_name, 'value': value, **data}
        self.log(LogLevel.METRIC, f"Metric: {metric_name} = {value}", metric_data)
    
    def get_recent_logs(self, n: int = 100, level: Optional[LogLevel] = None) -> list:
        """Retorna logs recentes"""
        with self.lock:
            logs = list(self.recent_logs)
            
            if level:
                logs = [log for log in logs if log.level == level.value]
            
            return logs[-n:]
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas de logging"""
        with self.lock:
            return self.stats.copy()


class TradingLogger(StructuredLogger):
    """Logger especializado para sistema de trading"""
    
    def __init__(self):
        super().__init__("TradingSystem")
        
        # Campos específicos para trading
        self.position = 0
        self.pnl = 0
        self.trade_count = 0
    
    def log_feature_calculation(self, features: Dict[str, float], latency_ms: float):
        """Log de cálculo de features"""
        self.log(
            LogLevel.FEATURE,
            "Features calculated",
            {
                'features_calculated': len(features),
                'latency_ms': latency_ms,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def log_prediction(self, ml_prediction: float, confidence: float, features_used: int):
        """Log de predição ML"""
        self.log(
            LogLevel.INFO,
            "ML prediction generated",
            {
                'prediction': ml_prediction,
                'confidence': confidence,
                'features_used': features_used,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def log_agent_consensus(self, agents: Dict, consensus: Dict):
        """Log de consenso dos agentes"""
        self.log(
            LogLevel.AGENT,
            "Agent consensus reached",
            {
                'agents': agents,
                'consensus': consensus,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def log_trade_signal(self, signal: str, confidence: float, reasoning: Dict):
        """Log de sinal de trade"""
        self.trade_count += 1
        
        self.log(
            LogLevel.TRADE,
            f"Trade signal: {signal}",
            {
                'signal': signal,
                'confidence': confidence,
                'reasoning': reasoning,
                'trade_number': self.trade_count,
                'current_position': self.position,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def log_order_execution(self, order_id: str, side: str, price: float, 
                           quantity: int, status: str):
        """Log de execução de ordem"""
        self.log(
            LogLevel.TRADE,
            f"Order {status}: {order_id}",
            {
                'order_id': order_id,
                'side': side,
                'price': price,
                'quantity': quantity,
                'status': status,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def log_risk_alert(self, risk_type: str, severity: str, details: Dict):
        """Log de alerta de risco"""
        level = LogLevel.WARNING if severity == "medium" else LogLevel.ERROR
        
        self.log(
            level,
            f"Risk alert: {risk_type}",
            {
                'risk_type': risk_type,
                'severity': severity,
                'details': details,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def log_performance_metrics(self, metrics: Dict):
        """Log de métricas de performance"""
        self.log(
            LogLevel.METRIC,
            "Performance update",
            {
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            }
        )


class LogAggregator:
    """Agregador de logs de múltiplos componentes"""
    
    def __init__(self, components: list):
        self.loggers = {
            component: StructuredLogger(component) 
            for component in components
        }
        
        self.aggregated_stats = {}
    
    def get_logger(self, component: str) -> StructuredLogger:
        """Retorna logger para componente"""
        if component not in self.loggers:
            self.loggers[component] = StructuredLogger(component)
        return self.loggers[component]
    
    def aggregate_stats(self) -> Dict:
        """Agrega estatísticas de todos os loggers"""
        total_stats = {
            'total_logs': 0,
            'total_errors': 0,
            'total_warnings': 0,
            'by_component': {}
        }
        
        for component, logger in self.loggers.items():
            stats = logger.get_stats()
            total_stats['total_logs'] += stats['total_logs']
            total_stats['total_errors'] += stats['errors']
            total_stats['total_warnings'] += stats['warnings']
            total_stats['by_component'][component] = stats
        
        return total_stats
    
    def search_logs(self, query: str, component: Optional[str] = None) -> list:
        """Busca logs por query"""
        results = []
        
        loggers = [self.loggers[component]] if component else self.loggers.values()
        
        for logger in loggers:
            for log in logger.get_recent_logs(1000):
                if query.lower() in log.message.lower():
                    results.append(log)
        
        return results


def test_structured_logging():
    """Teste do sistema de logging estruturado"""
    # Habilitar console output para teste
    os.environ['LOG_TO_CONSOLE'] = 'true'
    
    # Criar logger de trading
    logger = TradingLogger()
    
    print("=" * 60)
    print("TESTE DE LOGGING ESTRUTURADO")
    print("=" * 60)
    
    # Teste 1: Log de features
    features = {f'feature_{i}': i * 0.1 for i in range(65)}
    logger.log_feature_calculation(features, 2.5)
    
    # Teste 2: Log de predição
    logger.log_prediction(0.75, 0.82, 65)
    
    # Teste 3: Log de agentes
    agents = {
        'OrderFlow': {'signal': 'BUY', 'confidence': 0.8},
        'Liquidity': {'signal': 'HOLD', 'confidence': 0.6}
    }
    consensus = {'action': 'BUY', 'confidence': 0.7}
    logger.log_agent_consensus(agents, consensus)
    
    # Teste 4: Log de trade
    logger.log_trade_signal(
        'BUY',
        0.75,
        {'ml_signal': 0.8, 'agent_consensus': 0.7}
    )
    
    # Teste 5: Log de ordem
    logger.log_order_execution(
        'ORD_001',
        'BUY',
        5450.50,
        1,
        'FILLED'
    )
    
    # Teste 6: Log de risco
    logger.log_risk_alert(
        'POSITION_SIZE',
        'medium',
        {'current': 1, 'max': 2}
    )
    
    # Teste 7: Log de métricas
    logger.log_performance_metrics({
        'win_rate': 0.55,
        'sharpe': 1.5,
        'max_drawdown': 0.05
    })
    
    # Teste 8: Log de erro
    try:
        1 / 0
    except Exception as e:
        logger.error("Division by zero error", exception=e)
    
    # Estatísticas
    print("\n" + "=" * 60)
    print("ESTATÍSTICAS DE LOGGING")
    print("=" * 60)
    stats = logger.get_stats()
    print(json.dumps(stats, indent=2))
    
    # Logs recentes
    print("\n" + "=" * 60)
    print("ÚLTIMOS 5 LOGS")
    print("=" * 60)
    recent = logger.get_recent_logs(5)
    for log in recent:
        print(f"[{log.level}] {log.message}")
    
    print("\nTeste concluído!")
    print(f"Logs salvos em: {logger.log_file}")


if __name__ == "__main__":
    test_structured_logging()