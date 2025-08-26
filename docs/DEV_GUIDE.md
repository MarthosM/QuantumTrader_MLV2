# 🔧 Developer Guide - QuantumTrader Production v4.1

## Arquitetura e Desenvolvimento do Sistema Híbrido ML + HMARL com Dados Reais

---

## 🆕 Atualizações v4.1 (26/08/2025 - Conexão com Dados Reais)

### 🎯 MUDANÇA CRÍTICA: Implementação de Conexão Real com ProfitDLL

#### ✅ PROBLEMA RESOLVIDO: Sistema Agora Recebe Dados Reais do Mercado!

### 📡 Como Obter Dados Reais do Mercado através da DLL

#### 1. **Arquitetura de Conexão que Funciona**

O sistema DEVE usar a seguinte abordagem (baseada no `book_collector.py` funcional):

```python
# CRÍTICO: Usar ConnectionManagerWorking ao invés de ConnectionManagerV4
from src.connection_manager_working import ConnectionManagerWorking

# Estrutura simplificada que funciona
class TAssetIDRec(Structure):
    _fields_ = [
        ("ticker", c_wchar * 35),
        ("bolsa", c_wchar * 15),
    ]
```

#### 2. **Sequência Correta de Inicialização**

```python
def connect():
    # 1. Carregar DLL
    dll = WinDLL("ProfitDLL64.dll")
    
    # 2. CRIAR CALLBACKS ANTES DO LOGIN (CRÍTICO!)
    callbacks = _create_all_callbacks()
    
    # 3. Usar DLLInitializeLogin com callbacks
    result = dll.DLLInitializeLogin(
        key, user, pwd,
        callbacks['state'],      # stateCallback
        None,                    # historyCallback
        None,                    # orderChangeCallback
        None,                    # accountCallback
        None,                    # accountInfoCallback
        callbacks['daily'],      # newDailyCallback
        callbacks['price_book'], # priceBookCallback
        callbacks['offer_book'], # offerBookCallback
        None,                    # historyTradeCallback
        None,                    # progressCallBack
        callbacks['tiny_book']   # tinyBookCallBack
    )
    
    # 4. Aguardar conexão completa
    wait_for_market_connection()
    
    # 5. Registrar callbacks adicionais APÓS login
    dll.SetNewTradeCallback(callbacks['trade'])
    dll.SetTinyBookCallback(callbacks['tiny_book'])
    dll.SetOfferBookCallbackV2(callbacks['offer_book'])
    dll.SetPriceBookCallback(callbacks['price_book'])
    
    # 6. Subscrever ao símbolo
    dll.SubscribeTicker(c_wchar_p("WDOU25"), c_wchar_p("F"))
    dll.SubscribeOfferBook(c_wchar_p("WDOU25"), c_wchar_p("F"))
    dll.SubscribePriceBook(c_wchar_p("WDOU25"), c_wchar_p("F"))
```

#### 3. **Callbacks Essenciais para Dados Reais**

```python
# TinyBook - Recebe bid/ask básico
@WINFUNCTYPE(None, POINTER(TAssetIDRec), c_double, c_int, c_int)
def tinyBookCallBack(assetId, price, qtd, side):
    # side: 0 = Bid, 1 = Ask
    # price: Preço real (validar > 1000 e < 10000 para WDO)
    if price > 1000 and price < 10000:
        if side == 0:
            self.last_bid = price
        else:
            self.last_ask = price
```

#### 4. **Validação de Dados Reais**

**IMPORTANTE**: Sempre validar que os preços são reais:
- WDO geralmente entre R$ 4000 - R$ 7000
- Rejeitar valores 0.00 ou fora da faixa
- Verificar bid < ask

#### 5. **Problemas Comuns e Soluções**

| Problema | Causa | Solução |
|----------|-------|---------|
| Bid/Ask = 0.00 | Callbacks criados após login | Criar callbacks ANTES do DLLInitializeLogin |
| Sem dados | Método initialize() errado | Usar DLLInitializeLogin, não DLLInitialize |
| Dados não atualizam | Subscrição incorreta | Usar SubscribeTicker + SubscribeOfferBook + SubscribePriceBook |
| ML retorna valores iguais | Sem dados reais | Verificar se bid/ask > 0 antes de processar |

#### 6. **Arquivos Críticos**

- `src/connection_manager_working.py` - Implementação correta da conexão
- `test_book_connection.py` - Script de teste que comprova funcionamento
- `book_collector.py` (projeto antigo) - Referência de implementação funcional

#### 7. **Verificação de Funcionamento**

Para confirmar que está recebendo dados reais:

```python
# Nos logs, procurar por:
"[TINY_BOOK] WDOU25 BID: R$ 5441.50 x 500"  # ✅ Dados reais
"[TINY_BOOK] WDOU25 ASK: R$ 5442.00 x 525"  # ✅ Dados reais

# Evitar:
"Bid: 0.00 Ask: 0.00"  # ❌ Sem dados reais
```

#### 8. **Notas Importantes**

- **NÃO é necessário ter o ProfitChart aberto** - A DLL faz conexão direta com o servidor
- **Servidor de produção**: producao.nelogica.com.br:8184
- **Símbolo atual**: WDOU25 (confirmar mensalmente)
- **Horário de funcionamento**: 9h às 18h (dias úteis)

---

## 🆕 Atualizações v4.0 (20/08/2025 - Sistema Baseado em Regime)

### 🎯 MUDANÇA PRINCIPAL: ML Substituído por Sistema de Regime

1. **🔄 Nova Arquitetura: Regime-Based Trading**
   - **Removido**: Sistema ML defeituoso com 3 camadas
   - **Adicionado**: Detector de regime de mercado determinístico
   - **Estratégias**: Específicas por regime (Tendência vs Lateralização)
   - **HMARL**: Mantido para timing de entrada

2. **📊 Detector de Regime**
   ```python
   # Arquivo: src/trading/regime_based_strategy.py
   
   class MarketRegime(Enum):
       STRONG_UPTREND = "strong_uptrend"    # Tendência forte de alta
       UPTREND = "uptrend"                  # Tendência de alta
       LATERAL = "lateral"                  # Lateralização
       DOWNTREND = "downtrend"              # Tendência de baixa
       STRONG_DOWNTREND = "strong_downtrend" # Tendência forte de baixa
   ```

3. **🎲 Estratégias por Regime**
   - **Tendências**: 
     - Opera a favor da tendência
     - Aguarda pullback para entrada
     - Risk/Reward: 1.5:1
   - **Lateralização**:
     - Opera reversão em suporte/resistência
     - Identifica níveis automaticamente
     - Risk/Reward: 1.0:1 (ajustado para lateral)

4. **🔧 Parâmetros Otimizados (20/08)**
   ```python
   # Detecção de regime
   trend_threshold = 0.0005        # 0.05% para tendência
   strong_trend_threshold = 0.0015 # 0.15% para tendência forte
   lateral_threshold = 0.0002      # 0.02% para lateralização
   
   # Estratégia lateral
   support_resistance_buffer = 0.002  # 0.2% de tolerância
   min_buffer_size = 30               # Reduzido de 50
   ```

5. **📈 Monitores Atualizados**
   - **Monitor Unificado**: `core/monitor_unified_system.py`
   - **Monitor de Regime**: `core/monitor_regime_enhanced.py`
   - **Monitor Enhanced**: `core/monitor_console_enhanced.py` (legado)

---

## 🆕 Atualizações v3.1 (19/08/2025 - Correção ML Predictions Congeladas)

### 🔧 Correção Crítica: ML Predictions Não Atualizando

1. **✅ Problema Identificado e Corrigido**
   - **Sintoma**: Valores ML fixos em 57.2%, 63.9%, 67.2% no monitor
   - **Causa**: Sistema travado/congelado após ~30min de execução
   - **Arquivo**: `ml_status.json` parava de atualizar após algum tempo
   
2. **📊 Correções Implementadas**
   ```python
   # ANTES:
   if self.ml_predictor and len(self.book_buffer) >= 100:  # Requisito muito alto
   
   # DEPOIS:
   if self.ml_predictor and len(self.book_buffer) >= 20:   # Reduzido para 20
   ```

3. **🔄 Melhorias no Sistema ML**
   - Buffer mínimo reduzido de 100 para 20 amostras
   - Contador `_ml_saved_count` incrementado a cada save
   - Timestamp sempre atualizado com `datetime.now().isoformat()`
   - ID único para cada update: `int(time.time() * 1000)`
   - Flush forçado após salvar: `f.flush()`
   - Logs de debug a cada 10 saves

