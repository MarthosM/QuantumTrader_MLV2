#!/usr/bin/env python3
"""
Visualizador do Project Board - Mostra status atual do projeto
"""

import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
from datetime import datetime
import json
from typing import Dict, Any
import argparse

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.mcp.project_board_server import ProjectBoardStore, PhaseStatus


class BoardViewer:
    """Visualizador do Project Board"""
    
    def __init__(self):
        self.board = ProjectBoardStore()
        self.colors = {
            PhaseStatus.COMPLETED.value: '\033[92m',  # Green
            PhaseStatus.IN_PROGRESS.value: '\033[93m',  # Yellow
            PhaseStatus.TESTING.value: '\033[96m',  # Cyan
            PhaseStatus.BLOCKED.value: '\033[91m',  # Red
            PhaseStatus.NOT_STARTED.value: '\033[90m',  # Gray
            PhaseStatus.FAILED.value: '\033[91m',  # Red
        }
        self.reset_color = '\033[0m'
    
    def get_status_emoji(self, status: str) -> str:
        """Retorna emoji para o status"""
        # Use ASCII alternatives for better compatibility
        if sys.platform == "win32":
            return {
                PhaseStatus.COMPLETED.value: "[OK]",
                PhaseStatus.IN_PROGRESS.value: "[>>]",
                PhaseStatus.TESTING.value: "[T]",
                PhaseStatus.BLOCKED.value: "[X]",
                PhaseStatus.NOT_STARTED.value: "[.]",
                PhaseStatus.FAILED.value: "[!]"
            }.get(status, "[?]")
        else:
            return {
                PhaseStatus.COMPLETED.value: "✅",
                PhaseStatus.IN_PROGRESS.value: "🔄",
                PhaseStatus.TESTING.value: "🧪",
                PhaseStatus.BLOCKED.value: "🚫",
                PhaseStatus.NOT_STARTED.value: "⏸️",
                PhaseStatus.FAILED.value: "❌"
            }.get(status, "❓")
    
    def format_progress_bar(self, progress: float, width: int = 20) -> str:
        """Cria uma barra de progresso visual"""
        filled = int(progress * width / 100)
        empty = width - filled
        if sys.platform == "win32":
            # Use ASCII characters for Windows
            bar = "#" * filled + "-" * empty
        else:
            bar = "█" * filled + "░" * empty
        return f"[{bar}] {progress:.1f}%"
    
    def print_header(self):
        """Imprime cabeçalho"""
        print("\n" + "="*80)
        print("                    QUANTUMTRADER PROJECT BOARD")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")
    
    def print_overview(self):
        """Imprime visão geral do projeto"""
        phases = self.board.get_phases()
        
        if not phases:
            print("No phases found in project board.")
            return
        
        # Calcula estatísticas
        total = len(phases)
        completed = len([p for p in phases if p.status == PhaseStatus.COMPLETED.value])
        in_progress = len([p for p in phases if p.status == PhaseStatus.IN_PROGRESS.value])
        testing = len([p for p in phases if p.status == PhaseStatus.TESTING.value])
        blocked = len([p for p in phases if p.status == PhaseStatus.BLOCKED.value])
        not_started = len([p for p in phases if p.status == PhaseStatus.NOT_STARTED.value])
        
        overall_progress = sum(p.progress for p in phases) / total if total > 0 else 0
        
        print("PROJECT OVERVIEW")
        print("-" * 40)
        print(f"Overall Progress: {self.format_progress_bar(overall_progress, 30)}")
        print(f"\nPhase Distribution ({total} total):")
        print(f"  [OK] Completed:    {completed:2d} ({completed*100/total:.1f}%)")
        print(f"  [>>] In Progress:  {in_progress:2d} ({in_progress*100/total:.1f}%)")
        print(f"  [T]  Testing:      {testing:2d} ({testing*100/total:.1f}%)")
        print(f"  [X]  Blocked:      {blocked:2d} ({blocked*100/total:.1f}%)")
        print(f"  [.]  Not Started:  {not_started:2d} ({not_started*100/total:.1f}%)")
        print()
    
    def print_phases(self, detailed: bool = False):
        """Imprime status das fases"""
        phases = self.board.get_phases()
        
        print("PROJECT PHASES")
        print("-" * 40)
        
        for phase in phases:
            color = self.colors.get(phase.status, '')
            emoji = self.get_status_emoji(phase.status)
            
            print(f"\n{emoji} {color}{phase.name}{self.reset_color}")
            print(f"   Status: {phase.status}")
            print(f"   Progress: {self.format_progress_bar(phase.progress)}")
            
            if detailed:
                if phase.description:
                    print(f"   Description: {phase.description}")
                
                if phase.components:
                    print(f"   Components: {', '.join(phase.components[:3])}")
                    if len(phase.components) > 3:
                        print(f"                (+{len(phase.components)-3} more)")
                
                if phase.dependencies:
                    print(f"   Dependencies: {', '.join(phase.dependencies)}")
                
                if phase.issues:
                    print(f"   [!] Issues:")
                    for issue in phase.issues[:3]:
                        print(f"      - {issue}")
                    if len(phase.issues) > 3:
                        print(f"      (+{len(phase.issues)-3} more)")
                
                if phase.start_date:
                    print(f"   Started: {phase.start_date}")
                if phase.end_date:
                    print(f"   Ended: {phase.end_date}")
        
        print()
    
    def print_tasks(self, limit: int = 10):
        """Imprime tarefas abertas"""
        tasks = self.board.get_tasks(status="open")
        
        if not tasks:
            print("NO OPEN TASKS")
            print("-" * 40)
            print("All tasks completed!\n")
            return
        
        print(f"OPEN TASKS ({len(tasks)} total)")
        print("-" * 40)
        
        # Ordena por prioridade
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        tasks.sort(key=lambda t: priority_order.get(t.priority, 99))
        
        # Mostra até 'limit' tarefas
        for i, task in enumerate(tasks[:limit], 1):
            priority_emoji = {
                "critical": "[!!!]",
                "high": "[!!]",
                "medium": "[!]",
                "low": "[-]"
            }.get(task.priority, "[?]")
            
            print(f"\n{i}. {priority_emoji} {task.title}")
            if task.description:
                print(f"   {task.description}")
            print(f"   Priority: {task.priority} | Created: {task.created_at[:10]}")
        
        if len(tasks) > limit:
            print(f"\n   ... and {len(tasks) - limit} more tasks")
        
        print()
    
    def print_critical_items(self):
        """Imprime itens críticos que precisam atenção"""
        phases = self.board.get_phases()
        tasks = self.board.get_tasks(status="open")
        
        blocked_phases = [p for p in phases if p.status == PhaseStatus.BLOCKED.value]
        failed_phases = [p for p in phases if p.status == PhaseStatus.FAILED.value]
        critical_tasks = [t for t in tasks if t.priority == "critical"]
        
        if not (blocked_phases or failed_phases or critical_tasks):
            print("NO CRITICAL ITEMS")
            print("-" * 40)
            print("System is healthy!\n")
            return
        
        print("CRITICAL ITEMS REQUIRING ATTENTION")
        print("-" * 40)
        
        if blocked_phases:
            print("\n[X] Blocked Phases:")
            for phase in blocked_phases:
                print(f"   - {phase.name}")
                if phase.issues:
                    print(f"     Issues: {', '.join(phase.issues[:2])}")
        
        if failed_phases:
            print("\n[!] Failed Phases:")
            for phase in failed_phases:
                print(f"   - {phase.name}")
        
        if critical_tasks:
            print("\n[!!!] Critical Tasks:")
            for task in critical_tasks[:5]:
                print(f"   - {task.title}")
        
        print()
    
    def print_next_steps(self):
        """Imprime próximos passos recomendados"""
        phases = self.board.get_phases()
        
        # Fases em progresso ou teste
        active_phases = [p for p in phases if p.status in [
            PhaseStatus.IN_PROGRESS.value, 
            PhaseStatus.TESTING.value
        ]]
        
        # Fases bloqueadas
        blocked_phases = [p for p in phases if p.status == PhaseStatus.BLOCKED.value]
        
        # Fases não iniciadas com dependências completas
        ready_to_start = []
        for phase in phases:
            if phase.status == PhaseStatus.NOT_STARTED.value:
                if not phase.dependencies:
                    ready_to_start.append(phase)
                else:
                    deps_complete = all(
                        any(p.name == dep and p.status == PhaseStatus.COMPLETED.value 
                            for p in phases)
                        for dep in phase.dependencies
                    )
                    if deps_complete:
                        ready_to_start.append(phase)
        
        print("RECOMMENDED NEXT STEPS")
        print("-" * 40)
        
        step_num = 1
        
        # Resolver bloqueios primeiro
        if blocked_phases:
            for phase in blocked_phases:
                print(f"{step_num}. Resolve blockage in '{phase.name}'")
                if phase.issues:
                    print(f"   Fix: {phase.issues[0]}")
                step_num += 1
        
        # Completar fases ativas
        for phase in active_phases:
            if phase.progress < 100:
                remaining = 100 - phase.progress
                print(f"{step_num}. Complete '{phase.name}' ({remaining:.0f}% remaining)")
                step_num += 1
        
        # Iniciar novas fases prontas
        for phase in ready_to_start[:2]:
            print(f"{step_num}. Start '{phase.name}'")
            step_num += 1
        
        if step_num == 1:
            print("[OK] All phases completed! Ready for production deployment.")
        
        print()
    
    def export_json(self, output_file: str):
        """Exporta status do board para JSON"""
        phases = self.board.get_phases()
        tasks = self.board.get_tasks()
        
        data = {
            "generated": datetime.now().isoformat(),
            "project": "QuantumTrader Production System",
            "phases": [
                {
                    "name": p.name,
                    "status": p.status,
                    "progress": p.progress,
                    "description": p.description,
                    "components": p.components,
                    "dependencies": p.dependencies,
                    "issues": p.issues
                }
                for p in phases
            ],
            "tasks": [
                {
                    "title": t.title,
                    "priority": t.priority,
                    "status": t.status,
                    "description": t.description
                }
                for t in tasks
            ],
            "summary": {
                "total_phases": len(phases),
                "completed": len([p for p in phases if p.status == PhaseStatus.COMPLETED.value]),
                "overall_progress": sum(p.progress for p in phases) / len(phases) if phases else 0,
                "open_tasks": len([t for t in tasks if t.status == "open"])
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"[OK] Board status exported to {output_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="View QuantumTrader Project Board")
    parser.add_argument('--detailed', '-d', action='store_true', 
                       help='Show detailed phase information')
    parser.add_argument('--tasks', '-t', type=int, default=5,
                       help='Number of tasks to show (default: 5)')
    parser.add_argument('--export', '-e', help='Export to JSON file')
    parser.add_argument('--section', '-s', 
                       choices=['overview', 'phases', 'tasks', 'critical', 'next'],
                       help='Show specific section only')
    args = parser.parse_args()
    
    viewer = BoardViewer()
    
    if args.export:
        viewer.export_json(args.export)
        return
    
    viewer.print_header()
    
    if args.section:
        # Show only specific section
        if args.section == 'overview':
            viewer.print_overview()
        elif args.section == 'phases':
            viewer.print_phases(detailed=args.detailed)
        elif args.section == 'tasks':
            viewer.print_tasks(limit=args.tasks)
        elif args.section == 'critical':
            viewer.print_critical_items()
        elif args.section == 'next':
            viewer.print_next_steps()
    else:
        # Show all sections
        viewer.print_overview()
        viewer.print_phases(detailed=args.detailed)
        viewer.print_critical_items()
        viewer.print_tasks(limit=args.tasks)
        viewer.print_next_steps()
    
    print("="*80)
    print("Use 'python view_project_board.py -h' for more options")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()