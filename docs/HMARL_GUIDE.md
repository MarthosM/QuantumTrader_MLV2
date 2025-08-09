# 🤖 HMARL System Guide

## Hierarchical Multi-Agent Reinforcement Learning para Trading

---

## 📊 Visão Geral do Sistema HMARL

O sistema HMARL (Hierarchical Multi-Agent Reinforcement Learning) implementa 4 agentes especializados que trabalham em conjunto para tomar decisões de trading mais robustas e adaptativas.

### Arquitetura Hierárquica

```
                    ┌──────────────────────┐
                    │   Consensus Engine   │
                    │    (Coordenador)     │
                    └──────────┬───────────┘
                               │
                ┌──────────────┼──────────────┬─────────────┐
                │              │              │             │
       ┌────────▼──────┐ ┌────▼──────┐ ┌────▼──────┐ ┌───▼───────┐
       │  OrderFlow    │ │ Liquidity │ │TapeReading│ │Footprint  │
       │  Specialist   │ │   Agent   │ │   Agent   │ │Pattern    │
       │     (30%)     │ │   (20%)   │ │   (25%)   │ │  (25%)    │
       └───────────────┘ └───────────┘ └───────────┘ └───────────┘
```

## 🎯 Agentes Especializados

### 1. OrderFlowSpecialist (30% peso)

**Objetivo:** Analisar o fluxo de ordens para identificar pressão compradora/vendedora

**Features Monitoradas:**
- `order_flow_imbalance_5, _10, _20`
- `signed_volume_5, _10, _20`
- `trade_flow_5, _10`
- `book_imbalance`
- `book_pressure`

**Estratégias de Detecção:**
```python
class OrderFlowSpecialist:
    def analyze(self, features):
        # 1. Absorção de Volume
        if features['signed_volume_10'] > threshold and \
           features['price_change'] < 0.001:
            # Volume sendo absorvido sem mover preço
            signal = "Absorção detectada"
        
        # 2. Divergência de Fluxo
        if features['order_flow_imbalance_5'] > 0.3 and \
           features['returns_5'] < 0:
            # Fluxo comprador mas preço caindo
            signal = "Divergência bullish"
        
        # 3. Momentum de Fluxo
        if all(features[f'order_flow_imbalance_{p}'] > 0.2 
               for p in [5, 10, 20]):
            # Fluxo consistente em múltiplos períodos
            signal = "Momentum forte"
```

**Sinais Gerados:**
- `STRONG_BUY`: Absorção vendedora + divergência bullish
- `BUY`: Momentum comprador consistente
- `HOLD`: Fluxo neutro ou inconclusivo
- `SELL`: Momentum vendedor consistente
- `STRONG_SELL`: Absorção compradora + divergência bearish

### 2. LiquidityAgent (20% peso)

**Objetivo:** Monitorar liquidez e profundidade do book para timing de entrada/saída

**Features Monitoradas:**
- `bid_volume_total, ask_volume_total`
- `bid_levels_active, ask_levels_active`
- `spread, spread_ma, spread_std`
- `book_depth_imbalance`
- `liquidity_consumption_rate`

**Estratégias de Detecção:**
```python
class LiquidityAgent:
    def analyze(self, features):
        # 1. Liquidez Seca
        if features['bid_volume_total'] < historical_avg * 0.5:
            # Pouca liquidez no bid - cuidado com vendas
            risk = "HIGH"
        
        # 2. Suporte/Resistência por Volume
        if features['bid_levels_active'] > 4 and \
           features['bid_volume_total'] > threshold:
            # Forte suporte no book
            signal = "Suporte robusto"
        
        # 3. Spread Analysis
        if features['spread'] > features['spread_ma'] * 1.5:
            # Spread alargando - possível movimento
            signal = "Preparar para volatilidade"
```

**Métricas de Liquidez:**
- `liquidity_score`: 0-1 (qualidade da liquidez)
- `execution_risk`: LOW/MEDIUM/HIGH
- `optimal_size`: Tamanho recomendado baseado em liquidez

### 3. TapeReadingAgent (25% peso)

**Objetivo:** Ler a "fita" de negócios para identificar atividade institucional

**Features Monitoradas:**
- `trade_flow_5, _10`
- `volume_20, _50, _100`
- `buy_intensity, sell_intensity`
- `large_trade_ratio`
- `trade_velocity`

**Padrões Identificados:**
```python
class TapeReadingAgent:
    def analyze(self, features):
        # 1. Iceberg Orders
        if features['trade_count'] > normal and \
           features['avg_trade_size'] < normal:
            # Muitos trades pequenos - possível iceberg
            pattern = "Iceberg detectado"
        
        # 2. Institutional Sweeps
        if features['large_trade_ratio'] > 0.3 and \
           features['trade_velocity'] > threshold:
            # Trades grandes e rápidos
            pattern = "Institutional buying"
        
        # 3. Stop Hunting
        sudden_volume = features['volume_5'] > features['volume_20'] * 3
        price_reversal = abs(features['returns_5']) > 0.01
        if sudden_volume and price_reversal:
            pattern = "Possível stop hunt"
```