4. **📈 HMARL com Features Reais**
   - Novo método `_generate_hmarl_features()` com 30+ features
   - OrderFlowSpecialist usa order flow imbalance real
   - LiquidityAgent analisa spread e volume ratio do book
   - FootprintPatternAgent usa delta profile e absorption
   - Variação temporal com `sin(time.time())` para evitar valores fixos

5. **🖥️ Monitor Corrigido**
   ```python
   # Conversão automática de valores numéricos
   if isinstance(val, (int, float)):
       if val > 0.3 or val == 1:
           ml_status[key] = 'BUY'
       elif val < -0.3 or val == -1:
           ml_status[key] = 'SELL'
       else:
           ml_status[key] = 'HOLD'
   ```

### Scripts de Diagnóstico Criados

1. **test_ml_updates.py** - Monitora atualizações em tempo real
2. **test_ml_monitor.py** - Verifica status e logs
3. **check_ml_update.py** - Testa se arquivo está sendo atualizado
4. **fix_ml_frozen.py** - Aplica correções automaticamente

### Como Resolver Sistema Travado

```bash
# 1. PARAR todos os processos Python
taskkill /F /IM python.exe

# 2. REINICIAR o sistema
python START_SYSTEM_COMPLETE_OCO_EVENTS.py

# 3. MONITORAR atualizações
python test_ml_updates.py

# 4. VERIFICAR no monitor
python core/monitor_console_enhanced.py
```

### Resultados Esperados Após Correção

✅ **ML Predictions**: Contador incrementando continuamente
✅ **Context/Micro/Meta**: Valores variando com dados do mercado
✅ **Timestamp**: Atualizando a cada predição
✅ **HMARL Agents**: Todos os 4 agentes com valores dinâmicos
✅ **Monitor**: Exibindo valores atualizados em tempo real

---

## 🆕 Atualizações v3.0 (18/08/2025 - Sistema de Otimização Completo)

### 🎯 Sistema de Otimização para Mercados Lateralizados

1. **✅ 7 Novos Módulos de Otimização Implementados**
   - `MarketRegimeDetector` - Detecta regime de mercado (TRENDING/RANGING/VOLATILE)
   - `AdaptiveTargetSystem` - Ajusta stops/takes dinamicamente por regime
   - `ConcordanceFilter` - Só opera quando ML e HMARL concordam
   - `PartialExitManager` - Gerencia saídas parciais escalonadas
   - `TrailingStopManager` - 4 modos de trailing stop adaptativo
   - `RegimeMetricsTracker` - Rastreia performance por regime
   - `OptimizationSystem` - Integração completa de todos módulos

2. **📊 Sistema ML Real Implementado**
   ```python
   # ANTES (simulado):
   ml_signal = random.choice([-1, 0, 1])  # SIMULAÇÃO!
   
   # AGORA (real):
   predictor = HybridMLPredictor()
   features = self._calculate_features_from_buffer()
   result = predictor.predict(features)  # Predição real com 3 camadas
   ```

3. **🔄 Targets Adaptativos por Regime**
   
   | Regime | Stop | Take | R:R | Estratégia |
   |--------|------|------|-----|------------|
   | **RANGING** | 5 pts | 8 pts | 1:1.6 | Scalping rápido |
   | **TRENDING** | 8 pts | 25 pts | 1:3.1 | Deixar correr |
   | **VOLATILE** | 15 pts | 30 pts | 1:2 | Conservador |

4. **🛡️ Filtro de Concordância ML+HMARL**
   - Exige concordância de direção (BUY/SELL)
   - Confiança mínima ML: 60%
   - Confiança mínima HMARL: 55%
   - Confiança combinada: 58%
   - Filtros específicos por regime

5. **📈 Sistema de Saídas Parciais**
   ```python
   # Escalonamento de saídas
   Nível 1: 33% em 5 pontos → Move stop para breakeven
   Nível 2: 33% em 10 pontos → Ativa trailing stop
   Nível 3: 34% em 20 pontos → Saída final
   ```

6. **🔒 Trailing Stop Adaptativo**
   - **AGGRESSIVE**: Para ranging (aperta 20% a cada update)
   - **MODERATE**: Padrão (aperta 10%)
   - **CONSERVATIVE**: Para trending (aperta 5%)
   - **PROTECTIVE**: Para volatilidade (não aperta)

7. **📊 Métricas por Regime de Mercado**
   - Win rate por regime
   - P&L por regime
   - Melhor/pior horário
   - Recomendações automáticas

### Integração Completa no Sistema Principal

```python
# START_SYSTEM_COMPLETE_OCO_EVENTS.py
class QuantumTraderCompleteOCOEvents:
    def __init__(self):
        # Sistema de Otimização integrado
        self.optimization_system = OptimizationSystem({
            'enable_regime_detection': True,
            'enable_adaptive_targets': True,
            'enable_concordance_filter': True,
            'enable_partial_exits': True,
            'enable_trailing_stop': True,
            'enable_metrics_tracking': True
        })
        
        # Preditor ML Real
        self.ml_predictor = HybridMLPredictor()
```

### Fluxo de Execução com Otimização

```
Market Data → Regime Detection
    ↓
ML Prediction (3 layers) + HMARL Consensus
    ↓
Concordance Filter (ML ↔ HMARL agreement)
    ↓
Adaptive Targets (based on regime)
    ↓
OCO Order Execution
    ↓
Partial Exits + Trailing Stop
    ↓
Performance Metrics by Regime
```

---

## 🆕 Atualizações v2.3 (15/08/2025 - 13:30)

### 🔧 Correção Crítica do HMARL

1. **✅ HMARL Agents Funcionando Corretamente**
   - Corrigido erro: `'HMARLAgentsRealtime' object has no attribute 'get_signals'`
   - Método correto: usar `update_market_data()` seguido de `get_consensus()`
   - Arquivo `hmarl_status.json` sendo atualizado em tempo real
   - Monitor exibe dados atualizados dos 4 agentes

2. **📊 Integração HMARL Corrigida**
   ```python
   # ANTES (incorreto):
   signals = self.hmarl_agents.get_signals(market_data)  # Método não existe!
   consensus = self.hmarl_agents.get_consensus(signals)
   
   # DEPOIS (correto):
   self.hmarl_agents.update_market_data(price, volume, book_data)
   consensus = self.hmarl_agents.get_consensus()  # Calcula sinais internamente
   ```

3. **🔄 Thread de Limpeza de Ordens Órfãs**
   - Nova thread dedicada: `cleanup_orphan_orders_loop()`
   - Verifica a cada 5 segundos por ordens pendentes sem posição
   - Cancela automaticamente ordens órfãs detectadas
   - Corrige inconsistências entre lock global e posição local

### Sistema de Lock Global para Controle de Posição

1. **🔐 Variável Global GLOBAL_POSITION_LOCK**
   - Controle absoluto de posição única via lock global
   - Thread-safe com `GLOBAL_POSITION_LOCK_MUTEX`
   - Bloqueio mínimo de 30 segundos (configurável)
   - Detecção automática de inconsistências

2. **🚫 Cancelamento Agressivo de Ordens**
   - Ao fechar posição, cancela TODAS ordens pendentes
   - Duplo cancelamento para garantir limpeza
   - Callback automático do OCO Monitor
   - Reset completo do estado do sistema

3. **🔍 Verificação de Consistência**
   - Checagem periódica a cada 5 segundos (melhorado de 10s)
   - Detecção de lock sem posição (inconsistência)
   - Auto-correção após 30 segundos de inconsistência (melhorado de 60s)
   - Logs detalhados para debugging com prefixo [CLEANUP]

### Implementação do Lock Global

```python
# Variáveis globais (topo do arquivo)
GLOBAL_POSITION_LOCK = False
GLOBAL_POSITION_LOCK_TIME = None
GLOBAL_POSITION_LOCK_MUTEX = threading.Lock()

# Verificação antes de trade
with GLOBAL_POSITION_LOCK_MUTEX:
    if GLOBAL_POSITION_LOCK:
        return False  # Bloqueia novo trade

# Ao abrir posição
with GLOBAL_POSITION_LOCK_MUTEX:
    GLOBAL_POSITION_LOCK = True
    GLOBAL_POSITION_LOCK_TIME = datetime.now()

# Ao fechar posição
with GLOBAL_POSITION_LOCK_MUTEX:
    GLOBAL_POSITION_LOCK = False
    GLOBAL_POSITION_LOCK_TIME = None
```

---

## 🆕 Atualizações v2.1 (14/08/2025)

### Melhorias Críticas Implementadas

1. **🔒 Controle de Posição Única Robusto**
   - Sistema impede múltiplas posições simultâneas
   - Bloqueio de 30 segundos após abrir posição
   - Tempo mínimo de 60 segundos entre trades
   - Registro de tempo de abertura (`position_open_time`)

