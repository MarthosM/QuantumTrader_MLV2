# Gestão de Risco para WDO - Sistema QuantumTrader

## 📊 Configurações Ajustadas para WDO

### Características do Contrato
- **Tick Size**: 0.5 ponto (mínima variação)
- **Valor do Ponto**: R$ 10,00
- **Stop Padrão**: 5 pontos = R$ 50 por contrato
- **Take Padrão**: 10 pontos = R$ 100 por contrato

## 🎯 Níveis de Stop Loss e Take Profit por Confiança

| Confiança | Stop Loss | Take Profit | Risco (R$) | Retorno (R$) | Risk:Reward |
|-----------|-----------|-------------|------------|--------------|-------------|
| **Alta (≥80%)** | 5 pontos | 15 pontos | R$ 50 | R$ 150 | 1:3.0 |
| **Média-Alta (70-79%)** | 6 pontos | 12 pontos | R$ 60 | R$ 120 | 1:2.0 |
| **Média (60-69%)** | 7 pontos | 10 pontos | R$ 70 | R$ 100 | 1:1.4 |
| **Baixa (<60%)** | 8 pontos | 8 pontos | R$ 80 | R$ 80 | 1:1.0 |

## 📈 Estratégias por Tipo de Operação

### Scalping (Alta Frequência)
- **Stop**: 3 pontos (R$ 30)
- **Take**: 5 pontos (R$ 50)
- **R:R**: 1:1.67
- **Ideal para**: Movimentos rápidos intraday

### Day Trade (Padrão)
- **Stop**: 5 pontos (R$ 50)
- **Take**: 10 pontos (R$ 100)
- **R:R**: 1:2.0
- **Ideal para**: Operações normais do dia

### Swing Trade
- **Stop**: 7 pontos (R$ 70)
- **Take**: 14 pontos (R$ 140)
- **R:R**: 1:2.0
- **Ideal para**: Tendências mais longas

### Position Trade
- **Stop**: 10 pontos (R$ 100)
- **Take**: 20 pontos (R$ 200)
- **R:R**: 1:2.0
- **Ideal para**: Movimentos estruturais

## 🛡️ Trailing Stop

- **Ativação**: Após 3 pontos de lucro
- **Distância**: 3 pontos do preço atual
- **Exemplo**: 
  - Compra em 5645.0
  - Preço sobe para 5648.0 (3 pontos de lucro)
  - Stop ajustado de 5640.0 para 5645.0 (breakeven)
  - Preço sobe para 5650.0
  - Stop ajustado para 5647.0 (protege 2 pontos de lucro)

## 💰 Position Sizing (Gestão de Capital)

### Cálculo Automático baseado em 2% de risco

| Capital | Stop 5pts | Stop 7pts | Stop 10pts |
|---------|-----------|-----------|------------|
| R$ 10.000 | 4 contratos | 2 contratos | 2 contratos |
| R$ 25.000 | 10 contratos | 7 contratos | 5 contratos |
| R$ 50.000 | 10 contratos* | 10 contratos* | 10 contratos* |
| R$ 100.000 | 10 contratos* | 10 contratos* | 10 contratos* |

*Limitado a máximo de 10 contratos por operação

### Fórmula
```
Contratos = (Capital × 2%) / (Stop_Points × R$10)
```

## 📊 Exemplos Práticos

### Exemplo 1: Trade com Alta Confiança (85%)
```
Preço Atual: 5645.5
Sinal: COMPRA
Confiança: 85%

Ordem Executada:
- Entrada: 5645.5
- Stop Loss: 5640.5 (5 pontos = R$ 50)
- Take Profit: 5660.5 (15 pontos = R$ 150)
- Risk:Reward: 1:3
```

### Exemplo 2: Trade com Média Confiança (65%)
```
Preço Atual: 5650.0
Sinal: VENDA
Confiança: 65%

Ordem Executada:
- Entrada: 5650.0
- Stop Loss: 5657.0 (7 pontos = R$ 70)
- Take Profit: 5640.0 (10 pontos = R$ 100)
- Risk:Reward: 1:1.4
```

## ⚠️ Limites de Segurança

- **Stop Mínimo**: 3 pontos (R$ 30)
- **Take Mínimo**: 5 pontos (R$ 50)
- **Máximo de Trades/Dia**: 10
- **Máximo Drawdown Diário**: 5%
- **Máximo de Contratos**: 10

## 🔄 Ajustes Dinâmicos

O sistema ajusta automaticamente:

1. **Stop menor com alta confiança**: Reduz risco quando sinal é forte
2. **Stop maior com baixa confiança**: Aumenta proteção quando sinal é fraco
3. **Take proporcional ao stop**: Mantém risk:reward favorável
4. **Trailing stop automático**: Protege lucros em trades vencedores

## 📝 Configuração no Sistema

### Arquivo `.env.production`
```env
DEFAULT_STOP_POINTS=5.0     # 5 pontos = R$ 50
DEFAULT_TAKE_POINTS=10.0    # 10 pontos = R$ 100
MIN_STOP_POINTS=3.0         # Stop mínimo
MIN_TAKE_POINTS=5.0         # Take mínimo
TRAILING_STOP_POINTS=3.0    # Trailing de 3 pontos
RISK_PER_TRADE=0.02         # 2% de risco por trade
```

## 🎯 Metas de Performance

Com esta configuração, as metas realistas são:

- **Win Rate**: 45-55%
- **Risk:Reward Médio**: 1:2
- **Expectativa Matemática**: Positiva com 40%+ de acerto
- **Drawdown Máximo**: 10-15%
- **Retorno Mensal Esperado**: 5-15%

## 🚨 Avisos Importantes

1. **Sempre opere com stop**: Nunca remova o stop loss
2. **Respeite o position sizing**: Não aumente lotes por emoção
3. **Siga o sistema**: Não altere stops/takes manualmente
4. **Horário de maior liquidez**: 09:30-11:30 e 14:00-16:00
5. **Evite notícias de alto impacto**: COPOM, FOMC, PIB, etc.

## 📈 Monitoramento

O sistema registra automaticamente:
- Todas as ordens executadas
- P&L de cada operação
- Estatísticas de win rate
- Drawdown atual
- Performance acumulada

---

*Última atualização: 12/08/2025*
*Sistema configurado para operar com gestão de risco conservadora e consistente.*