"""
Sistema de Broadcasting de Features
Distribui as 65 features para agentes HMARL via ZMQ
"""

import zmq
import json
import time
import logging
import threading
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import msgpack
import lz4.frame
from enum import Enum

logger = logging.getLogger(__name__)


class CompressionType(Enum):
    """Tipos de compressão suportados"""
    NONE = "none"
    LZ4 = "lz4"
    MSGPACK = "msgpack"
    MSGPACK_LZ4 = "msgpack_lz4"


@dataclass
class FeatureMessage:
    """Mensagem de features para broadcast"""
    timestamp: str
    sequence: int
    features: Dict[str, float]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        """Converte para dicionário"""
        return asdict(self)


class FeatureBroadcaster:
    """Broadcaster de features via ZMQ"""
    
    def __init__(self, 
                 port: int = 5556,
                 compression: CompressionType = CompressionType.MSGPACK_LZ4):
        self.port = port
        self.compression = compression
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind(f"tcp://*:{port}")
        
        self.sequence = 0
        self.stats = {
            'messages_sent': 0,
            'bytes_sent': 0,
            'compression_ratio': [],
            'send_latencies': []
        }
        
        self.running = False
        self.monitor_thread = None
        
        logger.info(f"FeatureBroadcaster iniciado na porta {port} com compressão {compression.value}")
    
    def broadcast_features(self, features: Dict[str, float], metadata: Optional[Dict] = None) -> bool:
        """Broadcast features para todos os subscribers"""
        try:
            start_time = time.perf_counter()
            
            # Criar mensagem
            self.sequence += 1
            message = FeatureMessage(
                timestamp=datetime.now().isoformat(),
                sequence=self.sequence,
                features=features,
                metadata=metadata or {}
            )
            
            # Serializar e comprimir
            data = self._serialize_message(message)
            
            # Enviar via ZMQ
            self.publisher.send(data)
            
            # Atualizar estatísticas
            send_latency = (time.perf_counter() - start_time) * 1000
            self.stats['messages_sent'] += 1
            self.stats['bytes_sent'] += len(data)
            self.stats['send_latencies'].append(send_latency)
            
            # Manter apenas últimas 100 latências
            if len(self.stats['send_latencies']) > 100:
                self.stats['send_latencies'].pop(0)
            
            logger.debug(f"Features broadcast: seq={self.sequence}, size={len(data)} bytes, latency={send_latency:.2f}ms")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao fazer broadcast: {e}")
            return False
    
    def _serialize_message(self, message: FeatureMessage) -> bytes:
        """Serializa e comprime mensagem"""
        msg_dict = message.to_dict()
        
        if self.compression == CompressionType.NONE:
            # JSON sem compressão
            data = json.dumps(msg_dict).encode('utf-8')
            
        elif self.compression == CompressionType.LZ4:
            # JSON com LZ4
            json_data = json.dumps(msg_dict).encode('utf-8')
            data = lz4.frame.compress(json_data)
            
        elif self.compression == CompressionType.MSGPACK:
            # MessagePack sem compressão
            data = msgpack.packb(msg_dict)
            
        elif self.compression == CompressionType.MSGPACK_LZ4:
            # MessagePack com LZ4 (mais eficiente)
            msgpack_data = msgpack.packb(msg_dict)
            data = lz4.frame.compress(msgpack_data)
            
            # Calcular taxa de compressão
            original_size = len(json.dumps(msg_dict).encode('utf-8'))
            compressed_size = len(data)
            ratio = original_size / compressed_size
            self.stats['compression_ratio'].append(ratio)
            
            if len(self.stats['compression_ratio']) > 100:
                self.stats['compression_ratio'].pop(0)
        
        return data
    
    def start_monitoring(self):
        """Inicia thread de monitoramento"""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Para thread de monitoramento"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def _monitor_loop(self):
        """Loop de monitoramento de estatísticas"""
        while self.running:
            time.sleep(10)  # Log a cada 10 segundos
            self.log_stats()
    
    def log_stats(self):
        """Log estatísticas de broadcast"""
        if self.stats['messages_sent'] > 0:
            avg_latency = np.mean(self.stats['send_latencies']) if self.stats['send_latencies'] else 0
            avg_compression = np.mean(self.stats['compression_ratio']) if self.stats['compression_ratio'] else 1
            
            logger.info(f"Broadcast Stats: msgs={self.stats['messages_sent']}, "
                       f"bytes={self.stats['bytes_sent']/1024:.1f}KB, "
                       f"latency={avg_latency:.2f}ms, "
                       f"compression={avg_compression:.1f}x")
    
    def close(self):
        """Fecha conexões ZMQ"""
        self.stop_monitoring()
        self.publisher.close()
        self.context.term()
        logger.info("FeatureBroadcaster fechado")


