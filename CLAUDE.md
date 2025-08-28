# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 📚 Important References

### ProfitDLL Manual
- **Location**: `C:\Users\marth\Downloads\ProfitDLL\Manual`
- **Main File**: `Manual - ProfitDLL pt_br.pdf`
- **Version**: 4.0.0.30
- Use this manual as reference when working with ProfitDLL integration and order sending functions

## 🚀 QuantumTrader Production System v2.0 - Sistema Híbrido Completo

This is a **production-ready algorithmic trading system** with:
- 🧠 **3-Layer Hybrid ML System** (Context + Microstructure + Meta-Learner)
- 🤖 **4 HMARL Agents** (OrderFlow, Liquidity, TapeReading, Footprint)
- 📊 **65 Real-time Features** from book and tick data
- 🔄 **Automatic Daily Retraining** with market data
- 📈 **93%+ Accuracy** on microstructure predictions

## 🎯 PRIORIDADE MÁXIMA: Resultados Positivos de Trading

### Princípio Fundamental
**TODA mudança no sistema deve priorizar resultados positivos de trading**. Antes de qualquer modificação, perguntar:
1. Isso vai melhorar o Win Rate?
2. Isso vai reduzir drawdown?
3. Isso vai aumentar o lucro líquido?

Se a resposta for "não" ou "incerto", reconsiderar a mudança.

### Decisões de Desenvolvimento
Ao escolher entre opções, sempre preferir:
- **Rapidez vs Perfeição**: Sistema funcionando hoje > Sistema perfeito amanhã
- **Testado vs Novo**: Código validado > Código experimental  
- **Simples vs Complexo**: Solução simples que funciona > Solução complexa teórica
- **Dados Reais vs Simulados**: Sempre usar dados reais do mercado

### Exemplo Prático: ML Features Incompatíveis
- **Problema**: Modelos ML treinados com features diferentes das geradas
- **Opção 1**: Retreinar modelos (2-5 dias, resultado incerto)
- **Opção 2**: Ajustar código para gerar features corretas (2 horas, modelos validados)
- **Decisão**: Opção 2 - Sistema operacional hoje com modelos já testados

## 🔍 Development Rules

### CRITICAL: Missing Module Policy
1. **When a module/file is missing during development**:
   - FIRST search in the original project folder: `C:\Users\marth\OneDrive\Programacao\Python\Projetos\QuantumTrader_ML`
   - Copy the module from the original if found
   - Only create new if not found in original
2. **During import errors**:
   - Check the original project structure first
   - Maintain consistency with original architecture
3. **When developing new features**:
   - Reference original implementations
   - Preserve original design patterns

### IMPORTANT: New Development Policy
1. **When creating NEW features or updating existing ones**:
   - Do NOT search in the original project for new modules
   - Create/update modules directly in this project
   - New modules won't exist in the original project
2. **Differentiate between**:
   - Missing EXISTING modules → Search in original first
   - NEW modules being developed → Create directly here
3. **Examples**:
   - Import error for existing feature → Check original
   - Creating new analysis tool → Build new module
   - Adding new strategy → Create without checking original

## 📋 Quick Commands

### Start System
```bash
# Sistema completo com ML + HMARL + Re-treinamento
python START_HYBRID_COMPLETE.py

# Com dashboard HTML
python start_hybrid_system.py --dashboard

# Modo teste (limita trades)
python start_hybrid_system.py --test

# Sem re-treinamento automático
python start_hybrid_system.py --no-training
```

### Train Models
```bash
# Treinar sistema híbrido completo (3 camadas)
python train_hybrid_pipeline.py

# Treinar modelos básicos (não recomendado)
python train_wdo_models.py
```

### Start Legacy System
```bash
# Windows (sistema antigo)
START_SYSTEM.bat

# Linux/Mac (sistema antigo)
./start_system.sh
```

### Stop System
```bash
python stop_production.py
```

### Monitor Only
```bash
python core/monitor_console_enhanced.py
```