2. **📊 Sistema 100% Dados Reais**
   - Removidos TODOS os dados simulados
   - Sistema aguarda dados reais ou não opera
   - Aborta trades sem preço real do mercado
   - Captura de preços via callbacks da DLL

3. **💰 Correção de Preços de Mercado**
   - `ConnectionManagerWorking` captura `last_price`, `best_bid`, `best_ask`
   - Prioridade: preço real > média bid/ask > último conhecido
   - Trade abortado se preço < 1000 (validação WDO)

4. **📈 Monitor HMARL/ML Dinâmico**
   - `HMARLMonitorBridge` atualiza em tempo real
   - Arquivos JSON para comunicação entre processos
   - Visualização clara de sinais e confiança

5. **⚙️ Sistema de Risco Dinâmico**
   - Stop/Take ajustados por tipo de trade
   - Scalping: 5-10 pontos
   - Híbrido: 10-20 pontos
   - Swing: 20-30 pontos

---

## 🏗️ Novos Módulos de Otimização v3.0

### 1. MarketRegimeDetector (`src/trading/market_regime_detector.py`)

```python
class MarketRegimeDetector:
    """Detecta regime atual: TRENDING_UP, TRENDING_DOWN, RANGING, VOLATILE"""
    
    def update(self, price, high, low, volume) -> Dict:
        # Analisa:
        # - ATR (Average True Range)
        # - Força direcional (regressão linear)
        # - Score de lateralização
        # - Volatilidade normalizada
        # - Consistência de tendência
        return {
            'regime': 'RANGING',  # ou TRENDING_UP, etc
            'confidence': 0.75,
            'recommendations': {
                'stop_loss': 5,     # pts para ranging
                'take_profit': 8,   # pts para ranging
            }
        }
```

### 2. AdaptiveTargetSystem (`src/trading/adaptive_targets.py`)

```python
class AdaptiveTargetSystem:
    """Ajusta stops/takes baseado no regime"""
    
    regime_configs = {
        'RANGING': {
            'stop_loss': 5,      # Stop apertado
            'take_profit': 8,    # Alvo pequeno (scalping)
            'position_multiplier': 0.8  # Posição menor
        },
        'TRENDING_UP': {
            'stop_loss': 8,      # Stop normal
            'take_profit': 25,   # Deixar correr
            'position_multiplier': 1.2  # Posição maior
        }
    }
```

### 3. ConcordanceFilter (`src/trading/concordance_filter.py`)

```python
class ConcordanceFilter:
    """Filtro de concordância ML+HMARL"""
    
    def check_concordance(ml_pred, hmarl_cons, regime) -> Tuple[bool, Dict]:
        # Verifica:
        # 1. ML confidence >= 60%
        # 2. HMARL confidence >= 55%
        # 3. Mesma direção (BUY/SELL)
        # 4. Regime favorável
        # 5. Combined confidence >= 58%
        
        if not all_checks_pass:
            return False, {'filters_failed': ['low_confidence']}
        
        return True, {'approved': True}
```

### 4. HybridMLPredictor (`src/ml/hybrid_predictor.py`)

```python
class HybridMLPredictor:
    """Sistema ML real de 3 camadas"""
    
    def predict(self, features: Dict) -> Dict:
        # Layer 1: Context (regime, volatility, session)
        context_pred = self._predict_context(features)
        
        # Layer 2: Microstructure (order flow, book dynamics)
        micro_pred = self._predict_microstructure(features)
        
        # Layer 3: Meta-Learner (combina tudo)
        final_pred = self._predict_meta(context_pred, micro_pred)
        
        return {
            'signal': -1/0/1,
            'confidence': 0.75,
            'ml_data': {...}
        }
```

## 📐 Arquitetura do Sistema v3.0

### Visão Geral da Arquitetura Híbrida com Otimização

```
┌─────────────────────────────────────────────────────────┐
│                   ProfitDLL Interface                    │
│              (Callbacks & Real-time Data)                │
└─────────────────┬───────────────┬───────────────────────┘
                  │               │
            Book Data         Tick Data
                  │               │
                  ▼               ▼
┌─────────────────────────────────────────────────────────┐
│              Circular Buffers (Thread-Safe)             │
│  ┌──────────────────┐  ┌──────────────────────────┐   │
│  │  BookBuffer(100)  │  │    TradeBuffer(1000)     │   │
│  └──────────────────┘  └──────────────────────────┘   │
└─────────────────┬───────────────┬───────────────────────┘
                  │               │
                  ▼               ▼
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
│                   ┌──────────────┐                      │
│                   │   Temporal   │                      │
│                   │      (6)     │                      │
│                   └──────────────┘                      │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│           3-Layer Hybrid ML System (60%)                │
│  ┌────────────────────────────────────────────────┐    │
│  │  Layer 1: Context Analysis (Tick Data)         │    │
│  │  - Regime Detector (73% acc)                   │    │
│  │  - Volatility Forecaster (74% acc)             │    │
│  │  - Session Classifier (74% acc)                │    │
│  └────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────┐    │
│  │  Layer 2: Microstructure (Book Data)           │    │
│  │  - Order Flow Analyzer (95% acc)               │    │
│  │  - Book Dynamics Model (90% acc)               │    │
│  └────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────┐    │
│  │  Layer 3: Meta-Learner (Final Decision)        │    │
│  │  - Combines all predictions (94% acc)          │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│              HMARL Agents System (40%)                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  • OrderFlowSpecialist (30% weight)              │  │
│  │  • LiquidityAgent (20% weight)                   │  │
│  │  • TapeReadingAgent (25% weight)                 │  │
│  │  • FootprintPatternAgent (25% weight)            │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│          Consensus System (60% ML + 40% HMARL)          │
│            Adaptive Weighted Voting + Risk              │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│             Order Management with OCO                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │  ConnectionManagerOCO (if USE_OCO_ORDERS=true)   │  │
│  │  • Main Order (Entry)                            │  │
│  │  • Stop Loss Order (Automatic)                   │  │
│  │  • Take Profit Order (Automatic)                 │  │
│  │  • One-Cancels-Other Logic                       │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 🔄 Fluxo de Dados v2.0

### 1. Entrada de Dados (ProfitDLL Callbacks)

```python
# src/connection_manager_working.py
class ConnectionManagerWorking:
    def __init__(self, dll_path):
        self.dll = None
        self.bMarketConnected = False
        self.bBrokerConnected = False
        
    def initialize(self, key, username, password):
        # Login com callbacks configurados
        result = self.dll.DLLInitializeLogin(
            key, username, password,
            stateCallback, historyCallback, ...
        )
        
    # Callbacks para book e trades
    def tinyBookCallBack(assetId, price, qtd, side):
        # Processa book simplificado
        
    def tradeCallback(assetId, date, price, volume, ...):
        # Processa trades/ticks
```

### 2. Sistema de 3 Camadas ML

```python
# START_HYBRID_COMPLETE.py
class HybridCompleteSystem:
    def load_hybrid_models(self):
        # Layer 1: Context (Tick Data)
        self.context_models = {
            'regime': load_model('regime_detector.pkl'),
            'volatility': load_model('volatility_forecaster.pkl'),
            'session': load_model('session_classifier.pkl')
        }
        
        # Layer 2: Microstructure (Book Data)
        self.micro_models = {
            'order_flow': load_model('order_flow_analyzer.pkl'),
            'book_dynamics': load_model('book_dynamics.pkl')
        }
        
        # Layer 3: Meta-Learner
        self.meta_learner = load_model('meta_learner.pkl')
```

## 🔒 Controle de Posição Única (NOVO v2.1)

### Sistema Anti-Múltiplas Posições

```python
# START_SYSTEM_COMPLETE_OCO.py
class QuantumTraderCompleteOCO:
    def __init__(self):
        # Controle robusto de posição
        self.has_open_position = False
        self.position_open_time = None  # Timestamp de abertura
        self.min_position_hold_time = 30  # Mínimo 30s com posição
        self.min_time_between_trades = 60  # 60s entre trades
```

### Fluxo de Controle

```
Sinal de Trade
    ↓
Verifica has_open_position
    ├─ True → Verifica tempo com posição
    │         ├─ < 30s → BLOQUEIA (muito recente)
    │         └─ ≥ 30s → BLOQUEIA (posição aberta)
    └─ False → Verifica tempo desde último trade
              ├─ < 60s → BLOQUEIA (aguardar)
              └─ ≥ 60s → PERMITE TRADE
