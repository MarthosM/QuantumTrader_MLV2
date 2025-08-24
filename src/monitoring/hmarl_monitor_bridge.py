"""
Bridge entre os agentes HMARL e o monitor
Permite que o monitor leia os dados reais dos agentes
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import threading
import logging

logger = logging.getLogger(__name__)

class HMARLMonitorBridge:
    """Bridge para comunicação entre HMARL e Monitor"""
    
    def __init__(self, data_dir: str = "data/monitor"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Arquivo compartilhado
        self.hmarl_file = self.data_dir / "hmarl_status.json"
        
        # Cache local
        self.last_update = None
        self.lock = threading.RLock()
        
        # Dados padrão
        self.default_data = {
            "timestamp": None,
            "consensus": {
                "action": "HOLD",
                "signal": 0.0,
                "confidence": 0.5
            },
            "agents": {
                "OrderFlowSpecialist": {
                    "signal": 0.0,
                    "confidence": 0.5,
                    "weight": 0.30,
                    "action": "HOLD"
                },
                "LiquidityAgent": {
                    "signal": 0.0,
                    "confidence": 0.5,
                    "weight": 0.20,
                    "action": "HOLD"
                },
                "TapeReadingAgent": {
                    "signal": 0.0,
                    "confidence": 0.5,
                    "weight": 0.25,
                    "action": "HOLD"
                },
                "FootprintPatternAgent": {
                    "signal": 0.0,
                    "confidence": 0.5,
                    "weight": 0.25,
                    "action": "HOLD"
                }
            }
        }
    
    def write_hmarl_data(self, consensus_data: Dict):
        """Escreve dados dos agentes HMARL para arquivo compartilhado"""
        try:
            with self.lock:
                # Preparar dados
                data = {
                    "timestamp": datetime.now().isoformat(),
                    "consensus": {
                        "action": consensus_data.get("action", "HOLD"),
                        "signal": consensus_data.get("signal", 0.0),
                        "confidence": consensus_data.get("confidence", 0.5)
                    },
                    "agents": {}
                }
                
                # Processar cada agente
                agents_data = consensus_data.get("agents", {})
                
                for agent_name, agent_info in agents_data.items():
                    # Determinar ação baseada no sinal
                    signal = agent_info.get("signal", 0)
                    if signal > 0.3:
                        action = "BUY"
                    elif signal < -0.3:
                        action = "SELL"
                    else:
                        action = "HOLD"
                    
                    data["agents"][agent_name] = {
                        "signal": signal,
                        "confidence": agent_info.get("confidence", 0.5),
                        "weight": agent_info.get("weight", 0.25),
                        "action": action,
                        "reasoning": agent_info.get("reasoning", {})
                    }
                
                # Escrever arquivo
                with open(self.hmarl_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                self.last_update = datetime.now()
                logger.info(f"[BRIDGE] HMARL written: {data['consensus']['action']} @ {data['consensus']['confidence']:.1%}")
                
        except Exception as e:
            logger.error(f"Erro ao escrever dados HMARL: {e}")
    
    def write_ml_data(self, ml_data: Dict):
        """Escreve dados dos modelos ML para arquivo compartilhado"""
        try:
            with self.lock:
                ml_file = self.data_dir / "ml_status.json"
                
                # Preparar dados
                data = {
                    "timestamp": datetime.now().isoformat(),
                    "context_pred": ml_data.get("context_pred", 0),
                    "context_conf": ml_data.get("context_conf", 0.5),
                    "micro_pred": ml_data.get("micro_pred", 0),
                    "micro_conf": ml_data.get("micro_conf", 0.5),
                    "meta_pred": ml_data.get("meta_pred", 0),
                    "ml_confidence": ml_data.get("ml_confidence", 0.0),
                    "ml_status": "ACTIVE" if ml_data.get("ml_confidence", 0) > 0 else "WAITING",
                    "ml_predictions": ml_data.get("predictions_count", 0)
                }
                
                # Escrever no arquivo
                with open(ml_file, 'w') as f:
                    json.dump(data, f)
                
                logger.info(f"[BRIDGE] ML written: signal={data['meta_pred']} @ {data['ml_confidence']:.1%}")
                
        except Exception as e:
            logger.error(f"Erro ao escrever dados ML: {e}")
    
    def update(self, data_type: str, data: Dict):
        """Método unificado de atualização"""
        try:
            if data_type == 'hmarl':
                logger.debug(f"[BRIDGE] Atualizando HMARL com {len(data.get('agents', {}))} agentes")
                self.write_hmarl_data(data)
            elif data_type in ['ml', 'ml_prediction']:
                self.write_ml_data(data)
            elif data_type == 'metrics':
                metrics_file = self.data_dir / "metrics.json"
                with open(metrics_file, 'w') as f:
                    json.dump(data, f)
                logger.debug(f"[BRIDGE] Metrics updated")
            elif data_type == 'last_trade':
                trade_file = self.data_dir / "last_trade.json"
                with open(trade_file, 'w') as f:
                    json.dump(data, f)
                logger.info(f"[BRIDGE] Trade: {data.get('side')} @ {data.get('confidence', 0):.1%}")
        except Exception as e:
            logger.error(f"Erro no update: {e}")
    
    def send_update(self, data: Dict):
        """Método alternativo"""
        self.update(data.get('type', 'unknown'), data)
    
    def read_hmarl_data(self) -> Dict:
        """Lê dados dos agentes HMARL do arquivo compartilhado"""
        max_retries = 3
        retry_delay = 0.1  # 100ms
        
        for retry in range(max_retries):
            try:
                with self.lock:
                    if self.hmarl_file.exists():
                        # Verificar se arquivo não está vazio
                        if self.hmarl_file.stat().st_size == 0:
                            logger.warning("Arquivo HMARL vazio, aguardando...")
                            time.sleep(retry_delay)
                            continue
                        
                        # Verificar idade do arquivo
                        file_age = time.time() - self.hmarl_file.stat().st_mtime
                        
                        # Se arquivo muito antigo (>30s), retornar dados padrão
                        if file_age > 30:
                            logger.warning(f"Dados HMARL muito antigos ({file_age:.1f}s)")
                            return self.default_data
                        
                        # Ler arquivo com retry em caso de erro
                        try:
                            with open(self.hmarl_file, 'r') as f:
                                content = f.read()
                                if not content:
                                    logger.warning("Arquivo HMARL sem conteúdo")
                                    time.sleep(retry_delay)
                                    continue
                                data = json.loads(content)
                                return data
                        except json.JSONDecodeError as je:
                            if retry < max_retries - 1:
                                logger.debug(f"JSON inválido, tentativa {retry+1}/{max_retries}")
                                time.sleep(retry_delay)
                                continue
                            else:
                                logger.error(f"Erro ao decodificar JSON após {max_retries} tentativas: {je}")
                                return self.default_data
                    else:
                        logger.debug("Arquivo HMARL não existe")
                        return self.default_data
                        
            except Exception as e:
                if retry < max_retries - 1:
                    logger.debug(f"Erro na leitura, tentativa {retry+1}/{max_retries}: {e}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Erro ao ler dados HMARL após {max_retries} tentativas: {e}")
                    return self.default_data
        
        return self.default_data
    
    def get_formatted_agents_data(self) -> list:
        """Retorna dados dos agentes formatados para o monitor"""
        data = self.read_hmarl_data()
        agents_list = []
        
        for agent_name, agent_info in data.get("agents", {}).items():
            # Nome curto para display
            if agent_name == "OrderFlowSpecialist":
                display_name = "OrderFlow"
            elif agent_name == "LiquidityAgent":
                display_name = "Liquidity"
            elif agent_name == "TapeReadingAgent":
                display_name = "TapeReading"
            elif agent_name == "FootprintPatternAgent":
                display_name = "Footprint"
            else:
                display_name = agent_name[:12]
            
            agents_list.append({
                "name": display_name,
                "full_name": agent_name,
                "signal": agent_info.get("action", "HOLD"),
                "confidence": agent_info.get("confidence", 0.5),
                "weight": agent_info.get("weight", 0.25),
                "raw_signal": agent_info.get("signal", 0.0)
            })
        
        return agents_list
    
    def get_consensus_data(self) -> Dict:
        """Retorna dados do consenso"""
        data = self.read_hmarl_data()
        return data.get("consensus", {
            "action": "HOLD",
            "signal": 0.0,
            "confidence": 0.5
        })
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Remove arquivos antigos"""
        try:
            cutoff_time = time.time() - (max_age_hours * 3600)
            
            for file in self.data_dir.glob("*.json"):
                if file.stat().st_mtime < cutoff_time:
                    file.unlink()
                    logger.info(f"Arquivo antigo removido: {file.name}")
                    
        except Exception as e:
            logger.error(f"Erro ao limpar arquivos: {e}")


