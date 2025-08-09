"""
Sistema de Métricas e Alertas
Monitoramento com Prometheus e sistema de alertas inteligente
"""

import time
import json
import threading
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
from collections import deque
import numpy as np
import logging

# Prometheus metrics (será instalado opcionalmente)
try:
    from prometheus_client import Counter, Gauge, Histogram, Summary, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    print("Prometheus client não instalado. Usando métricas internas.")

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Níveis de severidade de alertas"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MetricType(Enum):
    """Tipos de métricas"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Alert:
    """Estrutura de um alerta"""
    id: str
    timestamp: datetime
    severity: AlertSeverity
    component: str
    metric: str
    message: str
    value: Any
    threshold: Any
    metadata: Dict
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['severity'] = self.severity.value
        return data


class MetricsCollector:
    """Coletor de métricas do sistema"""
    
    def __init__(self, namespace: str = "trading_system"):
        self.namespace = namespace
        self.metrics = {}
        self.metric_history = {}
        self.lock = threading.Lock()
        
        # Inicializar Prometheus se disponível
        if PROMETHEUS_AVAILABLE:
            self._init_prometheus_metrics()
        
        # Buffer de métricas
        self.buffer_size = 1000
        
    def _init_prometheus_metrics(self):
        """Inicializa métricas Prometheus"""
        # Contadores
        self.prom_features_calculated = Counter(
            f'{self.namespace}_features_calculated_total',
            'Total de features calculadas'
        )
        self.prom_predictions_made = Counter(
            f'{self.namespace}_predictions_made_total',
            'Total de predições realizadas'
        )
        self.prom_trades_executed = Counter(
            f'{self.namespace}_trades_executed_total',
            'Total de trades executados',
            ['side', 'result']
        )
        
        # Gauges
        self.prom_active_position = Gauge(
            f'{self.namespace}_active_position',
            'Posição ativa atual'
        )
        self.prom_current_pnl = Gauge(
            f'{self.namespace}_current_pnl',
            'PnL atual'
        )
        self.prom_win_rate = Gauge(
            f'{self.namespace}_win_rate',
            'Taxa de acerto'
        )
        
        # Histogramas
        self.prom_feature_latency = Histogram(
            f'{self.namespace}_feature_latency_seconds',
            'Latência de cálculo de features',
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
        )
        self.prom_prediction_latency = Histogram(
            f'{self.namespace}_prediction_latency_seconds',
            'Latência de predição ML'
        )
        
        # Summary
        self.prom_trade_pnl = Summary(
            f'{self.namespace}_trade_pnl',
            'PnL por trade'
        )
    
    def record_counter(self, name: str, value: float = 1, labels: Dict = None):
        """Registra métrica tipo contador"""
        with self.lock:
            # Atualizar métrica interna
            if name not in self.metrics:
                self.metrics[name] = 0
            self.metrics[name] += value
            
            # Adicionar ao histórico
            if name not in self.metric_history:
                self.metric_history[name] = deque(maxlen=self.buffer_size)
            self.metric_history[name].append({
                'timestamp': datetime.now(),
                'value': self.metrics[name]
            })
            
            # Prometheus se disponível
            if PROMETHEUS_AVAILABLE:
                self._update_prometheus_counter(name, value, labels)
    
    def record_gauge(self, name: str, value: float):
        """Registra métrica tipo gauge"""
        with self.lock:
            # Atualizar métrica interna
            self.metrics[name] = value
            
            # Adicionar ao histórico
            if name not in self.metric_history:
                self.metric_history[name] = deque(maxlen=self.buffer_size)
            self.metric_history[name].append({
                'timestamp': datetime.now(),
                'value': value
            })
            
            # Prometheus se disponível
            if PROMETHEUS_AVAILABLE:
                self._update_prometheus_gauge(name, value)
    
    def record_histogram(self, name: str, value: float):
        """Registra métrica tipo histograma"""
        with self.lock:
            # Adicionar ao histórico
            if name not in self.metric_history:
                self.metric_history[name] = deque(maxlen=self.buffer_size)
            self.metric_history[name].append({
                'timestamp': datetime.now(),
                'value': value
            })
            
            # Calcular estatísticas
            values = [h['value'] for h in self.metric_history[name]]
            self.metrics[f"{name}_mean"] = np.mean(values)
            self.metrics[f"{name}_p50"] = np.percentile(values, 50)
            self.metrics[f"{name}_p95"] = np.percentile(values, 95)
            self.metrics[f"{name}_p99"] = np.percentile(values, 99)
            
            # Prometheus se disponível
            if PROMETHEUS_AVAILABLE:
                self._update_prometheus_histogram(name, value)
    
    def _update_prometheus_counter(self, name: str, value: float, labels: Dict):
        """Atualiza contador Prometheus"""
        if name == 'features_calculated':
            self.prom_features_calculated.inc(value)
        elif name == 'predictions_made':
            self.prom_predictions_made.inc(value)
        elif name == 'trades_executed' and labels:
            self.prom_trades_executed.labels(**labels).inc(value)
    
    def _update_prometheus_gauge(self, name: str, value: float):
        """Atualiza gauge Prometheus"""
        if name == 'active_position':
            self.prom_active_position.set(value)
        elif name == 'current_pnl':
            self.prom_current_pnl.set(value)
        elif name == 'win_rate':
            self.prom_win_rate.set(value)
    
    def _update_prometheus_histogram(self, name: str, value: float):
        """Atualiza histograma Prometheus"""
        if name == 'feature_latency':
            self.prom_feature_latency.observe(value)
        elif name == 'prediction_latency':
            self.prom_prediction_latency.observe(value)
    
    def get_metric(self, name: str) -> Optional[float]:
        """Obtém valor atual de uma métrica"""
        with self.lock:
            return self.metrics.get(name)
    
    def get_metric_history(self, name: str, n: int = 100) -> List[Dict]:
        """Obtém histórico de uma métrica"""
        with self.lock:
            if name in self.metric_history:
                return list(self.metric_history[name])[-n:]
            return []
    
    def get_all_metrics(self) -> Dict:
        """Obtém todas as métricas atuais"""
        with self.lock:
            return self.metrics.copy()
    
    def get_metrics_summary(self) -> Dict:
        """Obtém resumo das métricas"""
        with self.lock:
            summary = {
                'timestamp': datetime.now().isoformat(),
                'counters': {},
                'gauges': {},
                'histograms': {}
            }
            
            for name, value in self.metrics.items():
                if '_mean' in name or '_p50' in name or '_p95' in name or '_p99' in name:
                    base_name = name.rsplit('_', 1)[0]
                    if base_name not in summary['histograms']:
                        summary['histograms'][base_name] = {}
                    stat_type = name.rsplit('_', 1)[1]
                    summary['histograms'][base_name][stat_type] = value
                elif isinstance(value, (int, float)):
                    if name in ['active_position', 'current_pnl', 'win_rate']:
                        summary['gauges'][name] = value
                    else:
                        summary['counters'][name] = value
            
            return summary


class AlertManager:
    """Gerenciador de alertas do sistema"""
    
    def __init__(self):
        self.alerts = deque(maxlen=1000)
        self.alert_rules = {}
        self.alert_handlers = {}
        self.lock = threading.Lock()
        self.alert_counter = 0
        
        # Estatísticas de alertas
        self.alert_stats = {
            'total': 0,
            'by_severity': {},
            'by_component': {}
        }
    
    def add_rule(self, name: str, metric: str, condition: Callable, 
                 threshold: Any, severity: AlertSeverity, component: str):
        """Adiciona regra de alerta"""
        self.alert_rules[name] = {
            'metric': metric,
            'condition': condition,
            'threshold': threshold,
            'severity': severity,
            'component': component,
            'last_triggered': None
        }
    
    def add_handler(self, severity: AlertSeverity, handler: Callable):
        """Adiciona handler para alertas de determinada severidade"""
        if severity not in self.alert_handlers:
            self.alert_handlers[severity] = []
        self.alert_handlers[severity].append(handler)
    
    def check_alerts(self, metrics: Dict):
        """Verifica regras de alerta com base nas métricas"""
        triggered_alerts = []
        
        with self.lock:
            for rule_name, rule in self.alert_rules.items():
                metric_value = metrics.get(rule['metric'])
                
                if metric_value is not None:
                    # Verificar condição
                    if rule['condition'](metric_value, rule['threshold']):
                        # Evitar alertas duplicados em curto período
                        now = datetime.now()
                        if rule['last_triggered'] is None or \
                           (now - rule['last_triggered']).seconds > 60:
                            
                            # Criar alerta
                            alert = self._create_alert(
                                rule_name, rule, metric_value
                            )
                            
                            # Adicionar à lista
                            self.alerts.append(alert)
                            triggered_alerts.append(alert)
                            
                            # Atualizar timestamp
                            rule['last_triggered'] = now
                            
                            # Atualizar estatísticas
                            self._update_stats(alert)
                            
                            # Executar handlers
                            self._execute_handlers(alert)
        
        return triggered_alerts
    
    def _create_alert(self, rule_name: str, rule: Dict, metric_value: Any) -> Alert:
        """Cria um alerta"""
        self.alert_counter += 1
        
        return Alert(
            id=f"ALERT_{self.alert_counter:06d}",
            timestamp=datetime.now(),
            severity=rule['severity'],
            component=rule['component'],
            metric=rule['metric'],
            message=f"Alert: {rule_name} - {rule['metric']} = {metric_value}",
            value=metric_value,
            threshold=rule['threshold'],
            metadata={'rule': rule_name}
        )
    
    def _update_stats(self, alert: Alert):
        """Atualiza estatísticas de alertas"""
        self.alert_stats['total'] += 1
        
        # Por severidade
        severity = alert.severity.value
        if severity not in self.alert_stats['by_severity']:
            self.alert_stats['by_severity'][severity] = 0
        self.alert_stats['by_severity'][severity] += 1
        
        # Por componente
        component = alert.component
        if component not in self.alert_stats['by_component']:
            self.alert_stats['by_component'][component] = 0
        self.alert_stats['by_component'][component] += 1
    
    def _execute_handlers(self, alert: Alert):
        """Executa handlers para o alerta"""
        if alert.severity in self.alert_handlers:
            for handler in self.alert_handlers[alert.severity]:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Erro ao executar handler: {e}")
    
    def get_recent_alerts(self, n: int = 10, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Obtém alertas recentes"""
        with self.lock:
            alerts = list(self.alerts)
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            
            return alerts[-n:]
    
    def get_alert_stats(self) -> Dict:
        """Obtém estatísticas de alertas"""
        with self.lock:
            return self.alert_stats.copy()


