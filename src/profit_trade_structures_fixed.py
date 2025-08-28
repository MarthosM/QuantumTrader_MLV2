"""
Estruturas CORRIGIDAS para decodificar trades da ProfitDLL
Versão com alinhamentos testados para WDO
"""

from ctypes import *
from datetime import datetime
import struct

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
                self.wMilliseconds * 1000
            )
        except:
            return datetime.now()

# OPÇÃO 1: Estrutura sem Version byte
class TConnectorTradeNoVersion(Structure):
    """Estrutura começando direto com SYSTEMTIME"""
    _pack_ = 1
    _fields_ = [
        ("TradeDate", SYSTEMTIME),      # 16 bytes
        ("TradeNumber", c_uint32),      # 4 bytes
        ("Price", c_double),            # 8 bytes
        ("Quantity", c_int32),          # 4 bytes - VOLUME EM CONTRATOS!
        ("BuyerBroker", c_int32),       # 4 bytes
        ("SellerBroker", c_int32),      # 4 bytes
        # Total: 40 bytes mínimo
    ]

# OPÇÃO 2: Estrutura com Version byte
class TConnectorTradeWithVersion(Structure):
    """Estrutura com byte de versão no início"""
    _pack_ = 1
    _fields_ = [
        ("Version", c_byte),            # 1 byte
        ("TradeDate", SYSTEMTIME),      # 16 bytes
        ("TradeNumber", c_uint32),      # 4 bytes
        ("Price", c_double),            # 8 bytes
        ("Quantity", c_int32),          # 4 bytes - VOLUME!
        ("BuyerBroker", c_int32),       # 4 bytes
        ("SellerBroker", c_int32),      # 4 bytes
        # Total: 41 bytes mínimo
    ]

# OPÇÃO 3: Estrutura simplificada (teste)
class TConnectorTradeSimple(Structure):
    """Estrutura mínima para teste"""
    _pack_ = 1
    _fields_ = [
        ("Price", c_double),            # 8 bytes
        ("Quantity", c_int32),          # 4 bytes
        ("TradeNumber", c_uint32),      # 4 bytes
    ]

def decode_trade_smart(trade_ptr):
    """
    Decodifica trade tentando múltiplas estruturas
    Retorna a que fizer mais sentido
    """
    results = []
    
    # Pegar bytes raw para análise
    try:
        raw_bytes = cast(trade_ptr, POINTER(c_byte * 100))
        raw_data = bytes(raw_bytes.contents[:50])
    except:
        return {'error': 'Cannot read raw bytes', 'price': 0, 'quantity': 0}
    
    # Tentar OPÇÃO 1: Sem Version
    try:
        trade = cast(trade_ptr, POINTER(TConnectorTradeNoVersion)).contents
        price = trade.Price
        volume = trade.Quantity
        
        # Validar valores
        if 5000 < price < 6000 and 0 < volume < 1000:
            return {
                'structure': 'NoVersion',
                 'price': price,
                'quantity': volume,
                'trade_number': trade.TradeNumber,
                'timestamp': trade.TradeDate.to_datetime().isoformat(),
                'buyer_broker': trade.BuyerBroker,
                'seller_broker': trade.SellerBroker
            }
    except:
        pass
    
    # Tentar OPÇÃO 2: Com Version
    try:
        trade = cast(trade_ptr, POINTER(TConnectorTradeWithVersion)).contents
        price = trade.Price
        volume = trade.Quantity
        
        if 5000 < price < 6000 and 0 < volume < 1000:
            return {
                'structure': 'WithVersion',
                'version': trade.Version,
                'price': price,
                'quantity': volume,
                'trade_number': trade.TradeNumber,
                'timestamp': trade.TradeDate.to_datetime().isoformat(),
                'buyer_broker': trade.BuyerBroker,
                'seller_broker': trade.SellerBroker
            }
    except:
        pass
    
    # Tentar busca manual de padrões
    try:
        # Buscar preço (double)
        for offset in range(0, min(len(raw_data)-7, 40), 4):
            val = struct.unpack_from('<d', raw_data, offset)[0]
            if 5000 < val < 6000:
                price_offset = offset
                price_value = val
                
                # Buscar volume próximo ao preço
                for vol_offset in range(max(0, offset-20), min(len(raw_data)-3, offset+20), 4):
                    vol = struct.unpack_from('<i', raw_data, vol_offset)[0]
                    if 0 < vol < 1000:
                        return {
                            'structure': 'Manual',
                            'price': price_value,
                            'quantity': vol,
                            'price_offset': price_offset,
                            'volume_offset': vol_offset,
                            'raw_bytes_sample': raw_data[:32].hex()
                        }
                break
    except:
        pass
    
    # Falhou todas as tentativas
    return {
        'error': 'Could not decode structure',
        'price': 0,
        'quantity': 0,
        'raw_bytes': raw_data[:32].hex() if raw_data else ''
    }

# Função principal para usar no sistema
def decode_trade_v2(trade_ptr):
    """
    Decodifica trade V2 com detecção automática de estrutura
    """
    return decode_trade_smart(trade_ptr)

# Função de teste
def analyze_trade_bytes(raw_bytes):
    """
    Analisa bytes raw para encontrar campos
    Útil para debug
    """
    analysis = {
        'total_bytes': len(raw_bytes),
        'possible_prices': [],
        'possible_volumes': [],
        'hex_dump': raw_bytes[:64].hex()
    }
    
    # Procurar preços
    for offset in range(0, min(len(raw_bytes)-7, 80), 4):
        try:
            val = struct.unpack_from('<d', raw_bytes, offset)[0]
            if 5000 < val < 6000:
                analysis['possible_prices'].append({
                    'offset': offset,
                    'value': val
                })
        except:
            pass
    
    # Procurar volumes
    for offset in range(0, min(len(raw_bytes)-3, 80), 4):
        try:
            val32 = struct.unpack_from('<i', raw_bytes, offset)[0]
            if 0 < val32 < 500:
                analysis['possible_volumes'].append({
                    'offset': offset,
                    'value': val32,
                    'type': 'int32'
                })
        except:
            pass
    
    return analysis