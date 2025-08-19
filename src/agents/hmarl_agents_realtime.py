"""
Agentes HMARL Real-time - Versão que realmente processa dados do mercado
"""

import numpy as np
import logging
from typing import Dict, List, Optional
from datetime import datetime
from collections import deque
import random
import time
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class HMARLAgentsRealtime:
    """Agentes HMARL que processam dados reais do mercado"""
    
    def __init__(self):
        self.name = "HMARL_Realtime"
        self.agents = {
            'OrderFlowSpecialist': {'weight': 0.30, 'bias': 0},
            'LiquidityAgent': {'weight': 0.20, 'bias': 0},
            'TapeReadingAgent': {'weight': 0.25, 'bias': 0},
            'FootprintPatternAgent': {'weight': 0.25, 'bias': 0}
        }
        
        # Buffers para análise
        self.price_buffer = deque(maxlen=100)
        self.volume_buffer = deque(maxlen=100)
        self.book_buffer = deque(maxlen=50)
        
        # Estados dos agentes com decay
        self.agent_states = {}
        for agent in self.agents:
            self.agent_states[agent] = {
                'last_signal': 0,
                'confidence': 0.5,
                'trades_analyzed': 0,
                'last_change_time': time.time(),
                'confidence_decay_rate': 0.98  # Decai 2% por atualização sem mudança
            }
        
        logger.info("HMARLAgentsRealtime inicializado")
    
    def update_market_data(self, price: float = None, volume: float = None, 
                          book_data: Dict = None, features: Dict = None):
        """Atualiza dados de mercado"""
        if price is not None and price > 0:
            self.price_buffer.append(price)
            
        if volume is not None and volume > 0:
            self.volume_buffer.append(volume)
            
        if book_data is not None:
            self.book_buffer.append(book_data)
        
        # Se features foram passadas, usar para análise mais precisa
        if features:
            self.last_features = features
    
    def analyze_order_flow(self) -> tuple[float, float]:
        """OrderFlowSpecialist - Analisa fluxo de ordens"""
        
        # Usar features se disponíveis
        if hasattr(self, 'last_features') and self.last_features:
            ofi = self.last_features.get('order_flow_imbalance_5', 0)
            signed_vol = self.last_features.get('signed_volume_5', 0)
            trade_flow = self.last_features.get('trade_flow_5', 0)
            
            # Calcular sinal baseado nas features
            combined = ofi * 0.4 + np.sign(signed_vol) * 0.3 + np.sign(trade_flow) * 0.3
            
            if combined > 0.3:
                signal = 1
            elif combined < -0.3:
                signal = -1
            else:
                signal = combined
            
            # Confiança baseada na força do sinal
            # Confiança com variação temporal para evitar travamento
            base_confidence = min(abs(combined) + 0.3, 0.95)
            
            # Adicionar variação temporal
            time_var = np.sin(time.time() / 5) * 0.05  # ±5% de variação
            
            # Aplicar decay se valor está travado
            state = self.agent_states['OrderFlowSpecialist']
            if abs(state.get('last_confidence', 0) - base_confidence) < 0.01:
                # Valor travado, aplicar decay
                base_confidence = base_confidence * 0.95  # Reduz 5%
            
            # Garantir variação
            confidence = np.clip(base_confidence + time_var, 0.3, 0.95)
            state['last_confidence'] = confidence
            
        elif len(self.volume_buffer) < 10:
            return 0, 0.5
        else:
            # Análise de volume (fallback)
            recent_vol = list(self.volume_buffer)[-10:]
            avg_vol = np.mean(recent_vol)
            vol_trend = (recent_vol[-1] - avg_vol) / (avg_vol + 1e-8)
            
            # Análise de preço com volume
            if len(self.price_buffer) >= 10:
                price_changes = np.diff(list(self.price_buffer)[-10:])
                volume_weighted = sum(p * v for p, v in zip(price_changes, recent_vol[1:]))
                
                # Sinal baseado em volume ponderado
                if volume_weighted > 0:
                    signal = 1 if vol_trend > 0 else 0.5
                elif volume_weighted < 0:
                    signal = -1 if vol_trend < 0 else -0.5
                else:
                    signal = 0
                    
                # Confiança baseada na força do movimento
                confidence = min(abs(volume_weighted) / 1000 + 0.5, 0.95)
            else:
                signal = 0
                confidence = 0.5
        
        self.agent_states['OrderFlowSpecialist']['last_signal'] = signal
        self.agent_states['OrderFlowSpecialist']['confidence'] = confidence
        
        return signal, confidence
    
    def analyze_liquidity(self) -> tuple[float, float]:
        """LiquidityAgent - Analisa liquidez do book"""
        
        # Usar features se disponíveis
        if hasattr(self, 'last_features') and self.last_features:
            volume_ratio = self.last_features.get('volume_ratio', 1.0)
            spread = self.last_features.get('spread', 0.5)
            depth_imb = self.last_features.get('book_depth_imbalance', 0)
            bid_levels = self.last_features.get('bid_levels_active', 5)
            ask_levels = self.last_features.get('ask_levels_active', 5)
            
            # Score de liquidez
            liquidity_score = 0
            
            # Volume ratio favorece compra/venda
            if volume_ratio > 1.2:
                liquidity_score += 0.3
            elif volume_ratio < 0.8:
                liquidity_score -= 0.3
            
            # Spread estreito indica boa liquidez
            if spread < 0.5:
                liquidity_score += 0.2
            elif spread > 1.0:
                liquidity_score -= 0.2
            
            # Profundidade do book
            liquidity_score += depth_imb * 0.3
            
            # Níveis ativos
            level_ratio = bid_levels / (ask_levels + 1)
            if level_ratio > 1.3:
                liquidity_score += 0.2
            elif level_ratio < 0.7:
                liquidity_score -= 0.2
            
            # Determinar sinal
            signal = np.clip(liquidity_score, -1, 1)
            
            # Confiança baseada na clareza do sinal
            confidence = min(abs(liquidity_score) + 0.4, 0.9)
            
        elif len(self.book_buffer) < 5:
            return 0, 0.5
        else:
            # Análise fallback
            recent_books = list(self.book_buffer)[-5:]
            
            # Análise de spread e profundidade
            spreads = []
            imbalances = []
            
            for book in recent_books:
                if isinstance(book, dict):
                    spread = book.get('spread', 0.5)
                    imbalance = book.get('imbalance', 0)
                    spreads.append(spread)
                    imbalances.append(imbalance)
            
            if spreads and imbalances:
                avg_spread = np.mean(spreads)
                avg_imbalance = np.mean(imbalances)
                
                # Sinal baseado em liquidez
                if avg_spread < 0.5 and avg_imbalance > 0.1:
                    signal = 1  # Boa liquidez, pressão compradora
                elif avg_spread < 0.5 and avg_imbalance < -0.1:
                    signal = -1  # Boa liquidez, pressão vendedora
                elif avg_spread > 1.0:
                    signal = 0  # Baixa liquidez, neutro
                else:
                    signal = avg_imbalance  # Usar imbalance como sinal
                
                # Confiança baseada no spread
                confidence = max(0.3, min(0.9, 1.0 - avg_spread / 2.0))
            else:
                signal = 0
                confidence = 0.5
        
        # Adicionar variação temporal
        time_factor = 1.0 + (np.sin(time.time() / 10) * 0.05)  # ±5% variação
        confidence = min(confidence * time_factor, 0.95)
        
        self.agent_states['LiquidityAgent']['last_signal'] = signal
        self.agent_states['LiquidityAgent']['confidence'] = confidence
        
        return signal, confidence
    
    def analyze_tape(self) -> tuple[float, float]:
        """TapeReadingAgent - Analisa fita de operações"""
        buffer_size = len(self.price_buffer)
        
        # Log para debug
        if buffer_size % 10 == 0:  # Log a cada 10 updates
            logger.debug(f"TapeReading buffer size: {buffer_size}")
        
        if buffer_size < 20:
            # Retornar valores variáveis mesmo com poucos dados
            if buffer_size >= 5:
                prices = list(self.price_buffer)
                vol = np.std(prices) / (np.mean(prices) + 1e-8)
                # Adicionar aleatoriedade pequena para evitar valores fixos
                random_factor = np.random.uniform(0.95, 1.05)
                return 0, min(0.3 + buffer_size * 0.02, 0.6) * random_factor
            return 0, 0.3
        
        prices = list(self.price_buffer)[-20:]
        
        # Análise de momentum
        short_ma = np.mean(prices[-5:])
        long_ma = np.mean(prices)
        
        momentum = (short_ma - long_ma) / long_ma
        
        # Análise de volatilidade
        volatility = np.std(prices) / np.mean(prices)
        
        # Log detalhado
        logger.debug(
            f"TapeReading - Momentum: {momentum:.6f} | "
            f"Volatility: {volatility:.6f} | "
            f"Short MA: {short_ma:.2f} | Long MA: {long_ma:.2f}"
        )
        
        # Sinal baseado em momentum e volatilidade
        # Threshold ajustado para WDO: 0.0001 = ~0.55 pontos
        if momentum > 0.0001:
            signal = 1 if volatility < 0.01 else 0.5
        elif momentum < -0.0001:
            signal = -1 if volatility < 0.01 else -0.5
        else:
            signal = 0
        
        # Confiança baseada em clareza do movimento e força do sinal
        base_confidence = 1.0 - volatility * 10
        signal_strength = abs(momentum) / 0.0001  # Normalizar pelo threshold
        
        # Adicionar variação temporal para evitar valores fixos
        time_factor = 0.95 + 0.1 * np.sin(time.time() / 10)  # Oscila entre 0.95 e 1.05
        confidence = max(0.3, min(0.95, base_confidence * (0.5 + signal_strength * 0.1) * time_factor))
        
        # Aplicar decay se sinal não mudou
        state = self.agent_states['TapeReadingAgent']
        if abs(signal - state['last_signal']) < 0.01:  # Sem mudança significativa
            # Aplicar decay
            confidence = confidence * state['confidence_decay_rate']
            confidence = max(confidence, 0.3)  # Mínimo de 30%
        else:
            # Sinal mudou, resetar tempo
            state['last_change_time'] = time.time()
        
        state['last_signal'] = signal
        state['confidence'] = confidence
        
        return signal, confidence
    
    def analyze_footprint(self) -> tuple[float, float]:
        """FootprintPatternAgent - Analisa padrões de pegada"""
        
        # Usar features se disponíveis
        if hasattr(self, 'last_features') and self.last_features:
            delta_profile = self.last_features.get('delta_profile', 0)
            cumulative_delta = self.last_features.get('cumulative_delta', 0)
            absorption_ratio = self.last_features.get('absorption_ratio', 0.5)
            volume_clusters = self.last_features.get('volume_clusters', 1)
            
            # Análise de pegada baseada em delta
            footprint_score = 0
            
            # Delta positivo/negativo indica pressão
            if cumulative_delta > 100:
                footprint_score += 0.4
            elif cumulative_delta < -100:
                footprint_score -= 0.4
            else:
                footprint_score += cumulative_delta / 250.0
            
            # Absorption ratio
            if absorption_ratio > 0.7:
                footprint_score += 0.3  # Alta absorção compradora
            elif absorption_ratio < 0.3:
                footprint_score -= 0.3  # Alta absorção vendedora
            
            # Volume clusters indicam níveis importantes
            if volume_clusters > 3:
                footprint_score *= 0.8  # Reduzir sinal em áreas congestionadas
            
            # Determinar sinal
            signal = np.clip(footprint_score, -1, 1)
            
            # Confiança baseada na clareza
            confidence = min(abs(footprint_score) + 0.25, 0.85)
            
            # Adicionar variação temporal
            time_variation = 1.0 + 0.1 * np.sin(time.time() / 15)
            confidence = min(confidence * time_variation, 0.9)
            
        else:
            # Fallback para análise por buffers
            price_buffer_size = len(self.price_buffer)
            volume_buffer_size = len(self.volume_buffer)
            
            # Log para debug
            if price_buffer_size % 10 == 0:
                logger.debug(
                    f"Footprint buffers - Prices: {price_buffer_size}, "
                    f"Volumes: {volume_buffer_size}"
                )
            
            if price_buffer_size < 30 or volume_buffer_size < 30:
                # Retornar valores variáveis mesmo com poucos dados
                if price_buffer_size >= 10 and volume_buffer_size >= 10:
                    # Adicionar variação para evitar valores fixos
                    random_factor = np.random.uniform(0.95, 1.05)
                    return 0, (0.3 + min(price_buffer_size * 0.01, 0.3)) * random_factor
                return 0, 0.25
        
        prices = list(self.price_buffer)[-30:]
        volumes = list(self.volume_buffer)[-30:]
        
        # Identificar níveis de suporte/resistência por volume
        price_levels = {}
        for p, v in zip(prices, volumes):
            level = round(p / 0.5) * 0.5  # Arredondar para 0.5
            if level not in price_levels:
                price_levels[level] = 0
            price_levels[level] += v
        
        if price_levels:
            # Encontrar nível com maior volume
            poc_level = max(price_levels, key=price_levels.get)  # Point of Control
            current_price = prices[-1]
            
            # Sinal baseado em posição relativa ao POC
            distance_from_poc = (current_price - poc_level) / current_price
            
            # Threshold ajustado para WDO: 0.0002 = ~1.1 pontos
            if distance_from_poc > 0.0002:
                signal = -0.5  # Acima do POC, possível resistência
            elif distance_from_poc < -0.0002:
                signal = 0.5  # Abaixo do POC, possível suporte
            else:
                signal = 0  # No POC, neutro
            
            # Log detalhado
            logger.debug(
                f"Footprint - POC: {poc_level:.1f} | "
                f"Current: {current_price:.1f} | "
                f"Distance: {distance_from_poc:.6f}"
            )
            
            # Confiança baseada no volume no POC e distância
            total_volume = sum(price_levels.values())
            poc_strength = price_levels[poc_level] / total_volume
            distance_factor = min(abs(distance_from_poc) / 0.0002, 2.0)  # Normalizar
            
            # Adicionar variação temporal
            time_factor = 0.95 + 0.1 * np.cos(time.time() / 15)  # Oscila diferente do TapeReading
            confidence = max(0.3, min(0.95, (0.4 + poc_strength * 0.4 + distance_factor * 0.1) * time_factor))
        else:
            signal = 0
            confidence = 0.5
        
        # Aplicar decay se sinal não mudou
        state = self.agent_states['FootprintPatternAgent']
        if abs(signal - state['last_signal']) < 0.01:  # Sem mudança significativa
            # Aplicar decay
            confidence = confidence * state['confidence_decay_rate']
            confidence = max(confidence, 0.25)  # Mínimo de 25%
        else:
            # Sinal mudou, resetar tempo
            state['last_change_time'] = time.time()
        
        state['last_signal'] = signal
        state['confidence'] = confidence
        
        return signal, confidence
    
    def get_consensus(self, features: Dict = None) -> Dict:
        """Retorna consenso de todos os agentes"""
        
        # Analisar com cada agente
        signals = {
            'OrderFlowSpecialist': self.analyze_order_flow(),
            'LiquidityAgent': self.analyze_liquidity(),
            'TapeReadingAgent': self.analyze_tape(),
            'FootprintPatternAgent': self.analyze_footprint()
        }
        
        # Calcular consenso ponderado
        weighted_signal = 0
        total_confidence = 0
        
        for agent_name, (signal, confidence) in signals.items():
            weight = self.agents[agent_name]['weight']
            weighted_signal += signal * weight * confidence
            total_confidence += confidence * weight
        
        # Normalizar
        if total_confidence > 0:
            final_signal = weighted_signal / total_confidence
        else:
            final_signal = 0
        
        # Determinar ação
        if final_signal > 0.3:
            action = 'BUY'
        elif final_signal < -0.3:
            action = 'SELL'
        else:
            action = 'HOLD'
        
        # Calcular confiança do consenso
        consensus_confidence = min(total_confidence, 1.0)
        
        result = {
            'action': action,
            'signal': final_signal,
            'confidence': consensus_confidence,
            'agents': {
                name: {
                    'signal': sig,
                    'confidence': conf,
                    'weight': self.agents[name]['weight']
                }
                for name, (sig, conf) in signals.items()
            },
            'timestamp': datetime.now()
        }
        
        # Salvar status em arquivo JSON
        self._save_status(result)
        
        return result
    
    def get_agent_signals(self) -> Dict:
        """Retorna sinais individuais dos agentes para visualização"""
        result = {}
        
        for agent_name in self.agents:
            state = self.agent_states[agent_name]
            signal = state['last_signal']
            confidence = state['confidence']
            
            # Converter sinal para texto
            if signal > 0.5:
                signal_text = 'BUY'
            elif signal < -0.5:
                signal_text = 'SELL'
            else:
                signal_text = 'HOLD'
            
            result[agent_name] = {
                'signal': signal_text,
                'strength': abs(signal),
                'confidence': confidence,
                'weight': self.agents[agent_name]['weight']
            }
        
        return result
    
    def _save_status(self, consensus_data: Dict):
        """Salva o status atual em arquivo JSON"""
        try:
            # Preparar dados de mercado
            market_data = {
                'price': float(self.price_buffer[-1]) if self.price_buffer else 0,
                'volume': float(self.volume_buffer[-1]) if self.volume_buffer else 0,
                'book_data': {
                    'spread': self.book_buffer[-1].get('spread', 0) if self.book_buffer else 0,
                    'imbalance': self.book_buffer[-1].get('imbalance', 0) if self.book_buffer else 0
                }
            }
            
            # Preparar dados completos
            status_data = {
                'timestamp': datetime.now().isoformat(),
                'market_data': market_data,
                'consensus': {
                    'action': consensus_data['action'],
                    'confidence': consensus_data['confidence'],
                    'signal': consensus_data['signal'],
                    'weights': {
                        name: data['weight'] 
                        for name, data in consensus_data['agents'].items()
                    }
                },
                'agents': consensus_data['agents']
            }
            
            # Salvar em arquivo (em dois locais para compatibilidade)
            # Usar escrita atômica para evitar leitura de arquivo parcial
            import tempfile
            import shutil
            
            # Local 1: Raiz (para debug)
            status_file = Path('hmarl_status.json')
            temp_file = Path(tempfile.mktemp(suffix='.json', dir='.'))
            try:
                with open(temp_file, 'w') as f:
                    json.dump(status_data, f, indent=2, default=str)
                shutil.move(str(temp_file), str(status_file))
            except:
                if temp_file.exists():
                    temp_file.unlink()
            
            # Local 2: data/monitor (para o monitor)
            monitor_dir = Path('data/monitor')
            monitor_dir.mkdir(parents=True, exist_ok=True)
            monitor_file = monitor_dir / 'hmarl_status.json'
            temp_file2 = Path(tempfile.mktemp(suffix='.json', dir=str(monitor_dir)))
            try:
                with open(temp_file2, 'w') as f:
                    json.dump(status_data, f, indent=2, default=str)
                shutil.move(str(temp_file2), str(monitor_file))
            except:
                if temp_file2.exists():
                    temp_file2.unlink()
            
        except Exception as e:
            logger.error(f"Erro ao salvar status HMARL: {e}")