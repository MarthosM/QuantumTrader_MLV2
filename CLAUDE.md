# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚀 QuantumTrader Production System

This is a **production-ready algorithmic trading system** with 65 microstructure features and 4 HMARL agents.

## 📋 Quick Commands

### Start System
```bash
# Windows
START_SYSTEM.bat

# Linux/Mac
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

## 🏗️ System Architecture

### Core Components
1. **Enhanced Production System** (`core/enhanced_production_system.py`)
   - Manages 65 real-time features
   - Integrates all components
   - Thread-safe data management

2. **Feature Engineering** (`src/features/book_features_rt.py`)
   - 65 microstructure features
   - Latency < 2ms requirement
   - Categories: Volatility(10), Returns(10), OrderFlow(8), Volume(8), Technical(8), Microstructure(15), Temporal(6)

3. **HMARL Agents** (`src/agents/hmarl_agents_enhanced.py`)
   - OrderFlowSpecialist (30% weight)
   - LiquidityAgent (20% weight)
   - TapeReadingAgent (25% weight)
   - FootprintPatternAgent (25% weight)

4. **Consensus System** (`src/consensus/hmarl_consensus_system.py`)
   - ML models: 40% weight
   - HMARL agents: 60% weight
   - Adaptive weight adjustment

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

## 📊 Data Flow

```
ProfitDLL Callbacks
    ↓
Circular Buffers (Thread-Safe)
    ↓
Feature Calculation (65 features)
    ↓
ML Prediction + HMARL Agents
    ↓
Consensus System
    ↓
Trading Decision
```

## 🛡️ Production Safety Rules

### CRITICAL: Data Policy
1. **ALWAYS use real market data** from ProfitDLL
2. **NEVER use mock/synthetic data** in production
3. **System must fail gracefully** when models unavailable
4. **NO random/synthetic predictions** as fallback

### Threading Safety
- All buffers use `threading.RLock()`
- Feature calculation is thread-safe
- No shared mutable state without locks

### Performance Requirements
- Feature calculation: < 10ms (currently ~2ms)
- Memory usage: < 1GB
- CPU usage: < 20%

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

## 🎯 Best Practices

### When Adding Features
1. Add calculation to `book_features_rt.py`
2. Ensure thread-safety
3. Test latency impact
4. Update feature count in docs

### When Modifying Trading Logic
1. Test with `MIN_CONFIDENCE=0.80` first
2. Use paper trading mode
3. Monitor for 24h before going live
4. Keep backup of working version

### When Debugging
1. Check logs first: `logs/production_*.log`
2. Use monitor: `python core/monitor_console_enhanced.py`
3. Verify all components load
4. Test with historical data

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

## 🛠️ Maintenance

### Daily
- Check logs for errors
- Verify win rate > 50%
- Monitor latency < 10ms

### Weekly
- Backup `data/` folder
- Clean old logs > 30 days
- Review trading metrics

### Monthly
- Update ML models if needed
- Review and adjust thresholds
- Performance analysis

## 💡 Important Notes

1. **Market Hours**: System only works when market is open
2. **ProfitChart**: Must be connected for real data
3. **Models**: Add your trained `.pkl` files to `models/`
4. **Buffer Time**: Wait 5-10 minutes after start for buffers to fill

## 🚀 Commands Reference

```bash
# Install dependencies
pip install -r requirements.txt

# Start system
START_SYSTEM.bat

# Stop system
python stop_production.py

# Monitor only
python core/monitor_console_enhanced.py

# Check status
python -c "from pathlib import Path; print('Running' if Path('quantum_trader.pid').exists() else 'Stopped')"
```

---

**This is a production system. Always test changes thoroughly before deploying.**