"""
Project Board MCP Server for QuantumTrader Production System

Mantém um board de projeto com status de cada fase do sistema de trading,
permitindo tracking de progresso, issues, melhorias e deployments.
"""

import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("MCP SDK not installed. Please install with: pip install mcp[cli]")
    FastMCP = None

logger = logging.getLogger(__name__)


class PhaseStatus(Enum):
    """Status possíveis de uma fase do projeto"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class TaskPriority(Enum):
    """Prioridades das tarefas"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ProjectPhase:
    """Fase do projeto"""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    status: str = PhaseStatus.NOT_STARTED.value
    progress: float = 0.0  # 0-100
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    components: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


@dataclass
class Task:
    """Tarefa ou issue do projeto"""
    id: Optional[int] = None
    phase_id: int = 0
    title: str = ""
    description: str = ""
    priority: str = TaskPriority.MEDIUM.value
    status: str = "open"
    assignee: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    completed_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class Deployment:
    """Registro de deployment"""
    id: Optional[int] = None
    version: str = ""
    phase: str = ""
    status: str = ""
    features: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)
    rollback_version: Optional[str] = None
    deployed_at: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)


class ProjectBoardStore:
    """SQLite storage para o project board"""
    
    def __init__(self, db_path: str = "data/project_board.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()
    
    def _initialize_db(self):
        """Inicializa schema do banco de dados"""
        with sqlite3.connect(self.db_path) as conn:
            # Tabela de fases do projeto
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_phases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    progress REAL DEFAULT 0.0,
                    start_date TEXT,
                    end_date TEXT,
                    dependencies TEXT,
                    components TEXT,
                    metrics TEXT,
                    issues TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Tabela de tarefas/issues
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phase_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'open',
                    assignee TEXT,
                    tags TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (phase_id) REFERENCES project_phases(id)
                )
            """)
            
            # Tabela de deployments
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deployments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT UNIQUE NOT NULL,
                    phase TEXT,
                    status TEXT,
                    features TEXT,
                    fixes TEXT,
                    rollback_version TEXT,
                    deployed_at TEXT NOT NULL,
                    metrics TEXT
                )
            """)
            
            # Tabela de métricas do sistema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    value REAL,
                    unit TEXT,
                    phase TEXT,
                    metadata TEXT
                )
            """)
            
            # Índices para performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_phase_status ON project_phases(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_phase ON tasks(phase_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_deployment_version ON deployments(version)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON system_metrics(timestamp)")
            
            conn.commit()
    
    def create_or_update_phase(self, phase: ProjectPhase) -> int:
        """Cria ou atualiza uma fase do projeto"""
        phase.updated_at = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            # Verifica se a fase já existe
            cursor = conn.execute("SELECT id FROM project_phases WHERE name = ?", (phase.name,))
            existing = cursor.fetchone()
            
            if existing:
                # Atualiza fase existente
                phase.id = existing[0]
                conn.execute("""
                    UPDATE project_phases SET
                        description = ?, status = ?, progress = ?,
                        start_date = ?, end_date = ?, dependencies = ?,
                        components = ?, metrics = ?, issues = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    phase.description, phase.status, phase.progress,
                    phase.start_date, phase.end_date,
                    json.dumps(phase.dependencies), json.dumps(phase.components),
                    json.dumps(phase.metrics), json.dumps(phase.issues),
                    phase.updated_at, phase.id
                ))
            else:
                # Cria nova fase
                cursor = conn.execute("""
                    INSERT INTO project_phases 
                    (name, description, status, progress, start_date, end_date,
                     dependencies, components, metrics, issues, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    phase.name, phase.description, phase.status, phase.progress,
                    phase.start_date, phase.end_date,
                    json.dumps(phase.dependencies), json.dumps(phase.components),
                    json.dumps(phase.metrics), json.dumps(phase.issues),
                    phase.created_at, phase.updated_at
                ))
                phase.id = cursor.lastrowid
            
            conn.commit()
            return phase.id
    
    def get_phases(self, status: Optional[str] = None) -> List[ProjectPhase]:
        """Obtém fases do projeto"""
        query = "SELECT * FROM project_phases"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        query += " ORDER BY id"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            phases = []
            for row in cursor:
                phase = ProjectPhase(
                    id=row['id'],
                    name=row['name'],
                    description=row['description'],
                    status=row['status'],
                    progress=row['progress'],
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    dependencies=json.loads(row['dependencies']) if row['dependencies'] else [],
                    components=json.loads(row['components']) if row['components'] else [],
                    metrics=json.loads(row['metrics']) if row['metrics'] else {},
                    issues=json.loads(row['issues']) if row['issues'] else [],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                phases.append(phase)
            
            return phases
    
    def create_task(self, task: Task) -> int:
        """Cria uma nova tarefa"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO tasks 
                (phase_id, title, description, priority, status, assignee, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.phase_id, task.title, task.description,
                task.priority, task.status, task.assignee,
                json.dumps(task.tags), task.created_at
            ))
            return cursor.lastrowid
    
    def update_task_status(self, task_id: int, status: str):
        """Atualiza status de uma tarefa"""
        with sqlite3.connect(self.db_path) as conn:
            completed_at = datetime.now().isoformat() if status == "completed" else None
            conn.execute(
                "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
                (status, completed_at, task_id)
            )
            conn.commit()
    
    def get_tasks(self, phase_id: Optional[int] = None, status: Optional[str] = None) -> List[Task]:
        """Obtém tarefas"""
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if phase_id:
            query += " AND phase_id = ?"
            params.append(phase_id)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY priority DESC, created_at DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            tasks = []
            for row in cursor:
                task = Task(
                    id=row['id'],
                    phase_id=row['phase_id'],
                    title=row['title'],
                    description=row['description'],
                    priority=row['priority'],
                    status=row['status'],
                    assignee=row['assignee'],
                    tags=json.loads(row['tags']) if row['tags'] else [],
                    created_at=row['created_at'],
                    completed_at=row['completed_at']
                )
                tasks.append(task)
            
            return tasks
    
    def record_deployment(self, deployment: Deployment) -> int:
        """Registra um deployment"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO deployments 
                (version, phase, status, features, fixes, rollback_version, deployed_at, metrics)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                deployment.version, deployment.phase, deployment.status,
                json.dumps(deployment.features), json.dumps(deployment.fixes),
                deployment.rollback_version, deployment.deployed_at,
                json.dumps(deployment.metrics)
            ))
            return cursor.lastrowid
    
    def record_metric(self, metric_name: str, value: float, unit: str = "", phase: str = "", metadata: Dict = None):
        """Registra uma métrica do sistema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO system_metrics 
                (timestamp, metric_name, value, unit, phase, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(), metric_name, value,
                unit, phase, json.dumps(metadata) if metadata else "{}"
            ))
            conn.commit()


