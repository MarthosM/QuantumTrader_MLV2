# 🔧 Troubleshooting Guide

## Resolução de Problemas Comuns

---

## 🚨 Problemas de Inicialização

### Sistema não inicia

#### Sintoma
```
[ERRO] Sistema Enhanced não disponível!
```

#### Soluções
1. **Verificar imports:**
```bash
python -c "import xgboost, lightgbm, numpy, pandas"
```

2. **Reinstalar dependências:**
```bash
pip install -r requirements.txt --force-reinstall
```

3. **Verificar estrutura de pastas:**
```bash
# Deve existir:
core/
src/
models/
data/
logs/
```

### Erro de conexão ProfitDLL

#### Sintoma
```
[ERRO] Falha ao conectar com ProfitDLL
```

#### Soluções
1. **Profit Chart está aberto?**
2. **Chave correta em `.env.production`?**
3. **Porta 9995 livre?**
```bash
netstat -an | findstr 9995
```

4. **Testar conexão:**
```python
from src.connection_manager_v4 import ConnectionManagerV4
cm = ConnectionManagerV4()
print(cm.connected)
```

---

## 📊 Problemas de Features

### Features retornando 0 ou NaN

#### Sintoma
```
[DEBUG] Features calculadas: 0
```

#### Soluções
1. **Aguardar buffers encherem:**
   - Mínimo 200 candles
   - Mínimo 100 snapshots de book

2. **Verificar callbacks:**
```python
# Adicionar em start_production_65features.py
logger.debug(f"Callbacks recebidos: {self.enhanced_callbacks}")
```

3. **Mercado fechado:**
   - Sem dados fora do horário de pregão
   - Usar dados históricos para teste

### Latência alta (>10ms)

#### Sintoma
```
[AVISO] Latência de features: 15.3ms
```

#### Soluções
1. **Reduzir buffer sizes:**
```env
FEATURE_BUFFER_SIZE=100
BOOK_BUFFER_SIZE=50
```

2. **Desabilitar features complexas:**
```python
# Comentar em book_features_rt.py
# features.update(self._calculate_microstructure_features())
```

3. **Verificar CPU:**
```bash
# Windows
wmic cpu get loadpercentage

# Linux
top -bn1 | grep "Cpu(s)"
```

---

## 🤖 Problemas dos Agentes HMARL

### HMARL não inicializa

#### Sintoma
```
[AVISO] Continuando sem HMARL - apenas ML será usado
```

#### Soluções
1. **Instalar dependências:**
```bash
pip install pyzmq msgpack lz4
```

2. **Verificar porta ZMQ:**
```bash
netstat -an | findstr 5559
```

3. **Modo fallback (só ML):**
   - Sistema funciona sem HMARL
   - Performance pode ser reduzida

### Agentes com baixa confiança

#### Sintoma
```
Todos os agentes < 50% confiança
```

#### Soluções
1. **Ajustar thresholds:**
```json
// config_production.json
"agents": {
  "min_confidence": 0.40
}
```

2. **Verificar features necessárias:**
   - Cada agente precisa de features específicas
   - Ver HMARL_GUIDE.md

---

## 💾 Problemas de Dados

### Não está gravando book/tick

#### Sintoma
```
Book records: 0
Tick records: 0
```

#### Soluções
1. **Verificar configuração:**
```env
ENABLE_DATA_RECORDING=true
```

2. **Permissões de escrita:**
```bash
# Windows
icacls data /grant Everyone:F

# Linux
chmod 777 data/
```

3. **Espaço em disco:**
```bash
# Windows
dir data

# Linux
df -h data/
```

### Arquivos CSV corrompidos

#### Soluções
1. **Validar CSV:**
```python
import pandas as pd
df = pd.read_csv('data/book_tick_data/book_data_*.csv')
print(df.info())
```

2. **Limpar e recriar:**
```bash
rm data/book_tick_data/*.csv
```

---

## 📈 Problemas de Performance

### Sistema usando muita CPU

#### Sintoma
```
CPU > 50% constantemente
```

#### Soluções
1. **Aumentar sleep no loop:**
```python
# start_production_65features.py
time.sleep(2)  # Aumentar de 1 para 2
```

2. **Reduzir frequência de logs:**
```env
LOG_LEVEL=WARNING
```

3. **Desabilitar monitor:**
   - Não abrir monitor_console_enhanced.py

### Memória crescendo (memory leak)

#### Sintoma
```
RAM usage aumentando constantemente
```

#### Soluções
1. **Limitar buffers:**
```python
# circular_buffer.py
self.buffer = deque(maxlen=50)  # Reduzir
```

2. **Garbage collection:**
```python
import gc
gc.collect()  # Adicionar no loop principal
```

3. **Reiniciar periodicamente:**
```bash
# Cron/Task Scheduler
0 */6 * * * python stop_production.py && python start_production_65features.py
```

---

## 🔴 Erros Críticos

### Sistema trava completamente

#### Soluções
1. **Kill processo:**
```bash
# Windows
taskkill /F /IM python.exe

# Linux
pkill -9 python
```

2. **Limpar PID:**
```bash
rm quantum_trader.pid
```

3. **Reiniciar limpo:**
```bash
python stop_production.py
python core/start_production_65features.py
```

### Perda de dados

#### Prevenção
1. **Backup automático:**
```bash
# Adicionar ao cron
0 * * * * cp -r data/ backups/data_$(date +%Y%m%d_%H%M%S)/
```

2. **Verificação de integridade:**
```python
# validate_data.py
import hashlib
def check_file(path):
    return hashlib.md5(open(path,'rb').read()).hexdigest()
```

---

## 📊 Monitor Console

### Monitor não atualiza

#### Soluções
1. **Verificar arquivo de métricas:**
```bash
ls -la metrics/current_metrics.json
```

2. **Executar manualmente:**
```bash
python core/monitor_console_enhanced.py
```

### Cores não aparecem

#### Soluções
1. **Instalar colorama:**
```bash
pip install colorama
```

2. **Terminal compatível:**
   - Windows: Use Windows Terminal
   - Linux: Qualquer terminal moderno

---

## 🔍 Debug Avançado

### Habilitar modo debug

```python
# .env.production
LOG_LEVEL=DEBUG
```

### Logs detalhados

```python
# start_production_65features.py
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(filename)s:%(lineno)d'
)
```

### Profiling

```python
import cProfile
profiler = cProfile.Profile()
profiler.enable()
# ... código ...
profiler.disable()
profiler.print_stats()
```

### Verificar threads

```python
import threading
print(f"Threads ativas: {threading.active_count()}")
for thread in threading.enumerate():
    print(f"  - {thread.name}")
```

---

## 💡 Dicas Gerais

1. **Sempre verifique logs primeiro**
2. **Teste componentes isoladamente**
3. **Mantenha backups regulares**
4. **Documente mudanças de configuração**
5. **Monitore recursos do sistema**

## 📞 Quando Tudo Falhar

1. **Resetar completamente:**
```bash
# Backup dados importantes
cp -r data/ data_backup/

# Limpar tudo
rm -rf logs/* data/* *.pid

# Reinstalar
pip install -r requirements.txt --upgrade

# Reiniciar
python core/start_production_65features.py
```

2. **Verificar versão Python:**
```bash
python --version  # Deve ser 3.8+
```

3. **Sistema operacional:**
   - Windows: Executar como Administrador
   - Linux: Verificar permissões

---

**Lembre-se: A maioria dos problemas está nos logs! Sempre verifique `logs/production_*.log` primeiro.**