### Trading & Testing Commands
```bash
# Verificar configuração de trading
python test_trading_config.py

# Reiniciar com trading real (Windows)
RESTART_REAL_TRADING.bat

# Testar sistema de re-treinamento
python test_retraining.py

# Verificar configurações de re-treinamento
python test_retraining_config.py

# Forçar re-treinamento manual
python -c "from src.training.smart_retraining_system import SmartRetrainingSystem; s = SmartRetrainingSystem(min_hours=8.0); s.run_retraining_pipeline(force=True)"

# Verificar modelo atual
python -c "from src.training.model_selector import ModelSelector; s = ModelSelector(); m = s.get_current_best_model(); print(m)"

# Forçar re-avaliação de modelos
python src/training/model_selector.py

# Testar seleção de modelos
python test_model_selection.py
```

### Project Board
```bash
# Windows - Interactive menu
PROJECT_BOARD.bat

# View project status
python view_project_board.py

# View detailed status
python view_project_board.py --detailed

# Start Project Board server
python start_project_board.py
```

## 🏗️ System Architecture v2.0 - Hybrid System

### NEW: Hybrid Production System (`hybrid_production_system.py`) ⭐
**This is the MAIN SYSTEM - Use this for production**
- 3-layer ML architecture (Context + Microstructure + Meta-Learner)
- Real-time integration with HMARL agents
- Automatic daily retraining at 18:30
- Continuous data collection for training
- Model validation and rollback system
- Performance monitoring and alerts

### Core Components

#### 1. **Hybrid ML Models** (NEW)
- **Layer 1 - Context Models** (Tick Data)
  - Regime Detector (73% accuracy)
  - Volatility Forecaster (74% accuracy)
  - Session Classifier (74% accuracy)
- **Layer 2 - Microstructure Models** (Book Data)
  - Order Flow Analyzer (95% accuracy) ⭐
  - Book Dynamics Model (90% accuracy)
- **Layer 3 - Meta-Learner**
  - Combines all predictions (94% accuracy)

#### 2. **Feature Engineering** (`src/features/book_features_rt.py`)
- 65 microstructure features
- Latency < 2ms requirement
- Categories: Volatility(10), Returns(10), OrderFlow(8), Volume(8), Technical(8), Microstructure(15), Temporal(6)

#### 3. **HMARL Agents** (`src/agents/hmarl_agents_enhanced.py`)
- OrderFlowSpecialist (30% weight)
- LiquidityAgent (20% weight)
- TapeReadingAgent (25% weight)
- FootprintPatternAgent (25% weight)

#### 4. **Consensus System** (UPDATED)
- ML models: 60% weight (increased from 40%)
- HMARL agents: 40% weight (decreased from 60%)
- Adaptive weight adjustment based on performance

## 🔧 Critical Configuration

### Environment Variables (.env.production)
```env
# ESSENTIAL
PROFIT_KEY=your_key_here        # ProfitChart key
TRADING_SYMBOL=WDOU25           # Trading symbol

# RISK MANAGEMENT
MIN_CONFIDENCE=0.60             # Minimum confidence for trades
MAX_DAILY_TRADES=10             # Daily trade limit
STOP_LOSS=0.005                 # 0.5% stop loss
TAKE_PROFIT=0.010               # 1% take profit

# SYSTEM
ENABLE_DATA_RECORDING=true      # Record book/tick data
LOG_LEVEL=INFO                  # Logging level
```

## 📊 Data Flow v2.0 - Hybrid System

```
ProfitDLL Callbacks (Book + Tick)
    ↓
Circular Buffers (Thread-Safe)
    ↓
Feature Calculation
    ├── Context Features (from Tick)
    └── Microstructure Features (from Book)
    ↓
3-Layer ML Prediction
    ├── Layer 1: Context Analysis (Regime/Volatility)
    ├── Layer 2: Microstructure Analysis (OrderFlow/Dynamics)
    └── Layer 3: Meta-Learner (Final Decision)
    ↓
HMARL Agents Consensus
    ↓
Final Weighted Decision (60% ML + 40% HMARL)
    ↓
Trading Execution
    ↓
Data Collection for Daily Retraining
```

## 🛡️ Production Safety Rules

