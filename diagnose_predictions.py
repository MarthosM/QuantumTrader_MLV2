#!/usr/bin/env python3
"""
Diagnóstico completo do sistema de predições ML e HMARL
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import json
from pathlib import Path
from datetime import datetime
import time

def test_ml_predictions():
    """Testa o sistema ML isoladamente"""
    print("\n" + "="*70)
    print("1. TESTANDO ML PREDICTIONS")
    print("="*70)
    
    try:
        from src.ml.hybrid_predictor import HybridMLPredictor
        
        # Criar instância
        predictor = HybridMLPredictor(models_dir="models/hybrid")
        
        # Verificar se modelos foram carregados
        if predictor.load_models():
            print("[OK] Modelos carregados com sucesso")
            
            # Verificar quantos modelos
            model_count = 0
            if predictor.context_models:
                model_count += len(predictor.context_models)
                print(f"   Context models: {len(predictor.context_models)}")
            if predictor.microstructure_models:
                model_count += len(predictor.microstructure_models)
                print(f"   Microstructure models: {len(predictor.microstructure_models)}")
            if predictor.meta_learner:
                model_count += 1
                print(f"   Meta learner: OK")
            
            print(f"   Total: {model_count} modelos")
        else:
            print("[ERRO] Falha ao carregar modelos")
            return False
        
        # Criar features dummy (65 features)
        print("\n2. Testando predição com features dummy...")
        
        # Gerar 65 features com valores variados
        features = {}
        feature_names = [
            # Volatilidade (10)
            "volatility_10", "volatility_20", "volatility_50", "volatility_100",
            "volatility_ratio_10_20", "volatility_ratio_20_50", "volatility_ratio_50_100", "volatility_ratio_100_200",
            "volatility_gk", "bb_position",
            
            # Retornos (10)
            "returns_1", "returns_2", "returns_5", "returns_10", "returns_20",
            "returns_50", "returns_100", "log_returns_1", "log_returns_5", "log_returns_20",
            
            # Order Flow (8)
            "order_flow_imbalance_10", "order_flow_imbalance_20",
            "order_flow_imbalance_50", "order_flow_imbalance_100",
            "cumulative_signed_volume", "signed_volume",
            "volume_weighted_return", "agent_turnover",
            
            # Volume (8)
            "volume_ratio_20", "volume_ratio_50", "volume_ratio_100",
            "volume_zscore_20", "volume_zscore_50", "volume_zscore_100",
            "trade_intensity", "trade_intensity_ratio",
            
            # Técnicos (8)
            "ma_5_20_ratio", "ma_20_50_ratio",
            "momentum_5_20", "momentum_20_50",
            "sharpe_5", "sharpe_20",
            "time_normalized", "rsi_14",
            
            # Microestrutura (15)
            "spread", "spread_ma", "spread_std", "spread_ratio",
            "depth_imbalance", "depth_total", "depth_ratio",
            "book_pressure", "book_imbalance_ratio", "book_concentration",
            "tick_rule", "quote_rule", "mid_price_change",
            "microprice", "weighted_mid_price",
            
            # Temporal (6)
            "hour", "minute", "hour_sin", "hour_cos", "minute_sin", "minute_cos"
        ]
        
        # Preencher com valores realistas
        np.random.seed(42)
        for i, name in enumerate(feature_names):
            if "returns" in name:
                features[name] = np.random.uniform(-0.01, 0.01)  # Returns pequenos
            elif "volatility" in name:
                features[name] = np.random.uniform(0.0001, 0.01)  # Volatilidade positiva
            elif "ratio" in name:
                features[name] = np.random.uniform(0.8, 1.2)  # Ratios próximos de 1
            elif "hour" == name:
                features[name] = 14  # Horário de trading
            elif "minute" == name:
                features[name] = 30
            else:
                features[name] = np.random.uniform(-1, 1)  # Valores normalizados
        
        print(f"   Total features criadas: {len(features)}")
        
        # Fazer predição
        print("\n3. Fazendo predição...")
        result = predictor.predict(features)
        
        if result:
            print("[OK] Predição realizada com sucesso!")
            print(f"   Signal: {result.get('signal', 'N/A')}")
            print(f"   Confidence: {result.get('confidence', 0):.2%}")
            
            # Verificar estrutura da predição
            if 'predictions' in result:
                preds = result['predictions']
                if 'context' in preds:
                    print(f"   Context regime: {preds['context'].get('regime', 'N/A')}")
                if 'microstructure' in preds:
                    print(f"   Micro order_flow: {preds['microstructure'].get('order_flow', 'N/A')}")
                if 'meta' in preds:
                    print(f"   Meta prediction: {preds.get('meta', 'N/A')}")
            
            # Verificar se está sempre retornando 0
            if result.get('signal') == 0 and result.get('confidence', 0) == 0:
                print("\n[AVISO] PROBLEMA: ML retornando signal=0, confidence=0")
                print("   Possível causa: Modelos não treinados ou features fora do range")
            
            return True
        else:
            print("[ERRO] Predição retornou None")
            return False
            
    except Exception as e:
        print(f"[ERRO] Erro ao testar ML: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_hmarl_agents():
    """Testa os agentes HMARL"""
    print("\n" + "="*70)
    print("2. TESTANDO HMARL AGENTS")
    print("="*70)
    
    try:
        from src.agents.hmarl_agents_realtime import HMARLAgentsRealtime
        
        # Criar instância
        agents = HMARLAgentsRealtime()
        print("[OK] HMARL Agents inicializados")
        
        # Criar dados dummy para teste
        book_data = {
            'timestamp': datetime.now(),
            'bid_price_1': 5430.0,
            'bid_volume_1': 100,
            'ask_price_1': 5431.0,
            'ask_volume_1': 100,
            'spread': 1.0,
            'mid_price': 5430.5
        }
        
        tick_data = {
            'timestamp': datetime.now(),
            'price': 5430.5,
            'volume': 10,
            'side': 'BUY'
        }
        
        features = {'test_feature': 0.5}
        
        print("\n2. Testando consensus...")
        
        # Fazer predição
        result = agents.get_consensus(book_data, tick_data, features)
        
        if result:
            print("[OK] Consensus obtido com sucesso!")
            print(f"   Signal: {result.get('signal', 'N/A')}")
            print(f"   Confidence: {result.get('confidence', 0):.2%}")
            print(f"   Action: {result.get('action', 'N/A')}")
            
            # Verificar agentes individuais
            if 'agents_decisions' in result:
                print("\n   Decisões dos agentes:")
                for agent, decision in result['agents_decisions'].items():
                    print(f"      {agent}: {decision}")
            
            # Verificar timestamp
            if 'timestamp' in result:
                ts = result['timestamp']
                if isinstance(ts, datetime):
                    age = (datetime.now() - ts).total_seconds()
                    print(f"\n   Idade dos dados: {age:.1f} segundos")
                    if age > 60:
                        print("   [AVISO] PROBLEMA: Dados muito antigos!")
            
            return True
        else:
            print("[ERRO] Consensus retornou None")
            return False
            
    except Exception as e:
        print(f"[ERRO] Erro ao testar HMARL: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_data_flow():
    """Verifica o fluxo de dados no sistema"""
    print("\n" + "="*70)
    print("3. VERIFICANDO FLUXO DE DADOS")
    print("="*70)
    
    # Verificar arquivos de status
    status_files = {
        "ml_status.json": "data/monitor/ml_status.json",
        "hmarl_status.json": "data/monitor/hmarl_status.json",
        "latest_signal.json": "data/monitor/latest_signal.json"
    }
    
    for name, path in status_files.items():
        file_path = Path(path)
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                print(f"\n{name}:")
                
                # Verificar timestamp
                if 'timestamp' in data:
                    ts = datetime.fromisoformat(data['timestamp'])
                    age = (datetime.now() - ts).total_seconds()
                    print(f"   Última atualização: {age:.1f}s atrás")
                    
                    if age > 60:
                        print("   [AVISO] Dados desatualizados!")
                
                # Verificar últimas predições
                if 'last_prediction' in data:
                    pred = data['last_prediction']
                    print(f"   Última predição: signal={pred.get('signal')}, conf={pred.get('confidence', 0):.2%}")
                
                # Verificar features
                if 'last_features' in data:
                    features = data['last_features']
                    print(f"   Features disponíveis: {len(features)}")
                    
                    # Verificar se features são dinâmicas
                    if 'returns_1' in features:
                        if abs(features['returns_1']) < 1e-8:
                            print("   [AVISO] Returns zerados - features estáticas!")
                
            except Exception as e:
                print(f"   Erro ao ler: {e}")
        else:
            print(f"\n{name}: NÃO EXISTE")
    
    return True

def check_system_integration():
    """Verifica integração do sistema completo"""
    print("\n" + "="*70)
    print("4. VERIFICANDO INTEGRAÇÃO DO SISTEMA")
    print("="*70)
    
    # Tentar importar o sistema principal
    try:
        import START_SYSTEM_COMPLETE_OCO_EVENTS as main_system
        print("[OK] Sistema principal importado")
        
        # Verificar se tem instância rodando
        import gc
        system_instance = None
        for obj in gc.get_objects():
            if hasattr(obj, '__class__') and obj.__class__.__name__ == 'QuantumTraderCompleteOCOEvents':
                system_instance = obj
                break
        
        if system_instance:
            print("[OK] Instância do sistema encontrada")
            
            # Verificar componentes
            checks = {
                'ml_predictor': hasattr(system_instance, 'ml_predictor') and system_instance.ml_predictor is not None,
                'hmarl_agents': hasattr(system_instance, 'hmarl_agents') and system_instance.hmarl_agents is not None,
                'price_history': hasattr(system_instance, 'price_history') and len(system_instance.price_history) > 0,
                'running': hasattr(system_instance, 'running') and system_instance.running
            }
            
            print("\nComponentes:")
            for component, status in checks.items():
                status_str = "[OK] OK" if status else "[ERRO] Problema"
                print(f"   {component}: {status_str}")
            
            # Verificar price_history
            if checks['price_history']:
                print(f"\n   Price history size: {len(system_instance.price_history)}")
                if len(system_instance.price_history) > 0:
                    prices = list(system_instance.price_history)[-5:]
                    print(f"   Últimos preços: {prices}")
        else:
            print("[AVISO] Sistema não está rodando ou não encontrado em memória")
            
    except Exception as e:
        print(f"[ERRO] Erro ao verificar integração: {e}")
    
    return True

def main():
    """Executa diagnóstico completo"""
    print("\n" + "="*80)
    print(" DIAGNÓSTICO COMPLETO - ML & HMARL PREDICTIONS")
    print("="*80)
    
    results = {
        'ML': test_ml_predictions(),
        'HMARL': test_hmarl_agents(),
        'Data Flow': check_data_flow(),
        'Integration': check_system_integration()
    }
    
    print("\n" + "="*80)
    print(" RESUMO DO DIAGNÓSTICO")
    print("="*80)
    
    for component, status in results.items():
        status_str = "[OK] OK" if status else "[ERRO] PROBLEMA"
        print(f"{component:15s}: {status_str}")
    
    print("\n" + "="*80)
    print(" PROBLEMAS IDENTIFICADOS E SOLUÇÕES")
    print("="*80)
    
    if not results['ML']:
        print("\n[!] ML não está funcionando:")
        print("   1. Verificar se modelos existem em models/hybrid/")
        print("   2. Retreinar modelos se necessário")
        print("   3. Verificar formato das features")
    
    if not results['HMARL']:
        print("\n[!] HMARL não está funcionando:")
        print("   1. Verificar inicialização dos agentes")
        print("   2. Garantir que dados são passados corretamente")
        print("   3. Verificar timestamps")
    
    if not results['Data Flow']:
        print("\n[!] Fluxo de dados com problemas:")
        print("   1. Verificar se callbacks estão funcionando")
        print("   2. Garantir que buffers são atualizados")
        print("   3. Verificar se features são calculadas")
    
    if not results['Integration']:
        print("\n[!] Integração com problemas:")
        print("   1. Verificar se sistema está rodando")
        print("   2. Garantir que componentes são inicializados")
        print("   3. Verificar logs para erros")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()