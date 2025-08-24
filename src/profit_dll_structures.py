"""
Estruturas de dados para ProfitDLL v4.0.0.30
Baseado no manual oficial da API

Este arquivo contém todas as estruturas ctypes necessárias para
integração completa com a ProfitDLL versão 4.0.0.30
"""

# CORREÇÃO APLICADA: Todos callbacks retornam c_int para evitar crashes

from ctypes import (
    Structure, Union, c_int, c_double, c_wchar_p, c_longlong, 
    c_char, c_uint, c_void_p, c_bool, c_byte, c_ubyte, c_int64,
    POINTER, WINFUNCTYPE, byref
)
from enum import IntEnum
from typing import Optional


# =============================================================================
# ENUMS E CONSTANTES
# =============================================================================

class OrderSide(IntEnum):
    """Lado da ordem"""
    BUY = 1
    SELL = 2


class OrderType(IntEnum):
    """Tipos de ordem suportados pela v4.0.0.30"""
    MARKET = 0
    LIMIT = 1
    STOP = 2
    STOP_LIMIT = 3
    MARKET_WITH_LEFTOVER = 4


class OrderStatus(IntEnum):
    """Status da ordem"""
    NEW = 0
    PARTIALLY_FILLED = 1
    FILLED = 2
    CANCELLED = 3
    REPLACED = 4
    PENDING_CANCEL = 5
    REJECTED = 6
    PENDING_NEW = 7
    PENDING_REPLACE = 8


class Exchange(IntEnum):
    """Códigos de bolsa"""
    BOVESPA = 66  # 'B'
    BMF = 70      # 'F' - Futuros
    CME = 77      # 'M'
    NASDAQ = 78   # 'N'
    NYSE = 89     # 'Y'


class ConnectionState(IntEnum):
    """Estados de conexão"""
    LOGIN = 0
    ROTEAMENTO = 1
    MARKET_DATA = 2
    MARKET_LOGIN = 3


class NResult(IntEnum):
    """Códigos de retorno da API"""
    NL_OK = 0
    NL_INTERNAL_ERROR = -2147483647
    NL_NOT_INITIALIZED = -2147483646
    NL_INVALID_ARGS = -2147483645
    NL_WAITING_SERVER = -2147483644
    NL_NO_LOGIN = -2147483643
    NL_NO_LICENSE = -2147483642
    NL_NO_POSITION = -2147483637
    NL_NOT_FOUND = -2147483636
    NL_NO_PASSWORD = -2147483620


# =============================================================================
# ESTRUTURAS BÁSICAS
# =============================================================================

class TAssetID(Structure):
    """Identificador de ativo"""
    _fields_ = [
        ("pwcTicker", c_wchar_p),
        ("pwcBolsa", c_wchar_p),
        ("nFeed", c_int)
    ]


class TSystemTime(Structure):
    """Estrutura de tempo do sistema"""
    _fields_ = [
        ("wYear", c_uint),
        ("wMonth", c_uint),
        ("wDayOfWeek", c_uint),
        ("wDay", c_uint),
        ("wHour", c_uint),
        ("wMinute", c_uint),
        ("wSecond", c_uint),
        ("wMilliseconds", c_uint)
    ]


# =============================================================================
# ESTRUTURAS DE CONTA
# =============================================================================

class TConnectorAccountIdentifier(Structure):
    """Identificador de conta para API v4.0.0.30"""
    _fields_ = [
        ("Version", c_ubyte),
        ("BrokerID", c_int),
        ("AccountID", c_wchar_p),
        ("SubAccountID", c_wchar_p),
        ("Reserved", c_int64)
    ]


class TConnectorTradingAccountOut(Structure):
    """Detalhes da conta de trading"""
    _fields_ = [
        ("AccountID", TConnectorAccountIdentifier),
        ("AccountName", c_wchar_p),
        ("Balance", c_double),
        ("AvailableBalance", c_double),
        ("BlockedBalance", c_double),
        ("Currency", c_wchar_p),
        ("IsActive", c_bool),
        ("IsMaster", c_bool),  # Novo na v4.0.0.30
        ("AllowTrading", c_bool),
        ("AllowMarketData", c_bool)
    ]


