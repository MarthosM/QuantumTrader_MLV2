# 🔧 Developer Guide - QuantumTrader Production

## Arquitetura e Desenvolvimento do Sistema

---

## 📐 Arquitetura do Sistema

### Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                   ProfitDLL Interface                    │
│                  (Callbacks & Data Feed)                 │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│              Enhanced Production System                  │
│  ┌─────────────────────────────────────────────────┐   │
│  │           Circular Buffers (Thread-Safe)         │   │
│  │  - CandleBuffer (200)                           │   │
│  │  - BookBuffer (100)                             │   │
│  │  - TradeBuffer (1000)                           │   │
│  └─────────────────┬───────────────────────────────┘   │
└────────────────────┼────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│            Feature Engineering (65 Features)            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │  Volatility  │ │   Returns    │ │  Order Flow  │   │
│  │     (10)     │ │     (10)     │ │      (8)     │   │
│  └──────────────┘ └──────────────┘ └──────────────┘   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │    Volume    │ │  Technical   │ │Microstructure│   │
│  │      (8)     │ │      (8)     │ │     (15)     │   │
│  └──────────────┘ └──────────────┘ └──────────────┘   │
│  ┌──────────────┐                                      │
│  │   Temporal   │                                      │
│  │      (6)     │                                      │
│  └──────────────┘                                      │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│              ML Models & HMARL Agents                   │
│  ┌─────────────┐     ┌──────────────────────────────┐ │
│  │  XGBoost/   │     │     4 HMARL Agents:          │ │
│  │  LightGBM   │     │  - OrderFlowSpecialist       │ │
│  │     40%     │     │  - LiquidityAgent            │ │
│  └─────────────┘     │  - TapeReadingAgent          │ │
│                      │  - FootprintPatternAgent     │ │
│                      │           60%                 │ │
│                      └──────────────────────────────┘ │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                   Consensus System                      │
│         (Adaptive Weighted Voting + Risk Check)         │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                   Trading Decision                      │
│              (BUY / SELL / HOLD + Size)                │
└─────────────────────────────────────────────────────────┘
```

## 🔄 Fluxo de Dados

### 1. Entrada de Dados (Callbacks)

```python
# src/connection_manager_v4.py
class ConnectionManagerV4:
    def on_price_book_callback(self, asset, book_info):
        # Recebe dados do book
        # Armazena em BookBuffer
        # Trigger feature calculation
        
    def on_daily_callback(self, asset, daily_info):
        # Recebe candles
        # Armazena em CandleBuffer
        # Update indicators
```

### 2. Buffers Circulares Thread-Safe

```python
# src/buffers/circular_buffer.py
class CircularBuffer:
    def __init__(self, capacity):
        self.buffer = deque(maxlen=capacity)
        self.lock = threading.RLock()
    
    def add(self, item):
        with self.lock:
            self.buffer.append(item)
```

### 3. Cálculo de Features (65)

```python
# src/features/book_features_rt.py
class BookFeatureEngineerRT:
    def calculate_incremental_features(self, new_data):
        features = {}
        
        # Volatility (10 features)
        features.update(self._calculate_volatility_features())
        
        # Returns (10 features)  
        features.update(self._calculate_return_features())
        
        # Order Flow (8 features)
        features.update(self._calculate_order_flow_features())
        
        # Volume (8 features)
        features.update(self._calculate_volume_features())
        
        # Technical (8 features)
        features.update(self._calculate_technical_features())
        
        # Microstructure (15 features)
        features.update(self._calculate_microstructure_features())
        
        # Temporal (6 features)
        features.update(self._calculate_temporal_features())
        
        return features  # Total: 65 features
```

## 🤖 Sistema HMARL

### Arquitetura dos Agentes

```python
# src/agents/hmarl_agents_enhanced.py

class OrderFlowSpecialist(BaseAgent):
    """Especialista em fluxo de ordens"""
    def analyze(self, features):
        # Foco em: order_flow_imbalance, signed_volume, trade_flow
        # Detecta: Absorção, divergências, momentum
        
class LiquidityAgent(BaseAgent):
    """Especialista em liquidez"""
    def analyze(self, features):
        # Foco em: bid/ask volumes, spread, book depth
        # Detecta: Liquidez seca, suporte/resistência
        
class TapeReadingAgent(BaseAgent):
    """Leitor de fita"""
    def analyze(self, features):
        # Foco em: trade prints, volume clusters, speed
        # Detecta: Institutional flow, iceberg orders
        
class FootprintPatternAgent(BaseAgent):
    """Detector de padrões de pegadas"""
    def analyze(self, features):
        # Foco em: volume profile, delta, imbalances
        # Detecta: P/b patterns, unfinished auctions
```

### Sistema de Consenso

```python
# src/consensus/hmarl_consensus_system.py

class ConsensusEngine:
    def calculate_consensus(self, ml_prediction, agent_signals):
        # 1. Coletar votos ponderados
        ml_vote = ml_prediction * 0.40
        
        agent_votes = []
        for agent, signal in agent_signals.items():
            weight = self.agent_weights[agent]
            vote = signal.value * signal.confidence * weight
            agent_votes.append(vote)
        
        # 2. Combinar votos
        total_vote = ml_vote + sum(agent_votes) * 0.60
        
        # 3. Aplicar threshold adaptativo
        if abs(total_vote) > self.threshold:
            return self.create_trading_decision(total_vote)
        
        return HOLD