### CRITICAL: Git Commit Policy
1. **NEVER commit automatically** without explicit user request
2. **ONLY commit when user explicitly says**: "commit", "faça commit", "git commit"
3. **ALWAYS wait for user approval** before pushing to repository
4. **NO automatic commits** after code changes

### CRITICAL: Data Policy
1. **ALWAYS use real market data** from ProfitDLL
2. **NEVER use mock/synthetic data** - nem mesmo para inicialização
3. **System must wait for real data** - não operar sem dados reais
4. **NO random/synthetic predictions** - nunca gerar sinais de teste
5. **Abort trades without real prices** - cancelar se não há preço real do mercado
6. **System must fail gracefully** when models unavailable

### Threading Safety
- All buffers use `threading.RLock()`
- Feature calculation is thread-safe
- No shared mutable state without locks

### Performance Requirements
- Feature calculation: < 10ms (currently ~2ms)
- Memory usage: < 1GB
- CPU usage: < 20%

## 📊 Project Board (MCP Memory Server)

O sistema inclui um **Project Board** baseado em MCP (Model Context Protocol) que mantém o status de cada fase do projeto, permitindo tracking completo do desenvolvimento, testes e deployment.

### Visualizar Status do Projeto
```bash
# Menu interativo (Windows)
PROJECT_BOARD.bat

# Visualizar board completo
python view_project_board.py

# Visualizar com detalhes
python view_project_board.py --detailed

# Apenas itens críticos
python view_project_board.py --section critical

# Próximos passos recomendados
python view_project_board.py --section next

# Exportar para JSON
python view_project_board.py --export board_status.json
```

### Fases do Projeto Monitoradas

1. **Infrastructure** - Sistema base e configuração
2. **Feature Engineering** - 65 features de microestrutura
3. **ML Models** - Modelos de machine learning
4. **HMARL Agents** - 4 agentes especializados
5. **Consensus System** - Sistema de consenso ML+HMARL
6. **Risk Management** - Gestão de risco e limites
7. **Monitoring** - Monitoramento em tempo real
8. **MCP Integration** - Integração com Model Context Protocol
9. **Production Deployment** - Deploy final em produção

### Iniciar Serviços do Board

```bash
# Iniciar servidor MCP (requer mcp[cli])
python start_project_board.py --mode server

# Iniciar integração com monitoramento automático
python start_project_board.py --mode integration

# Iniciar ambos
python start_project_board.py --mode both
```

### Estrutura do Board

```
src/mcp/
├── project_board_server.py   # Servidor MCP principal
├── board_integration.py       # Integração com sistema de trading
└── memory_server.py          # Servidor de memória para trading insights
```

### Status Visual

- **[OK]** ou ✅ - Fase completada
- **[>>]** ou 🔄 - Em progresso
- **[T]** ou 🧪 - Em testes
- **[X]** ou 🚫 - Bloqueada
- **[.]** ou ⏸️ - Não iniciada
- **[!]** ou ❌ - Falhou

### Métricas Monitoradas

- Progresso geral do projeto (%)
- Status de cada componente
- Tarefas abertas e prioridades
- Issues e bloqueios
- Métricas de performance
- Histórico de deployments

## 🔍 Debugging

### Enable Debug Mode
```env
LOG_LEVEL=DEBUG
```

### Key Log Messages
- `"Features calculadas: 65"` - System working correctly
- `"Loop iteração X"` - Main loop running
- `"HMARL não disponível"` - Running ML-only mode (acceptable)
- `"Erro ao calcular features"` - Critical issue

### Health Check
```python
# Check system components
python -c "
from core.enhanced_production_system import EnhancedProductionSystem
system = EnhancedProductionSystem()
print(f'System initialized: {system is not None}')
"
```

## 📈 Performance Optimization

### If Latency > 10ms
1. Reduce buffer sizes in `.env.production`
2. Disable complex features temporarily
3. Check CPU usage with Task Manager

### If Memory > 1GB
1. Reduce `FEATURE_BUFFER_SIZE`
2. Enable garbage collection
3. Restart system every 6 hours

## 🚨 Common Issues