```

### Implementação

```python
def execute_trade_with_oco(self, signal, confidence):
    # VERIFICAÇÃO 1: Posição aberta
    if self.has_open_position:
        if self.position_open_time:
            time_with_position = (datetime.now() - self.position_open_time).total_seconds()
            if time_with_position < self.min_position_hold_time:
                logger.debug(f"[BLOQUEADO] Posição recente ({time_with_position:.0f}s)")
                return False
        logger.debug("[BLOQUEADO] Posição aberta")
        return False
    
    # VERIFICAÇÃO 2: Tempo entre trades
    if self.last_trade_time:
        time_since = (datetime.now() - self.last_trade_time).total_seconds()
        if time_since < self.min_time_between_trades:
            logger.debug(f"[BLOQUEADO] Aguardar {60-time_since:.0f}s")
            return False
    
    # ... enviar ordem ...
    
    # Marcar posição aberta
    self.has_open_position = True
    self.position_open_time = datetime.now()
    logger.warning("[POSIÇÃO ABERTA] Bloqueando por 30s")
```

## 🔐 Ordens OCO (One-Cancels-Other) - ATUALIZADO

### Arquitetura OCO v2.0

```python
# src/connection_manager_oco.py
class ConnectionManagerOCO(ConnectionManagerWorking):
    """Extensão com suporte a ordens bracket"""
    
    def send_order_with_bracket(self, symbol, side, quantity, 
                               entry_price, stop_price, take_price):
        """
        Envia 3 ordens automaticamente:
        1. Ordem Principal (MERCADO para execução imediata)
        2. Stop Loss (proteção com slippage)
        3. Take Profit (alvo)
        
        Quando stop OU take é executado, o outro é cancelado
        """
        
        # 1. Enviar ordem principal (MERCADO)
        if side == "BUY":
            main_order_id = self.dll.SendBuyOrder(price=0)  # 0 = mercado
        else:
            main_order_id = self.dll.SendSellOrder(price=0)
        
        # 2. Enviar Stop Loss (com slippage de 20 pontos)
        if side == "BUY":
            # Stop sell para posição comprada
            stop_order_id = self.dll.SendStopSellOrder(
                price_limit=stop_price - 20,  # Slippage
                stop_trigger=stop_price        # Trigger
            )
        else:
            # Stop buy para posição vendida
            stop_order_id = self.dll.SendStopBuyOrder(
                price_limit=stop_price + 20,  # Slippage
                stop_trigger=stop_price        # Trigger
            )
        
        # 3. Enviar Take Profit (ordem limite)
        if side == "BUY":
            take_order_id = self.dll.SendSellOrder(price=take_price)
        else:
            take_order_id = self.dll.SendBuyOrder(price=take_price)
        
        # 4. OCO Monitor (rastreia e cancela órfãs)
        self.oco_monitor.register_oco_group(main_order_id, 
                                           stop_order_id, 
                                           take_order_id)
```

### Configuração OCO Atualizada

```env
# .env.production (AJUSTADO PARA WDO)
USE_OCO_ORDERS=true      # Ativar ordens OCO
ENABLE_TRADING=true      # Trading real
STOP_LOSS=0.002          # Stop de 0.2% (~10-15 pontos WDO)
TAKE_PROFIT=0.004        # Take de 0.4% (~20-30 pontos WDO)
STOP_SLIPPAGE=20         # Slippage máximo em pontos
```

### Vantagens das Ordens OCO

1. **Executadas pela bolsa** - Não dependem do sistema
2. **Mais rápidas** - Execução imediata quando preço é atingido
3. **Mais seguras** - Funcionam mesmo se sistema desconectar
4. **Automáticas** - Uma ordem cancela a outra automaticamente

## 🎯 Sistema de Risco Dinâmico (NOVO)

### DynamicRiskCalculator

```python
# src/trading/dynamic_risk_calculator.py
class DynamicRiskCalculator:
    """Calcula stops/takes dinâmicos baseados no contexto"""
    
    def calculate_dynamic_levels(self, current_price, signal, 
                                confidence, signal_source):
        """
        Ajusta stop/take baseado em:
        - Tipo de trade (scalping/swing/híbrido)
        - Volatilidade atual do mercado
        - Confiança do sinal
        - Horário do pregão
        """
        
        # Determinar tipo baseado na origem
        if signal_source['microstructure_weight'] > 0.7:
            trade_type = 'scalping'  # 5-15 pts stop, 10-30 pts take
        elif signal_source['context_weight'] > 0.7:
            trade_type = 'swing'     # 15-50 pts stop, 30-100 pts take
        else:
            trade_type = 'hybrid'    # 10-30 pts stop, 20-60 pts take
        
        # Calcular volatilidade
        volatility = self.calculate_volatility()
        
        # Ajustar por volatilidade e confiança
        stop_points = base_stop * volatility_factor * (2 - confidence)
        take_points = base_take * volatility_factor * confidence
        
        return {
            'stop_price': stop_price,
            'take_price': take_price,
            'trade_type': trade_type,
            'risk_reward_ratio': take_points / stop_points
        }
```

### Tipos de Trade e Distâncias (ATUALIZADO)

| Tipo | Origem | Stop (pts) | Take (pts) | R:R |
|------|--------|-----------|------------|-----|
| **Scalping** | Book/Microestrutura | 5-10 | 5-10 | 1:1-1:2 |
| **Hybrid** | Misto ML+HMARL | 7-15 | 10-20 | 1:1.5-1:2 |
| **Swing** | ML/Contexto | 10-20 | 20-30 | 1:2-1:3 |

### Integração no Sistema

```python
# START_SYSTEM_COMPLETE_OCO.py
class QuantumTraderCompleteOCO:
    def __init__(self):
        self.risk_calculator = DynamicRiskCalculator()
        
    def execute_trade_with_oco(self, signal, confidence):
        # Calcular níveis dinâmicos
        risk_levels = self.risk_calculator.calculate_dynamic_levels(
            current_price=self.current_price,
            signal=signal,
            confidence=confidence,
            signal_source={
                'microstructure_weight': self._last_micro_conf,
                'context_weight': self._last_context_conf
            }
        )
        
        stop_price = risk_levels['stop_price']
        take_price = risk_levels['take_price']
        
        logger.info(f"[DYNAMIC RISK] {risk_levels['trade_type']}")
        logger.info(f"  Risk/Reward: 1:{risk_levels['risk_reward_ratio']:.1f}")
```

## 🖥️ GUI Trading System

### Arquitetura da Interface

```python
# gui_trading_system.py
class TradingSystemGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.system_process = None  # Processo do START_HYBRID_COMPLETE.py
        
    def start_system(self):
        # Inicia sistema em processo separado
        cmd = [sys.executable, "START_HYBRID_COMPLETE.py"]
        self.system_process = subprocess.Popen(cmd, 
                                              stdout=subprocess.PIPE)
        
    def process_system_output(self, line):
        # Processa outputs do sistema
        # Compatível com formato do START_HYBRID_COMPLETE.py
```

### Componentes da GUI

```
┌─────────────────────────────────────────────────────┐
│                    HEADER                           │
│         QuantumTrader v2.0 | Status: ONLINE        │
├──────────────┬─────────────────────┬───────────────┤
│   CONTROLES  │      MÉTRICAS       │     LOGS      │
│              │                     │               │
│ [✓] Trading  │  Preço: 5400.0     │ [INFO] ...    │
│ [✓] OCO      │  P&L: +R$120       │ [OK] ...      │
│ Conf: 60%    │  Win: 65%          │ [TRADE] ...   │
│              │                     │               │
│ [▶ INICIAR]  │  ┌──────────────┐  │               │
│ [■ PARAR]    │  │   📈 Gráfico  │  │               │
│              │  └──────────────┘  │               │
├──────────────┴─────────────────────┴───────────────┤
│              ORDENS ATIVAS (OCO)                    │
│  • Main: #123 | Stop: #124 | Take: #125            │
└─────────────────────────────────────────────────────┘
```

### Processamento de Outputs

```python
def process_system_output(self, line):
    # Conexões
    if "CONECTADO À B3" in line:
        self.metrics['market_connected'] = True
        
    # Ordens OCO
    elif "Usando ordens OCO" in line:
        self.metrics['oco_enabled'] = True
        
    # Predições ML
    elif "[ML Meta] Signal:" in line:
        # Parse: [ML Meta] Signal: 1 | Conf: 0.65
        conf = float(line.split("Conf:")[-1])
        self.metrics['ml_prediction'] = conf
        
    # HMARL
    elif "[HMARL] Signal:" in line:
        # Parse: [HMARL] Signal: 0.456 | Conf: 0.678
        conf = float(line.split("Conf:")[-1])
        self.metrics['hmarl_consensus'] = conf
