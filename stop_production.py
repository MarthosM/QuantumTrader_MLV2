"""
Script para parar o sistema de produção de forma segura
"""

import os
import sys
import signal
import time
from pathlib import Path
import psutil
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('StopProduction')


def stop_production_system():
    """Para o sistema de produção de forma segura"""
    
    logger.info("=" * 60)
    logger.info(" PARANDO SISTEMA DE PRODUÇÃO")
    logger.info("=" * 60)
    
    # Verificar arquivo PID
    pid_file = Path('quantum_trader.pid')
    
    if not pid_file.exists():
        logger.warning("Sistema não está em execução (arquivo PID não encontrado)")
        return False
    
    try:
        # Ler PID
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        logger.info(f"PID do sistema: {pid}")
        
        # Verificar se processo existe
        if not psutil.pid_exists(pid):
            logger.warning("Processo não está mais ativo")
            pid_file.unlink()
            return False
        
        # Obter processo
        process = psutil.Process(pid)
        
        # Verificar se é o processo correto
        if 'python' not in process.name().lower():
            logger.error("PID não corresponde a um processo Python")
            return False
        
        logger.info(f"Processo encontrado: {process.name()}")
        logger.info("Enviando sinal de parada...")
        
        # Enviar SIGTERM (parada graciosa)
        if sys.platform == 'win32':
            # Windows não suporta SIGTERM, usar terminate()
            process.terminate()
        else:
            os.kill(pid, signal.SIGTERM)
        
        # Aguardar processo terminar
        logger.info("Aguardando sistema finalizar...")
        
        timeout = 30  # 30 segundos de timeout
        start_time = time.time()
        
        while process.is_running() and (time.time() - start_time) < timeout:
            time.sleep(1)
            logger.info("  Aguardando...")
        
        if process.is_running():
            logger.warning("Sistema não respondeu. Forçando parada...")
            process.kill()
            time.sleep(2)
        
        # Remover arquivo PID
        if pid_file.exists():
            pid_file.unlink()
        
        logger.info("✅ Sistema parado com sucesso!")
        return True
        
    except psutil.NoSuchProcess:
        logger.info("Processo já foi finalizado")
        if pid_file.exists():
            pid_file.unlink()
        return True
        
    except Exception as e:
        logger.error(f"Erro ao parar sistema: {e}")
        return False


def cleanup_resources():
    """Limpa recursos e processos órfãos"""
    logger.info("\nLimpando recursos...")
    
    # Matar processos Python órfãos relacionados ao trading
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('quantum' in str(arg).lower() or 
                                  'production' in str(arg).lower() or
                                  'enhanced' in str(arg).lower() 
                                  for arg in cmdline):
                    logger.info(f"  Finalizando processo órfão: PID {proc.info['pid']}")
                    proc.kill()
                    killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if killed > 0:
        logger.info(f"  {killed} processos órfãos finalizados")
    
    # Limpar arquivos temporários
    temp_files = [
        'quantum_trader.pid',
        'cache/*.tmp',
        'logs/*.lock'
    ]
    
    for pattern in temp_files:
        for file in Path('.').glob(pattern):
            try:
                file.unlink()
                logger.info(f"  Removido: {file}")
            except:
                pass
    
    logger.info("✅ Limpeza concluída")


def main():
    """Função principal"""
    
    # Parar sistema
    success = stop_production_system()
    
    if success:
        # Limpar recursos
        cleanup_resources()
        
        logger.info("\n" + "=" * 60)
        logger.info(" SISTEMA PARADO E RECURSOS LIMPOS")
        logger.info("=" * 60)
    else:
        logger.warning("\n⚠ Sistema pode já estar parado")
    
    # Perguntar se deseja verificar status
    print("\nDeseja verificar o status dos processos? (s/n): ", end='')
    if input().lower() == 's':
        print("\nProcessos Python ativos:")
        for proc in psutil.process_iter(['pid', 'name']):
            if 'python' in proc.info['name'].lower():
                print(f"  PID {proc.info['pid']}: {proc.info['name']}")


if __name__ == "__main__":
    main()