# Guia dos Monitores do Sistema

## 📊 Monitores Disponíveis

### 1. Monitor Unificado (RECOMENDADO)
**Arquivo**: `core/monitor_unified_system.py`
**Comando**: `python core/monitor_unified_system.py` ou `START_UNIFIED_MONITOR.bat`

Combina todas as informações em uma única interface:
- Regime de mercado atual
- Estratégia ativa (Trend Following ou Support/Resistance)
- Sinais de trading com níveis (Entry, Stop, Target)
- Consenso dos agentes HMARL
- Estatísticas de performance
- Status do sistema (Running/Stopped)

**Layout**:
```
MARKET REGIME & STRATEGY
- Mostra regime detectado (Uptrend/Downtrend/Lateral)
- Estratégia ativa com Risk/Reward

ML SYSTEM STATUS
- Status das 3 camadas (compatibilidade)
- Decisão final e confiança

TRADING SIGNALS & LEVELS
- Último sinal gerado
- Níveis de entrada, stop e alvo
- Risk/Reward do trade

HMARL AGENTS CONSENSUS
- Status dos 4 agentes
- Consenso para timing

PERFORMANCE & STATISTICS
- Total de trades, wins, losses
- Win rate
- Distribuição de mercado (Trending vs Ranging)
```

### 2. Monitor de Regime
**Arquivo**: `core/monitor_regime_enhanced.py`
**Comando**: `python core/monitor_regime_enhanced.py` ou `START_REGIME_MONITOR.bat`

Focado especificamente no sistema de regime:
- Detecção detalhada de regime
- Estratégia específica ativa
- Sinais com Risk/Reward
- HMARL para timing

### 3. Monitor Enhanced (Legado)
**Arquivo**: `core/monitor_console_enhanced.py`
**Comando**: `python core/monitor_console_enhanced.py`

Monitor original com foco em features e ML:
- 65 features em tempo real
- Status das camadas ML
- Agentes HMARL detalhados
- Logs do sistema

## 🚀 Como Usar

### Opção 1: Sistema Completo com Monitor Unificado
```bash
# Terminal 1 - Sistema principal
python START_SYSTEM_COMPLETE_OCO_EVENTS.py

# Terminal 2 - Monitor unificado
START_UNIFIED_MONITOR.bat
```

### Opção 2: Script Automatizado
```bash
# Abre sistema e monitor em janelas separadas
python start_regime_system.py
```

## 📈 Interpretação dos Dados

### Regimes de Mercado
- **STRONG_UPTREND**: Tendência forte de alta (^^)
- **UPTREND**: Tendência de alta (^)
- **LATERAL**: Mercado lateralizado (=)
- **DOWNTREND**: Tendência de baixa (v)
- **STRONG_DOWNTREND**: Tendência forte de baixa (vv)
- **UNDEFINED**: Regime não identificado (?)

### Estratégias
- **TREND FOLLOWING**: Opera a favor da tendência, RR 1.5:1
- **SUPPORT/RESISTANCE**: Opera reversão em níveis, RR 1.0:1
- **WAITING FOR SETUP**: Aguardando condições ideais

### Sinais de Trading
- **BUY (^)**: Sinal de compra
- **SELL (v)**: Sinal de venda
- **HOLD (=)**: Manter posição/aguardar

### HMARL Consensus
- Mostra acordo entre os 4 agentes
- Usado para refinar timing de entrada
- Consensus: BUY/SELL/HOLD baseado em maioria

### Performance Metrics
- **WR (Win Rate)**: Taxa de acerto
  - Verde: >= 60%
  - Amarelo: 40-59%
  - Vermelho: < 40%
- **Trend/Lateral Trades**: Trades por tipo de regime
- **Market Distribution**: % de tempo em cada regime

## 🔧 Configuração

### Refresh Rate
Todos os monitores atualizam a cada 2 segundos por padrão.
Para alterar, edite a variável `self.refresh_rate` no código.

### Largura da Tela
Configurada para 120 caracteres de largura.
Ajuste `self.screen_width` se necessário.

### Cores
Os monitores usam `colorama` para cores no terminal.
Se as cores não funcionarem, instale:
```bash
pip install colorama
```

## 📁 Arquivos de Dados

Os monitores leem dados de:
- `data/monitor/regime_status.json` - Status do regime atual
- `data/monitor/latest_signal.json` - Último sinal gerado
- `data/monitor/regime_stats.json` - Estatísticas acumuladas
- `data/monitor/ml_status.json` - Status ML (compatibilidade)

Estes arquivos são atualizados automaticamente pelo sistema principal.

## 🛠️ Troubleshooting

### "SYSTEM STOPPED"
- Sistema principal não está rodando
- Ou arquivos de status não estão sendo atualizados
- Inicie o sistema: `python START_SYSTEM_COMPLETE_OCO_EVENTS.py`

### Dados não atualizam
- Verifique se o sistema principal está rodando
- Confirme que a pasta `data/monitor/` existe
- Verifique permissões de escrita

### HMARL mostra valores padrão
- Normal se bridge HMARL não está disponível
- Sistema funciona sem HMARL (usa apenas regime)

### Cores não aparecem
- Instale colorama: `pip install colorama`
- Em alguns terminais, cores podem não funcionar

## 💡 Dicas

1. **Use o Monitor Unificado** para visão geral completa
2. **Monitor de Regime** para análise específica de estratégia
3. **Dois monitores** podem rodar simultaneamente
4. **Logs detalhados** estão em `logs/`
5. **Performance** é acumulada desde o início do sistema

## 📊 Exemplo de Leitura

```
MARKET REGIME & STRATEGY
| Regime: UPTREND        Conf: ###....... 75%  |
| Strategy: TREND FOLLOWING (RR 1.5:1)          |
```

Interpretação:
- Mercado em tendência de alta
- 75% de confiança na detecção
- Estratégia de trend following ativa
- Operando com Risk/Reward 1.5:1

```
TRADING SIGNALS & LEVELS
| Signal: BUY     Conf: 65% RR: 1.5:1           |
| Entry:  5520.00  Stop:  5500.00  Target:  5550.00 |
```

Interpretação:
- Sinal de compra gerado
- 65% de confiança
- Entrada em 5520
- Stop loss em 5500 (risco de 20 pontos)
- Alvo em 5550 (ganho de 30 pontos)
- Risk/Reward 1.5:1 (30/20)