```

## 🔄 Sistema de Re-treinamento Automático

### SmartRetrainingSystem

```python
# src/training/smart_retraining_system.py
class SmartRetrainingSystem:
    def __init__(self):
        self.training_hour = 18  # Após fechamento
        self.training_minute = 40
        self.min_hours = 8.0     # Mínimo de dados
        self.min_samples = 5000
        
    def validate_data_for_training(self, df):
        # Validações rigorosas
        checks = {
            'samples': len(df) >= self.min_samples,
            'hours': self._check_continuous_hours(df),
            'variance': df['price'].std() > 0,
            'balance': self._check_class_balance(df),
            'trading_hours': self._check_trading_hours_only(df)
        }
        return all(checks.values())
```

### ModelSelector

```python
# src/training/model_selector.py
class ModelSelector:
    def get_current_best_model(self):
        """Seleciona melhor modelo disponível"""
        models = self._list_available_models()
        
        for model_info in models:
            # 1. Modelos re-treinados recentes (< 7 dias)
            if model_info['is_retrained'] and model_info['age_days'] < 7:
                score = self._evaluate_model(model_info['path'])
                model_info['score'] = score
        
        # 2. Retorna modelo com melhor score
        return max(models, key=lambda x: x['score'])
```

### Fluxo de Re-treinamento

```
18:00 → Mercado fecha
18:40 → SmartRetrainingSystem inicia
   ↓
Valida dados coletados durante o dia
   ↓
Se válido → Treina novos modelos
   ↓  
ModelSelector avalia performance
   ↓
Se melhor → Substitui modelos em produção
Se pior → Mantém modelos atuais
```

## 🎯 Política de Dados Reais (CRÍTICO v2.1)

### Sistema 100% Dados Reais

```python
# NUNCA usar dados simulados
# START_SYSTEM_COMPLETE_OCO.py

def data_collection_loop(self):
    # PRIORIDADE 1: Preço real da conexão
    if self.connection.last_price > 0:
        current_price = self.connection.last_price
        logger.info(f"[REAL PRICE] R$ {current_price:.2f}")
    
    # PRIORIDADE 2: Book real
    elif self.connection.best_bid > 0 and self.connection.best_ask > 0:
        current_price = (self.connection.best_bid + self.connection.best_ask) / 2
    
    # SEM DADOS = SEM OPERAÇÃO
    else:
        logger.info("[WAITING] Aguardando dados reais...")
        return  # NÃO OPERA
```

### Verificações Obrigatórias

```python
def execute_trade_with_oco(self, signal, confidence):
    # Obter preço REAL
    if self.connection.last_price > 0:
        current_price = self.connection.last_price
    else:
        logger.error("[ERRO] Sem preço real! Abortando.")
        return False  # ABORTA SEM PREÇO REAL
```

### ConnectionManagerWorking - Captura de Preços

```python
# src/connection_manager_working.py
def tinyBookCallBack(assetId, price, qtd, side):
    # Atualizar preços reais
    if side == 0:  # Bid
        self.best_bid = float(price)
    else:  # Ask
        self.best_ask = float(price)
    
    # Atualizar preço médio
    if self.best_bid > 0 and self.best_ask > 0:
        self.last_price = (self.best_bid + self.best_ask) / 2.0

def tradeCallback(price, volume):
    # Atualizar último preço negociado
    self.last_price = float(price)
```

## 💻 Estrutura de Código v2.0

### Módulos Principais

```
src/
├── connection_manager_working.py  # Conexão funcional com B3
├── connection_manager_oco.py      # Extensão para ordens OCO
├── START_HYBRID_COMPLETE.py       # Sistema principal v2.0
├── gui_trading_system.py          # Interface gráfica
│
├── features/
│   └── book_features_rt.py       # 65 features em real-time
│
├── training/
│   ├── smart_retraining_system.py # Re-treinamento automático
│   └── model_selector.py          # Seleção de modelos
│
├── agents/
│   └── hmarl_agents_realtime.py  # 4 agentes HMARL
│
├── consensus/
│   └── hmarl_consensus_system.py # Sistema de consenso
│
└── trading/
    ├── order_manager.py          # Gestão de ordens
    └── profit_order_sender.py    # Ordens OCO via ProfitDLL
```

### Configurações de Produção

```env
# .env.production
# === TRADING ===
ENABLE_TRADING=true          # Trading real ativado
USE_OCO_ORDERS=true         # Ordens OCO automáticas
MIN_CONFIDENCE=0.60         # Confiança mínima

# === CONEXÃO B3 ===
PROFIT_USERNAME=29936354842 # CPF para login
PROFIT_PASSWORD=Ultra3376!  # Senha do ProfitChart
PROFIT_BROKER_ID=33005      # ID da corretora
PROFIT_ACCOUNT_ID=70562000  # Conta de trading
PROFIT_ROUTING_PASSWORD=Ultra3376!  # Senha roteamento

# === RISK MANAGEMENT (ATUALIZADO) ===
STOP_LOSS=0.002             # Stop de 0.2% (~10-15 pontos WDO)
TAKE_PROFIT=0.004           # Take de 0.4% (~20-30 pontos WDO) 
MAX_DAILY_TRADES=10         # Limite diário
MIN_CONFIDENCE=0.65         # Confiança mínima (aumentada)
MIN_TIME_BETWEEN_TRADES=60  # Segundos entre trades
```

## 🔬 Testing v2.1

### Testes de Controle de Posição

```python
# tests/test_position_control.py
def test_no_multiple_positions():
    system = QuantumTraderCompleteOCO()
    
    # Abrir primeira posição
    system.has_open_position = True
    system.position_open_time = datetime.now()
    
    # Tentar abrir segunda (deve bloquear)
    result = system.execute_trade_with_oco(signal=1, confidence=0.7)
    assert result == False  # Bloqueado!
    
    # Aguardar 30s
    time.sleep(31)
    
    # Ainda deve bloquear (posição aberta)
    result = system.execute_trade_with_oco(signal=1, confidence=0.7)
    assert result == False
```

### Testes de Preços Reais

```python
# tests/test_real_prices.py
def test_real_price_capture():
    connection = ConnectionManagerWorking()
    connection.initialize()
    
    # Aguardar callbacks
    time.sleep(5)
    
    # Verificar preços
    assert connection.last_price > 0
    assert connection.best_bid > 0
    assert connection.best_ask > 0
    
    print(f"Preço real: R$ {connection.last_price:.2f}")
```

## 🔬 Testing v2.0

### Testes de Ordens OCO

```python
# tests/test_oco_orders.py
def test_send_order_with_bracket():
    connection = ConnectionManagerOCO()
    result = connection.send_order_with_bracket(
        symbol="WDOU25",
        side="BUY", 
        quantity=1,
        entry_price=5400.0,
        stop_price=5395.0,   # -5 pontos
        take_price=5410.0    # +10 pontos
    )
    
    assert 'main_order' in result
    assert 'stop_order' in result
    assert 'take_order' in result
```

### Testes de GUI

```python
# tests/test_gui.py
def test_gui_process_output():
    gui = TradingSystemGUI()
    
    # Testar parsing de outputs
    gui.process_system_output("[OK] CONECTADO À B3!")
    assert gui.metrics['market_connected'] == True
    
    gui.process_system_output("[CONFIG] Usando ordens OCO")
    assert gui.metrics['oco_enabled'] == True
```

### Testes de Re-treinamento

```python
# tests/test_retraining.py
def test_validate_training_data():
    system = SmartRetrainingSystem()
    
    # Dados válidos
    df_valid = create_valid_training_data()
    assert system.validate_data_for_training(df_valid) == True
    
    # Dados insuficientes
    df_invalid = create_insufficient_data()
    assert system.validate_data_for_training(df_invalid) == False
```

## 🚀 Deployment v2.1

### Checklist de Produção

- [x] Modelos híbridos treinados (3 camadas)
- [x] Configuração .env.production revisada
- [x] BrokerID e AccountID corretos
- [x] GUI testada e funcional
- [x] Ordens OCO configuradas
- [x] Re-treinamento agendado (18:40)
- [x] Backup automático habilitado
- [x] ProfitChart conectado
- [x] **Controle de posição única ativo**
- [x] **Sistema usando apenas dados reais**
- [x] **Preços reais validados**

### Comandos de Inicialização

```bash
# Treinar modelos iniciais
python train_hybrid_pipeline.py

# Iniciar com GUI
START_GUI.bat

# Iniciar direto (sem GUI)
python START_HYBRID_COMPLETE.py