### "No features calculated"
- Wait for 200+ candles to fill buffers
- Check if market is open
- Verify ProfitDLL connection

### "HMARL not available"
- This is OK - system works with ML only
- Check if pyzmq, msgpack, lz4 are installed

### "High CPU usage"
- Increase sleep time in main loop
- Reduce log level to WARNING
- Disable monitor if not needed

## 📁 Project Structure

```
QuantumTrader_Production/
├── core/                # Main scripts
│   ├── enhanced_production_system.py
│   ├── start_production_65features.py
│   └── monitor_console_enhanced.py
├── src/                 # Source modules
│   ├── features/       # Feature engineering
│   ├── agents/         # HMARL agents
│   ├── consensus/      # Consensus system
│   ├── buffers/        # Circular buffers
│   ├── metrics/        # Metrics & alerts
│   └── logging/        # Structured logging
├── models/             # ML models (.pkl files)
├── data/               # Collected data
├── logs/               # System logs
└── docs/               # Documentation
```

## 🚀 Training Pipeline v2.0

### Initial Training (One-time)
```bash
# Train complete hybrid system with book + tick data
python train_hybrid_pipeline.py

# This creates:
# - models/hybrid/context/*.pkl (3 models)
# - models/hybrid/microstructure/*.pkl (2 models)
# - models/hybrid/meta_learner/*.pkl (1 model)
```

### Daily Retraining (Automatic)
The system automatically retrains daily at 18:30 with collected market data:
- Collects data continuously during trading
- Validates new models before deployment (>70% accuracy required)
- Automatic backup and rollback on failure
- Keeps 7 days of training data

### Manual Retraining
```bash
# Force immediate retraining
python train_hybrid_pipeline.py

# Analyze collected book data
python analyze_book_data.py
```

## 🎯 Best Practices

### When Starting the System
1. Ensure models are trained: `python train_hybrid_pipeline.py`
2. Start with test mode: `python start_hybrid_system.py --test`
3. Monitor initial predictions for 30 minutes
4. Enable live trading only after validation

### When Adding Features
1. Add calculation to `book_features_rt.py`
2. Ensure thread-safety
3. Test latency impact
4. Update feature count in docs
5. Retrain models with new features

### When Modifying Trading Logic
1. Test with `MIN_CONFIDENCE=0.80` first
2. Use paper trading mode
3. Monitor for 24h before going live
4. Keep backup of working version

### When Debugging
1. Check logs first: `logs/hybrid_production_*.log`
2. Use monitor: `python core/monitor_console_enhanced.py`
3. Verify all components load
4. Test with historical data
5. Check model versions in `models/hybrid/config.json`

## 📞 Key Files to Check

1. **Logs**: `logs/production_YYYYMMDD.log`
2. **Metrics**: `metrics/current_metrics.json`
3. **Data**: `data/book_tick_data/*.csv`
4. **Config**: `.env.production`, `config_production.json`

## 🔐 Security

- Never commit `.env.production` with real keys
- Use environment variables for sensitive data
- Validate all external inputs
- Implement rate limiting for API calls

## 📊 Expected Performance

- **Latency**: < 2ms per feature calculation
- **Throughput**: 600+ features/second
- **Win Rate**: 55-65%
- **Sharpe Ratio**: 1.5-2.5
- **Max Drawdown**: < 10%

## 🚨 Trading Real - IMPORTANTE

### Ativação do Trading Real
Para ativar o envio de ordens reais ao mercado:

1. **Editar `.env.production`**:
   ```
   ENABLE_TRADING=true  # Mudar de false para true
   ```

2. **Reiniciar o sistema** (OBRIGATÓRIO):
   ```bash
   # Parar sistema atual
   python stop_production.py
   
   # Reiniciar com trading real
   python START_HYBRID_COMPLETE.py
   # ou
   RESTART_REAL_TRADING.bat
   ```

3. **Verificar no console**:
   - Procure por: `[OK] Trading ATIVO - Confiança mínima: 60%`
   - Quando executar ordem: `[REAL] Ordem enviada com sucesso! OrderID: XXX`