**Classificação de Trades:**
- `RETAIL`: Trades pequenos, aleatórios
- `ALGORITHMIC`: Trades consistentes, mesmo tamanho
- `INSTITUTIONAL`: Trades grandes, direcionais
- `MARKET_MAKER`: Two-way flow, spread capture

### 4. FootprintPatternAgent (25% peso)

**Objetivo:** Analisar padrões de volume e pegadas deixadas por grandes players

**Features Monitoradas:**
- `volume_profile_skew`
- `volume_concentration`
- `delta_cumulative`
- `top_trader_ratio`
- `top_trader_side_bias`

**Padrões de Footprint:**
```python
class FootprintPatternAgent:
    def analyze(self, features):
        # 1. P-Pattern (Compra no fundo)
        if features['volume_concentration'] > 0.7 and \
           features['price_level'] == "low":
            pattern = "P-Pattern bullish"
        
        # 2. b-Pattern (Venda no topo)
        if features['volume_concentration'] > 0.7 and \
           features['price_level'] == "high":
            pattern = "b-Pattern bearish"
        
        # 3. Unfinished Auction
        if features['delta_cumulative'] > 0 and \
           features['close'] < features['vwap']:
            pattern = "Unfinished business - mais alta"
        
        # 4. Volume Clusters
        if features['volume_profile_skew'] > 0.3:
            # Volume concentrado em níveis específicos
            pattern = "Níveis importantes identificados"
```

**Métricas de Footprint:**
- `delta`: Diferença entre volume comprador/vendedor
- `cumulative_delta`: Delta acumulado da sessão
- `imbalance_zones`: Zonas de desequilíbrio
- `poc` (Point of Control): Preço com maior volume

## 🎮 Sistema de Consenso

### Votação Ponderada Adaptativa

```python
class ConsensusEngine:
    def __init__(self):
        self.ml_weight = 0.40
        self.agent_weights = {
            'OrderFlowSpecialist': 0.30,
            'LiquidityAgent': 0.20,
            'TapeReadingAgent': 0.25,
            'FootprintPatternAgent': 0.25
        }
        
    def calculate_consensus(self, ml_pred, agent_signals):
        # 1. Coletar votos
        votes = {
            'ml': ml_pred * self.ml_weight,
            'agents': {}
        }
        
        for agent, signal in agent_signals.items():
            weight = self.agent_weights[agent]
            confidence = signal['confidence']
            direction = signal['direction']  # -1, 0, 1
            
            votes['agents'][agent] = direction * confidence * weight
        
        # 2. Calcular consenso
        ml_vote = votes['ml']
        agent_vote = sum(votes['agents'].values()) * 0.60
        
        final_signal = ml_vote + agent_vote
        
        # 3. Determinar ação
        if final_signal > 0.3:
            return 'BUY'
        elif final_signal < -0.3:
            return 'SELL'
        else:
            return 'HOLD'
```

### Ajuste Adaptativo de Pesos

```python
def update_weights(self, performance_history):
    """Ajusta pesos baseado em performance"""
    
    for agent in self.agent_weights:
        # Calcular accuracy do agente
        accuracy = performance_history[agent]['accuracy']
        sharpe = performance_history[agent]['sharpe']
        
        # Ajustar peso proporcionalmente
        performance_score = accuracy * 0.6 + sharpe * 0.4
        
        if performance_score > 0.7:
            self.agent_weights[agent] *= 1.1  # Aumenta 10%
        elif performance_score < 0.4:
            self.agent_weights[agent] *= 0.9  # Reduz 10%
    
    # Normalizar pesos
    total = sum(self.agent_weights.values())
    for agent in self.agent_weights:
        self.agent_weights[agent] /= total
```

## 📈 Estratégias de Trading por Consenso

### Estratégia 1: Consenso Forte (High Confidence)

```python
if all(agent_signals[agent]['direction'] == 1 for agent in agents):
    # Todos os agentes concordam em comprar
    signal = 'STRONG_BUY'
    size = max_position_size
    confidence = 0.95
```

### Estratégia 2: Maioria Qualificada

```python
buy_votes = sum(1 for s in agent_signals.values() if s['direction'] == 1)
if buy_votes >= 3 and ml_prediction > 0:
    # Maioria dos agentes + ML concordam
    signal = 'BUY'
    size = normal_position_size
    confidence = 0.75
```

### Estratégia 3: Especialista Dominante

```python
if agent_signals['OrderFlowSpecialist']['confidence'] > 0.9:
    # Especialista com alta confiança override outros
    signal = agent_signals['OrderFlowSpecialist']['signal']
    size = normal_position_size * 0.8
    confidence = 0.80
```

