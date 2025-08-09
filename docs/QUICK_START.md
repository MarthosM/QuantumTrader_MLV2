# ⚡ Quick Start Guide

## Iniciar o Sistema em 5 Minutos

---

## 📋 Pré-requisitos

- Python 3.8 ou superior
- Profit Chart instalado
- Windows 10/11 (ou Linux/Mac)
- 4GB RAM mínimo
- Conexão com internet

## 🚀 Instalação Rápida

### 1️⃣ Criar Ambiente Virtual

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

### 2️⃣ Instalar Dependências

```bash
pip install -r requirements.txt
```

### 3️⃣ Configurar Sistema

Edite `.env.production`:
```env
# ESSENCIAL - Sua chave do Profit
PROFIT_KEY=sua_chave_aqui

# Símbolo para trading
TRADING_SYMBOL=WDOU25

# Opcional - Ajustar se necessário
MIN_CONFIDENCE=0.60
MAX_DAILY_TRADES=10
```

### 4️⃣ Iniciar Sistema

**Windows:**
```cmd
START_SYSTEM.bat
```

**Linux/Mac:**
```bash
./start_system.sh
```

## ✅ Verificação

Você verá 2 janelas:

### Janela Principal
```
================================================================================
                    QUANTUM TRADER PRODUCTION SYSTEM
                  65 Features + 4 HMARL Agents + ML Models
================================================================================
[OK] Sistema Enhanced inicializado (65 features)
[OK] Gravação de dados book/tick habilitada
[INFO] Loop de trading rodando...
```

### Janela do Monitor
```
════════════════════════════════════════════════
       QUANTUM TRADER ML - ENHANCED MONITOR
════════════════════════════════════════════════
╔════════════════════════════════════════════╗
║        📊 65 FEATURES MONITOR              ║
╠════════════════════════════════════════════╣
║ Volatility (10)    vol_5:0.015 ...         ║
║ Returns (10)       ret_1:-0.002 ...        ║
║ Order Flow (8)     ofi_5:0.234 ...         ║
╚════════════════════════════════════════════╝
```

## 🎯 Comandos Essenciais

### Parar Sistema
```bash
python stop_production.py
```

### Ver Apenas Monitor
```bash
python core/monitor_console_enhanced.py
```

### Verificar Status
```bash
# Windows
type logs\production_*.log | findstr "STATUS"

# Linux/Mac
tail -f logs/production_*.log | grep "STATUS"
```

## ⚠️ Troubleshooting Rápido

### "Sistema não inicia"
- ✅ Profit Chart está aberto?
- ✅ Chave correta em `.env.production`?
- ✅ Ambiente virtual ativado?

### "Sem dados/features"
- ✅ Mercado está aberto?
- ✅ Símbolo correto configurado?
- ✅ Aguardar 1-2 minutos para buffers

### "Erro de importação"
```bash
pip install -r requirements.txt --upgrade
```

### "Monitor não abre"
Execute manualmente em outro terminal:
```bash
python core/monitor_console_enhanced.py
```

## 📊 Primeiros Passos

1. **Deixe rodar por 30 minutos** para coletar dados
2. **Observe o monitor** para entender o sistema
3. **Verifique logs** para erros ou avisos
4. **Ajuste configurações** conforme necessário

## 🔍 Verificar se Está Funcionando

✅ **Monitor mostra features atualizando**
✅ **Logs mostram "Loop iteração X"**
✅ **Pasta `data/` tem arquivos CSV**
✅ **Sem erros críticos nos logs**

## 💡 Dicas

- Inicie com `MIN_CONFIDENCE=0.70` (mais conservador)
- Use `MAX_DAILY_TRADES=5` no início
- Monitore por 1 semana antes de aumentar limites
- Faça backup diário da pasta `data/`

## 📞 Precisa de Ajuda?

1. Consulte [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Verifique logs em `logs/`
3. Revise configurações em `.env.production`
4. Consulte documentação completa em [README.md](README.md)

---

**Sistema pronto! Bom trading! 🚀**