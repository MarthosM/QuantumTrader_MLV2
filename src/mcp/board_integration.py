"""
Integração do Project Board com o sistema de trading

Monitora o sistema e atualiza automaticamente o status das fases no board.
"""

import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import sqlite3

from src.mcp.project_board_server import ProjectBoardStore, ProjectPhase, PhaseStatus, Task, TaskPriority

logger = logging.getLogger(__name__)


class BoardIntegration:
    """Integra o Project Board com o sistema de trading"""
    
    def __init__(self):
        self.board = ProjectBoardStore()
        self.metrics_file = Path("metrics/current_metrics.json")
        self.log_dir = Path("logs")
        self.models_dir = Path("models")
        self.last_check = {}
        
    def check_infrastructure_status(self) -> Dict[str, Any]:
        """Verifica status da infraestrutura"""
        status = {
            "healthy": True,
            "components": {},
            "issues": []
        }
        
        # Verifica arquivos core
        core_files = [
            "core/enhanced_production_system.py",
            "src/buffers/circular_buffer.py",
            "src/connection_manager_v4.py"
        ]
        
        for file in core_files:
            if Path(file).exists():
                status["components"][file] = "ok"
            else:
                status["components"][file] = "missing"
                status["healthy"] = False
                status["issues"].append(f"Missing: {file}")
        
        # Verifica PID file (sistema rodando)
        if Path("quantum_trader.pid").exists():
            status["system_running"] = True
        else:
            status["system_running"] = False
            status["issues"].append("System not running")
        
        return status
    
    def check_features_status(self) -> Dict[str, Any]:
        """Verifica status do Feature Engineering"""
        status = {
            "healthy": True,
            "feature_count": 0,
            "latency": None,
            "issues": []
        }
        
        # Verifica arquivo de features
        features_file = Path("src/features/book_features_rt.py")
        if not features_file.exists():
            status["healthy"] = False
            status["issues"].append("Feature file missing")
            return status
        
        # Lê métricas se disponível
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file) as f:
                    metrics = json.load(f)
                    
                if "feature_calculation" in metrics:
                    status["feature_count"] = metrics["feature_calculation"].get("count", 0)
                    status["latency"] = metrics["feature_calculation"].get("latency_ms", None)
                    
                    # Verifica se latência está aceitável (< 10ms)
                    if status["latency"] and status["latency"] > 10:
                        status["issues"].append(f"High latency: {status['latency']}ms")
            except Exception as e:
                status["issues"].append(f"Error reading metrics: {e}")
        
        return status
    
    def check_ml_models_status(self) -> Dict[str, Any]:
        """Verifica status dos modelos ML"""
        status = {
            "healthy": True,
            "models_loaded": [],
            "models_missing": [],
            "issues": []
        }
        
        expected_models = [
            "lightgbm_balanced.pkl",
            "xgboost_fast.pkl",
            "random_forest_stable.pkl"
        ]
        
        for model in expected_models:
            model_path = self.models_dir / model
            if model_path.exists():
                status["models_loaded"].append(model)
            else:
                status["models_missing"].append(model)
                status["issues"].append(f"Model missing: {model}")
        
        if status["models_missing"]:
            status["healthy"] = False
        
        return status
    
    def check_hmarl_status(self) -> Dict[str, Any]:
        """Verifica status dos agentes HMARL"""
        status = {
            "healthy": True,
            "agents_available": False,
            "agent_performance": {},
            "issues": []
        }
        
        # Verifica arquivo dos agentes
        agents_file = Path("src/agents/hmarl_agents_enhanced.py")
        if not agents_file.exists():
            status["healthy"] = False
            status["issues"].append("HMARL agents file missing")
            return status
        
        # Verifica logs para status dos agentes
        latest_log = self.get_latest_log()
        if latest_log:
            try:
                with open(latest_log) as f:
                    content = f.read()
                    
                    if "HMARL agents initialized" in content:
                        status["agents_available"] = True
                    elif "HMARL não disponível" in content:
                        status["issues"].append("HMARL agents not available")
                    
                    # Procura por métricas de performance
                    if "OrderFlowSpecialist:" in content:
                        # Parse performance metrics from logs
                        pass
                        
            except Exception as e:
                status["issues"].append(f"Error reading logs: {e}")
        
        return status
    
    def check_consensus_status(self) -> Dict[str, Any]:
        """Verifica status do sistema de consenso"""
        status = {
            "healthy": True,
            "ml_weight": 0.4,
            "hmarl_weight": 0.6,
            "last_decision": None,
            "issues": []
        }
        
        # Verifica arquivo de consenso
        consensus_file = Path("src/consensus/hmarl_consensus_system.py")
        if not consensus_file.exists():
            status["healthy"] = False
            status["issues"].append("Consensus system file missing")
            return status
        
        # Lê métricas se disponível
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file) as f:
                    metrics = json.load(f)
                    
                if "consensus" in metrics:
                    status["last_decision"] = metrics["consensus"].get("last_decision")
                    status["ml_weight"] = metrics["consensus"].get("ml_weight", 0.4)
                    status["hmarl_weight"] = metrics["consensus"].get("hmarl_weight", 0.6)
                    
            except Exception as e:
                status["issues"].append(f"Error reading metrics: {e}")
        
        return status
    
    def check_risk_management_status(self) -> Dict[str, Any]:
        """Verifica status do gerenciamento de risco"""
        status = {
            "healthy": True,
            "stop_loss": 0.005,
            "take_profit": 0.010,
            "max_daily_trades": 10,
            "current_trades": 0,
            "issues": []
        }
        
        # Lê configuração
        config_file = Path("config_production.json")
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                    
                status["stop_loss"] = config.get("stop_loss", 0.005)
                status["take_profit"] = config.get("take_profit", 0.010)
                status["max_daily_trades"] = config.get("max_daily_trades", 10)
                
            except Exception as e:
                status["issues"].append(f"Error reading config: {e}")
        
        # Verifica trades do dia
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file) as f:
                    metrics = json.load(f)
                    
                if "trading" in metrics:
                    status["current_trades"] = metrics["trading"].get("daily_trades", 0)
                    
                    if status["current_trades"] >= status["max_daily_trades"]:
                        status["issues"].append("Daily trade limit reached")
                        
            except Exception as e:
                status["issues"].append(f"Error reading metrics: {e}")
        
        return status
    
    def check_monitoring_status(self) -> Dict[str, Any]:
        """Verifica status do monitoramento"""
        status = {
            "healthy": True,
            "monitor_running": False,
            "logs_active": False,
            "issues": []
        }
        
        # Verifica se monitor está rodando
        monitor_files = [
            "core/monitor_console_enhanced.py",
            "src/logging/structured_logger.py"
        ]
        
        for file in monitor_files:
            if not Path(file).exists():
                status["issues"].append(f"Monitor file missing: {file}")
                status["healthy"] = False
        
        # Verifica logs recentes
        latest_log = self.get_latest_log()
        if latest_log:
            # Log foi modificado nos últimos 5 minutos?
            log_age = datetime.now() - datetime.fromtimestamp(latest_log.stat().st_mtime)
            if log_age.total_seconds() < 300:
                status["logs_active"] = True
            else:
                status["issues"].append("Logs not being updated")
        else:
            status["issues"].append("No log files found")
            status["healthy"] = False
        
        return status
    
    def get_latest_log(self) -> Optional[Path]:
        """Obtém o arquivo de log mais recente"""
        if not self.log_dir.exists():
            return None
        
        log_files = list(self.log_dir.glob("production_*.log"))
        if not log_files:
            return None
        
        return max(log_files, key=lambda f: f.stat().st_mtime)
    
    async def update_board(self):
        """Atualiza o board com status atual do sistema"""
        
        # Mapeia checagens para fases
        checks = {
            "Infrastructure": self.check_infrastructure_status(),
            "Feature Engineering": self.check_features_status(),
            "ML Models": self.check_ml_models_status(),
            "HMARL Agents": self.check_hmarl_status(),
            "Consensus System": self.check_consensus_status(),
            "Risk Management": self.check_risk_management_status(),
            "Monitoring": self.check_monitoring_status()
        }
        
        for phase_name, status in checks.items():
            # Determina novo status da fase
            if status["healthy"]:
                if phase_name in ["Infrastructure", "Feature Engineering", "ML Models", "Monitoring"]:
                    phase_status = PhaseStatus.COMPLETED.value
                    progress = 100.0
                else:
                    phase_status = PhaseStatus.TESTING.value
                    progress = 80.0
            else:
                if status.get("issues"):
                    phase_status = PhaseStatus.BLOCKED.value
                    progress = 50.0
                else:
                    phase_status = PhaseStatus.IN_PROGRESS.value
                    progress = 60.0
            
            # Busca fase existente
            phases = self.board.get_phases()
            phase = next((p for p in phases if p.name == phase_name), None)
            
            if phase:
                # Atualiza apenas se mudou
                if phase.status != phase_status or phase.progress != progress:
                    phase.status = phase_status
                    phase.progress = progress
                    phase.issues = status.get("issues", [])
                    
                    # Adiciona métricas específicas
                    phase.metrics = {
                        "last_check": datetime.now().isoformat(),
                        "details": status
                    }
                    
                    self.board.create_or_update_phase(phase)
                    logger.info(f"Updated {phase_name}: {phase_status} ({progress}%)")
            
            # Cria tarefas para issues críticas
            if status.get("issues"):
                for issue in status["issues"][:3]:  # Limita a 3 issues por fase
                    # Verifica se tarefa já existe
                    existing_tasks = self.board.get_tasks(phase_id=phase.id if phase else None)
                    if not any(t.title == issue for t in existing_tasks if t.status == "open"):
                        task = Task(
                            phase_id=phase.id if phase else 0,
                            title=issue,
                            description=f"Issue detected in {phase_name}",
                            priority=TaskPriority.HIGH.value if "missing" in issue.lower() else TaskPriority.MEDIUM.value,
                            status="open"
                        )
                        self.board.create_task(task)
                        logger.info(f"Created task for issue: {issue}")
    
    async def monitor_loop(self, interval: int = 60):
        """Loop de monitoramento contínuo"""
        logger.info("Starting Project Board monitoring...")
        
        while True:
            try:
                await self.update_board()
                
                # Registra métricas gerais
                phases = self.board.get_phases()
                total_progress = sum(p.progress for p in phases) / len(phases) if phases else 0
                
                self.board.record_metric(
                    "overall_progress",
                    total_progress,
                    unit="%",
                    phase="System"
                )
                
                # Aguarda próximo ciclo
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval)


async def main():
    """Entry point para integração standalone"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Project Board Integration")
    parser.add_argument('--interval', type=int, default=60, help='Update interval in seconds')
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    integration = BoardIntegration()
    
    try:
        await integration.monitor_loop(interval=args.interval)
    except KeyboardInterrupt:
        logger.info("Stopping Project Board integration...")


if __name__ == "__main__":
    asyncio.run(main())