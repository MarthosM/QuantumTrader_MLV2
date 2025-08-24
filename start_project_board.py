#!/usr/bin/env python3
"""
Inicializa o Project Board MCP Server e integração
"""

import asyncio
import sys
import logging
from pathlib import Path
import subprocess
import argparse

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from src.mcp.project_board_server import ProjectBoardMCP
from src.mcp.board_integration import BoardIntegration


async def start_mcp_server():
    """Inicia o MCP server"""
    server = ProjectBoardMCP()
    await server.run()


async def start_integration():
    """Inicia a integração com monitoramento"""
    integration = BoardIntegration()
    await integration.monitor_loop(interval=30)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="QuantumTrader Project Board")
    parser.add_argument('--mode', choices=['server', 'integration', 'both'], 
                       default='both', help='Execution mode')
    parser.add_argument('--install-mcp', action='store_true', 
                       help='Install MCP SDK first')
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/project_board.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Install MCP if requested
    if args.install_mcp:
        logger.info("Installing MCP SDK...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "mcp[cli]"], check=True)
            logger.info("MCP SDK installed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install MCP SDK: {e}")
            return
    
    try:
        if args.mode == 'server':
            logger.info("Starting Project Board MCP Server...")
            await start_mcp_server()
        elif args.mode == 'integration':
            logger.info("Starting Project Board Integration...")
            await start_integration()
        else:
            logger.info("Starting both MCP Server and Integration...")
            # Run both concurrently
            await asyncio.gather(
                start_mcp_server(),
                start_integration()
            )
    except KeyboardInterrupt:
        logger.info("Shutting down Project Board...")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())