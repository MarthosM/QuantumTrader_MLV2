"""
Rastreador de Métricas por Regime de Mercado
Analisa performance em diferentes condições de mercado
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class RegimeMetricsTracker:
    """Rastreia e analisa métricas de trading por regime de mercado"""
    
    def __init__(self, data_dir: str = "data/metrics"):
        """
        Inicializa o rastreador de métricas
        
        Args:
            data_dir: Diretório para salvar dados
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Métricas por regime
        self.regime_metrics = {
            'TRENDING_UP': self._create_metrics_dict(),
            'TRENDING_DOWN': self._create_metrics_dict(),
            'RANGING': self._create_metrics_dict(),
            'VOLATILE': self._create_metrics_dict(),
            'UNDEFINED': self._create_metrics_dict()
        }
        
        # Histórico de trades
        self.trade_history = []
        
        # Sessão atual
        self.current_session = {
            'start_time': datetime.now(),
            'trades': [],
            'regime_changes': [],
            'daily_pnl': 0
        }
        
        # Carregar dados históricos se existirem
        self._load_historical_data()
        
        logger.info("RegimeMetricsTracker inicializado")
    
    def _create_metrics_dict(self) -> Dict:
        """Cria estrutura de métricas vazia"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0,
            'max_win': 0.0,
            'max_loss': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'average_duration': 0,
            'best_hour': None,
            'worst_hour': None,
            'trade_distribution': defaultdict(int),
            'pnl_curve': [],
            'confidence_stats': {
                'ml_avg': 0.0,
                'hmarl_avg': 0.0,
                'combined_avg': 0.0
            }
        }
    
    def record_trade(self, trade_data: Dict):
        """
        Registra um trade executado
        
        Args:
            trade_data: Dados do trade
        """
        # Extrair informações
        regime = trade_data.get('regime', 'UNDEFINED')
        entry_time = trade_data.get('entry_time', datetime.now())
        exit_time = trade_data.get('exit_time')
        direction = trade_data.get('direction')
        entry_price = trade_data.get('entry_price', 0)
        exit_price = trade_data.get('exit_price', 0)
        quantity = trade_data.get('quantity', 1)
        
        # Calcular P&L
        if direction == 'BUY':
            pnl_points = (exit_price - entry_price) / 0.5
        else:  # SELL
            pnl_points = (entry_price - exit_price) / 0.5
        
        pnl_value = pnl_points * quantity * 0.5  # Valor monetário
        
        # Criar registro completo
        trade_record = {
            'id': trade_data.get('id', f"trade_{len(self.trade_history)}"),
            'regime': regime,
            'direction': direction,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'duration': (exit_time - entry_time).total_seconds() / 60 if exit_time else 0,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'quantity': quantity,
            'pnl_points': pnl_points,
            'pnl_value': pnl_value,
            'is_winner': pnl_points > 0,
            'ml_confidence': trade_data.get('ml_confidence', 0),
            'hmarl_confidence': trade_data.get('hmarl_confidence', 0),
            'combined_confidence': trade_data.get('combined_confidence', 0),
            'exit_reason': trade_data.get('exit_reason', 'unknown'),
            'max_profit': trade_data.get('max_profit', 0),
            'max_loss': trade_data.get('max_loss', 0),
            'partial_exits': trade_data.get('partial_exits', [])
        }
        
        # Adicionar ao histórico
        self.trade_history.append(trade_record)
        self.current_session['trades'].append(trade_record)
        
        # Atualizar métricas do regime
        self._update_regime_metrics(regime, trade_record)
        
        # Atualizar P&L diário
        self.current_session['daily_pnl'] += pnl_value
        
        # Log
        status = "✓ WIN" if trade_record['is_winner'] else "✗ LOSS"
        logger.info(
            f"[METRICS] Trade {status} | Regime: {regime} | "
            f"P&L: {pnl_points:.1f} pts ({pnl_value:.2f} R$) | "
            f"Duração: {trade_record['duration']:.1f} min"
        )
    
    def _update_regime_metrics(self, regime: str, trade: Dict):
        """Atualiza métricas específicas do regime"""
        
        metrics = self.regime_metrics[regime]
        
        # Contadores básicos
        metrics['total_trades'] += 1
        if trade['is_winner']:
            metrics['winning_trades'] += 1
        else:
            metrics['losing_trades'] += 1
        
        # Win rate
        metrics['win_rate'] = metrics['winning_trades'] / metrics['total_trades']
        
        # P&L
        metrics['total_pnl'] += trade['pnl_points']
        metrics['pnl_curve'].append(metrics['total_pnl'])
        
        # Médias de ganho/perda
        if trade['is_winner']:
            if metrics['winning_trades'] == 1:
                metrics['average_win'] = trade['pnl_points']
            else:
                metrics['average_win'] = (
                    metrics['average_win'] * (metrics['winning_trades'] - 1) + 
                    trade['pnl_points']
                ) / metrics['winning_trades']
            
            metrics['max_win'] = max(metrics['max_win'], trade['pnl_points'])
        else:
            if metrics['losing_trades'] == 1:
                metrics['average_loss'] = abs(trade['pnl_points'])
            else:
                metrics['average_loss'] = (
                    metrics['average_loss'] * (metrics['losing_trades'] - 1) + 
                    abs(trade['pnl_points'])
                ) / metrics['losing_trades']
            
            metrics['max_loss'] = max(metrics['max_loss'], abs(trade['pnl_points']))
        
        # Profit Factor
        if metrics['average_loss'] > 0:
            metrics['profit_factor'] = (
                metrics['average_win'] * metrics['winning_trades']
            ) / (
                metrics['average_loss'] * metrics['losing_trades']
            )
        
        # Duração média
        if metrics['total_trades'] == 1:
            metrics['average_duration'] = trade['duration']
        else:
            metrics['average_duration'] = (
                metrics['average_duration'] * (metrics['total_trades'] - 1) + 
                trade['duration']
            ) / metrics['total_trades']
        
        # Distribuição por hora
        hour = trade['entry_time'].hour
        metrics['trade_distribution'][hour] += 1
        
        # Estatísticas de confiança
        metrics['confidence_stats']['ml_avg'] = (
            metrics['confidence_stats']['ml_avg'] * (metrics['total_trades'] - 1) + 
            trade['ml_confidence']
        ) / metrics['total_trades']
        
        metrics['confidence_stats']['hmarl_avg'] = (
            metrics['confidence_stats']['hmarl_avg'] * (metrics['total_trades'] - 1) + 
            trade['hmarl_confidence']
        ) / metrics['total_trades']
        
        metrics['confidence_stats']['combined_avg'] = (
            metrics['confidence_stats']['combined_avg'] * (metrics['total_trades'] - 1) + 
            trade['combined_confidence']
        ) / metrics['total_trades']
        
        # Calcular Sharpe Ratio
        if len(metrics['pnl_curve']) > 1:
            returns = np.diff(metrics['pnl_curve'])
            if np.std(returns) > 0:
                metrics['sharpe_ratio'] = np.mean(returns) / np.std(returns) * np.sqrt(252)
        
        # Calcular Max Drawdown
        if metrics['pnl_curve']:
            cumulative = np.array(metrics['pnl_curve'])
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / np.maximum(running_max, 1)
            metrics['max_drawdown'] = abs(np.min(drawdown)) if len(drawdown) > 0 else 0
    
    def record_regime_change(self, old_regime: str, new_regime: str):
        """Registra mudança de regime"""
        
        change_record = {
            'timestamp': datetime.now(),
            'from': old_regime,
            'to': new_regime,
            'session_trades': len(self.current_session['trades']),
            'session_pnl': self.current_session['daily_pnl']
        }
        
        self.current_session['regime_changes'].append(change_record)
        
        logger.info(
            f"[METRICS] Mudança de regime: {old_regime} → {new_regime} | "
            f"Trades na sessão: {change_record['session_trades']} | "
            f"P&L: {change_record['session_pnl']:.2f}"
        )
    
    def get_regime_performance(self, regime: str = None) -> Dict:
        """
        Retorna performance de um regime específico ou todos
        
        Args:
            regime: Regime específico ou None para todos
            
        Returns:
            Métricas de performance
        """
        if regime:
            return self.regime_metrics.get(regime, {})
        
        return self.regime_metrics
    
    def get_best_regime(self) -> Tuple[str, Dict]:
        """Retorna o regime com melhor performance"""
        
        best_regime = None
        best_score = -float('inf')
        
        for regime, metrics in self.regime_metrics.items():
            if metrics['total_trades'] < 5:  # Mínimo de trades
                continue
            
            # Score composto
            score = (
                metrics['win_rate'] * 100 +
                metrics['profit_factor'] * 10 +
                metrics['total_pnl'] -
                metrics['max_drawdown'] * 50
            )
            
            if score > best_score:
                best_score = score
                best_regime = regime
        
        if best_regime:
            return best_regime, self.regime_metrics[best_regime]
        
        return 'UNDEFINED', self.regime_metrics['UNDEFINED']
    
    def get_comparison_table(self) -> pd.DataFrame:
        """Retorna tabela comparativa de regimes"""
        
        data = []
        for regime, metrics in self.regime_metrics.items():
            if metrics['total_trades'] == 0:
                continue
            
            data.append({
                'Regime': regime,
                'Trades': metrics['total_trades'],
                'Win Rate': f"{metrics['win_rate']:.1%}",
                'Avg Win': f"{metrics['average_win']:.1f}",
                'Avg Loss': f"{metrics['average_loss']:.1f}",
                'P. Factor': f"{metrics['profit_factor']:.2f}",
                'Total P&L': f"{metrics['total_pnl']:.1f}",
                'Sharpe': f"{metrics['sharpe_ratio']:.2f}",
                'Max DD': f"{metrics['max_drawdown']:.1%}",
                'Avg Duration': f"{metrics['average_duration']:.0f}m"
            })
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        return df.sort_values('Total P&L', ascending=False)
    
    def get_hourly_performance(self) -> Dict:
        """Retorna performance por hora do dia"""
        
        hourly_stats = defaultdict(lambda: {
            'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0
        })
        
        for trade in self.trade_history:
            hour = trade['entry_time'].hour
            hourly_stats[hour]['trades'] += 1
            
            if trade['is_winner']:
                hourly_stats[hour]['wins'] += 1
            else:
                hourly_stats[hour]['losses'] += 1
            
            hourly_stats[hour]['pnl'] += trade['pnl_points']
        
        # Calcular win rate por hora
        for hour in hourly_stats:
            if hourly_stats[hour]['trades'] > 0:
                hourly_stats[hour]['win_rate'] = (
                    hourly_stats[hour]['wins'] / hourly_stats[hour]['trades']
                )
        
        return dict(hourly_stats)
    
    def get_recommendations(self) -> Dict:
        """Retorna recomendações baseadas nas métricas"""
        
        recommendations = {
            'best_regime': None,
            'worst_regime': None,
            'best_hours': [],
            'worst_hours': [],
            'suggestions': []
        }
        
        # Melhor e pior regime
        regimes_with_trades = {
            r: m for r, m in self.regime_metrics.items() 
            if m['total_trades'] >= 5
        }
        
        if regimes_with_trades:
            best = max(regimes_with_trades.items(), 
                      key=lambda x: x[1]['win_rate'] * x[1]['profit_factor'])
            worst = min(regimes_with_trades.items(), 
                       key=lambda x: x[1]['win_rate'] * x[1]['profit_factor'])
            
            recommendations['best_regime'] = best[0]
            recommendations['worst_regime'] = worst[0]
            
            # Sugestões baseadas em performance
            if best[1]['win_rate'] > 0.6:
                recommendations['suggestions'].append(
                    f"Aumentar tamanho de posição em {best[0]} (WR: {best[1]['win_rate']:.1%})"
                )
            
            if worst[1]['win_rate'] < 0.4:
                recommendations['suggestions'].append(
                    f"Evitar trades em {worst[0]} (WR: {worst[1]['win_rate']:.1%})"
                )
        
        # Melhores e piores horários
        hourly = self.get_hourly_performance()
        if hourly:
            sorted_hours = sorted(hourly.items(), 
                                key=lambda x: x[1].get('win_rate', 0), 
                                reverse=True)
            
            if len(sorted_hours) >= 3:
                recommendations['best_hours'] = [h[0] for h in sorted_hours[:3]]
                recommendations['worst_hours'] = [h[0] for h in sorted_hours[-3:]]
                
                # Sugestão de horário
                if sorted_hours[0][1]['win_rate'] > 0.65:
                    recommendations['suggestions'].append(
                        f"Focar trades entre {sorted_hours[0][0]}:00-{sorted_hours[0][0]+1}:00"
                    )
        
        # Análise de drawdown
        for regime, metrics in self.regime_metrics.items():
            if metrics['max_drawdown'] > 0.15:  # 15%
                recommendations['suggestions'].append(
                    f"Reduzir risco em {regime} (DD: {metrics['max_drawdown']:.1%})"
                )
        
        return recommendations
    
    def save_session_data(self):
        """Salva dados da sessão atual"""
        
        session_file = self.data_dir / f"session_{datetime.now():%Y%m%d_%H%M%S}.json"
        
        session_data = {
            'start_time': self.current_session['start_time'].isoformat(),
            'end_time': datetime.now().isoformat(),
            'total_trades': len(self.current_session['trades']),
            'daily_pnl': self.current_session['daily_pnl'],
            'regime_changes': len(self.current_session['regime_changes']),
            'trades': self.current_session['trades'],
            'regime_metrics': {
                regime: {
                    k: v if not isinstance(v, (defaultdict, np.ndarray)) else str(v)
                    for k, v in metrics.items()
                }
                for regime, metrics in self.regime_metrics.items()
            }
        }
        
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2, default=str)
        
        logger.info(f"[METRICS] Sessão salva em {session_file}")
    
    def _load_historical_data(self):
        """Carrega dados históricos salvos"""
        
        try:
            # Procurar arquivos de sessão
            session_files = sorted(self.data_dir.glob("session_*.json"))
            
            if session_files:
                # Carregar última sessão
                with open(session_files[-1], 'r') as f:
                    last_session = json.load(f)
                
                # Restaurar métricas (simplificado)
                logger.info(f"[METRICS] Carregado histórico de {len(session_files)} sessões")
        except Exception as e:
            logger.error(f"Erro ao carregar histórico: {e}")
    
    def reset_daily_metrics(self):
        """Reseta métricas diárias"""
        
        self.current_session = {
            'start_time': datetime.now(),
            'trades': [],
            'regime_changes': [],
            'daily_pnl': 0
        }
        
        logger.info("[METRICS] Métricas diárias resetadas")
    
    def get_summary_report(self) -> str:
        """Gera relatório resumido"""
        
        report = []
        report.append("=" * 60)
        report.append("RELATÓRIO DE PERFORMANCE POR REGIME")
        report.append("=" * 60)
        
        # Tabela comparativa
        df = self.get_comparison_table()
        if not df.empty:
            report.append("\n" + df.to_string(index=False))
        
        # Melhor regime
        best_regime, best_metrics = self.get_best_regime()
        report.append(f"\n✓ Melhor Regime: {best_regime}")
        report.append(f"  Win Rate: {best_metrics['win_rate']:.1%}")
        report.append(f"  Profit Factor: {best_metrics['profit_factor']:.2f}")
        
        # Recomendações
        recommendations = self.get_recommendations()
        if recommendations['suggestions']:
            report.append("\n📊 Recomendações:")
            for suggestion in recommendations['suggestions']:
                report.append(f"  • {suggestion}")
        
        # P&L do dia
        report.append(f"\n💰 P&L do Dia: {self.current_session['daily_pnl']:.2f} R$")
        report.append(f"📈 Total de Trades: {len(self.current_session['trades'])}")
        
        return "\n".join(report)