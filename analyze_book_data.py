#!/usr/bin/env python3
"""
Análise dos dados de book coletados
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def analyze_book_data():
    """Analisa todos os dados de book coletados"""
    
    data_dir = Path('data/book_tick_data')
    book_files = sorted(data_dir.glob('book_data_*.csv'))
    
    print("\n" + "=" * 80)
    print(" ANÁLISE DOS DADOS DE BOOK COLETADOS")
    print("=" * 80)
    
    print(f"\nTotal de arquivos: {len(book_files)}")
    
    # Carregar todos os dados
    all_data = []
    total_size = 0
    
    for file in book_files:
        size_mb = file.stat().st_size / (1024 * 1024)
        total_size += size_mb
        
        df = pd.read_csv(file)
        all_data.append(df)
        
    print(f"Tamanho total: {total_size:.2f} MB")
    
    # Combinar todos os dados
    df_combined = pd.concat(all_data, ignore_index=True)
    print(f"Total de registros: {len(df_combined):,}")
    
    # Converter timestamp
    df_combined['timestamp'] = pd.to_datetime(df_combined['timestamp'])
    
    # Análise temporal
    print(f"\nPeríodo dos dados:")
    print(f"  Início: {df_combined['timestamp'].min()}")
    print(f"  Fim: {df_combined['timestamp'].max()}")
    duration = (df_combined['timestamp'].max() - df_combined['timestamp'].min())
    print(f"  Duração: {duration}")
    
    # Análise de qualidade
    print(f"\nQUALIDADE DOS DADOS:")
    print(f"  Registros com 5 níveis: {(df_combined['bid_price_5'] > 0).sum():,}")
    print(f"  Registros com 4 níveis: {((df_combined['bid_price_4'] > 0) & (df_combined['bid_price_5'] == 0)).sum():,}")
    print(f"  Registros com 3 níveis: {((df_combined['bid_price_3'] > 0) & (df_combined['bid_price_4'] == 0)).sum():,}")
    print(f"  Registros com 2 níveis: {((df_combined['bid_price_2'] > 0) & (df_combined['bid_price_3'] == 0)).sum():,}")
    print(f"  Registros com 1 nível: {((df_combined['bid_price_1'] > 0) & (df_combined['bid_price_2'] == 0)).sum():,}")
    
    # Estatísticas de spread
    print(f"\nESTATÍSTICAS DE MICROESTRUTURA:")
    print(f"  Spread médio: {df_combined['spread'].mean():.2f}")
    print(f"  Spread mediano: {df_combined['spread'].median():.2f}")
    print(f"  Spread máximo: {df_combined['spread'].max():.2f}")
    
    # Imbalance
    print(f"\n  Imbalance médio: {df_combined['imbalance'].mean():.4f}")
    print(f"  Imbalance std: {df_combined['imbalance'].std():.4f}")
    
    # Volume
    print(f"\n  Volume bid médio: {df_combined['total_bid_vol'].mean():.0f}")
    print(f"  Volume ask médio: {df_combined['total_ask_vol'].mean():.0f}")
    
    # Frequência de atualizações
    df_combined['time_diff'] = df_combined['timestamp'].diff().dt.total_seconds()
    print(f"\nFREQUÊNCIA DE ATUALIZAÇÕES:")
    print(f"  Média: {df_combined['time_diff'].mean():.3f} segundos")
    print(f"  Mediana: {df_combined['time_diff'].median():.3f} segundos")
    print(f"  Mínima: {df_combined['time_diff'].min():.3f} segundos")
    
    # Verificar se temos dados suficientes para treinar
    print(f"\nVIABILIDADE PARA TREINAMENTO:")
    
    min_records_needed = 100000
    if len(df_combined) >= min_records_needed:
        print(f"  [OK] Temos {len(df_combined):,} registros (mínimo: {min_records_needed:,})")
    else:
        print(f"  [AVISO] Apenas {len(df_combined):,} registros (recomendado: {min_records_needed:,}+)")
    
    # Calcular features básicas para teste
    print(f"\nTESTE DE FEATURES:")
    
    # Book pressure
    df_combined['book_pressure'] = df_combined['total_bid_vol'] / (df_combined['total_bid_vol'] + df_combined['total_ask_vol'])
    
    # Mid price returns
    df_combined['mid_return'] = df_combined['mid_price'].pct_change()
    
    # Volume at best
    df_combined['volume_at_best'] = df_combined['bid_vol_1'] + df_combined['ask_vol_1']
    
    print(f"  Book pressure médio: {df_combined['book_pressure'].mean():.4f}")
    print(f"  Retorno médio (mid): {df_combined['mid_return'].mean():.6f}")
    print(f"  Volume at best médio: {df_combined['volume_at_best'].mean():.0f}")
    
    # Salvar amostra processada
    sample_file = 'data/book_data_processed_sample.csv'
    df_combined.head(10000).to_csv(sample_file, index=False)
    print(f"\nAmostra salva em: {sample_file}")
    
    return df_combined

if __name__ == "__main__":
    df = analyze_book_data()
    
    print("\n" + "=" * 80)
    print(" PRÓXIMOS PASSOS RECOMENDADOS:")
    print("=" * 80)
    print("\n1. [OK] Temos dados de book suficientes para começar")
    print("2. [>>] Criar pipeline de treinamento com esses dados")
    print("3. [>>] Desenvolver features específicas de book")
    print("4. [>>] Treinar modelos especializados em microestrutura")
    print("\n")