class TradingMetricsSystem:
    """Sistema integrado de métricas para trading"""
    
    def __init__(self, prometheus_port: int = 8000):
        self.collector = MetricsCollector("quantum_trader")
        self.alert_manager = AlertManager()
        
        # Iniciar servidor Prometheus se disponível
        if PROMETHEUS_AVAILABLE and prometheus_port:
            try:
                start_http_server(prometheus_port)
                logger.info(f"Servidor Prometheus iniciado na porta {prometheus_port}")
            except Exception as e:
                logger.error(f"Erro ao iniciar servidor Prometheus: {e}")
        
        # Configurar regras de alerta padrão
        self._setup_default_alerts()
        
        # Thread de monitoramento
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def _setup_default_alerts(self):
        """Configura alertas padrão do sistema"""
        
        # Alerta de latência alta
        self.alert_manager.add_rule(
            name="high_feature_latency",
            metric="feature_latency_p99",
            condition=lambda v, t: v > t,
            threshold=0.05,  # 50ms
            severity=AlertSeverity.WARNING,
            component="FeatureEngine"
        )
        
        # Alerta de win rate baixo
        self.alert_manager.add_rule(
            name="low_win_rate",
            metric="win_rate",
            condition=lambda v, t: v < t,
            threshold=0.45,  # 45%
            severity=AlertSeverity.WARNING,
            component="TradingSystem"
        )
        
        # Alerta de drawdown alto
        self.alert_manager.add_rule(
            name="high_drawdown",
            metric="max_drawdown",
            condition=lambda v, t: v > t,
            threshold=0.1,  # 10%
            severity=AlertSeverity.ERROR,
            component="RiskManager"
        )
        
        # Alerta de erro rate alto
        self.alert_manager.add_rule(
            name="high_error_rate",
            metric="error_rate",
            condition=lambda v, t: v > t,
            threshold=0.05,  # 5%
            severity=AlertSeverity.ERROR,
            component="System"
        )
        
        # Handlers de exemplo
        self.alert_manager.add_handler(
            AlertSeverity.WARNING,
            lambda alert: logger.warning(f"Alert: {alert.message}")
        )
        
        self.alert_manager.add_handler(
            AlertSeverity.ERROR,
            lambda alert: logger.error(f"Alert: {alert.message}")
        )
        
        self.alert_manager.add_handler(
            AlertSeverity.CRITICAL,
            lambda alert: logger.critical(f"CRITICAL Alert: {alert.message}")
        )
    
    def _monitor_loop(self):
        """Loop de monitoramento contínuo"""
        while self.monitoring:
            try:
                # Verificar alertas
                metrics = self.collector.get_all_metrics()
                self.alert_manager.check_alerts(metrics)
                
                # Aguardar próximo ciclo
                time.sleep(10)  # Verificar a cada 10 segundos
                
            except Exception as e:
                logger.error(f"Erro no monitoramento: {e}")
    
    def record_feature_calculation(self, features_count: int, latency_ms: float):
        """Registra cálculo de features"""
        self.collector.record_counter('features_calculated', features_count)
        self.collector.record_histogram('feature_latency', latency_ms / 1000)
    
    def record_prediction(self, confidence: float, latency_ms: float):
        """Registra predição ML"""
        self.collector.record_counter('predictions_made')
        self.collector.record_histogram('prediction_latency', latency_ms / 1000)
        self.collector.record_gauge('last_prediction_confidence', confidence)
    
    def record_trade(self, side: str, pnl: float):
        """Registra trade executado"""
        result = 'win' if pnl > 0 else 'loss'
        self.collector.record_counter('trades_executed', labels={'side': side, 'result': result})
        
        if PROMETHEUS_AVAILABLE:
            self.collector.prom_trade_pnl.observe(pnl)
    
    def update_position(self, position: int):
        """Atualiza posição ativa"""
        self.collector.record_gauge('active_position', position)
    
    def update_pnl(self, pnl: float):
        """Atualiza PnL atual"""
        self.collector.record_gauge('current_pnl', pnl)
    
    def update_win_rate(self, win_rate: float):
        """Atualiza win rate"""
        self.collector.record_gauge('win_rate', win_rate)
    
    def update_drawdown(self, drawdown: float):
        """Atualiza drawdown"""
        self.collector.record_gauge('max_drawdown', drawdown)
    
    def get_dashboard_data(self) -> Dict:
        """Obtém dados para dashboard"""
        return {
            'metrics': self.collector.get_metrics_summary(),
            'alerts': [a.to_dict() for a in self.alert_manager.get_recent_alerts(20)],
            'alert_stats': self.alert_manager.get_alert_stats()
        }
    
    def stop(self):
        """Para o sistema de métricas"""
        self.monitoring = False
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)