⚠️ **ATENÇÃO**: Com `ENABLE_TRADING=true`, as ordens serão enviadas REALMENTE ao mercado!

## 🔄 Re-treinamento Automático Inteligente

### Configurações Atuais
- **Horário**: 18:40 (após fechamento do mercado às 18:00)
- **Dados mínimos**: 8 horas contínuas
- **Amostras mínimas**: 5000
- **Período de dados**: Apenas horário de trading (9:00-18:00)

### Sistema de Validação
O re-treinamento só ocorre se TODOS os critérios forem atendidos:
1. ✅ Mínimo de 8 horas de dados contínuos
2. ✅ Mínimo de 5000 amostras
3. ✅ Dados com variância adequada
4. ✅ Classes balanceadas
5. ✅ Apenas dados do horário de trading

### Fluxo de Re-treinamento
```
18:00 - Mercado fecha
18:40 - Inicia validação de dados
      ↓
[Validação aprovada?]
   Sim → Treina novos modelos → Recarrega automaticamente
   Não → Mantém modelos atuais → Log do motivo
```

## 🎯 Seleção Automática de Modelos

### ModelSelector
Sistema inteligente que escolhe o melhor modelo disponível:

- **Avaliação**: Testa modelos com dados das últimas 24h
- **Métricas**: Accuracy, F1-Score, Precision, Recall
- **Penalização**: Modelos antigos recebem penalidade
- **Frequência**: Re-avaliação a cada 24 horas

### Prioridade de Seleção
1. Modelos re-treinados recentes (< 7 dias)
2. Modelos com melhor performance em validação
3. Modelos originais (fallback)

### Arquivos de Controle
- `models/current_model_selection.json` - Modelo atualmente selecionado
- `models/retrained_model_*.pkl` - Modelos re-treinados
- `models/training_report_*.json` - Relatórios de treinamento

## 🛠️ Maintenance

### Daily
- Check logs for errors
- Verify win rate > 50%
- Monitor latency < 10ms
- Verificar se re-treinamento foi executado (18:40)

### Weekly
- Backup `data/` folder
- Clean old logs > 30 days
- Review trading metrics
- Verificar performance dos modelos re-treinados

### Monthly
- Review and adjust thresholds
- Performance analysis
- Limpar modelos antigos (> 30 dias)

## 🧹 System Cleanup & Maintenance

### Files to Remove Periodically

#### Obsolete/Deprecated Files
```bash
# Remove old development files
rm -f src/production_old.py
rm -f src/production_v1.py
rm -f src/production_backup*.py
rm -f core/start_production_old.py
rm -f core/*_deprecated.py
rm -f core/*_backup.py

# Remove test/development artifacts
rm -rf test_*.py
rm -rf *_test.py
rm -rf __pycache__/
rm -rf .pytest_cache/
rm -rf .coverage
rm -rf htmlcov/

# Remove temporary files
rm -f *.tmp
rm -f *.swp
rm -f *~
rm -f .DS_Store
rm -f Thumbs.db
```

#### Log Cleanup (Keep Last 30 Days)
```bash
# Windows PowerShell
Get-ChildItem -Path "logs" -Filter "*.log" | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-30)} | Remove-Item

# Linux/Mac
find logs/ -name "*.log" -mtime +30 -delete
find logs/ -name "*.jsonl" -mtime +30 -delete
```

#### Data Cleanup (Archive Old Data)
```bash
# Archive old trading data (keep last 90 days)
python -c "
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

data_dir = Path('data/book_tick_data')
archive_dir = Path('data/archive')
archive_dir.mkdir(exist_ok=True)

cutoff_date = datetime.now() - timedelta(days=90)

for file in data_dir.glob('*.csv'):
    file_date = datetime.fromtimestamp(file.stat().st_mtime)
    if file_date < cutoff_date:
        shutil.move(str(file), str(archive_dir / file.name))
        print(f'Archived: {file.name}')
"
```