# Tipo para array de identificadores de conta
PConnectorAccountIdentifierArrayOut = POINTER(TConnectorAccountIdentifier)


# =============================================================================
# ESTRUTURAS DE ORDENS
# =============================================================================

class TConnectorSendOrder(Structure):
    """Estrutura unificada para envio de ordens - v4.0.0.30"""
    _fields_ = [
        ("AccountID", POINTER(TConnectorAccountIdentifier)),
        ("Password", c_wchar_p),
        ("Ticker", c_wchar_p),
        ("Exchange", c_wchar_p),
        ("Side", c_int),           # OrderSide enum
        ("OrderType", c_int),      # OrderType enum
        ("Quantity", c_int),
        ("Price", c_double),       # Para ordens limite
        ("StopPrice", c_double),   # Para ordens stop
        ("ClientOrderID", c_wchar_p),
        ("ValidityType", c_int),   # 0=Day, 1=GTC, 2=GTD, 3=IOC, 4=FOK
        ("ValidityDate", POINTER(TSystemTime)),  # Para GTD
        ("DisplayQuantity", c_int),  # Iceberg
        ("MinQuantity", c_int),      # Quantidade mínima
        ("ExecInst", c_wchar_p),     # Instruções especiais
        ("Memo", c_wchar_p)          # Observações
    ]


class TConnectorChangeOrder(Structure):
    """Estrutura para modificação de ordens - v4.0.0.30"""
    _fields_ = [
        ("AccountID", POINTER(TConnectorAccountIdentifier)),
        ("Password", c_wchar_p),
        ("ClientOrderID", c_wchar_p),    # ID original da ordem
        ("NewClientOrderID", c_wchar_p), # Novo ID (opcional)
        ("Quantity", c_int),             # Nova quantidade
        ("Price", c_double),             # Novo preço
        ("StopPrice", c_double),         # Novo stop price
        ("ValidityType", c_int),         # Nova validade
        ("ValidityDate", POINTER(TSystemTime))
    ]


class TConnectorOrderIdentifier(Structure):
    """Identificador de ordem - v4.0.0.30"""
    _fields_ = [
        ("Version", c_ubyte),
        ("LocalOrderID", c_int64),  # ProfitID
        ("ClOrderID", c_wchar_p)    # Client Order ID
    ]


class TConnectorCancelOrder(Structure):
    """Estrutura para cancelamento de ordem específica - v4.0.0.30"""
    _fields_ = [
        ("Version", c_ubyte),
        ("AccountID", TConnectorAccountIdentifier),
        ("OrderID", TConnectorOrderIdentifier),
        ("Password", c_wchar_p)
    ]


class TConnectorCancelOrders(Structure):
    """Estrutura para cancelar todas as ordens de um ativo - v4.0.0.30"""
    _fields_ = [
        ("AccountID", POINTER(TConnectorAccountIdentifier)),
        ("Password", c_wchar_p),
        ("Ticker", c_wchar_p),
        ("Exchange", c_wchar_p),
        ("Side", c_int)  # 0=Ambos, 1=Buy, 2=Sell
    ]


class TConnectorCancelAllOrders(Structure):
    """Estrutura para cancelar todas as ordens - v4.0.0.30"""
    _fields_ = [
        ("AccountID", POINTER(TConnectorAccountIdentifier)),
        ("Password", c_wchar_p)
    ]


class TConnectorOrderOut(Structure):
    """Estrutura de saída para detalhes da ordem - v4.0.0.30"""
    _fields_ = [
        ("Version", c_byte),  # Versão da estrutura
        ("AccountID", TConnectorAccountIdentifier),
        ("ProfitID", c_longlong),
        ("ClientOrderID", c_wchar_p),
        ("AssetID", TAssetID),
        ("Side", c_int),
        ("OrderType", c_int),
        ("Status", c_int),
        ("Quantity", c_int),
        ("ExecutedQuantity", c_int),
        ("RemainingQuantity", c_int),
        ("Price", c_double),
        ("StopPrice", c_double),
        ("AveragePrice", c_double),
        ("CreationTime", TSystemTime),
        ("LastUpdateTime", TSystemTime),
        ("ValidityType", c_int),
        ("ValidityDate", TSystemTime),
        ("ExecutionInstructions", c_wchar_p),
        ("StatusMessage", c_wchar_p),
        ("Memo", c_wchar_p)
    ]