```

## 💻 Estrutura de Código

### Módulos Principais

```
src/
├── connection_manager_v4.py    # Interface com ProfitDLL
├── trading_system.py           # Sistema principal de trading
├── data_structure.py           # Estruturas de dados centralizadas
│
├── features/
│   └── book_features_rt.py    # Cálculo de 65 features em RT
│
├── buffers/
│   └── circular_buffer.py     # Buffers thread-safe
│
├── agents/
│   └── hmarl_agents_enhanced.py # 4 agentes especializados
│
├── consensus/
│   └── hmarl_consensus_system.py # Sistema de consenso
│
├── metrics/
│   └── metrics_and_alerts.py  # Métricas e alertas
│
└── logging/
    └── structured_logger.py   # Logs estruturados JSON
```

### Padrões de Código

#### 1. Thread Safety

```python
# SEMPRE use locks para dados compartilhados
class ThreadSafeComponent:
    def __init__(self):
        self.lock = threading.RLock()
        self.data = {}
    
    def update(self, key, value):
        with self.lock:
            self.data[key] = value
```

#### 2. Error Handling

```python
# SEMPRE capture e logue erros
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    # Fallback ou recovery
    result = default_value
except Exception as e:
    logger.critical(f"Unexpected error: {e}")
    # Notificar e possivelmente parar
```

#### 3. Performance

```python
# Use numpy para operações vetorizadas
import numpy as np

# Ruim
result = []
for x in data:
    result.append(x * 2)

# Bom
result = np.array(data) * 2
```

## 🔬 Testing

### Unit Tests

```python
# tests/test_features.py
def test_volatility_calculation():
    buffer = CandleBuffer(100)
    # Add test data
    features = calculate_volatility_features(buffer)
    assert len(features) == 10
    assert features['volatility_20'] > 0
```

### Integration Tests

```python
# tests/test_integration.py
def test_full_pipeline():
    # Simular callbacks
    # Verificar features
    # Testar consenso
    # Validar decisão
```

### Performance Tests

```python
# tests/test_performance.py
def test_feature_latency():
    start = time.perf_counter()
    features = calculate_all_features(data)
    latency = (time.perf_counter() - start) * 1000
    assert latency < 10  # Must be under 10ms
```

## 🚀 Deployment

### Checklist de Produção

- [ ] Todos os testes passando
- [ ] Configuração revisada (.env.production)
- [ ] Modelos ML presentes em models/
- [ ] Logs configurados corretamente
- [ ] Backup automático habilitado
- [ ] Monitoring ativo
- [ ] ProfitDLL conectado

### Monitoramento

```python
# Métricas críticas a monitorar
- Latência de features < 10ms
- Taxa de erro < 1%
- Uso de memória < 1GB
- CPU < 20%
- Win rate > 50%
- Drawdown < 10%
```

## 📊 Otimização

### Profile de Performance

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Código a analisar
run_trading_system()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)  # Top 10 funções
```

### Otimizações Comuns

1. **Cache de cálculos repetidos**
2. **Vectorização com NumPy**
3. **Uso de numba para loops críticos**
4. **Redução de alocações de memória**
5. **Batch processing quando possível**

## 🔐 Segurança

### Boas Práticas

1. **Nunca commitar credenciais**
2. **Usar variáveis de ambiente**
3. **Validar todas as entradas**
4. **Sanitizar logs**
5. **Implementar rate limiting**
6. **Backup encriptado**

## 📝 Convenções

### Nomenclatura

```python
# Classes: PascalCase
class TradingSystem:
    pass

# Funções: snake_case
def calculate_features():
    pass

# Constantes: UPPER_SNAKE_CASE
MAX_BUFFER_SIZE = 1000

# Privado: underscore prefix
def _internal_method():
    pass
```

### Documentação

```python
def calculate_feature(data: pd.DataFrame, period: int = 20) -> float:
    """
    Calcula feature específica.
    
    Args:
        data: DataFrame com dados OHLCV
        period: Período para cálculo
        
    Returns:
        float: Valor da feature calculada
        
    Raises:
        ValueError: Se dados insuficientes
    """
    pass
```

## 🛠️ Ferramentas Úteis

### Debugging

```python
# Use logging ao invés de print
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Feature value: {feature}")

# Use breakpoints
import pdb; pdb.set_trace()

# Ou com Python 3.7+
breakpoint()
```

### Profiling

```bash
# Line profiler
kernprof -l -v script.py

# Memory profiler
python -m memory_profiler script.py
```

## 📚 Recursos

### Documentação Relacionada
- [HMARL_GUIDE.md](HMARL_GUIDE.md) - Detalhes do sistema HMARL
- [README.md](README.md) - Visão geral do sistema
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Resolução de problemas

### Bibliotecas Principais
- NumPy - Computação numérica
- Pandas - Manipulação de dados
- XGBoost/LightGBM - Modelos ML
- Threading - Concorrência
- Deque - Buffers circulares

---

**Para dúvidas técnicas, consulte a documentação ou o código fonte.**