### Automated Cleanup Script
Create `cleanup.py`:
```python
#!/usr/bin/env python3
"""
System cleanup script - Run weekly
"""
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_system():
    """Complete system cleanup"""
    
    # 1. Remove Python cache
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            shutil.rmtree(os.path.join(root, '__pycache__'))
            print(f'Removed: {root}/__pycache__')
    
    # 2. Clean old logs (30+ days)
    log_dir = Path('logs')
    cutoff = datetime.now() - timedelta(days=30)
    for log_file in log_dir.glob('*.log'):
        if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff:
            log_file.unlink()
            print(f'Removed old log: {log_file.name}')
    
    # 3. Clean temporary files
    patterns = ['*.tmp', '*.swp', '*~', '*.bak']
    for pattern in patterns:
        for temp_file in Path('.').rglob(pattern):
            temp_file.unlink()
            print(f'Removed temp: {temp_file}')
    
    # 4. Compress old data files
    data_dir = Path('data/book_tick_data')
    for csv_file in data_dir.glob('*.csv'):
        if csv_file.stat().st_size > 100_000_000:  # 100MB
            # Compress large files
            import gzip
            with open(csv_file, 'rb') as f_in:
                with gzip.open(f'{csv_file}.gz', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            csv_file.unlink()
            print(f'Compressed: {csv_file.name}')
    
    # 5. Clean backups older than 7 days
    backup_dir = Path('backups')
    if backup_dir.exists():
        cutoff = datetime.now() - timedelta(days=7)
        for backup in backup_dir.glob('*.json'):
            if datetime.fromtimestamp(backup.stat().st_mtime) < cutoff:
                backup.unlink()
                print(f'Removed old backup: {backup.name}')
    
    print('Cleanup completed!')

if __name__ == '__main__':
    cleanup_system()
```

### Files to NEVER Delete
```
IMPORTANT - PRESERVE THESE FILES:
├── models/*.pkl              # Trained ML models
├── .env.production          # Production configuration
├── config_production.json   # System configuration
├── src/                     # All source code
├── core/                    # All core scripts
├── requirements.txt         # Dependencies
└── CLAUDE.md               # This file
```

### Obsolete Modules to Remove
If you find any of these old modules, they can be safely deleted:
- `src/production_old.py`
- `src/production_v1.py`
- `src/start_hmarl_old.py`
- `src/agents/base_agent_old.py`
- `src/agents/*_deprecated.py`
- `core/start_production_old.py`
- `core/monitor_old.py`
- Any file with `_backup`, `_old`, `_deprecated` suffix

### Database/Cache Cleanup
```bash
# Clear Redis/Valkey cache if using
redis-cli FLUSHDB

# Clear system cache
python -c "
import shutil
cache_dirs = ['.cache', 'cache', '__pycache__']
for dir in cache_dirs:
    if Path(dir).exists():
        shutil.rmtree(dir)
        print(f'Cleared: {dir}')
"
```

### Git Repository Cleanup
```bash
# Remove untracked files (careful!)
git clean -n  # Dry run first
git clean -f  # Actually remove

# Clean git history (reduce size)
git gc --aggressive --prune=now

# Remove large files from history (if needed)
# Use BFG Repo-Cleaner or git filter-branch
```

### Schedule Cleanup
Add to crontab (Linux) or Task Scheduler (Windows):
```bash
# Weekly cleanup - Sunday 3 AM
0 3 * * 0 cd /path/to/QuantumTrader && python cleanup.py

# Daily log rotation
0 0 * * * find /path/to/QuantumTrader/logs -name "*.log" -mtime +30 -delete
```

## 🎯 NEXT STEPS - TODO LIST

### Phase 1: Testing & Validation ⏳
- [ ] Test hybrid system with live market data (paper trading)
- [ ] Validate predictions accuracy in real-time
- [ ] Fine-tune confidence thresholds based on results
- [ ] Test automatic daily retraining cycle
- [ ] Validate model rollback mechanism

### Phase 2: Production Deployment 🚀
- [ ] Run 1 week paper trading with full monitoring
- [ ] Analyze win rate and drawdown metrics
- [ ] Implement Telegram/Discord alerts for trades
- [ ] Add position sizing based on Kelly Criterion
- [ ] Create backup and disaster recovery plan