# =============================================================================
# ESTRUTURAS DE POSIÇÃO
# =============================================================================

class TConnectorTradingAccountPosition(Structure):
    """Estrutura de posição para conta - v4.0.0.30"""
    _fields_ = [
        ("AccountID", TConnectorAccountIdentifier),
        ("AssetID", TAssetID),
        ("Side", c_int),  # 1=Long, 2=Short
        ("Quantity", c_int),
        ("AveragePrice", c_double),
        ("CurrentPrice", c_double),
        ("PnL", c_double),
        ("PnLPercent", c_double),
        ("DayTrade", c_bool),
        ("OpenQuantity", c_int),    # Quantidade em aberto
        ("BlockedQuantity", c_int),  # Quantidade bloqueada
        ("AvailableQuantity", c_int) # Quantidade disponível
    ]


class TConnectorZeroPosition(Structure):
    """Estrutura para zerar posição - v4.0.0.30"""
    _fields_ = [
        ("AccountID", POINTER(TConnectorAccountIdentifier)),
        ("Password", c_wchar_p),
        ("Ticker", c_wchar_p),
        ("Exchange", c_wchar_p),
        ("Price", c_double)  # -1 para ordem a mercado
    ]


# =============================================================================
# ESTRUTURAS DE TRADES
# =============================================================================

class TConnectorTrade(Structure):
    """Estrutura de negócio/trade - v4.0.0.30"""
    _fields_ = [
        ("AssetID", TAssetID),
        ("TradeDate", c_wchar_p),
        ("TradeNumber", c_uint),
        ("Price", c_double),
        ("Volume", c_double),
        ("Quantity", c_int),
        ("BuyAgent", c_int),
        ("SellAgent", c_int),
        ("TradeType", c_int),
        ("IsEdit", c_char),
        ("IsCanceled", c_char)
    ]


# =============================================================================
# TIPOS DE CALLBACK
# =============================================================================

# Callback de estado de conexão
TStateCallback = WINFUNCTYPE(c_int, c_int, c_int)

# Callback de trades em tempo real
TNewTradeCallback = WINFUNCTYPE(
    c_int, 
    TAssetID,      # Asset
    c_wchar_p,     # Date
    c_uint,        # TradeNumber
    c_double,      # Price
    c_double,      # Volume
    c_int,         # Quantity
    c_int,         # BuyAgent
    c_int,         # SellAgent
    c_int,         # TradeType
    c_char         # IsEdit
)

# Callback de histórico de trades
THistoryTradeCallback = WINFUNCTYPE(
    c_int,
    TAssetID,      # Asset
    c_wchar_p,     # Date
    c_uint,        # TradeNumber
    c_double,      # Price
    c_double,      # Volume
    c_int,         # Quantity
    c_int,         # BuyAgent
    c_int,         # SellAgent
    c_int          # TradeType
)

# Callback de progresso
TProgressCallback = WINFUNCTYPE(c_int, TAssetID, c_int)

# Callback de conta
TAccountCallback = WINFUNCTYPE(
    c_int,
    c_int,         # BrokerID
    c_wchar_p,     # AccountID
    c_wchar_p,     # AccountName
    c_wchar_p      # Titular
)

# Callback de ordens - v4.0.0.30
TConnectorOrderCallback = WINFUNCTYPE(
    c_int,
    POINTER(TConnectorOrderOut)  # Ponteiro para estrutura de ordem
)

# Callback de histórico de ordens
TConnectorAccountCallback = WINFUNCTYPE(
    c_int,
    POINTER(TConnectorAccountIdentifier)  # Conta processada
)

# Callback de book de preços
TPriceBookCallback = WINFUNCTYPE(
    c_int,
    TAssetID,      # Asset
    c_int,         # Position
    c_int,         # Side
    c_int,         # OrderCount
    c_longlong,    # Quantity
    c_int,         # DisplayQuantity
    c_double,      # Price
    c_void_p,      # BookArray
    c_void_p       # Reserved
)