## 🔧 Configuração e Tuning

### Parâmetros por Agente

```json
{
  "OrderFlowSpecialist": {
    "imbalance_threshold": 0.3,
    "momentum_periods": [5, 10, 20],
    "absorption_sensitivity": 0.7,
    "min_confidence": 0.60
  },
  "LiquidityAgent": {
    "liquidity_lookback": 100,
    "spread_threshold": 2.0,
    "depth_levels": 5,
    "min_confidence": 0.55
  },
  "TapeReadingAgent": {
    "large_trade_percentile": 90,
    "velocity_window": 10,
    "pattern_sensitivity": 0.65,
    "min_confidence": 0.60
  },
  "FootprintPatternAgent": {
    "volume_concentration_threshold": 0.7,
    "delta_significance": 100,
    "poc_window": 50,
    "min_confidence": 0.55
  }
}
```

### Métricas de Performance

```python
# Métricas por agente
agent_metrics = {
    'accuracy': 0.65,        # Taxa de acerto
    'sharpe_ratio': 1.8,     # Risk-adjusted return
    'avg_confidence': 0.72,  # Confiança média
    'contribution': 0.25,    # Contribuição para P&L
    'agreement_rate': 0.6    # Taxa de concordância com consenso
}

# Métricas do ensemble
ensemble_metrics = {
    'consensus_accuracy': 0.70,
    'diversity_index': 0.4,      # Diversidade de opiniões
    'stability': 0.85,           # Estabilidade de sinais
    'adaptation_rate': 0.1       # Taxa de adaptação de pesos
}
```

## 🚨 Monitoramento e Alertas

### Dashboard de Agentes

```
╔════════════════════════════════════════════════╗
║           HMARL AGENTS MONITOR                ║
╠════════════════════════════════════════════════╣
║ Agent                │ Signal │ Conf │ Weight ║
╟────────────────────┼────────┼──────┼────────╢
║ OrderFlowSpecialist │  BUY   │ 75%  │  30%   ║
║ LiquidityAgent      │  HOLD  │ 60%  │  20%   ║
║ TapeReadingAgent    │  BUY   │ 82%  │  25%   ║
║ FootprintPattern    │  BUY   │ 68%  │  25%   ║
╟────────────────────┼────────┼──────┼────────╢
║ ML Model            │  BUY   │ 71%  │  40%   ║
║ CONSENSUS           │  BUY   │ 73%  │  ---   ║
╚════════════════════════════════════════════════╝
```

### Alertas Críticos

1. **Divergência Extrema**: Agentes em total desacordo
2. **Confiança Baixa**: Todos os agentes < 50% confiança
3. **Mudança de Regime**: Padrões anormais detectados
4. **Falha de Agente**: Agente não respondendo

## 📊 Backtesting de Agentes

```python
def backtest_agent(agent, historical_data):
    """Testa performance histórica de um agente"""
    
    signals = []
    for timestamp, features in historical_data:
        signal = agent.analyze(features)
        signals.append({
            'time': timestamp,
            'signal': signal,
            'actual': historical_data.get_outcome(timestamp)
        })
    
    # Calcular métricas
    accuracy = calculate_accuracy(signals)
    sharpe = calculate_sharpe(signals)
    drawdown = calculate_max_drawdown(signals)
    
    return {
        'accuracy': accuracy,
        'sharpe': sharpe,
        'max_drawdown': drawdown,
        'total_signals': len(signals)
    }
```

## 🎯 Best Practices

### 1. Diversidade de Agentes
- Cada agente deve ter foco diferente
- Evitar correlação alta entre agentes
- Manter independência de decisão

### 2. Gestão de Confiança
- Nunca forçar trade com baixa confiança
- Usar confiança para sizing de posição
- Monitorar degradação de confiança

### 3. Adaptação Contínua
- Atualizar pesos semanalmente
- Retreinar agentes mensalmente
- Avaliar novos padrões trimestralmente

### 4. Risk Management
- Cada agente tem stop loss próprio
- Consenso inclui avaliação de risco
- Circuit breakers por agente

## 🔬 Pesquisa e Desenvolvimento

### Melhorias Futuras

1. **Deep Learning Agents**: LSTM para sequências
2. **Meta-Learning**: Agente que aprende a ponderar outros
3. **Adversarial Training**: Agente adversário para robustez
4. **Transfer Learning**: Compartilhar conhecimento entre mercados

### Papers de Referência

- "Multi-Agent Reinforcement Learning in Trading" (2023)
- "Hierarchical Decision Making in Financial Markets" (2022)
- "Ensemble Methods for High-Frequency Trading" (2023)

---

**O sistema HMARL representa o estado da arte em trading algorítmico, combinando especialização, adaptação e robustez.**