def test_metrics_system():
    """Teste do sistema de métricas e alertas"""
    print("=" * 60)
    print("TESTE DO SISTEMA DE MÉTRICAS E ALERTAS")
    print("=" * 60)
    
    # Criar sistema
    metrics_system = TradingMetricsSystem(prometheus_port=0)  # Sem servidor Prometheus para teste
    
    # Simular operações
    print("\n1. Simulando operações de trading...")
    
    for i in range(10):
        # Features
        metrics_system.record_feature_calculation(65, np.random.uniform(1, 10))
        
        # Predições
        metrics_system.record_prediction(np.random.uniform(0.4, 0.9), np.random.uniform(0.5, 5))
        
        # Trades
        if i % 3 == 0:
            side = np.random.choice(['BUY', 'SELL'])
            pnl = np.random.uniform(-100, 200)
            metrics_system.record_trade(side, pnl)
        
        time.sleep(0.1)
    
    # Atualizar métricas
    metrics_system.update_position(1)
    metrics_system.update_pnl(1500.50)
    metrics_system.update_win_rate(0.58)
    metrics_system.update_drawdown(0.03)
    
    # Simular latência alta para trigger de alerta
    print("\n2. Simulando latência alta...")
    metrics_system.collector.record_histogram('feature_latency', 0.1)  # 100ms
    
    # Aguardar processamento
    time.sleep(2)
    
    # Obter dashboard
    dashboard = metrics_system.get_dashboard_data()
    
    print("\n3. Dashboard de Métricas:")
    print("-" * 40)
    print(json.dumps(dashboard['metrics'], indent=2))
    
    print("\n4. Alertas Gerados:")
    print("-" * 40)
    for alert in dashboard['alerts']:
        print(f"[{alert['severity']}] {alert['message']}")
    
    print("\n5. Estatísticas de Alertas:")
    print("-" * 40)
    print(json.dumps(dashboard['alert_stats'], indent=2))
    
    # Parar sistema
    metrics_system.stop()
    
    print("\nTeste concluído!")


if __name__ == "__main__":
    test_metrics_system()