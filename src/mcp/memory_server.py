"""
Memory MCP Server for QuantumTrader Production System

Provides persistent memory management for trading decisions, patterns,
and market insights using SQLite and JSON storage.
"""

import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import logging
from contextlib import asynccontextmanager

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("MCP SDK not installed. Please install with: pip install mcp[cli]")
    FastMCP = None

logger = logging.getLogger(__name__)


@dataclass
class TradingMemory:
    """Trading memory entity"""
    id: Optional[int] = None
    timestamp: str = ""
    category: str = ""  # pattern, decision, insight, metric, alert
    symbol: str = ""
    content: Dict[str, Any] = None
    confidence: float = 0.0
    tags: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.content is None:
            self.content = {}
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class MemoryStore:
    """SQLite-based memory storage"""
    
    def __init__(self, db_path: str = "data/trading_memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL DEFAULT 0.0,
                    tags TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON memories(category)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol ON memories(symbol)
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    conditions TEXT,
                    success_rate REAL DEFAULT 0.0,
                    occurrences INTEGER DEFAULT 0,
                    last_seen TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trading_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_start TIMESTAMP NOT NULL,
                    session_end TIMESTAMP,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    total_pnl REAL DEFAULT 0.0,
                    max_drawdown REAL DEFAULT 0.0,
                    sharpe_ratio REAL,
                    metadata TEXT
                )
            """)
            
            conn.commit()
    
    def store_memory(self, memory: TradingMemory) -> int:
        """Store a trading memory"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO memories (timestamp, category, symbol, content, confidence, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.timestamp,
                memory.category,
                memory.symbol,
                json.dumps(memory.content),
                memory.confidence,
                json.dumps(memory.tags),
                json.dumps(memory.metadata)
            ))
            return cursor.lastrowid
    
    def recall_memories(self, 
                        category: Optional[str] = None,
                        symbol: Optional[str] = None,
                        tags: Optional[List[str]] = None,
                        since: Optional[datetime] = None,
                        limit: int = 100) -> List[TradingMemory]:
        """Recall memories based on filters"""
        query = "SELECT * FROM memories WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())
        
        if tags:
            for tag in tags:
                query += " AND tags LIKE ?"
                params.append(f'%"{tag}"%')
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            memories = []
            for row in cursor:
                memory = TradingMemory(
                    id=row['id'],
                    timestamp=row['timestamp'],
                    category=row['category'],
                    symbol=row['symbol'],
                    content=json.loads(row['content']),
                    confidence=row['confidence'],
                    tags=json.loads(row['tags']) if row['tags'] else [],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
                memories.append(memory)
            
            return memories
    
    def update_pattern(self, pattern_name: str, success: bool, conditions: Dict[str, Any] = None):
        """Update pattern statistics"""
        with sqlite3.connect(self.db_path) as conn:
            # Check if pattern exists
            cursor = conn.execute(
                "SELECT id, occurrences, success_rate FROM patterns WHERE pattern_name = ?",
                (pattern_name,)
            )
            row = cursor.fetchone()
            
            if row:
                # Update existing pattern
                pattern_id, occurrences, current_rate = row
                new_occurrences = occurrences + 1
                new_rate = ((current_rate * occurrences) + (1 if success else 0)) / new_occurrences
                
                conn.execute("""
                    UPDATE patterns 
                    SET occurrences = ?, success_rate = ?, last_seen = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_occurrences, new_rate, pattern_id))
            else:
                # Create new pattern
                conn.execute("""
                    INSERT INTO patterns (pattern_name, conditions, success_rate, occurrences, last_seen)
                    VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (pattern_name, json.dumps(conditions) if conditions else "{}", 1.0 if success else 0.0))
            
            conn.commit()
    
    def get_pattern_stats(self, min_occurrences: int = 5) -> List[Dict[str, Any]]:
        """Get pattern statistics"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM patterns 
                WHERE occurrences >= ? 
                ORDER BY success_rate DESC
            """, (min_occurrences,))
            
            return [dict(row) for row in cursor]
    
    def start_session(self) -> int:
        """Start a new trading session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO trading_sessions (session_start)
                VALUES (CURRENT_TIMESTAMP)
            """)
            return cursor.lastrowid
    
    def update_session(self, session_id: int, **kwargs):
        """Update session metrics"""
        allowed_fields = ['total_trades', 'winning_trades', 'losing_trades', 
                         'total_pnl', 'max_drawdown', 'sharpe_ratio', 'metadata']
        
        updates = []
        values = []
        for field, value in kwargs.items():
            if field in allowed_fields:
                if field == 'metadata':
                    value = json.dumps(value)
                updates.append(f"{field} = ?")
                values.append(value)
        
        if updates:
            values.append(session_id)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    f"UPDATE trading_sessions SET {', '.join(updates)} WHERE id = ?",
                    values
                )
                conn.commit()
    
    def end_session(self, session_id: int):
        """End a trading session"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE trading_sessions SET session_end = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,)
            )
            conn.commit()


class TradingMemoryMCP:
    """Trading Memory MCP Server"""
    
    def __init__(self, config_path: str = "config_production.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.memory_store = MemoryStore(
            db_path=self.config.get('memory_db_path', 'data/trading_memory.db')
        )
        self.current_session_id = None
        
        # Initialize MCP server if available
        if FastMCP:
            self.mcp = FastMCP("QuantumTrader Memory Server")
            self._setup_mcp_endpoints()
        else:
            self.mcp = None
            logger.warning("MCP SDK not available - Memory server running in standalone mode")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration"""
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)
        return {}
    
    def _setup_mcp_endpoints(self):
        """Setup MCP server endpoints"""
        
        @self.mcp.resource("memory://trading/recent")
        async def get_recent_memories() -> str:
            """Get recent trading memories"""
            memories = self.memory_store.recall_memories(limit=50)
            return json.dumps([asdict(m) for m in memories], indent=2)
        
        @self.mcp.resource("memory://patterns/successful")
        async def get_successful_patterns() -> str:
            """Get successful trading patterns"""
            patterns = self.memory_store.get_pattern_stats(min_occurrences=5)
            successful = [p for p in patterns if p['success_rate'] > 0.6]
            return json.dumps(successful, indent=2)
        
        @self.mcp.tool()
        async def store_trading_memory(
            category: str,
            symbol: str,
            content: Dict[str, Any],
            confidence: float = 0.0,
            tags: List[str] = None
        ) -> Dict[str, Any]:
            """Store a new trading memory
            
            Args:
                category: Type of memory (pattern, decision, insight, metric, alert)
                symbol: Trading symbol
                content: Memory content as dictionary
                confidence: Confidence level (0-1)
                tags: Optional tags for categorization
            """
            memory = TradingMemory(
                category=category,
                symbol=symbol,
                content=content,
                confidence=confidence,
                tags=tags or []
            )
            
            memory_id = self.memory_store.store_memory(memory)
            
            return {
                "status": "success",
                "memory_id": memory_id,
                "timestamp": memory.timestamp
            }
        
        @self.mcp.tool()
        async def recall_trading_memories(
            category: Optional[str] = None,
            symbol: Optional[str] = None,
            tags: Optional[List[str]] = None,
            hours_back: int = 24
        ) -> List[Dict[str, Any]]:
            """Recall trading memories based on filters
            
            Args:
                category: Filter by category
                symbol: Filter by trading symbol
                tags: Filter by tags
                hours_back: How many hours back to search
            """
            since = datetime.now() - timedelta(hours=hours_back)
            memories = self.memory_store.recall_memories(
                category=category,
                symbol=symbol,
                tags=tags,
                since=since
            )
            
            return [asdict(m) for m in memories]
        
        @self.mcp.tool()
        async def record_pattern_outcome(
            pattern_name: str,
            success: bool,
            conditions: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            """Record the outcome of a trading pattern
            
            Args:
                pattern_name: Name of the pattern
                success: Whether the pattern was successful
                conditions: Optional conditions that triggered the pattern
            """
            self.memory_store.update_pattern(pattern_name, success, conditions)
            
            # Get updated stats
            patterns = self.memory_store.get_pattern_stats(min_occurrences=1)
            pattern_stats = next((p for p in patterns if p['pattern_name'] == pattern_name), None)
            
            return {
                "status": "success",
                "pattern": pattern_name,
                "current_stats": pattern_stats
            }
        
        @self.mcp.tool()
        async def analyze_memory_insights() -> Dict[str, Any]:
            """Analyze stored memories for insights"""
            
            # Get recent memories
            recent_memories = self.memory_store.recall_memories(limit=100)
            
            # Get pattern statistics
            patterns = self.memory_store.get_pattern_stats()
            
            # Analyze by category
            category_counts = {}
            confidence_by_category = {}
            
            for memory in recent_memories:
                cat = memory.category
                category_counts[cat] = category_counts.get(cat, 0) + 1
                
                if cat not in confidence_by_category:
                    confidence_by_category[cat] = []
                confidence_by_category[cat].append(memory.confidence)
            
            # Calculate average confidence
            avg_confidence = {}
            for cat, confidences in confidence_by_category.items():
                avg_confidence[cat] = sum(confidences) / len(confidences) if confidences else 0
            
            # Find most successful patterns
            successful_patterns = [p for p in patterns if p['success_rate'] > 0.6]
            successful_patterns.sort(key=lambda x: x['success_rate'], reverse=True)
            
            return {
                "total_memories": len(recent_memories),
                "category_distribution": category_counts,
                "average_confidence": avg_confidence,
                "top_patterns": successful_patterns[:5],
                "total_patterns_tracked": len(patterns),
                "insights": {
                    "most_frequent_category": max(category_counts, key=category_counts.get) if category_counts else None,
                    "highest_confidence_category": max(avg_confidence, key=avg_confidence.get) if avg_confidence else None,
                    "pattern_success_rate": sum(p['success_rate'] for p in patterns) / len(patterns) if patterns else 0
                }
            }
        
        @self.mcp.tool()
        async def start_trading_session() -> Dict[str, Any]:
            """Start a new trading session"""
            self.current_session_id = self.memory_store.start_session()
            
            return {
                "status": "success",
                "session_id": self.current_session_id,
                "started_at": datetime.now().isoformat()
            }
        
        @self.mcp.tool()
        async def update_session_metrics(
            total_trades: Optional[int] = None,
            winning_trades: Optional[int] = None,
            losing_trades: Optional[int] = None,
            total_pnl: Optional[float] = None,
            max_drawdown: Optional[float] = None,
            sharpe_ratio: Optional[float] = None
        ) -> Dict[str, Any]:
            """Update current session metrics"""
            
            if not self.current_session_id:
                return {"status": "error", "message": "No active session"}
            
            kwargs = {}
            if total_trades is not None:
                kwargs['total_trades'] = total_trades
            if winning_trades is not None:
                kwargs['winning_trades'] = winning_trades
            if losing_trades is not None:
                kwargs['losing_trades'] = losing_trades
            if total_pnl is not None:
                kwargs['total_pnl'] = total_pnl
            if max_drawdown is not None:
                kwargs['max_drawdown'] = max_drawdown
            if sharpe_ratio is not None:
                kwargs['sharpe_ratio'] = sharpe_ratio
            
            self.memory_store.update_session(**kwargs)
            
            return {
                "status": "success",
                "session_id": self.current_session_id,
                "metrics_updated": list(kwargs.keys())
            }
        
        @self.mcp.tool()
        async def end_trading_session() -> Dict[str, Any]:
            """End the current trading session"""
            
            if not self.current_session_id:
                return {"status": "error", "message": "No active session"}
            
            self.memory_store.end_session(self.current_session_id)
            session_id = self.current_session_id
            self.current_session_id = None
            
            return {
                "status": "success",
                "session_id": session_id,
                "ended_at": datetime.now().isoformat()
            }
    
    async def run(self):
        """Run the MCP server"""
        if self.mcp:
            logger.info("Starting QuantumTrader Memory MCP Server...")
            await self.mcp.run()
        else:
            logger.error("Cannot run MCP server - SDK not installed")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="QuantumTrader Memory MCP Server")
    parser.add_argument('--config', default='config_production.json', help='Config file path')
    parser.add_argument('--standalone', action='store_true', help='Run in standalone mode')
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = TradingMemoryMCP(config_path=args.config)
    
    if args.standalone:
        logger.info("Running in standalone mode - Memory store available via direct API")
        # In standalone mode, just keep the service running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down Memory server...")
    else:
        await server.run()


if __name__ == "__main__":
    asyncio.run(main())