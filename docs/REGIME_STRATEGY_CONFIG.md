# Configuração da Estratégia Baseada em Regime

## Risk/Reward por Regime de Mercado

### 📈 Tendências (Alta/Baixa)
- **Risk/Reward**: 1.5:1
- **Razão**: Em tendências, o mercado tende a continuar na direção, permitindo alvos maiores
- **Entrada**: Aguarda pullback para média móvel
- **Stop**: Baseado em ATR (Average True Range)
- **Alvo**: 1.5x o risco assumido

### 📊 Lateralização
- **Risk/Reward**: 1.0:1
- **Razão**: Em lateralização, os movimentos são limitados entre suporte e resistência
- **Entrada**: Compra no suporte, vende na resistência
- **Stop**: 0.5% além do nível de suporte/resistência
- **Alvo**: Próximo nível ou 1:1 (o que for menor)

## Justificativa dos Ajustes

### Por que 1:1 em Lateralização?

1. **Movimentos Limitados**: Em mercados lateralizados, o preço oscila entre níveis definidos
2. **Alta Probabilidade**: Operações em suporte/resistência têm maior taxa de acerto
3. **Volume de Trades**: Mais oportunidades compensam o menor RR
4. **Gestão de Risco**: Stops menores e mais precisos

### Vantagens do Sistema

- **Adaptativo**: Ajusta estratégia conforme regime detectado
- **Realista**: RR adequado para cada condição de mercado
- **Consistente**: Regras claras para cada situação
- **HMARL**: Melhora timing de entrada em qualquer regime

## Estatísticas Esperadas

### Em Tendências
- Win Rate: 45-55%
- RR: 1.5:1
- Expectativa Matemática: Positiva (0.45 * 1.5 - 0.55 * 1 = 0.125)

### Em Lateralização
- Win Rate: 55-65%
- RR: 1.0:1
- Expectativa Matemática: Positiva (0.60 * 1 - 0.40 * 1 = 0.20)

## Configuração no Código

```python
# src/trading/regime_based_strategy.py
class RegimeBasedTradingSystem:
    def __init__(self):
        # Tendências: RR 1.5:1
        self.trend_strategy = TrendFollowingStrategy(risk_reward_ratio=1.5)
        
        # Lateralização: RR 1.0:1
        self.lateral_strategy = SupportResistanceStrategy(risk_reward_ratio=1.0)
```

## Monitoramento

O sistema registra automaticamente:
- Regime detectado a cada período
- Estratégia utilizada em cada trade
- Risk/Reward real de cada operação
- Taxa de acerto por regime

## Ajustes Futuros

Baseado nos resultados, podemos ajustar:
- Thresholds de detecção de regime
- Buffers de entrada em suporte/resistência
- Multiplicadores de ATR para stops
- Pesos do HMARL no timing