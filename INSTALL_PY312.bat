@echo off
echo ================================================================================
echo      INSTALACAO PARA PYTHON 3.12 - QUANTUM TRADER PRODUCTION
echo ================================================================================
echo.

cd /d C:\Users\marth\OneDrive\Programacao\Python\QuantumTrader_Production

REM Verificar versão do Python
echo Verificando versao do Python...
python --version
echo.

REM Ativar ambiente virtual
if exist venv\Scripts\activate (
    call venv\Scripts\activate
) else (
    echo [ERRO] Ambiente virtual nao encontrado!
    pause
    exit /b 1
)

echo ================================================================================
echo [1/4] Atualizando pip, setuptools e wheel...
echo ================================================================================
python -m pip install --upgrade pip setuptools wheel

echo.
echo ================================================================================
echo [2/4] Instalando pacotes essenciais compatíveis com Python 3.12...
echo ================================================================================

REM Instalar numpy primeiro (versão compatível com Python 3.12)
echo Instalando numpy (compativel com Python 3.12)...
pip install numpy>=1.26.0

echo.
echo Instalando pandas e scipy...
pip install pandas>=2.1.0 scipy>=1.11.3

echo.
echo ================================================================================
echo [3/4] Instalando pacotes de Machine Learning...
echo ================================================================================
pip install scikit-learn>=1.3.2
pip install xgboost>=2.0.0
pip install lightgbm>=4.1.0

echo.
echo ================================================================================
echo [4/4] Instalando utilitarios e comunicacao...
echo ================================================================================
pip install python-dotenv colorama psutil
pip install pyzmq msgpack lz4

echo.
echo ================================================================================
echo         VERIFICANDO INSTALACAO...
echo ================================================================================
echo.
python -c "import numpy; print(f'[OK] numpy {numpy.__version__}')"
python -c "import pandas; print(f'[OK] pandas {pandas.__version__}')"
python -c "import sklearn; print(f'[OK] scikit-learn {sklearn.__version__}')"
python -c "import xgboost; print(f'[OK] xgboost {xgboost.__version__}')"
python -c "import lightgbm; print(f'[OK] lightgbm {lightgbm.__version__}')"

echo.
echo ================================================================================
echo         INSTALACAO CONCLUIDA!
echo ================================================================================
echo.
echo IMPORTANTE: Use requirements_py312.txt para Python 3.12
echo.
echo Para iniciar o sistema:
echo   START_SYSTEM.bat
echo.
pause