# Com opções
python start_hybrid_system.py --dashboard  # Com dashboard web
python start_hybrid_system.py --test      # Modo teste
python start_hybrid_system.py --no-training  # Sem re-treinamento
```

### Monitoramento

```python
# Métricas críticas
- Latência features: < 2ms (atual) / < 10ms (máx)
- ML Accuracy: > 90% (microstructure)
- HMARL Confidence: > 60%
- Win Rate: > 55%
- Drawdown: < 10%
- Orders OCO: 100% (se ativado)
```

## 🔒 Controles de Posição e Proteções (ATUALIZADO)

### Sistema de Controle de Posição Única

```python
# START_SYSTEM_COMPLETE_OCO.py
class QuantumTraderCompleteOCO:
    def __init__(self):
        # Controle de posição
        self.has_open_position = False
        self.active_orders = {}
        
        # Controle de tempo
        self.last_trade_time = None
        self.min_time_between_trades = 60  # segundos
        
    def execute_trade_with_oco(self, signal, confidence):
        # 1. Verificar posição aberta
        if self.has_open_position or len(self.active_orders) > 0:
            logger.debug("[BLOQUEADO] Posição aberta")
            return False
            
        # 2. Verificar tempo mínimo
        if self.last_trade_time:
            time_since = (datetime.now() - self.last_trade_time).seconds
            if time_since < self.min_time_between_trades:
                logger.debug(f"[BLOQUEADO] Aguardar {60-time_since}s")
                return False
        
        # 3. Verificar limite diário
        if self.metrics['trades_today'] >= self.max_daily_trades:
            logger.warning("[LIMITE] Máximo de trades atingido")
            return False
```

### Frequência de Sinais Controlada

```python
# Redução drástica de sinais de teste
test_chance = 0.001  # 0.1% (era 2%)

# Confiança mínima aumentada
MIN_CONFIDENCE = 0.65  # 65% (era 60%)

# Máximo de trades por dia
MAX_DAILY_TRADES = 10  # (era 50)
```

## 📊 Otimização v2.0

### Performance com OCO

```python
# Sem OCO (stop/take manual)
- Latência ordem: ~100ms
- Risco de não executar: Alto
- Dependência do sistema: Total

# Com OCO (stop/take automático)
- Latência ordem: ~10ms
- Risco de não executar: Baixo
- Dependência do sistema: Mínima
```

### Otimizações da GUI

```python
# Processar outputs em thread separada
threading.Thread(target=self.read_system_output, daemon=True).start()

# Atualizar GUI a cada segundo apenas
self.root.after(1000, self.update_gui)

# Limitar histórico de preços
self.price_history = deque(maxlen=100)
```

## 🔐 Segurança v2.0

### Proteção de Credenciais

```python
# NUNCA fazer commit de:
- .env.production (com senhas reais)
- AccountID/BrokerID de produção
- Logs com informações sensíveis

# SEMPRE usar:
- Variáveis de ambiente
- Arquivos .gitignore
- Logs sanitizados
```

### Trading Seguro

```python
# Confirmações obrigatórias
if self.enable_trading.get():
    result = messagebox.askyesno(
        "Confirmar Trading Real",
        "Ordens serão enviadas REALMENTE ao mercado!\nContinuar?"
    )
```

## 🛠️ Troubleshooting v2.3

### Problema: HMARL mostrando "Dados muito antigos"

```python
# Causa:
- Arquivo hmarl_status.json não sendo atualizado
- Método get_signals() não existe em HMARLAgentsRealtime

# Solução implementada:
1. Usar update_market_data() + get_consensus()
2. Verificar atualização: cat data/monitor/hmarl_status.json
3. Timestamp deve ser recente (< 30s)

# Teste rápido:
python -c "
from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
from src.monitoring.hmarl_monitor_bridge import get_bridge
agents = HMARLAgentsRealtime()
agents.update_market_data(price=5500, volume=100, 
                         book_data={'spread': 5, 'imbalance': 0.1})
consensus = agents.get_consensus()
print(f'HMARL: {consensus[\"action\"]} @ {consensus[\"confidence\"]:.1%}')
"
```

### Problema: Múltiplas posições simultâneas

```python
# Verificar:
1. GLOBAL_POSITION_LOCK está funcionando
2. Thread cleanup_orphan_orders_loop está rodando
3. active_orders sendo limpo corretamente

# Solução v2.3:
- Lock global com mutex thread-safe
- Thread de limpeza a cada 5 segundos
- Logs com prefixo [GLOBAL LOCK] e [CLEANUP]
```

### Problema: Sistema usando preços simulados

```python
# Verificar:
1. connection.last_price > 0
2. ProfitChart está conectado e transmitindo
3. Callbacks estão sendo recebidos

# Solução:
- Sistema agora ABORTA se não tem preço real
- Verificar logs: "[REAL PRICE] R$ XXXX.XX"
- Testar: python test_real_prices.py
```

### Problema: Ordens órfãs após fechar posição

```python
# Verificar logs v2.3:
"[CLEANUP] Detectadas X ordens órfãs sem posição"
"[CLEANUP] Cancelando todas ordens órfãs..."
"[CLEANUP] Ordens órfãs canceladas e estado limpo"

# Solução automática:
- Thread cleanup_orphan_orders_loop() verifica a cada 5s
- Cancela órfãs automaticamente
- OCO Monitor com callback de posição fechada
```

## 🛠️ Troubleshooting v2.0

### Problema: Ordens OCO não funcionam

```python
# Verificar:
1. USE_OCO_ORDERS=true no .env
2. Broker suporta OCO (verificar logs)
3. DLL tem funções SendBuyStopOrder/SendSellStopOrder

# Solução:
- Desativar OCO e usar stop/take manual
- USE_OCO_ORDERS=false
```

### Problema: GUI não conecta

```python
# Verificar:
1. START_HYBRID_COMPLETE.py funciona sozinho
2. Python tem tkinter instalado
3. Outputs estão no formato esperado

# Debug:
python test_gui.py  # Teste básico
```

### Problema: Re-treinamento falha

```python
# Verificar logs em:
logs/smart_retraining_*.log

# Causas comuns:
- Dados insuficientes (< 8h)
- Mercado fechou cedo
- Classes desbalanceadas

# Forçar re-treinamento:
python train_hybrid_pipeline.py
```

### Problema: AccountID/BrokerID incorretos

```python
# Erro: -2147483645 (NL_INVALID_ARGS)

# Solução:
PROFIT_BROKER_ID=33005      # Correto
PROFIT_ACCOUNT_ID=70562000  # Usar conta, não CPF
```

## 📚 Recursos v2.0

### Documentação

- [GUI_MANUAL.md](GUI_MANUAL.md) - Manual da interface gráfica
- [HMARL_GUIDE.md](HMARL_GUIDE.md) - Sistema HMARL detalhado
- [README.md](../README.md) - Visão geral
- [CLAUDE.md](../CLAUDE.md) - Instruções para IA

### Arquivos Críticos

```python
# Sistema principal
START_HYBRID_COMPLETE.py      # Main v2.0
gui_trading_system.py         # Interface

# Conexão
src/connection_manager_working.py  # B3 funcional
src/connection_manager_oco.py      # Ordens OCO

# ML/HMARL
models/hybrid/                 # Modelos 3 camadas
src/agents/hmarl_agents_realtime.py  # Agentes

# Configuração
.env.production               # Config produção
```

### Comandos Úteis

```bash
# Ver status do projeto
python view_project_board.py

# Testar conexão
python test_final_order.py

# Verificar modelos
python test_model_selection.py

# Forçar re-treinamento
python -c "from src.training.smart_retraining_system import SmartRetrainingSystem; s = SmartRetrainingSystem(min_hours=0.1); s.run_retraining_pipeline(force=True)"
```

## 📝 Comandos Rápidos v2.3

### Sistema Principal
```bash
# Iniciar sistema completo com OCO e HMARL corrigido
python START_SYSTEM_COMPLETE_OCO.py

# Parar sistema
Ctrl+C
```

### Testes Importantes
```bash
# Testar HMARL (NOVO)
python -c "
from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
agents = HMARLAgentsRealtime()
agents.update_market_data(5500, 100, {'spread': 5, 'imbalance': 0.1})
print(agents.get_consensus())
"

# Verificar arquivo HMARL sendo atualizado
powershell -Command "Get-Item 'data\monitor\hmarl_status.json' | Select Name, LastWriteTime"

# Testar controle de posição única
python test_position_control.py

# Verificar captura de preços reais
python test_real_prices.py

# Testar envio de ordem simples
python test_final_order.py
```

### Monitoramento
```bash
# Monitor visual em tempo real
python core/monitor_console_enhanced.py

# Ver status do projeto
python view_project_board.py --detailed