# Singleton global
_bridge_instance = None

def get_bridge() -> HMARLMonitorBridge:
    """Retorna instância singleton do bridge"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = HMARLMonitorBridge()
    return _bridge_instance


if __name__ == "__main__":
    # Teste do bridge
    logging.basicConfig(level=logging.INFO)
    
    bridge = get_bridge()
    
    # Simular escrita de dados
    test_consensus = {
        "action": "BUY",
        "signal": 0.65,
        "confidence": 0.75,
        "agents": {
            "OrderFlowSpecialist": {
                "signal": 0.8,
                "confidence": 0.85,
                "weight": 0.30
            },
            "LiquidityAgent": {
                "signal": -0.2,
                "confidence": 0.60,
                "weight": 0.20
            },
            "TapeReadingAgent": {
                "signal": 0.5,
                "confidence": 0.70,
                "weight": 0.25
            },
            "FootprintPatternAgent": {
                "signal": 0.3,
                "confidence": 0.65,
                "weight": 0.25
            }
        }
    }
    
    print("Escrevendo dados de teste...")
    bridge.write_hmarl_data(test_consensus)
    
    print("\nLendo dados...")
    agents = bridge.get_formatted_agents_data()
    consensus = bridge.get_consensus_data()
    
    print("\nAgentes:")
    for agent in agents:
        print(f"  {agent['full_name']}: {agent['signal']} ({agent['confidence']:.1%})")
    
    print(f"\nConsenso: {consensus['action']} ({consensus['confidence']:.1%})")