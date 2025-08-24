"""
ProfitDLL Order Sender - Envia ordens reais para B3 via ProfitDLL
Com Stop Loss e Take Profit compatíveis com WDO
"""

import ctypes
from ctypes import *
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Estruturas do ProfitDLL para ordens
class TAssetIDRec(Structure):
    _fields_ = [
        ("ticker", c_wchar * 35),
        ("bolsa", c_wchar * 15),
    ]

class ProfitOrderSender:
    """Envia ordens reais via ProfitDLL com stop e take"""
    
    def __init__(self, dll):
        """
        Args:
            dll: Instância da ProfitDLL já carregada e conectada
        """
        self.dll = dll
        self.pending_orders = {}
        self.executed_orders = {}
        
        # Configurar tipos de ordem no ProfitDLL
        self.ORDER_TYPE_MARKET = 0      # Ordem a mercado
        self.ORDER_TYPE_LIMIT = 1       # Ordem limitada
        self.ORDER_TYPE_STOP = 2        # Ordem stop
        self.ORDER_TYPE_STOP_LIMIT = 3  # Stop limitado
        
        logger.info("ProfitOrderSender inicializado")
    
    def send_market_order_with_brackets(self,
                                       symbol: str,
                                       side: str,  # "BUY" ou "SELL"
                                       quantity: int,
                                       stop_price: float,
                                       take_price: float) -> Optional[str]:
        """
        Envia ordem a mercado com ordens bracket (stop loss e take profit)
        
        Args:
            symbol: Símbolo do ativo (ex: WDOU25)
            side: "BUY" ou "SELL"
            quantity: Quantidade de contratos
            stop_price: Preço do stop loss
            take_price: Preço do take profit
            
        Returns:
            ID da ordem principal ou None se falhou
        """
        try:
            # Criar estrutura do ativo
            asset = TAssetIDRec()
            asset.ticker = symbol
            asset.bolsa = "F"  # F para futuros BMF
            
            # Determinar tipo de operação
            is_buy = (side.upper() == "BUY")
            
            # ========== 1. Enviar ordem principal a mercado ==========
            logger.info(f"Enviando ordem {side} a mercado: {quantity} {symbol}")
            
            # SendBuyOrder ou SendSellOrder
            if is_buy:
                # SendBuyOrder(asset, quantity, price, order_type)
                # Para ordem a mercado, price = 0
                result = self.dll.SendBuyOrder(
                    byref(asset),
                    c_int(quantity),
                    c_double(0),  # 0 = ordem a mercado
                    c_int(self.ORDER_TYPE_MARKET)
                )
            else:
                # SendSellOrder(asset, quantity, price, order_type)
                result = self.dll.SendSellOrder(
                    byref(asset),
                    c_int(quantity),
                    c_double(0),  # 0 = ordem a mercado
                    c_int(self.ORDER_TYPE_MARKET)
                )
            
            if result == 0:
                logger.info(f"[OK] Ordem principal enviada com sucesso")
                
                # Gerar ID único para rastreamento
                order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                # ========== 2. Configurar ordens OCO (One-Cancels-Other) ==========
                # Stop Loss e Take Profit devem ser OCO - uma cancela a outra
                
                # Aguardar um pouco para ordem principal ser preenchida
                import time
                time.sleep(0.5)
                
                # ========== 3. Enviar ordem de Stop Loss ==========
                logger.info(f"Configurando Stop Loss em {stop_price:.1f}")
                
                if is_buy:
                    # Para posição comprada, stop é ordem de venda abaixo do mercado
                    stop_result = self.dll.SendSellStopOrder(
                        byref(asset),
                        c_int(quantity),
                        c_double(stop_price),
                        c_wchar_p(order_id + "_STOP")  # ID do stop
                    )
                else:
                    # Para posição vendida, stop é ordem de compra acima do mercado
                    stop_result = self.dll.SendBuyStopOrder(
                        byref(asset),
                        c_int(quantity),
                        c_double(stop_price),
                        c_wchar_p(order_id + "_STOP")  # ID do stop
                    )
                
                if stop_result == 0:
                    logger.info(f"[OK] Stop Loss configurado em {stop_price:.1f}")
                else:
                    logger.warning(f"Erro ao configurar Stop Loss: {stop_result}")
                
                # ========== 4. Enviar ordem de Take Profit ==========
                logger.info(f"Configurando Take Profit em {take_price:.1f}")
                
                if is_buy:
                    # Para posição comprada, take é ordem de venda limitada acima
                    take_result = self.dll.SendSellOrder(
                        byref(asset),
                        c_int(quantity),
                        c_double(take_price),
                        c_int(self.ORDER_TYPE_LIMIT)
                    )
                else:
                    # Para posição vendida, take é ordem de compra limitada abaixo
                    take_result = self.dll.SendBuyOrder(
                        byref(asset),
                        c_int(quantity),
                        c_double(take_price),
                        c_int(self.ORDER_TYPE_LIMIT)
                    )
                
                if take_result == 0:
                    logger.info(f"[OK] Take Profit configurado em {take_price:.1f}")
                else:
                    logger.warning(f"Erro ao configurar Take Profit: {take_result}")
                
                # ========== 5. Configurar OCO se disponível ==========
                if hasattr(self.dll, 'SetOCOOrders'):
                    # Vincular stop e take como OCO
                    oco_result = self.dll.SetOCOOrders(
                        c_wchar_p(order_id + "_STOP"),
                        c_wchar_p(order_id + "_TAKE")
                    )
                    if oco_result == 0:
                        logger.info("[OK] Ordens OCO configuradas (Stop/Take)")
                
                # Salvar informações da ordem
                self.pending_orders[order_id] = {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'stop_price': stop_price,
                    'take_price': take_price,
                    'timestamp': datetime.now(),
                    'status': 'PENDING'
                }
                
                logger.info("=" * 60)
                logger.info("ORDEM BRACKET ENVIADA COM SUCESSO")
                logger.info("=" * 60)
                logger.info(f"ID: {order_id}")
                logger.info(f"{side} {quantity} {symbol} @ MERCADO")
                logger.info(f"Stop Loss: {stop_price:.1f}")
                logger.info(f"Take Profit: {take_price:.1f}")
                logger.info("=" * 60)
                
                return order_id
                
            else:
                logger.error(f"Erro ao enviar ordem principal: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao enviar ordem bracket: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancela uma ordem pendente
        
        Args:
            order_id: ID da ordem a cancelar
            
        Returns:
            True se cancelou com sucesso
        """
        try:
            if order_id not in self.pending_orders:
                logger.warning(f"Ordem {order_id} não encontrada")
                return False
            
            order_info = self.pending_orders[order_id]
            
            # Criar estrutura do ativo
            asset = TAssetIDRec()
            asset.ticker = order_info['symbol']
            asset.bolsa = "F"
            
            # CancelOrder
            result = self.dll.CancelOrder(
                byref(asset),
                c_wchar_p(order_id)
            )
            
            if result == 0:
                logger.info(f"[OK] Ordem {order_id} cancelada")
                order_info['status'] = 'CANCELLED'
                self.executed_orders[order_id] = order_info
                del self.pending_orders[order_id]
                return True
            else:
                logger.error(f"Erro ao cancelar ordem: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao cancelar ordem: {e}")
            return False
    
    def modify_stop_loss(self, order_id: str, new_stop_price: float) -> bool:
        """
        Modifica o stop loss de uma ordem existente (para trailing stop)
        
        Args:
            order_id: ID da ordem
            new_stop_price: Novo preço de stop
            
        Returns:
            True se modificou com sucesso
        """
        try:
            if order_id not in self.pending_orders:
                logger.warning(f"Ordem {order_id} não encontrada")
                return False
            
            order_info = self.pending_orders[order_id]
            
            # Criar estrutura do ativo
            asset = TAssetIDRec()
            asset.ticker = order_info['symbol']
            asset.bolsa = "F"
            
            # ModifyOrder para alterar stop
            result = self.dll.ModifyOrder(
                byref(asset),
                c_wchar_p(order_id + "_STOP"),
                c_int(order_info['quantity']),
                c_double(new_stop_price)
            )
            
            if result == 0:
                old_stop = order_info['stop_price']
                order_info['stop_price'] = new_stop_price
                logger.info(f"[OK] Stop modificado: {old_stop:.1f} -> {new_stop_price:.1f}")
                return True
            else:
                logger.error(f"Erro ao modificar stop: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao modificar stop: {e}")
            return False
    
    def get_position(self, symbol: str) -> dict:
        """
        Obtém posição atual no símbolo
        
        Args:
            symbol: Símbolo do ativo
            
        Returns:
            Dict com informações da posição
        """
        try:
            # Criar estrutura do ativo
            asset = TAssetIDRec()
            asset.ticker = symbol
            asset.bolsa = "F"
            
            # GetPosition
            if hasattr(self.dll, 'GetPosition'):
                position = c_int()
                avg_price = c_double()
                
                result = self.dll.GetPosition(
                    byref(asset),
                    byref(position),
                    byref(avg_price)
                )
                
                if result == 0:
                    return {
                        'symbol': symbol,
                        'quantity': position.value,
                        'avg_price': avg_price.value,
                        'side': 'LONG' if position.value > 0 else ('SHORT' if position.value < 0 else 'FLAT')
                    }
            
            return {
                'symbol': symbol,
                'quantity': 0,
                'avg_price': 0,
                'side': 'FLAT'
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter posição: {e}")
            return {
                'symbol': symbol,
                'quantity': 0,
                'avg_price': 0,
                'side': 'FLAT'
            }
    
    def close_position(self, symbol: str) -> bool:
        """
        Fecha posição aberta no símbolo (zera posição)
        
        Args:
            symbol: Símbolo do ativo
            
        Returns:
            True se fechou com sucesso
        """
        try:
            # Obter posição atual
            position = self.get_position(symbol)
            
            if position['quantity'] == 0:
                logger.info(f"Sem posição aberta em {symbol}")
                return True
            
            quantity = abs(position['quantity'])
            
            # Criar estrutura do ativo
            asset = TAssetIDRec()
            asset.ticker = symbol
            asset.bolsa = "F"
            
            # Enviar ordem inversa para zerar
            if position['quantity'] > 0:
                # Posição comprada - vender para zerar
                result = self.dll.SendSellOrder(
                    byref(asset),
                    c_int(quantity),
                    c_double(0),  # A mercado
                    c_int(self.ORDER_TYPE_MARKET)
                )
            else:
                # Posição vendida - comprar para zerar
                result = self.dll.SendBuyOrder(
                    byref(asset),
                    c_int(quantity),
                    c_double(0),  # A mercado
                    c_int(self.ORDER_TYPE_MARKET)
                )
            
            if result == 0:
                logger.info(f"[OK] Posição zerada: {quantity} {symbol}")
                return True
            else:
                logger.error(f"Erro ao zerar posição: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao fechar posição: {e}")
            return False

# Exemplo de uso
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*60)
    print(" EXEMPLO DE USO - ProfitDLL Order Sender")
    print("="*60)
    print("\nATENÇÃO: Este é apenas um exemplo de estrutura.")
    print("Para uso real, é necessário ter a DLL conectada.")
    print("\nFunções disponíveis:")
    print("- send_market_order_with_brackets(): Ordem com stop e take")
    print("- modify_stop_loss(): Trailing stop")
    print("- get_position(): Consulta posição")
    print("- close_position(): Zera posição")
    print("- cancel_order(): Cancela ordem pendente")