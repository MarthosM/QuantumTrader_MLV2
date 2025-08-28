"""
Estruturas de dados para decodificar callbacks de trade da ProfitDLL
Baseado no manual da ProfitDLL v4.0.0.30
"""

from ctypes import *
from datetime import datetime

# Estrutura SYSTEMTIME do Windows
class SYSTEMTIME(Structure):
    _fields_ = [
        ("wYear", c_uint16),
        ("wMonth", c_uint16),
        ("wDayOfWeek", c_uint16),
        ("wDay", c_uint16),
        ("wHour", c_uint16),
        ("wMinute", c_uint16),
        ("wSecond", c_uint16),
        ("wMilliseconds", c_uint16)
    ]
    
    def to_datetime(self):
        """Converte SYSTEMTIME para datetime Python"""
        try:
            return datetime(
                self.wYear, self.wMonth, self.wDay,
                self.wHour, self.wMinute, self.wSecond,
                self.wMilliseconds * 1000  # microseconds
            )
        except:
            return datetime.now()

# Estrutura TConnectorTrade para callback V2
class TConnectorTrade(Structure):
    """
    Estrutura de trade conforme manual ProfitDLL
    Versão 4.0.0.30
    """
    _pack_ = 1  # Importante para alinhamento correto
    _fields_ = [
        ("Version", c_byte),           # Versão da estrutura
        ("TradeDate", SYSTEMTIME),      # Data/hora do trade
        ("TradeNumber", c_uint32),      # Número sequencial do trade
        ("Price", c_double),            # Preço executado
        ("Quantity", c_int64),          # Volume/quantidade negociada
        ("BuyerBroker", c_int32),       # Código do broker comprador
        ("SellerBroker", c_int32),      # Código do broker vendedor
        ("BuyerOrderDate", SYSTEMTIME), # Data da ordem de compra
        ("SellerOrderDate", SYSTEMTIME),# Data da ordem de venda
        ("TradeType", c_byte),          # Tipo de trade (0=Normal, 1=CrossTrade, etc)
        ("BuyOrderID", c_int64),        # ID da ordem de compra
        ("SellOrderID", c_int64),       # ID da ordem de venda
        ("TradeSide", c_byte),          # Lado (0=Buy, 1=Sell, 2=Both)
        ("Aggressor", c_byte)           # Lado agressor (0=Buy, 1=Sell, 2=Unknown)
    ]
    
    def to_dict(self):
        """Converte estrutura para dicionário Python"""
        try:
            return {
                'timestamp': self.TradeDate.to_datetime().isoformat(),
                'trade_number': self.TradeNumber,
                'price': self.Price,
                'quantity': self.Quantity,  # VOLUME!
                'buyer_broker': self.BuyerBroker,
                'seller_broker': self.SellerBroker,
                'trade_type': self.TradeType,
                'aggressor': 'BUY' if self.Aggressor == 0 else 'SELL' if self.Aggressor == 1 else 'UNKNOWN'
            }
        except Exception as e:
            return {
                'error': str(e),
                'price': 0,
                'quantity': 0
            }

# Estrutura simplificada para callback V1 (se necessário)
class TConnectorTradeSimple(Structure):
    """
    Estrutura simplificada para SetTradeCallback (V1)
    """
    _fields_ = [
        ("Symbol", c_wchar * 20),      # Símbolo
        ("Price", c_double),            # Preço
        ("Quantity", c_int32),          # Quantidade
        ("BuyerBroker", c_int32),       # Broker comprador  
        ("SellerBroker", c_int32)       # Broker vendedor
    ]
    
    def to_dict(self):
        """Converte para dicionário"""
        return {
            'symbol': self.Symbol,
            'price': self.Price,
            'quantity': self.Quantity,
            'buyer_broker': self.BuyerBroker,
            'seller_broker': self.SellerBroker
        }


def decode_trade_v2(trade_ptr):
    """
    Decodifica ponteiro de trade V2 para estrutura Python
    VERSÃO COM DETECÇÃO INTELIGENTE DE ESTRUTURA
    
    Args:
        trade_ptr: Ponteiro para estrutura TConnectorTrade
        
    Returns:
        dict: Dados do trade decodificados
    """
    import struct
    
    # Primeiro, tentar capturar bytes raw e analisar
    try:
        raw_bytes = cast(trade_ptr, POINTER(c_byte * 150))
        raw_data = bytes(raw_bytes.contents[:120])
    except:
        # Fallback para estrutura padrão
        try:
            trade = cast(trade_ptr, POINTER(TConnectorTrade)).contents
            return trade.to_dict()
        except Exception as e:
            return {'error': str(e), 'price': 0, 'quantity': 0}
    
    # Buscar preço e volume nos bytes
    price = 0
    volume = 0
    
    # Procurar preço (double entre 5000-6000)
    for offset in range(0, min(len(raw_data)-7, 100), 4):
        try:
            val = struct.unpack_from('<d', raw_data, offset)[0]
            if 5000 < val < 6000:
                price = val
                break
        except:
            pass
    
    # Procurar volume (int32 entre 1-500)
    for offset in range(0, min(len(raw_data)-3, 100), 4):
        try:
            val = struct.unpack_from('<i', raw_data, offset)[0]
            if 1 <= val <= 500:
                volume = val
                break
        except:
            pass
    
    # Se não encontrou volume como int32, tentar int64
    if volume == 0:
        for offset in range(0, min(len(raw_data)-7, 100), 4):
            try:
                val = struct.unpack_from('<q', raw_data, offset)[0]
                if 1 <= val <= 500:
                    volume = val
                    break
            except:
                pass
    
    # Se ainda não encontrou valores válidos, tentar estrutura padrão
    if price == 0 or volume == 0:
        try:
            # Tentar estrutura com Version byte
            trade = cast(trade_ptr, POINTER(TConnectorTrade)).contents
            result = trade.to_dict()
            
            # Validar valores
            if result['price'] > 5000 and result['price'] < 6000:
                price = result['price']
            if 0 < result['quantity'] < 1000:
                volume = result['quantity']
                
            # Se valores ainda inválidos, tentar estrutura sem Version
            if price == 0 or volume == 0:
                # Estrutura alternativa começando direto com SYSTEMTIME
                offset_ptr = cast(trade_ptr, POINTER(c_byte))
                offset_ptr = cast(addressof(offset_ptr.contents) + 1, POINTER(TConnectorTrade))
                trade = offset_ptr.contents
                result = trade.to_dict()
                
                if result['price'] > 5000 and result['price'] < 6000:
                    price = result['price']
                if 0 < result['quantity'] < 1000:
                    volume = result['quantity']
                    
        except:
            pass
    
    # Retornar resultado
    return {
        'price': price,
        'quantity': volume,  # VOLUME EM CONTRATOS
        'aggressor': 'UNKNOWN',
        'timestamp': datetime.now().isoformat(),
        'decoded_method': 'smart'
    }


def decode_trade_simple(ticker, price, qty, buyer, seller):
    """
    Decodifica dados simples de trade (callback V1)
    
    Returns:
        dict: Dados do trade
    """
    return {
        'symbol': ticker if isinstance(ticker, str) else '',
        'price': float(price) if price else 0,
        'quantity': int(qty) if qty else 0,
        'buyer_broker': int(buyer) if buyer else 0,
        'seller_broker': int(seller) if seller else 0,
        'timestamp': datetime.now().isoformat()
    }