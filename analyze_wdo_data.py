#!/usr/bin/env python3
"""
Script para analisar a estrutura dos dados do WDO antes do treinamento
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def analyze_wdo_data():
    """Analisa estrutura e conteúdo do arquivo WDO"""
    
    data_path = Path(r"C:\Users\marth\Downloads\WDO_FUT\WDOFUT_BMF_T.csv")
    
    logger.info(f"Analisando arquivo: {data_path}")
    logger.info(f"Tamanho do arquivo: {data_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    # Ler apenas primeiras linhas para análise
    logger.info("\n=== Analisando primeiras 1000 linhas ===")
    
    # Tentar diferentes encodings
    for encoding in ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']:
        try:
            df_sample = pd.read_csv(data_path, nrows=1000, encoding=encoding)
            logger.info(f"[OK] Arquivo lido com encoding: {encoding}")
            break
        except Exception as e:
            logger.debug(f"Encoding {encoding} falhou: {e}")
            continue
    
    # Mostrar informações básicas
    print("\n=== ESTRUTURA DOS DADOS ===")
    print(f"Shape: {df_sample.shape}")
    print(f"\nColunas ({len(df_sample.columns)}):")
    for i, col in enumerate(df_sample.columns, 1):
        dtype = str(df_sample[col].dtype)
        nulls = df_sample[col].isna().sum()
        unique = df_sample[col].nunique()
        print(f"  {i:2}. {col:30} | Tipo: {dtype:10} | Nulls: {nulls:4} | Únicos: {unique:6}")
    
    print("\n=== PRIMEIRAS 5 LINHAS ===")
    print(df_sample.head())
    
    print("\n=== ÚLTIMAS 5 LINHAS DA AMOSTRA ===")
    print(df_sample.tail())
    
    print("\n=== ESTATÍSTICAS NUMÉRICAS ===")
    print(df_sample.describe())
    
    # Identificar colunas importantes
    print("\n=== ANÁLISE DE COLUNAS ===")
    
    price_cols = []
    volume_cols = []
    time_cols = []
    other_cols = []
    
    for col in df_sample.columns:
        col_lower = col.lower()
        
        # Identificar tipo de coluna
        if any(x in col_lower for x in ['price', 'preco', 'last', 'close', 'open', 'high', 'low']):
            price_cols.append(col)
        elif any(x in col_lower for x in ['volume', 'vol', 'qty', 'quantidade']):
            volume_cols.append(col)
        elif any(x in col_lower for x in ['date', 'data', 'time', 'hora', 'timestamp']):
            time_cols.append(col)
        else:
            other_cols.append(col)
    
    print(f"\nColunas de Preço ({len(price_cols)}): {price_cols}")
    print(f"Colunas de Volume ({len(volume_cols)}): {volume_cols}")
    print(f"Colunas de Tempo ({len(time_cols)}): {time_cols}")
    print(f"Outras Colunas ({len(other_cols)}): {other_cols[:10]}...")  # Mostrar só as primeiras 10
    
    # Verificar se há dados de book
    bid_ask_cols = [col for col in df_sample.columns if any(x in col.lower() for x in ['bid', 'ask', 'compra', 'venda'])]
    if bid_ask_cols:
        print(f"\n[INFO] Dados de book encontrados: {bid_ask_cols}")
    
    # Contar total de linhas (sem carregar tudo)
    print("\n=== CONTANDO TOTAL DE LINHAS ===")
    try:
        total_lines = sum(1 for _ in open(data_path, 'r', encoding=encoding))
        print(f"Total de linhas no arquivo: {total_lines:,}")
        
        # Estimar tempo de processamento
        if total_lines > 1_000_000:
            print(f"[AVISO] Arquivo muito grande! Considere usar amostragem.")
            print(f"Sugestão: Usar últimas 500k linhas para treinamento")
            
    except Exception as e:
        print(f"Erro ao contar linhas: {e}")
    
    # Verificar período dos dados
    if time_cols:
        try:
            # Tentar converter para datetime
            for col in time_cols:
                try:
                    df_sample[col] = pd.to_datetime(df_sample[col])
                    print(f"\n=== PERÍODO DOS DADOS (coluna {col}) ===")
                    print(f"Início: {df_sample[col].min()}")
                    print(f"Fim: {df_sample[col].max()}")
                    print(f"Duração: {df_sample[col].max() - df_sample[col].min()}")
                    break
                except:
                    continue
        except:
            pass
    
    return df_sample

if __name__ == "__main__":
    df = analyze_wdo_data()
    
    print("\n" + "="*80)
    print("ANÁLISE CONCLUÍDA")
    print("="*80)
    print("\nPróximos passos:")
    print("1. Ajustar o script de treinamento baseado nas colunas identificadas")
    print("2. Considerar usar amostragem se o arquivo for muito grande")
    print("3. Verificar se há dados suficientes de bid/ask para features de microestrutura")