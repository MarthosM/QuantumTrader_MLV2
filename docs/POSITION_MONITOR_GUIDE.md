# Position Monitor - Guia de Uso

## 📊 Visão Geral

O **Position Monitor** é um sistema completo de monitoramento e gestão de posições em tempo real, integrado ao QuantumTrader. Ele rastreia automaticamente todas as posições abertas, calcula P&L em tempo real e implementa estratégias avançadas de gestão como trailing stop e breakeven.

## 🚀 Recursos Principais

### 1. **Position Monitor** (`src/monitoring/position_monitor.py`)
- Rastreamento automático de posições abertas
- Cálculo de P&L em tempo real
- Detecção de fechamento de posições
- Sincronização com OCO Monitor
- Arquivo de status JSON para visualização externa

### 2. **Position Manager** (`src/trading/position_manager.py`)
- **Trailing Stop**: Move stop automaticamente seguindo o lucro
- **Breakeven**: Move stop para entrada quando atinge lucro mínimo
- **Saídas Parciais**: Fecha parte da posição em níveis pré-definidos
- Estratégias configuráveis por símbolo

### 3. **Symbol Manager** (`src/utils/symbol_manager.py`)
- Atualização automática de símbolo baseado no mês
- Detecção de proximidade ao vencimento
- Sugestão de rollover de contratos

## 📋 Configuração

### Estratégia Padrão (já configurada)

```python
ManagementStrategy(
    trailing_stop_enabled=True,
    trailing_stop_distance=0.015,  # 1.5% trailing
    breakeven_enabled=True,
    breakeven_threshold=0.003,  # Move para breakeven com 0.3% de lucro
    partial_exit_enabled=False  # Desabilitado por padrão
)
```

### Customização de Estratégia

Para modificar a estratégia, edite em `START_SYSTEM_COMPLETE_OCO_EVENTS.py`:

```python
# Linha ~516
default_strategy = ManagementStrategy(
    trailing_stop_enabled=True,
    trailing_stop_distance=0.02,  # 2% trailing (mais conservador)
    breakeven_enabled=True,
    breakeven_threshold=0.005,  # 0.5% de lucro
    partial_exit_enabled=True,  # Habilitar saídas parciais
    partial_exit_levels=[
        {'profit_pct': 0.01, 'exit_pct': 0.33},  # 1% lucro, sair 33%
        {'profit_pct': 0.02, 'exit_pct': 0.50},  # 2% lucro, sair 50% do restante
    ]
)
```

## 📊 Monitoramento

### 1. Arquivo de Status (Tempo Real)
- **Local**: `data/monitor/position_status.json`
- **Atualização**: A cada 1 segundo
- **Conteúdo**:
```json
{
  "timestamp": "2025-08-25T08:15:00",
  "has_position": true,
  "positions": [{
    "symbol": "WDOQ25",
    "side": "BUY",
    "quantity": 1,
    "entry_price": 5500.0,
    "current_price": 5510.0,
    "pnl": 10.0,
    "pnl_percentage": 0.18,
    "status": "open"
  }]
}
```

### 2. Logs do Sistema
```bash
# Ver logs em tempo real
tail -f logs/system_complete_oco_events_*.log | grep POSITION

# Logs importantes:
[POSITION MONITOR] Posição aberta detectada
[POSITION MONITOR] P&L: 20.00 (0.36%)
[BREAKEVEN] Stop movido para breakeven
[TRAILING] Stop atualizado: WDOQ25 -> 5485.00
```

### 3. Eventos do Sistema
O Position Monitor emite eventos via EventBus:
- `POSITION_OPENED`: Quando posição é aberta
- `POSITION_CLOSED`: Quando posição fecha
- Integração automática com outros componentes

## 🔧 Comandos Úteis

### Testar Position Monitor
```bash
python test_position_monitor_integration.py
```

### Iniciar Sistema Completo
```bash
python START_SYSTEM_COMPLETE_OCO_EVENTS.py
```

### Verificar Status Atual
```bash
python -c "
import json
with open('data/monitor/position_status.json') as f:
    data = json.load(f)
    print(f\"Posição aberta: {data['has_position']}\")
    if data['positions']:
        pos = data['positions'][0]
        print(f\"  {pos['symbol']}: P&L = {pos['pnl']:.2f} ({pos['pnl_percentage']:.2f}%)\")
"
```

## 🎯 Estratégias de Gestão

### Trailing Stop
- **Ativação**: Assim que posição entra em lucro
- **Distância**: 1.5% do preço máximo (configurável)
- **Movimento**: Apenas para cima (BUY) ou para baixo (SELL)
- **Objetivo**: Proteger lucros deixando posição correr

### Breakeven
- **Ativação**: Quando lucro atinge 0.3% (configurável)
- **Ação**: Move stop para preço de entrada + 1 ponto
- **Objetivo**: Garantir que trade não vire prejuízo
- **Prioridade**: Executa antes do trailing stop

### Saídas Parciais (Opcional)
- **Níveis**: Configuráveis (ex: 1%, 2%, 3% de lucro)
- **Quantidade**: Percentual da posição (ex: 33%, 50%)
- **Objetivo**: Realizar lucros gradualmente

## 📈 Fluxo de Operação

1. **Abertura de Posição**
   - Sistema envia ordem OCO (entrada + stop + take)
   - Position Monitor registra a posição
   - Position Manager inicia gestão ativa

2. **Durante a Posição**
   - Monitor atualiza P&L a cada segundo
   - Manager verifica condições de breakeven
   - Se em lucro, trailing stop é ativado
   - Status salvo em JSON continuamente

3. **Fechamento**
   - Por Stop Loss / Take Profit / Manual
   - Monitor detecta e registra P&L final
   - Manager limpa estado de gestão
   - Métricas atualizadas no sistema

## ⚠️ Avisos Importantes

1. **Trailing Stop**: Só funciona se broker suportar modificação de ordens
2. **Breakeven**: Tem prioridade sobre trailing stop
3. **Sincronização**: Sistema verifica consistência a cada 10 segundos
4. **Vencimento**: Sistema avisa quando contrato está próximo do vencimento

## 🐛 Troubleshooting

### Position Monitor não detecta posição
```bash
# Verificar se connection manager está funcionando
python -c "
from src.connection_manager_oco import ConnectionManagerOCO
conn = ConnectionManagerOCO('ProfitDLL64.dll')
print(conn.check_position_exists('WDOQ25'))
"
```

### Trailing Stop não está funcionando
- Verificar logs: `grep TRAILING logs/*.log`
- Confirmar que `trailing_stop_enabled=True`
- Verificar se posição está em lucro

### Status file não atualiza
- Verificar se diretório existe: `mkdir -p data/monitor`
- Verificar permissões de escrita
- Checar logs para erros

## 📊 Métricas

O sistema coleta automaticamente:
- Total de trades
- Taxa de acerto (wins/losses)
- P&L total
- Máximo drawdown
- Trades bloqueados por segurança

Acessar métricas:
```python
# Durante execução
self.metrics['total_pnl']
self.metrics['wins']
self.metrics['losses']
```

## 🔄 Próximas Melhorias

- [ ] Dashboard web para visualização
- [ ] Alertas via Telegram/Discord
- [ ] Histórico de posições em banco de dados
- [ ] Machine Learning para otimizar trailing stop
- [ ] Suporte a múltiplos símbolos simultâneos

---

**Desenvolvido para QuantumTrader v2.1** | Última atualização: 25/08/2025