# Verificar logs de limpeza (NOVO)
grep "[CLEANUP]" logs/hybrid_complete_*.log | tail -20

# Verificar logs de lock global (NOVO)
grep "[GLOBAL LOCK]" logs/hybrid_complete_*.log | tail -20
```

### Verificações de Segurança
```bash
# Verificar se está usando dados reais
grep -n "REAL PRICE" logs/hybrid_complete_*.log | tail -20

# Verificar bloqueios de posição
grep -n "BLOQUEADO" logs/hybrid_complete_*.log | tail -20

# Verificar ordens enviadas
grep -n "TRADE OCO" logs/hybrid_complete_*.log | tail -10
```

### Configuração Crítica
```env
# .env.production
ENABLE_TRADING=true         # Trading real (cuidado!)
MIN_CONFIDENCE=0.65         # Confiança mínima 65%
MIN_TIME_BETWEEN_TRADES=60  # 60s entre trades
USE_OCO_ORDERS=true         # Sempre com stop/take
```

---

## 📈 Principais Melhorias v2.3

### Resumo das Correções Implementadas

1. **✅ HMARL Totalmente Funcional**
   - Corrigido erro de método inexistente `get_signals()`
   - Agentes atualizando em tempo real
   - Monitor exibindo dados corretos dos 4 agentes

2. **✅ Controle de Posição com Lock Global**
   - Variável `GLOBAL_POSITION_LOCK` thread-safe
   - Bloqueio mínimo de 30 segundos após abrir posição
   - Thread de limpeza verificando a cada 5 segundos

3. **✅ Sistema OCO com Limpeza Automática**
   - OCO Monitor detecta quando posição fecha
   - Cancela automaticamente ordem órfã (stop ou take)
   - Callback `position_closed_callback` configurado

4. **✅ Dados 100% Reais**
   - Sistema aguarda dados reais ou não opera
   - Aborta trades sem preço válido do mercado
   - Logs claros: "[REAL PRICE]" e "[WAITING]"

### Arquivos Modificados

- `START_SYSTEM_COMPLETE_OCO.py` - Correção da integração HMARL
- `src/agents/hmarl_agents_realtime.py` - Interface correta dos agentes
- `src/monitoring/hmarl_monitor_bridge.py` - Atualização contínua
- `docs/DEV_GUIDE.md` - Documentação atualizada v2.3

---

## 🆕 Atualizações v4.2 (21/08/2025 - Correções do Sistema de Regime)

### 🔧 Correções Críticas Implementadas

1. **✅ Correção do Tick Size do WDO**
   - Implementada função `round_to_tick()` para arredondar preços
   - WDO usa tick de 0.5 pontos
   - Todos os stops e takes agora respeitam o tick size
   ```python
   def round_to_tick(price: float, tick_size: float = 0.5) -> float:
       return round(price / tick_size) * tick_size
   ```

2. **✅ Correção de Targets para Ordens SELL**
   - **SELL**: Take profit deve estar ABAIXO do preço de entrada
   - **SELL**: Stop loss deve estar ACIMA do preço de entrada
   - Corrigido uso de `min()` para take profit em vendas
   ```python
   # Para SELL em lateralização
   risk = stop_loss - current_price  # Prejuízo potencial
   ideal_target = current_price - (risk * self.risk_reward_ratio)
   take_profit = min(ideal_target, nearest_support * 1.005)  # CORREÇÃO
   ```

3. **✅ Sistema de Gestão de Posição Aprimorado**
   - Thread `position_consistency_check` com delay de 30s para novas posições
   - Sincronização com OCO Monitor via `sync_with_oco_monitor()`
   - Detecção correta de fechamento de posição via GetPosition
   - Rastreamento de ordens canceladas em `attempted_cancels`

4. **✅ Correção da Função GetPosition (ProfitDLL v4.0.0.30)**
   ```python
   # Estrutura correta conforme manual
   class TAssetIDRec(Structure):
       _fields_ = [
           ("ticker", c_wchar * 35),
           ("bolsa", c_wchar * 15),
       ]
   
   # Assinatura correta
   self.dll.GetPosition.argtypes = [
       POINTER(TAssetIDRec),  # asset structure
       POINTER(c_int),         # quantity pointer  
       POINTER(c_double)       # average_price pointer
   ]
   self.dll.GetPosition.restype = c_bool
   ```

5. **✅ Atualização Contínua do HMARL**
   - Arquivo `hmarl_status.json` atualizado no loop principal
   - Dados HMARL sempre frescos no monitor (sem atraso)
   - Timestamp atualizado a cada iteração com consensus
   ```python
   # No loop principal após get_consensus()
   if consensus:
       hmarl_data = {
           "timestamp": datetime.now().isoformat(),
           "market_data": {...},
           "consensus": consensus,
           "agents": consensus.get('agents', {})
       }
       with open('hmarl_status.json', 'w') as f:
           json.dump(hmarl_data, f, indent=2)
   ```

6. **✅ Sistema de Limpeza de Ordens Órfãs**
   - Thread dedicada `cleanup_orphan_orders_loop()`
   - Verifica a cada 5 segundos por ordens sem posição
   - Cancela automaticamente ordens pendentes órfãs
   - Set `attempted_cancels` evita cancelamentos duplicados

### ❌ Problema Identificado: Regime UNDEFINED

1. **Diagnóstico do Problema**
   - Sistema tem 700+ preços coletados mas retorna UNDEFINED
   - `regime_system.update()` só é chamado quando `book_buffer >= 20`
   - Regime detector precisa de 20 preços próprios no buffer interno
   - Resultado: Atraso de 40+ updates para começar detecção

2. **Solução Necessária**
   ```python
   # ANTES (problemático):
   if self.last_book_update and buffer_size >= 20:
       regime_system.update(current_price, volume)
   
   # DEPOIS (correto):
   if self.last_book_update:  # Sem verificação de buffer
       regime_system.update(current_price, volume)
   ```

### Arquivos Modificados

- **`START_SYSTEM_COMPLETE_OCO_EVENTS.py`**:
  - Linha 1020-1090: Thread `position_consistency_check`
  - Linha 1100-1150: Método `sync_with_oco_monitor()`
  - Linha 1656: Chamada `regime_system.update()`
  - Linha 2190-2210: Salvamento `hmarl_status.json`

- **`src/connection_manager_oco.py`**:
  - Linha 450-470: Estrutura `TAssetIDRec` correta
  - Linha 500-550: Implementação `GetPosition` corrigida
  - Logs detalhados com prefixo `[GetPosition]`

- **`src/trading/regime_based_strategy.py`**:
  - Linha 16-21: Função `round_to_tick()`
  - Linha 357-358: Correção `min()` para SELL
  - Linha 340-370: Arredondamento com tick size

- **`src/oco_monitor.py`**:
  - Linha 113-118: Callback posição fechada por STOP
  - Linha 130-135: Callback posição fechada por TAKE

### Comandos de Verificação

```bash
# Verificar detecção de regime
grep "[REGIME]" logs/*.log | tail -20

# Verificar gestão de posição
grep "[POSITION CHECK]" logs/*.log | tail -20

# Verificar GetPosition
grep "[GetPosition]" logs/*.log | tail -20

# Verificar cancelamento de órfãs
grep "[CLEANUP]" logs/*.log | tail -20

# Verificar atualização HMARL (Windows)
powershell -Command "Get-Item 'hmarl_status.json' | Select LastWriteTime"

# Ver dados HMARL
cat hmarl_status.json | python -m json.tool | head -20
```

---

## 🆕 Atualizações v4.2 (26/08/2025 - Correções Críticas OCO e Callbacks)

### 🔧 Correções de Callbacks ProfitDLL

1. **✅ Correção Critical: Callbacks devem retornar inteiros**
   ```python
   # ERRO ANTERIOR:
   def order_history_callback_v2(account_id_ptr):
       # ... processamento ...
       # Sem retorno = None = TypeError no Windows
   
   # CORREÇÃO:
   def order_history_callback_v2(account_id_ptr):
       try:
           # ... processamento ...
       except Exception as e:
           self.logger.error(f"Erro: {e}")
       return 0  # SEMPRE retornar 0 (sucesso) ou 1 (erro)
   ```

2. **📌 Regra Fundamental para Callbacks ctypes**
   - **Windows x64**: TODOS callbacks devem retornar valor inteiro
   - **Convenção**: 0 = sucesso, 1 = erro
   - **Sem retorno**: Python retorna None → ctypes tenta converter → TypeError
   - **Impacto**: Callbacks sem retorno podem travar ou crashar o sistema

3. **🔍 Callbacks Corrigidos**
   ```python
   # src/connection_manager_v4.py
   
   # Callback de histórico de ordens
   def order_history_callback_v2(self, account_id_ptr):
       # ... processamento ...
       return 0  # OBRIGATÓRIO
   
   # Callback de estado
   def state_callback(broker_id, routing_id):
       # ... processamento ...
       return 0  # OBRIGATÓRIO
   
   # Callback de book
   def book_callback(asset_id, bid, ask):
       # ... processamento ...
       return 0  # OBRIGATÓRIO
   ```

### 🎯 Correção de Detecção de Posições Fechadas

1. **❌ Problema**: Sistema não resetava `has_open_position` após fechamento
   ```python
   # ANTES: Só verificava GetPosition
   position = self.connection.get_position(symbol)
   if not position:
       # Assumia que não tinha posição (ERRADO!)
   ```

2. **✅ Solução**: Verificar grupos OCO ativos também
   ```python
   # DEPOIS: Verifica posição E grupos OCO
   def check_position_status(self):
       # 1. Verificar grupos OCO ativos
       has_active_oco = False
       if self.connection.oco_monitor:
           active_groups = sum(1 for g in oco_monitor.oco_groups.values() 
                              if g.get('active'))
           has_active_oco = active_groups > 0
       
       # 2. Verificar posição real
       position = self.connection.check_position_exists(symbol)
       
       # 3. Só reseta se NÃO tem posição E NÃO tem OCO
       if not position and not has_active_oco:
           self.has_open_position = False  # Agora sim pode resetar
   ```

### 💰 Correção de Preços Incorretos

1. **❌ Problema**: Sistema usando preço 2726 quando mercado estava em 5452
   ```python
   # ANTES: Confiava em connection.last_price (desatualizado)
   def _get_real_market_price(self):
       if self.connection.last_price > 0:
           return self.connection.last_price  # Podia ter valor antigo!
   ```

2. **✅ Solução**: Hierarquia de fontes confiáveis
   ```python
   def _get_real_market_price(self):
       # Prioridade 1: Book update (mais recente)
       if self.last_book_update:
           bid = self.last_book_update.get('bid_price_1', 0)
           ask = self.last_book_update.get('ask_price_1', 0)
           if bid > 4000 and ask > 4000:  # WDO > 4000
               return (bid + ask) / 2.0
       
       # Prioridade 2: current_price atualizado
       if self.current_price > 4000:
           return self.current_price
       
       # Prioridade 3: last_mid_price
       if self.last_mid_price > 4000:
           return self.last_mid_price
       
       # Última opção: connection (menos confiável)
       # ... com validação > 4000
   ```

### 🔄 Script de Reset Manual

**Arquivo**: `reset_position_state.py`
```python
# Uso: Quando sistema trava com posição fantasma
python reset_position_state.py

# O que faz:
# 1. Backup do position_status.json
# 2. Limpa estado de posições
# 3. Desativa grupos OCO órfãos
# 4. Cria flag para reset no próximo startup
```

### 📝 Estrutura Correta de Callbacks ProfitDLL v4.0.0.30

```python
from ctypes import WINFUNCTYPE, POINTER, c_int, c_longlong, c_double, c_wchar_p

# Definição dos tipos de callback
StateCallbackType = WINFUNCTYPE(c_int, c_int, c_int)  # Retorna int!
HistoryCallbackType = WINFUNCTYPE(c_int, c_int, c_wchar_p, c_int, c_int, c_longlong)
OrderCallbackType = WINFUNCTYPE(c_int, c_int, c_longlong, c_int, c_double, c_double, c_int, c_wchar_p)
BookCallbackType = WINFUNCTYPE(c_int, POINTER(TAssetIDRec), c_int)
TradeCallbackType = WINFUNCTYPE(c_int, POINTER(TAssetIDRec), c_wchar_p, c_double, c_longlong, c_int, c_int)

# Implementação correta
@StateCallbackType
def state_callback(broker_id, routing_id):
    try:
        if broker_id == 1:
            print(f"Broker conectado: ID={routing_id}")
        # ... processamento ...
    except Exception as e:
        print(f"Erro no callback: {e}")
    return 0  # OBRIGATÓRIO: 0=sucesso, 1=erro

# Registro no DLL
dll.DLLInitializeLogin(
    key, username, password,
    state_callback,  # Callback de estado
    history_callback,  # Callback de histórico
    order_callback,  # Callback de ordens
    # ...
)
```

### 📋 Checklist de Verificação

```bash
# 1. Verificar callbacks funcionando
grep "callback.*return" src/connection_manager_v4.py

# 2. Verificar detecção de posições
grep "has_open_position\|OCO CHECK" logs/*.log | tail -20

# 3. Verificar preços corretos (devem ser > 4000)
grep "Entry:" logs/*.log | tail -10

# 4. Verificar ordens OCO sendo enviadas
grep "OCO.*enviadas\|ORDEM BRACKET" logs/*.log | tail -10

# 5. Status de posição atual
cat data/monitor/position_status.json

# 6. Verificar erros de callback
grep "TypeError.*NoneType.*integer" logs/*.log | tail -5

# 7. Verificar reset de posição
python reset_position_state.py  # Se necessário
```

---

## 📊 Atualizações v4.1 (20/08/2025 - Otimizações do Sistema de Regime)

### Melhorias na Geração de Sinais

1. **🎯 Estratégia de Lateralização Aprimorada**
   ```python
   # ANTES:
   support_resistance_buffer = 0.001  # 0.1% muito restritivo
   min_buffer_size = 50               # Muitos dados necessários
   
   # DEPOIS:
   support_resistance_buffer = 0.002  # 0.2% mais tolerante
   min_buffer_size = 30               # Menos dados necessários
   ```

2. **📉 Estratégia Alternativa para S/R**
   - Quando não há níveis claros de suporte/resistência
   - Usa mínimos e máximos dos últimos 20 períodos
   - Garante que sempre há níveis para operar

3. **🔕 Redução de Logs**
   - Regime logado apenas a cada 50 iterações
   - Debug de S/R a cada 100 chamadas
   - Status do monitor atualizado a cada 20 iterações
   - Eliminação de logs repetitivos

4. **📡 Monitor em Tempo Real**
   ```python
   # Salva status mesmo sem sinais
   if self._prediction_count % 20 == 0:
       self._save_regime_status_for_monitor(status_signal)
   ```

### Comandos Úteis

```bash
# Iniciar sistema com novo monitor unificado
python START_SYSTEM_COMPLETE_OCO_EVENTS.py  # Terminal 1
START_UNIFIED_MONITOR.bat                    # Terminal 2

# Ver logs do regime (menos poluído agora)
grep "[REGIME]" logs/*.log | tail -20

# Ver debug de suporte/resistência
grep "[S/R DEBUG]" logs/*.log | tail -10

# Monitorar sinais gerados
grep "[SIGNAL]" logs/*.log | tail -20

# Verificar status do regime
cat data/monitor/regime_status.json | python -m json.tool
```

### Estrutura de Sinais

```python
@dataclass
class RegimeSignal:
    regime: MarketRegime      # Regime detectado
    signal: int               # 1=BUY, -1=SELL, 0=HOLD
    confidence: float         # Confiança do sinal
    entry_price: float        # Preço de entrada
    stop_loss: float          # Stop loss
    take_profit: float        # Take profit
    risk_reward: float        # Relação risco/retorno
    strategy: str            # "trend_following" ou "support_resistance"
```

### Fluxo de Decisão

```
1. Detectar Regime (a cada tick)
   ↓
2. Se LATERAL:
   - Buscar níveis S/R
   - Se não houver, usar min/max recente
   - Verificar proximidade do preço
   
3. Se TENDÊNCIA:
   - Aguardar pullback para média
   - Confirmar com HMARL
   
4. Gerar Sinal:
   - Aplicar RR apropriado (1.5:1 ou 1.0:1)
   - Verificar confiança mínima
   - Executar trade
```

### Arquivos Principais

- `src/trading/regime_based_strategy.py` - Sistema de regime completo
- `START_SYSTEM_COMPLETE_OCO_EVENTS.py` - Integração principal
- `core/monitor_unified_system.py` - Monitor unificado
- `docs/REGIME_STRATEGY_CONFIG.md` - Configuração detalhada
- `docs/SYSTEM_MONITORS_GUIDE.md` - Guia dos monitores

---

**QuantumTrader v4.1 - Sistema Baseado em Regime**

Sistema determinístico baseado em detecção de regime de mercado, com estratégias específicas por condição e HMARL para timing. Substitui completamente o sistema ML defeituoso anterior.

Para suporte técnico, consulte a documentação ou revise o código fonte.