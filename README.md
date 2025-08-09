# QuantumTrader ML V2 🚀

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-success.svg)](https://github.com/MarthosM/QuantumTrader_MLV2)

## 📊 Sistema de Trading Algorítmico com Machine Learning e HMARL

Sistema de produção avançado para trading algorítmico que integra **65 features de microestrutura de mercado**, **4 agentes HMARL especializados** e **consenso ML/HMARL adaptativo** para tomada de decisão em tempo real.

### 🎯 Características Principais

- **65 Features de Microestrutura**: Análise profunda do livro de ofertas e fluxo de ordens
- **4 Agentes HMARL Especializados**:
  - OrderFlowSpecialist (30% peso)
  - LiquidityAgent (20% peso)  
  - TapeReadingAgent (25% peso)
  - FootprintPatternAgent (25% peso)
- **Sistema de Consenso Adaptativo**: ML (40%) + HMARL (60%)
- **Latência Ultra-Baixa**: < 2ms para cálculo de features
- **Broadcasting ZMQ**: Distribuição eficiente de features via MessagePack + LZ4
- **Gestão de Risco Integrada**: Stop loss, take profit e limites diários

### 🏗️ Arquitetura

```
ProfitChart (Dados de Mercado)
        ↓
Circular Buffers Thread-Safe
        ↓
Feature Engineering (65 features)
        ↓
    ┌───────┴───────┐
    │               │
ML Models      HMARL Agents
    │               │
    └───────┬───────┘
        ↓
Sistema de Consenso
        ↓
Decisão de Trading
        ↓
Execução de Ordens
```

### 📋 Requisitos

- Python 3.12+
- ProfitChart com ProfitDLL
- Windows 10/11 (suporte Linux em desenvolvimento)
- 8GB RAM mínimo
- Processador quad-core recomendado

### 🚀 Instalação Rápida

1. **Clone o repositório**
```bash
git clone https://github.com/MarthosM/QuantumTrader_MLV2.git
cd QuantumTrader_MLV2
```

2. **Crie ambiente virtual**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# ou
source venv/bin/activate  # Linux/Mac
```

3. **Instale dependências**
```bash
pip install -r requirements.txt
```

4. **Configure o sistema**
```bash
cp .env.example .env.production
# Edite .env.production com suas configurações
```

5. **Inicie o sistema**
```bash
START_SYSTEM.bat  # Windows
# ou
python core/start_production_65features.py
```

### ⚙️ Configuração

Edite `.env.production` com suas configurações:

```env
# Trading
PROFIT_KEY=sua_chave_aqui
TRADING_SYMBOL=WDOU25
MIN_CONFIDENCE=0.60
MAX_DAILY_TRADES=10

# Risk Management
STOP_LOSS=0.005
TAKE_PROFIT=0.010
MAX_POSITION_SIZE=1

# System
ENABLE_DATA_RECORDING=true
LOG_LEVEL=INFO
```

### 📊 Features Implementadas

#### Volatilidade (10)
- Volatilidade realizada (5, 10, 20, 50 períodos)
- ATR, Parkinson, Garman-Klass
- Volatilidade condicional

#### Retornos (10)
- Log returns (1, 5, 10, 20, 50 períodos)
- Retornos cumulativos
- Drawdown e recovery

#### Order Flow (8)
- Order Flow Imbalance
- Volume assinado
- Trade imbalance
- VPIN

#### Volume (8)
- Volume profiles
- VWAP e desvios
- Volume por nível de preço
- Large trade ratio

#### Técnicas (8)
- RSI, MACD, Bollinger Bands
- Stochastic, Williams %R
- Momentum indicators

#### Microestrutura (15)
- Bid-ask spread metrics
- Book imbalance e pressure
- Micro price e weighted mid
- Depth analysis

#### Temporais (6)
- Hora, minuto, dia da semana
- Sessão de trading
- Proximidade a eventos

### 📈 Performance

- **Latência de Features**: < 2ms (média 0.66ms)
- **Throughput**: 600+ features/segundo
- **Win Rate Esperado**: 55-65%
- **Sharpe Ratio Target**: 1.5-2.5
- **Max Drawdown**: < 10%

### 🔍 Monitoramento

```bash
# Monitor em tempo real
python core/monitor_console_enhanced.py

# Verificar logs
tail -f logs/production_*.log

# Status do sistema
python -c "from pathlib import Path; print('Running' if Path('quantum_trader.pid').exists() else 'Stopped')"
```

### 📁 Estrutura do Projeto

```
QuantumTrader_MLV2/
├── core/                       # Scripts principais
│   ├── enhanced_production_system.py
│   ├── start_production_65features.py
│   └── monitor_console_enhanced.py
├── src/                        # Módulos fonte
│   ├── features/              # Engenharia de features
│   ├── agents/                # Agentes HMARL
│   ├── consensus/             # Sistema de consenso
│   ├── broadcasting/          # Broadcasting ZMQ
│   ├── buffers/               # Buffers circulares
│   ├── metrics/               # Métricas e alertas
│   └── logging/               # Logging estruturado
├── models/                     # Modelos ML treinados
├── data/                       # Dados coletados
├── logs/                       # Logs do sistema
├── tests/                      # Testes unitários
└── docs/                       # Documentação
```

### 🛠️ Desenvolvimento

```bash
# Executar testes
pytest tests/

# Verificar cobertura
pytest --cov=src tests/

# Formatar código
black src/ core/

# Lint
pylint src/ core/
```

### 📝 Roadmap

- [x] Sistema base com 65 features
- [x] 4 agentes HMARL especializados
- [x] Broadcasting ZMQ
- [x] Sistema de consenso ML/HMARL
- [ ] Interface web de monitoramento
- [ ] Backtesting framework
- [ ] Suporte multi-symbol
- [ ] Cloud deployment
- [ ] API REST para controle remoto

### 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o projeto
2. Crie uma feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

### 📄 Licença

Este projeto está licenciado sob a MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

### ⚠️ Disclaimer

Este software é fornecido "como está" para fins educacionais e de pesquisa. Trading algorítmico envolve riscos substanciais. Use por sua conta e risco. Os desenvolvedores não se responsabilizam por perdas financeiras.

### 📞 Contato

**Marthos M** - [@MarthosM](https://github.com/MarthosM)

**Link do Projeto**: [https://github.com/MarthosM/QuantumTrader_MLV2](https://github.com/MarthosM/QuantumTrader_MLV2)

---

<p align="center">Desenvolvido com ❤️ para a comunidade de trading algorítmico</p>