# Callback de book de ofertas
TOfferBookCallback = WINFUNCTYPE(
    c_int,
    TAssetID,      # Asset
    c_int,         # BrokerID
    c_int,         # Position
    c_int,         # Side
    c_longlong,    # Volume
    c_int,         # Quantity
    c_longlong,    # OfferID
    c_double,      # Price
    c_char,        # HasPrice
    c_char,        # HasQuantity
    c_char,        # HasDate
    c_char,        # HasOfferID
    c_char,        # IsEdit
    c_wchar_p,     # Date
    c_void_p,      # BookArray
    c_void_p       # Reserved
)

# Callback para mudanças na lista de ativos com posição
TConnectorAssetPositionListCallback = WINFUNCTYPE(
    c_int,
    POINTER(TConnectorAccountIdentifier),  # AccountID
    c_int  # ChangeType: 0=Added, 1=Removed, 2=Changed
)

# Callback para enumeração de ordens
TConnectorEnumerateOrdersProc = WINFUNCTYPE(
    c_bool,  # Return True para continuar, False para parar
    c_void_p,  # LPARAM - parâmetro do usuário
    POINTER(TConnectorOrderOut)  # Ordem
)

# Callback para enumeração de ativos
TConnectorEnumerateAssetProc = WINFUNCTYPE(
    c_bool,  # Return True para continuar, False para parar
    c_void_p,  # LPARAM - parâmetro do usuário
    POINTER(TAssetID)  # Ativo
)

# Callback para trades v2
TConnectorTradeCallback = WINFUNCTYPE(
    c_int,
    POINTER(c_void_p)  # Ponteiro para dados do trade (usar TranslateTrade)
)


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def create_account_identifier(broker_id: int, account_id: str, 
                            sub_account_id: Optional[str] = None) -> TConnectorAccountIdentifier:
    """
    Cria um identificador de conta
    
    Args:
        broker_id: ID da corretora
        account_id: ID da conta
        sub_account_id: ID da sub-conta (opcional)
        
    Returns:
        TConnectorAccountIdentifier preenchido
    """
    identifier = TConnectorAccountIdentifier()
    identifier.BrokerID = broker_id
    identifier.AccountID = account_id
    identifier.SubAccountID = sub_account_id or ""
    return identifier


def create_send_order(account: TConnectorAccountIdentifier, symbol: str, 
                     side: OrderSide, order_type: OrderType, quantity: int,
                     price: float = 0.0, stop_price: float = 0.0,
                     password: str = "") -> TConnectorSendOrder:
    """
    Cria estrutura para envio de ordem
    
    Args:
        account: Identificador da conta
        symbol: Símbolo do ativo
        side: Lado da ordem (BUY/SELL)
        order_type: Tipo da ordem
        quantity: Quantidade
        price: Preço limite (se aplicável)
        stop_price: Preço stop (se aplicável)
        password: Senha de roteamento
        
    Returns:
        TConnectorSendOrder preenchida
    """
    order = TConnectorSendOrder()
    order.AccountID = POINTER(TConnectorAccountIdentifier)(account)
    order.Password = password
    order.Ticker = symbol
    order.Exchange = "F" if symbol.startswith("WDO") else ""
    order.Side = int(side)
    order.OrderType = int(order_type)
    order.Quantity = quantity
    order.Price = price
    order.StopPrice = stop_price
    order.ValidityType = 0  # Day order
    order.DisplayQuantity = 0  # Não usar iceberg
    order.MinQuantity = 0
    return order


def create_cancel_order(account: TConnectorAccountIdentifier, 
                       client_order_id: str, password: str = "") -> TConnectorCancelOrder:
    """
    Cria estrutura para cancelamento de ordem
    
    Args:
        account: Identificador da conta
        client_order_id: ID da ordem a cancelar
        password: Senha de roteamento
        
    Returns:
        TConnectorCancelOrder preenchida
    """
    cancel = TConnectorCancelOrder()
    cancel.AccountID = POINTER(TConnectorAccountIdentifier)(account)
    cancel.Password = password
    cancel.ClientOrderID = client_order_id
    return cancel


# =============================================================================
# CONSTANTES DE VERSÃO
# =============================================================================

PROFITDLL_VERSION = "4.0.0.30"
CONNECTOR_ORDER_VERSION = 1  # Versão atual da estrutura TConnectorOrderOut
CONNECTOR_ASSET_VERSION = 1  # Versão atual da estrutura de ativo