class ProjectBoardMCP:
    """Project Board MCP Server"""
    
    def __init__(self):
        self.store = ProjectBoardStore()
        self._initialize_default_phases()
        
        if FastMCP:
            self.mcp = FastMCP("QuantumTrader Project Board")
            self._setup_mcp_endpoints()
        else:
            self.mcp = None
            logger.warning("MCP SDK not available - Project Board running in standalone mode")
    
    def _initialize_default_phases(self):
        """Inicializa fases padrão do projeto QuantumTrader"""
        default_phases = [
            ProjectPhase(
                name="Infrastructure",
                description="Core infrastructure and system setup",
                components=["enhanced_production_system.py", "circular_buffer.py", "connection_manager.py"],
                status=PhaseStatus.COMPLETED.value,
                progress=100.0
            ),
            ProjectPhase(
                name="Feature Engineering",
                description="65 microstructure features implementation",
                components=["book_features_rt.py"],
                dependencies=["Infrastructure"],
                status=PhaseStatus.COMPLETED.value,
                progress=100.0
            ),
            ProjectPhase(
                name="ML Models",
                description="Machine learning models integration",
                components=["lightgbm_balanced.pkl", "xgboost_fast.pkl", "random_forest_stable.pkl"],
                dependencies=["Feature Engineering"],
                status=PhaseStatus.COMPLETED.value,
                progress=100.0
            ),
            ProjectPhase(
                name="HMARL Agents",
                description="4 specialized HMARL agents",
                components=["hmarl_agents_enhanced.py"],
                dependencies=["Feature Engineering"],
                status=PhaseStatus.TESTING.value,
                progress=80.0
            ),
            ProjectPhase(
                name="Consensus System",
                description="ML + HMARL consensus integration",
                components=["hmarl_consensus_system.py"],
                dependencies=["ML Models", "HMARL Agents"],
                status=PhaseStatus.IN_PROGRESS.value,
                progress=60.0
            ),
            ProjectPhase(
                name="Risk Management",
                description="Stop loss, take profit, position sizing",
                components=["metrics_and_alerts.py"],
                dependencies=["Consensus System"],
                status=PhaseStatus.IN_PROGRESS.value,
                progress=70.0
            ),
            ProjectPhase(
                name="Monitoring",
                description="Real-time monitoring and alerts",
                components=["monitor_console_enhanced.py", "structured_logger.py"],
                dependencies=["Infrastructure"],
                status=PhaseStatus.COMPLETED.value,
                progress=100.0
            ),
            ProjectPhase(
                name="MCP Integration",
                description="Model Context Protocol server integration",
                components=["project_board_server.py", "memory_server.py"],
                dependencies=["Infrastructure"],
                status=PhaseStatus.IN_PROGRESS.value,
                progress=30.0
            ),
            ProjectPhase(
                name="Production Deployment",
                description="Final production deployment and optimization",
                dependencies=["Consensus System", "Risk Management", "Monitoring"],
                status=PhaseStatus.NOT_STARTED.value,
                progress=0.0
            )
        ]
        
        for phase in default_phases:
            self.store.create_or_update_phase(phase)
    
    def _setup_mcp_endpoints(self):
        """Configura endpoints do MCP server"""
        
        @self.mcp.resource("board://phases/all")
        async def get_all_phases() -> str:
            """Obtém todas as fases do projeto"""
            phases = self.store.get_phases()
            return json.dumps([asdict(p) for p in phases], indent=2)
        
        @self.mcp.resource("board://phases/active")
        async def get_active_phases() -> str:
            """Obtém fases ativas (in_progress ou testing)"""
            in_progress = self.store.get_phases(PhaseStatus.IN_PROGRESS.value)
            testing = self.store.get_phases(PhaseStatus.TESTING.value)
            return json.dumps([asdict(p) for p in (in_progress + testing)], indent=2)
        
        @self.mcp.tool()
        async def update_phase_status(
            phase_name: str,
            status: str,
            progress: Optional[float] = None,
            issues: Optional[List[str]] = None
        ) -> Dict[str, Any]:
            """Atualiza status de uma fase do projeto
            
            Args:
                phase_name: Nome da fase
                status: Novo status (not_started, in_progress, testing, completed, blocked, failed)
                progress: Progresso percentual (0-100)
                issues: Lista de issues/problemas encontrados
            """
            phases = self.store.get_phases()
            phase = next((p for p in phases if p.name == phase_name), None)
            
            if not phase:
                return {"status": "error", "message": f"Phase {phase_name} not found"}
            
            phase.status = status
            if progress is not None:
                phase.progress = min(100.0, max(0.0, progress))
            if issues:
                phase.issues = issues
            
            phase_id = self.store.create_or_update_phase(phase)
            
            return {
                "status": "success",
                "phase_id": phase_id,
                "phase_name": phase_name,
                "new_status": status,
                "progress": phase.progress
            }
        
        @self.mcp.tool()
        async def create_task(
            phase_name: str,
            title: str,
            description: str = "",
            priority: str = "medium",
            assignee: str = "system"
        ) -> Dict[str, Any]:
            """Cria uma nova tarefa/issue
            
            Args:
                phase_name: Nome da fase relacionada
                title: Título da tarefa
                description: Descrição detalhada
                priority: Prioridade (critical, high, medium, low)
                assignee: Responsável pela tarefa
            """
            phases = self.store.get_phases()
            phase = next((p for p in phases if p.name == phase_name), None)
            
            if not phase:
                return {"status": "error", "message": f"Phase {phase_name} not found"}
            
            task = Task(
                phase_id=phase.id,
                title=title,
                description=description,
                priority=priority,
                assignee=assignee,
                status="open"
            )
            
            task_id = self.store.create_task(task)
            
            return {
                "status": "success",
                "task_id": task_id,
                "phase": phase_name,
                "title": title
            }
        
        @self.mcp.tool()
        async def get_project_overview() -> Dict[str, Any]:
            """Obtém visão geral do projeto"""
            phases = self.store.get_phases()
            
            # Calcula estatísticas
            total_phases = len(phases)
            completed = len([p for p in phases if p.status == PhaseStatus.COMPLETED.value])
            in_progress = len([p for p in phases if p.status == PhaseStatus.IN_PROGRESS.value])
            testing = len([p for p in phases if p.status == PhaseStatus.TESTING.value])
            blocked = len([p for p in phases if p.status == PhaseStatus.BLOCKED.value])
            not_started = len([p for p in phases if p.status == PhaseStatus.NOT_STARTED.value])
            
            # Calcula progresso geral
            total_progress = sum(p.progress for p in phases) / total_phases if total_phases > 0 else 0
            
            # Obtém tarefas abertas
            open_tasks = self.store.get_tasks(status="open")
            critical_tasks = [t for t in open_tasks if t.priority == TaskPriority.CRITICAL.value]
            
            # Fases com issues
            phases_with_issues = [p.name for p in phases if p.issues]
            
            return {
                "project": "QuantumTrader Production System",
                "total_phases": total_phases,
                "status_distribution": {
                    "completed": completed,
                    "in_progress": in_progress,
                    "testing": testing,
                    "blocked": blocked,
                    "not_started": not_started
                },
                "overall_progress": round(total_progress, 2),
                "open_tasks": len(open_tasks),
                "critical_tasks": len(critical_tasks),
                "phases_with_issues": phases_with_issues,
                "next_milestones": [
                    p.name for p in phases 
                    if p.status in [PhaseStatus.IN_PROGRESS.value, PhaseStatus.TESTING.value]
                ],
                "ready_for_production": completed == total_phases
            }
        
        @self.mcp.tool()
        async def record_deployment(
            version: str,
            phase: str,
            features: List[str] = None,
            fixes: List[str] = None,
            rollback_version: Optional[str] = None
        ) -> Dict[str, Any]:
            """Registra um novo deployment
            
            Args:
                version: Versão do deployment
                phase: Fase relacionada
                features: Lista de features adicionadas
                fixes: Lista de correções aplicadas
                rollback_version: Versão para rollback se necessário
            """
            deployment = Deployment(
                version=version,
                phase=phase,
                status="deployed",
                features=features or [],
                fixes=fixes or [],
                rollback_version=rollback_version,
                deployed_at=datetime.now().isoformat()
            )
            
            deployment_id = self.store.record_deployment(deployment)
            
            return {
                "status": "success",
                "deployment_id": deployment_id,
                "version": version,
                "deployed_at": deployment.deployed_at
            }
        
        @self.mcp.tool()
        async def track_metric(
            metric_name: str,
            value: float,
            unit: str = "",
            phase: str = ""
        ) -> Dict[str, Any]:
            """Registra uma métrica do sistema
            
            Args:
                metric_name: Nome da métrica
                value: Valor numérico
                unit: Unidade de medida
                phase: Fase relacionada
            """
            self.store.record_metric(metric_name, value, unit, phase)
            
            return {
                "status": "success",
                "metric": metric_name,
                "value": value,
                "timestamp": datetime.now().isoformat()
            }
        
        @self.mcp.tool()
        async def generate_status_report() -> str:
            """Gera relatório de status detalhado"""
            phases = self.store.get_phases()
            overview = await get_project_overview()
            
            report = f"""
# QuantumTrader Project Status Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overall Progress: {overview['overall_progress']}%

## Phase Status:
"""
            for phase in phases:
                status_emoji = {
                    PhaseStatus.COMPLETED.value: "✅",
                    PhaseStatus.IN_PROGRESS.value: "🔄",
                    PhaseStatus.TESTING.value: "🧪",
                    PhaseStatus.BLOCKED.value: "🚫",
                    PhaseStatus.NOT_STARTED.value: "⏸️",
                    PhaseStatus.FAILED.value: "❌"
                }.get(phase.status, "❓")
                
                report += f"\n### {status_emoji} {phase.name} ({phase.progress}%)\n"
                report += f"- Status: {phase.status}\n"
                report += f"- Description: {phase.description}\n"
                
                if phase.components:
                    report += f"- Components: {', '.join(phase.components)}\n"
                
                if phase.dependencies:
                    report += f"- Dependencies: {', '.join(phase.dependencies)}\n"
                
                if phase.issues:
                    report += f"- ⚠️ Issues: {', '.join(phase.issues)}\n"
            
            report += f"""
## Summary:
- Completed: {overview['status_distribution']['completed']}/{overview['total_phases']}
- In Progress: {overview['status_distribution']['in_progress']}
- Testing: {overview['status_distribution']['testing']}
- Open Tasks: {overview['open_tasks']}
- Critical Tasks: {overview['critical_tasks']}

## Next Steps:
"""
            for milestone in overview['next_milestones']:
                report += f"- Complete {milestone}\n"
            
            if overview['ready_for_production']:
                report += "\n✅ **System is ready for production deployment!**\n"
            
            return report
    
    async def run(self):
        """Executa o MCP server"""
        if self.mcp:
            logger.info("Starting QuantumTrader Project Board MCP Server...")
            await self.mcp.run()
        else:
            logger.error("Cannot run MCP server - SDK not installed")


async def main():
    """Entry point principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="QuantumTrader Project Board MCP Server")
    parser.add_argument('--standalone', action='store_true', help='Run in standalone mode')
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = ProjectBoardMCP()
    
    if args.standalone:
        logger.info("Running in standalone mode - Project Board available via direct API")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down Project Board server...")
    else:
        await server.run()


if __name__ == "__main__":
    asyncio.run(main())