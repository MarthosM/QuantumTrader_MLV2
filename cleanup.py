#!/usr/bin/env python3
"""
QuantumTrader System Cleanup Script
Run weekly to maintain system performance and clean unnecessary files
"""

import os
import sys
import shutil
import gzip
from pathlib import Path
from datetime import datetime, timedelta
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemCleaner:
    """System cleanup and maintenance"""
    
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.stats = {
            'files_removed': 0,
            'space_freed': 0,
            'logs_cleaned': 0,
            'data_archived': 0,
            'cache_cleared': 0
        }
        
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No files will be deleted")
    
    def cleanup_python_cache(self):
        """Remove Python cache directories"""
        logger.info("Cleaning Python cache...")
        
        cache_patterns = ['__pycache__', '.pytest_cache', '.mypy_cache']
        
        for pattern in cache_patterns:
            for cache_dir in Path('.').rglob(pattern):
                if self.dry_run:
                    logger.info(f"Would remove: {cache_dir}")
                else:
                    try:
                        shutil.rmtree(cache_dir)
                        logger.info(f"Removed: {cache_dir}")
                        self.stats['cache_cleared'] += 1
                    except Exception as e:
                        logger.error(f"Failed to remove {cache_dir}: {e}")
    
    def cleanup_old_logs(self, days=30):
        """Remove logs older than specified days"""
        logger.info(f"Cleaning logs older than {days} days...")
        
        log_dir = Path('logs')
        if not log_dir.exists():
            return
        
        cutoff = datetime.now() - timedelta(days=days)
        
        patterns = ['*.log', '*.jsonl', '*.txt']
        for pattern in patterns:
            for log_file in log_dir.glob(pattern):
                try:
                    file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_time < cutoff:
                        size = log_file.stat().st_size
                        if self.dry_run:
                            logger.info(f"Would remove log: {log_file.name} ({size/1024:.1f}KB)")
                        else:
                            log_file.unlink()
                            logger.info(f"Removed log: {log_file.name}")
                            self.stats['logs_cleaned'] += 1
                            self.stats['space_freed'] += size
                except Exception as e:
                    logger.error(f"Failed to remove {log_file}: {e}")
    
    def cleanup_temporary_files(self):
        """Remove temporary and backup files"""
        logger.info("Cleaning temporary files...")
        
        temp_patterns = [
            '*.tmp', '*.temp', '*.swp', '*~', '*.bak',
            '.DS_Store', 'Thumbs.db', 'desktop.ini'
        ]
        
        for pattern in temp_patterns:
            for temp_file in Path('.').rglob(pattern):
                try:
                    size = temp_file.stat().st_size
                    if self.dry_run:
                        logger.info(f"Would remove: {temp_file}")
                    else:
                        temp_file.unlink()
                        logger.info(f"Removed: {temp_file}")
                        self.stats['files_removed'] += 1
                        self.stats['space_freed'] += size
                except Exception as e:
                    logger.error(f"Failed to remove {temp_file}: {e}")
    
    def archive_old_data(self, days=90):
        """Archive old trading data"""
        logger.info(f"Archiving data older than {days} days...")
        
        data_dir = Path('data/book_tick_data')
        archive_dir = Path('data/archive')
        
        if not data_dir.exists():
            return
        
        if not self.dry_run:
            archive_dir.mkdir(parents=True, exist_ok=True)
        
        cutoff = datetime.now() - timedelta(days=days)
        
        for data_file in data_dir.glob('*.csv'):
            try:
                file_time = datetime.fromtimestamp(data_file.stat().st_mtime)
                if file_time < cutoff:
                    if self.dry_run:
                        logger.info(f"Would archive: {data_file.name}")
                    else:
                        # Compress and move
                        gz_path = archive_dir / f"{data_file.name}.gz"
                        with open(data_file, 'rb') as f_in:
                            with gzip.open(gz_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        original_size = data_file.stat().st_size
                        compressed_size = gz_path.stat().st_size
                        
                        data_file.unlink()
                        logger.info(f"Archived: {data_file.name} "
                                  f"({original_size/1024/1024:.1f}MB -> "
                                  f"{compressed_size/1024/1024:.1f}MB)")
                        
                        self.stats['data_archived'] += 1
                        self.stats['space_freed'] += (original_size - compressed_size)
            except Exception as e:
                logger.error(f"Failed to archive {data_file}: {e}")
    
    def compress_large_files(self, size_mb=100):
        """Compress files larger than specified size"""
        logger.info(f"Compressing files larger than {size_mb}MB...")
        
        size_threshold = size_mb * 1024 * 1024
        
        for csv_file in Path('data').rglob('*.csv'):
            try:
                if csv_file.stat().st_size > size_threshold:
                    if self.dry_run:
                        logger.info(f"Would compress: {csv_file} "
                                  f"({csv_file.stat().st_size/1024/1024:.1f}MB)")
                    else:
                        gz_path = csv_file.parent / f"{csv_file.name}.gz"
                        with open(csv_file, 'rb') as f_in:
                            with gzip.open(gz_path, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        original_size = csv_file.stat().st_size
                        compressed_size = gz_path.stat().st_size
                        
                        csv_file.unlink()
                        logger.info(f"Compressed: {csv_file.name} "
                                  f"({original_size/1024/1024:.1f}MB -> "
                                  f"{compressed_size/1024/1024:.1f}MB)")
                        
                        self.stats['space_freed'] += (original_size - compressed_size)
            except Exception as e:
                logger.error(f"Failed to compress {csv_file}: {e}")
    
    def cleanup_old_backups(self, days=7):
        """Remove old backup files"""
        logger.info(f"Cleaning backups older than {days} days...")
        
        backup_dir = Path('backups')
        if not backup_dir.exists():
            return
        
        cutoff = datetime.now() - timedelta(days=days)
        
        for backup in backup_dir.glob('*.json'):
            try:
                file_time = datetime.fromtimestamp(backup.stat().st_mtime)
                if file_time < cutoff:
                    size = backup.stat().st_size
                    if self.dry_run:
                        logger.info(f"Would remove backup: {backup.name}")
                    else:
                        backup.unlink()
                        logger.info(f"Removed backup: {backup.name}")
                        self.stats['files_removed'] += 1
                        self.stats['space_freed'] += size
            except Exception as e:
                logger.error(f"Failed to remove {backup}: {e}")
    
    def cleanup_obsolete_modules(self):
        """Remove known obsolete module files"""
        logger.info("Removing obsolete modules...")
        
        obsolete_patterns = [
            'src/production_old.py',
            'src/production_v1.py',
            'src/production_backup*.py',
            'src/start_hmarl_old.py',
            'src/agents/base_agent_old.py',
            'src/agents/*_deprecated.py',
            'core/start_production_old.py',
            'core/monitor_old.py',
            'core/*_backup.py',
            'core/*_deprecated.py',
            '*_old.py',
            '*_deprecated.py',
            '*_backup.py'
        ]
        
        for pattern in obsolete_patterns:
            for obsolete_file in Path('.').glob(pattern):
                try:
                    size = obsolete_file.stat().st_size
                    if self.dry_run:
                        logger.info(f"Would remove obsolete: {obsolete_file}")
                    else:
                        obsolete_file.unlink()
                        logger.info(f"Removed obsolete: {obsolete_file}")
                        self.stats['files_removed'] += 1
                        self.stats['space_freed'] += size
                except Exception as e:
                    logger.error(f"Failed to remove {obsolete_file}: {e}")
    
    def clean_empty_directories(self):
        """Remove empty directories"""
        logger.info("Cleaning empty directories...")
        
        # Directories to preserve even if empty
        preserve = {'logs', 'data', 'models', 'metrics', 'backups'}
        
        for root, dirs, files in os.walk('.', topdown=False):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                
                # Skip git directories and preserved directories
                if '.git' in str(dir_path) or dir_name in preserve:
                    continue
                
                try:
                    if not any(dir_path.iterdir()):
                        if self.dry_run:
                            logger.info(f"Would remove empty dir: {dir_path}")
                        else:
                            dir_path.rmdir()
                            logger.info(f"Removed empty dir: {dir_path}")
                except Exception:
                    pass  # Directory not empty or no permission
    
    def save_cleanup_report(self):
        """Save cleanup statistics to file"""
        report_file = Path('logs') / f"cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': self.dry_run,
            'statistics': self.stats,
            'space_freed_mb': round(self.stats['space_freed'] / 1024 / 1024, 2)
        }
        
        if not self.dry_run:
            report_file.parent.mkdir(exist_ok=True)
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Cleanup report saved to: {report_file}")
        
        return report
    
    def run_full_cleanup(self):
        """Run complete system cleanup"""
        logger.info("=" * 60)
        logger.info("Starting QuantumTrader System Cleanup")
        logger.info("=" * 60)
        
        # Run all cleanup tasks
        self.cleanup_python_cache()
        self.cleanup_old_logs(days=30)
        self.cleanup_temporary_files()
        self.archive_old_data(days=90)
        self.compress_large_files(size_mb=100)
        self.cleanup_old_backups(days=7)
        self.cleanup_obsolete_modules()
        self.clean_empty_directories()
        
        # Generate report
        report = self.save_cleanup_report()
        
        # Print summary
        logger.info("=" * 60)
        logger.info("Cleanup Summary:")
        logger.info(f"  Files removed: {self.stats['files_removed']}")
        logger.info(f"  Logs cleaned: {self.stats['logs_cleaned']}")
        logger.info(f"  Data archived: {self.stats['data_archived']}")
        logger.info(f"  Cache cleared: {self.stats['cache_cleared']}")
        logger.info(f"  Space freed: {self.stats['space_freed']/1024/1024:.2f} MB")
        logger.info("=" * 60)
        
        if self.dry_run:
            logger.info("🔍 DRY RUN COMPLETE - No files were actually deleted")
            logger.info("Run without --dry-run to perform actual cleanup")
        else:
            logger.info("✅ Cleanup completed successfully!")
        
        return report


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='QuantumTrader System Cleanup Utility'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--logs-days',
        type=int,
        default=30,
        help='Delete logs older than N days (default: 30)'
    )
    parser.add_argument(
        '--data-days',
        type=int,
        default=90,
        help='Archive data older than N days (default: 90)'
    )
    parser.add_argument(
        '--backup-days',
        type=int,
        default=7,
        help='Delete backups older than N days (default: 7)'
    )
    
    args = parser.parse_args()
    
    # Confirm before running
    if not args.dry_run:
        response = input("⚠️  This will delete files permanently. Continue? (y/N): ")
        if response.lower() != 'y':
            logger.info("Cleanup cancelled")
            return
    
    # Run cleanup
    cleaner = SystemCleaner(dry_run=args.dry_run)
    cleaner.run_full_cleanup()


if __name__ == '__main__':
    main()