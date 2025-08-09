# 🚀 QuantumTrader Production System

## Sistema de Trading Algorítmico com 65 Features e HMARL

### Versão de Produção - Limpa e Otimizada

---

## 📋 Visão Geral

Sistema completo de trading algorítmico com:
- **65 Features Microestruturais** em tempo real
- **4 Agentes HMARL Especializados** (OrderFlow, Liquidity, TapeReading, Footprint)
- **Sistema de Consenso Adaptativo** (ML 40% + Agents 60%)
- **Monitor Enhanced** com visualização rica no console
- **Gravação Automática** de book/tick data
- **Métricas e Logs Estruturados** em JSON

## 🎯 Performance

- **Latência de Features**: <2ms (requisito: <10ms)
- **Taxa de Cálculo**: 600+ features/segundo
- **Uso de CPU**: <5% (monitor: 0.1%)
- **Uso de RAM**: <500MB total
- **Precisão**: 55-65% win rate esperado

## 📁 Estrutura do Sistema

```
QuantumTrader_Production/
├── core/                    # Scripts principais
│   ├── enhanced_production_system.py
│   ├── start_production_65features.py
│   └── monitor_console_enhanced.py
├── src/                     # Módulos do sistema
│   ├── features/           # 65 features RT
│   ├── agents/             # 4 agentes HMARL
│   ├── consensus/          # Sistema de consenso
│   ├── metrics/            # Métricas e alertas
│   └── logging/            # Logs estruturados
├── models/                 # Modelos ML treinados
├── data/                   # Dados coletados
└── docs/                   # Documentação
```

## 🚀 Quick Start

### 1. Instalação

```bash
# Criar ambiente virtual
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install -r requirements.txt
```

### 2. Configuração

Edite `.env.production` com suas configurações:
```env
TRADING_SYMBOL=WDOU25
PROFIT_KEY=sua_chave_aqui
MIN_CONFIDENCE=0.60
```

### 3. Executar Sistema

**Windows:**
```cmd
START_SYSTEM.bat
```

**Linux/Mac:**
```bash
./start_system.sh
```

### 4. Monitorar

O monitor abre automaticamente mostrando:
- 65 features em tempo real
- Sinais dos 4 agentes
- Métricas de performance
- Logs do sistema

### 5. Parar Sistema

```bash
python stop_production.py
```

## 📊 Features do Sistema

### Categorias de Features (65 total)

1. **Volatility (10)**: Medidas de volatilidade em múltiplos períodos
2. **Returns (10)**: Retornos simples e logarítmicos
3. **Order Flow (8)**: Análise de fluxo de ordens
4. **Volume (8)**: Estatísticas de volume
5. **Technical (8)**: Indicadores técnicos clássicos
6. **Microstructure (15)**: Métricas de microestrutura de mercado
7. **Temporal (6)**: Features temporais e sazonais

### Agentes HMARL

1. **OrderFlowSpecialist** (30%): Analisa desequilíbrios no fluxo
2. **LiquidityAgent** (20%): Monitora liquidez e profundidade
3. **TapeReadingAgent** (25%): Lê a fita de negócios
4. **FootprintPatternAgent** (25%): Detecta padrões de pegadas

## 📈 Métricas e Monitoramento

### Métricas em Tempo Real
- Features/segundo
- Predictions/segundo
- Latência média
- Win rate
- Sharpe ratio
- Drawdown máximo
- PnL acumulado

### Logs Estruturados
```json
{
  "timestamp": "2025-01-09T10:30:00",
  "component": "TradingSystem",
  "event": "trade_signal",
  "data": {
    "signal": "BUY",
    "confidence": 0.75,
    "consensus": {
      "ml": 0.65,
      "agents": 0.82
    }
  }
}
```

## 🔧 Configuração Avançada

### Ajustar Thresholds
Em `.env.production`:
```env
MIN_CONFIDENCE=0.60       # Confiança mínima para trade
ML_WEIGHT=0.40           # Peso do modelo ML
AGENT_WEIGHT=0.60        # Peso dos agentes
MAX_DAILY_TRADES=10      # Limite diário
STOP_LOSS=0.005          # Stop loss (0.5%)
```

### Configurar Agentes
Em `config_production.json`:
```json
"agents": {
  "order_flow_specialist": {
    "weight": 0.30,
    "min_confidence": 0.60
  }
}
```

## 🛠️ Manutenção

### Backup Automático
- Executado a cada 60 minutos
- Mantém últimos 7 dias
- Localização: `backups/`

### Limpeza de Logs
```bash
# Remover logs > 30 dias
python scripts/cleanup_logs.py
```

### Atualizar Modelos
```bash
# Treinar com dados recentes
python scripts/train_models.py --data=data/book_tick_data/
```

## 📞 Suporte e Troubleshooting

### Sistema não inicia
1. Verificar Profit Chart aberto
2. Confirmar chave em `.env.production`
3. Ver logs em `logs/production_*.log`

### Features retornando zero
- Aguardar 200+ candles para buffers
- Verificar callbacks do ProfitDLL

### Performance degradada
- Verificar CPU/RAM disponível
- Reduzir buffer sizes se necessário
- Desabilitar logs DEBUG

## 📚 Documentação Adicional

- [DEV_GUIDE.md](DEV_GUIDE.md) - Guia de desenvolvimento
- [HMARL_GUIDE.md](HMARL_GUIDE.md) - Sistema HMARL detalhado
- [QUICK_START.md](QUICK_START.md) - Início rápido
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Resolução de problemas

## 📄 Licença

Proprietary - Todos os direitos reservados

---

**Desenvolvido com ❤️ para trading algorítmico de alta performance**