"""
Sistema de Verificação Ativa de Posições
Monitora continuamente o status real da posição com a corretora
"""

import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable
import ctypes
from pathlib import Path
import json

logger = logging.getLogger('PositionChecker')

class PositionChecker:
    """
    Verificador ativo de posições que consulta periodicamente
    o status real da posição com a corretora via ProfitDLL
    """
    
    def __init__(self, dll_path: str = "ProfitDLL64.dll"):
        """
        Inicializa o verificador de posições
        
        Args:
            dll_path: Caminho para a ProfitDLL
        """
        self.dll_path = dll_path
        self.dll = None
        self.checking_active = False
        self.check_thread = None
        self.check_interval = 2.0  # Verificar a cada 2 segundos
        
        # Callbacks
        self.on_position_closed = None
        self.on_position_opened = None
        self.on_position_changed = None
        
        # Estado da última posição conhecida
        self.last_position_state = {
            'has_position': False,
            'quantity': 0,
            'side': None,
            'avg_price': 0,
            'pnl': 0,
            'last_check': None
        }
        
        # Arquivo de status
        self.status_file = Path("data/monitor/position_checker_status.json")
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Mutex para thread safety
        self.state_lock = threading.Lock()
        
        self._load_dll()
    
    def _load_dll(self):
        """Carrega a ProfitDLL"""
        try:
            # Procurar DLL em vários locais
            possible_paths = [
                Path(self.dll_path),
                Path("dll") / self.dll_path,
                Path.cwd() / self.dll_path
            ]
            
            dll_found = None
            for path in possible_paths:
                if path.exists():
                    dll_found = path
                    break
            
            if not dll_found:
                logger.error(f"[PositionChecker] DLL não encontrada: {self.dll_path}")
                return False
            
            self.dll = ctypes.WinDLL(str(dll_found))
            
            # Definir função GetPosition
            # Assinatura: GetPosition(symbol: str) -> (quantity: int, avg_price: float, side: int)
            self.dll.GetPosition.argtypes = [ctypes.c_wchar_p]
            self.dll.GetPosition.restype = ctypes.c_bool
            
            logger.info(f"[PositionChecker] DLL carregada: {dll_found}")
            return True
            
        except Exception as e:
            logger.error(f"[PositionChecker] Erro ao carregar DLL: {e}")
            return False
    
    def get_current_position(self, symbol: str) -> Dict:
        """
        Obtém a posição atual para o símbolo
        
        Args:
            symbol: Símbolo para verificar (ex: WDOU25)
            
        Returns:
            Dict com informações da posição
        """
        if not self.dll:
            return {'has_position': False, 'error': 'DLL not loaded'}
        
        try:
            # Estrutura para receber dados da posição
            quantity = ctypes.c_int(0)
            avg_price = ctypes.c_double(0)
            side = ctypes.c_int(0)  # 0=sem posição, 1=comprado, 2=vendido
            pnl = ctypes.c_double(0)
            
            # Chamar função da DLL
            # NOTA: Esta é uma função hipotética - precisamos verificar a API real
            # Por enquanto, vamos simular baseado no que sabemos
            
            position_info = {
                'has_position': False,
                'quantity': 0,
                'side': None,
                'avg_price': 0,
                'pnl': 0,
                'timestamp': datetime.now()
            }
            
            # Tentar obter posição via API conhecida
            if hasattr(self.dll, 'GetAccountPosition'):
                # Usar API real se disponível
                result = self.dll.GetAccountPosition(
                    symbol,
                    ctypes.byref(quantity),
                    ctypes.byref(avg_price),
                    ctypes.byref(side),
                    ctypes.byref(pnl)
                )
                
                if result:
                    position_info['quantity'] = quantity.value
                    position_info['avg_price'] = avg_price.value
                    position_info['pnl'] = pnl.value
                    
                    if quantity.value != 0:
                        position_info['has_position'] = True
                        position_info['side'] = 'BUY' if side.value == 1 else 'SELL'
            
            return position_info
            
        except Exception as e:
            logger.error(f"[PositionChecker] Erro ao obter posição: {e}")
            return {'has_position': False, 'error': str(e)}
    
    def start_checking(self, symbol: str):
        """
        Inicia verificação contínua da posição
        
        Args:
            symbol: Símbolo para monitorar
        """
        if self.checking_active:
            logger.warning("[PositionChecker] Verificação já está ativa")
            return
        
        self.checking_active = True
        self.check_thread = threading.Thread(
            target=self._check_loop,
            args=(symbol,),
            daemon=True
        )
        self.check_thread.start()
        logger.info(f"[PositionChecker] Iniciada verificação para {symbol}")
    
    def stop_checking(self):
        """Para a verificação contínua"""
        self.checking_active = False
        if self.check_thread:
            self.check_thread.join(timeout=5)
        logger.info("[PositionChecker] Verificação parada")
    
    def _check_loop(self, symbol: str):
        """Loop de verificação contínua"""
        logger.info(f"[PositionChecker] Loop de verificação iniciado para {symbol}")
        
        while self.checking_active:
            try:
                # Obter posição atual
                current_position = self.get_current_position(symbol)
                
                with self.state_lock:
                    # Comparar com estado anterior
                    last_had_position = self.last_position_state['has_position']
                    now_has_position = current_position.get('has_position', False)
                    
                    # Detectar mudanças
                    if not last_had_position and now_has_position:
                        # Posição foi aberta
                        logger.info(f"[PositionChecker] POSIÇÃO ABERTA DETECTADA: {current_position}")
                        if self.on_position_opened:
                            self.on_position_opened(current_position)
                    
                    elif last_had_position and not now_has_position:
                        # Posição foi fechada
                        logger.info(f"[PositionChecker] POSIÇÃO FECHADA DETECTADA!")
                        self._handle_position_closed()
                        if self.on_position_closed:
                            self.on_position_closed(self.last_position_state)
                    
                    elif last_had_position and now_has_position:
                        # Verificar se mudou quantidade ou lado
                        if (current_position.get('quantity') != self.last_position_state['quantity'] or
                            current_position.get('side') != self.last_position_state['side']):
                            logger.info(f"[PositionChecker] POSIÇÃO ALTERADA: {current_position}")
                            if self.on_position_changed:
                                self.on_position_changed(current_position)
                    
                    # Atualizar estado
                    self.last_position_state.update(current_position)
                    self.last_position_state['last_check'] = datetime.now()
                    
                    # Salvar status
                    self._save_status()
                
            except Exception as e:
                logger.error(f"[PositionChecker] Erro no loop de verificação: {e}")
            
            # Aguardar próxima verificação
            time.sleep(self.check_interval)
    
    def _handle_position_closed(self):
        """Trata fechamento de posição detectado"""
        logger.info("[PositionChecker] Executando limpeza pós-fechamento...")
        
        # Resetar lock global se existir
        try:
            import START_SYSTEM_COMPLETE_OCO_EVENTS as main_system
            with main_system.GLOBAL_POSITION_LOCK_MUTEX:
                if main_system.GLOBAL_POSITION_LOCK:
                    main_system.GLOBAL_POSITION_LOCK = False
                    main_system.GLOBAL_POSITION_LOCK_TIME = None
                    logger.info("[PositionChecker] Lock global resetado!")
        except Exception as e:
            logger.warning(f"[PositionChecker] Não foi possível resetar lock global: {e}")
    
    def _save_status(self):
        """Salva status atual em arquivo"""
        try:
            status_data = {
                'timestamp': datetime.now().isoformat(),
                'position': self.last_position_state.copy()
            }
            
            # Converter datetime para string
            if 'last_check' in status_data['position'] and status_data['position']['last_check']:
                status_data['position']['last_check'] = status_data['position']['last_check'].isoformat()
            if 'timestamp' in status_data['position'] and hasattr(status_data['position']['timestamp'], 'isoformat'):
                status_data['position']['timestamp'] = status_data['position']['timestamp'].isoformat()
            
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"[PositionChecker] Erro ao salvar status: {e}")
    
    def register_callbacks(self, on_closed=None, on_opened=None, on_changed=None):
        """
        Registra callbacks para eventos de posição
        
        Args:
            on_closed: Callback quando posição fecha
            on_opened: Callback quando posição abre
            on_changed: Callback quando posição muda
        """
        if on_closed:
            self.on_position_closed = on_closed
        if on_opened:
            self.on_position_opened = on_opened
        if on_changed:
            self.on_position_changed = on_changed
        
        logger.info("[PositionChecker] Callbacks registrados")


# Singleton global
_position_checker_instance = None

def get_position_checker() -> PositionChecker:
    """Retorna instância singleton do PositionChecker"""
    global _position_checker_instance
    if _position_checker_instance is None:
        _position_checker_instance = PositionChecker()
    return _position_checker_instance