class FeatureSubscriber:
    """Subscriber de features via ZMQ"""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 5556,
                 compression: CompressionType = CompressionType.MSGPACK_LZ4,
                 topics: List[str] = None):
        self.host = host
        self.port = port
        self.compression = compression
        self.topics = topics or []
        
        self.context = zmq.Context()
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.connect(f"tcp://{host}:{port}")
        
        # Subscribe to topics (empty = all)
        if not self.topics:
            self.subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
        else:
            for topic in self.topics:
                self.subscriber.setsockopt_string(zmq.SUBSCRIBE, topic)
        
        self.running = False
        self.callback = None
        self.receive_thread = None
        
        self.stats = {
            'messages_received': 0,
            'bytes_received': 0,
            'process_latencies': []
        }
        
        logger.info(f"FeatureSubscriber conectado a {host}:{port}")
    
    def subscribe(self, callback):
        """Define callback para processar mensagens recebidas"""
        self.callback = callback
    
    def start_receiving(self):
        """Inicia recepção de mensagens"""
        if not self.callback:
            raise ValueError("Callback não definido. Use subscribe() primeiro.")
        
        self.running = True
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.start()
        logger.info("FeatureSubscriber iniciado")
    
    def stop_receiving(self):
        """Para recepção de mensagens"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join()
        logger.info("FeatureSubscriber parado")
    
    def _receive_loop(self):
        """Loop de recepção de mensagens"""
        while self.running:
            try:
                # Receber com timeout
                if self.subscriber.poll(1000):  # 1 segundo timeout
                    data = self.subscriber.recv()
                    
                    start_time = time.perf_counter()
                    
                    # Deserializar mensagem
                    message = self._deserialize_message(data)
                    
                    # Chamar callback
                    if message and self.callback:
                        self.callback(message)
                    
                    # Atualizar estatísticas
                    process_latency = (time.perf_counter() - start_time) * 1000
                    self.stats['messages_received'] += 1
                    self.stats['bytes_received'] += len(data)
                    self.stats['process_latencies'].append(process_latency)
                    
                    if len(self.stats['process_latencies']) > 100:
                        self.stats['process_latencies'].pop(0)
                    
            except zmq.ZMQError as e:
                if e.errno != zmq.EAGAIN:
                    logger.error(f"Erro ZMQ: {e}")
            except Exception as e:
                logger.error(f"Erro ao processar mensagem: {e}")
    
    def _deserialize_message(self, data: bytes) -> Optional[Dict]:
        """Deserializa mensagem recebida"""
        try:
            if self.compression == CompressionType.NONE:
                # JSON sem compressão
                return json.loads(data.decode('utf-8'))
                
            elif self.compression == CompressionType.LZ4:
                # JSON com LZ4
                decompressed = lz4.frame.decompress(data)
                return json.loads(decompressed.decode('utf-8'))
                
            elif self.compression == CompressionType.MSGPACK:
                # MessagePack sem compressão
                return msgpack.unpackb(data, raw=False)
                
            elif self.compression == CompressionType.MSGPACK_LZ4:
                # MessagePack com LZ4
                decompressed = lz4.frame.decompress(data)
                return msgpack.unpackb(decompressed, raw=False)
                
        except Exception as e:
            logger.error(f"Erro ao deserializar: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do subscriber"""
        stats = self.stats.copy()
        if stats['process_latencies']:
            stats['avg_latency'] = np.mean(stats['process_latencies'])
        return stats
    
    def close(self):
        """Fecha conexões"""
        self.stop_receiving()
        self.subscriber.close()
        self.context.term()
        logger.info("FeatureSubscriber fechado")


class BroadcastOrchestrator:
    """Orquestrador de broadcast para múltiplos agentes"""
    
    def __init__(self, port: int = 5556):
        self.broadcaster = FeatureBroadcaster(port=port)
        self.agent_subscribers = {}
        self.feature_buffer = []
        self.max_buffer_size = 100
        
        # Estatísticas
        self.broadcast_count = 0
        self.last_broadcast_time = None
        
    def broadcast_to_agents(self, features: Dict[str, float], 
                           ml_prediction: float = None,
                           regime: str = None) -> bool:
        """Broadcast features com metadados para agentes"""
        
        # Preparar metadata
        metadata = {
            'ml_prediction': ml_prediction,
            'regime': regime,
            'feature_count': len(features),
            'broadcast_count': self.broadcast_count
        }
        
        # Adicionar ao buffer
        self.feature_buffer.append({
            'timestamp': datetime.now(),
            'features': features,
            'metadata': metadata
        })
        
        # Limitar tamanho do buffer
        if len(self.feature_buffer) > self.max_buffer_size:
            self.feature_buffer.pop(0)
        
        # Fazer broadcast
        success = self.broadcaster.broadcast_features(features, metadata)
        
        if success:
            self.broadcast_count += 1
            self.last_broadcast_time = datetime.now()
            
            # Log periódico
            if self.broadcast_count % 100 == 0:
                logger.info(f"Broadcast #{self.broadcast_count} enviado com {len(features)} features")
        
        return success
    
    def get_feature_history(self, n: int = 10) -> List[Dict]:
        """Retorna últimas n broadcasts de features"""
        return self.feature_buffer[-n:] if self.feature_buffer else []
    
    def close(self):
        """Fecha broadcaster"""
        self.broadcaster.close()


def test_broadcasting():
    """Teste do sistema de broadcast"""
    logging.basicConfig(level=logging.INFO)
    
    # Criar broadcaster
    logger.info("Iniciando teste de broadcast...")
    orchestrator = BroadcastOrchestrator(port=5558)
    
    # Criar subscriber de teste
    def on_message_received(message):
        logger.info(f"Mensagem recebida: seq={message['sequence']}, "
                   f"features={len(message['features'])}, "
                   f"metadata={message['metadata']}")
    
    subscriber = FeatureSubscriber(port=5558)
    subscriber.subscribe(on_message_received)
    subscriber.start_receiving()
    
    # Simular broadcast de features
    for i in range(5):
        features = {f'feature_{j}': np.random.random() for j in range(65)}
        
        success = orchestrator.broadcast_to_agents(
            features=features,
            ml_prediction=0.65,
            regime='TREND'
        )
        
        if success:
            logger.info(f"Broadcast {i+1} enviado")
        
        time.sleep(1)
    
    # Estatísticas
    orchestrator.broadcaster.log_stats()
    subscriber_stats = subscriber.get_stats()
    logger.info(f"Subscriber stats: {subscriber_stats}")
    
    # Cleanup
    subscriber.close()
    orchestrator.close()
    
    logger.info("Teste concluído")


if __name__ == "__main__":
    test_broadcasting()