### Phase 3: Optimization 📈
- [ ] Collect 100k+ book data records for better training
- [ ] Implement ensemble voting with multiple meta-learners
- [ ] Add market regime detection for adaptive strategies
- [ ] Optimize feature engineering for lower latency
- [ ] Implement A/B testing for model versions

### Phase 4: Advanced Features 🔬
- [ ] Add sentiment analysis from news/social media
- [ ] Implement reinforcement learning for position sizing
- [ ] Create multi-timeframe analysis system
- [ ] Add correlation analysis with other assets
- [ ] Implement portfolio optimization

### Phase 5: Scaling 🌍
- [ ] Support multiple symbols simultaneously
- [ ] Implement cloud deployment (AWS/GCP)
- [ ] Add REST API for external monitoring
- [ ] Create mobile app for monitoring
- [ ] Implement distributed training

## 💡 Important Notes

1. **Market Hours**: System only works when market is open (9:00-18:00 BRT)
2. **ProfitDLL Connection**: **NÃO precisa do ProfitChart aberto!** A DLL conecta DIRETAMENTE ao servidor da corretora
3. **Models**: Hybrid models in `models/hybrid/` (train first!)
4. **Buffer Time**: Wait 5-10 minutes after start for buffers to fill
5. **Trading Real**: Sempre verificar `ENABLE_TRADING` em `.env.production` antes de iniciar
6. **Re-treinamento**: Ocorre automaticamente às 18:40 se houver 8h+ de dados contínuos
7. **Seleção de Modelos**: Sistema escolhe automaticamente o melhor modelo disponível
8. **Logs**: Verificar `logs/hybrid_complete_*.log` para detalhes do sistema

## ⚠️ IMPORTANTE: Conexão com ProfitDLL

**O sistema NÃO precisa do ProfitChart aberto para funcionar!**

A ProfitDLL estabelece uma conexão DIRETA e INDEPENDENTE com os servidores da corretora:
- A DLL conecta diretamente em `producao.nelogica.com.br:8184`
- Não é necessário ter o ProfitChart rodando
- A conexão é autônoma e gerenciada pela própria DLL
- Os dados de mercado vêm direto do servidor, não do ProfitChart

### Requisitos para Conexão
1. **ProfitDLL64.dll** presente no diretório do projeto ou em `dll/`
2. **Credenciais válidas** configuradas no `.env.production` (PROFIT_KEY)
3. **Internet ativa** para conectar ao servidor
4. **Mercado aberto** (9h-18h dias úteis) para receber dados reais

### Troubleshooting de Conexão
Se não estiver recebendo dados (Bid/Ask = 0.00):
1. Verificar se a DLL está no local correto (`dll/ProfitDLL64.dll` ou raiz do projeto)
2. Confirmar credenciais no `.env.production`
3. Verificar logs de conexão para erros de autenticação
4. Confirmar que o mercado está aberto
5. Verificar se o símbolo está correto (WDOU25 para agosto/2025)
6. Testar conexão com script isolado: `python test_profit_connection.py`

## 🚀 Commands Reference

```bash
# Install dependencies
pip install -r requirements.txt

# MAIN COMMANDS (v2.0 - Hybrid System)
# =====================================

# Train hybrid models (required first time)
python train_hybrid_pipeline.py

# Start hybrid production system
python start_hybrid_system.py

# Start with dashboard
python start_hybrid_system.py --dashboard

# Start in test mode
python start_hybrid_system.py --test

# Start without auto-retraining
python start_hybrid_system.py --no-training

# ANALYSIS & MONITORING
# =====================

# Analyze collected book data
python analyze_book_data.py

# Monitor system performance
python core/monitor_console_enhanced.py

# View project board
python view_project_board.py --detailed

# LEGACY COMMANDS (old system)
# =============================

# Start old system
START_SYSTEM.bat

# Stop system
python stop_production.py

# Check status
python -c "from pathlib import Path; print('Running' if Path('quantum_trader.pid').exists() else 'Stopped')"
```

---

**This is a production system. Always test changes thoroughly before deploying.**